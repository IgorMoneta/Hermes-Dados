from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from hermes_analytics.pipeline import load_dataset, process_dataset  # noqa: E402


for secret_name in ("HERMES_API_URL", "HERMES_API_TOKEN", "HERMES_TIMEOUT_SECONDS"):
    try:
        secret_value = st.secrets.get(secret_name)
    except FileNotFoundError:
        secret_value = None
    if secret_value and not os.getenv(secret_name):
        os.environ[secret_name] = str(secret_value)

INBOX = ROOT / "data" / "inbox"
OUTPUT = ROOT / "outputs" / "powerbi"
STATE = ROOT / "data" / "state"
st.set_page_config(page_title="Hermes Analytics", page_icon="H", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        background: #111827; border: 1px solid #263244; border-radius: 12px;
        padding: 14px 16px;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {color: #f8fafc;}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: float, compact: bool = False) -> str:
    if compact and abs(value) >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi".replace(".", ",")
    if compact and abs(value) >= 1_000:
        return f"R$ {value / 1_000:.0f} mil"
    return f"R$ {value:,.0f}".replace(",", ".")


def active_file() -> Path | None:
    uploaded = sorted(INBOX.glob("base_atual.*"), key=lambda path: path.stat().st_mtime)
    if uploaded:
        return uploaded[-1]
    candidates = sorted(
        [*INBOX.glob("*.csv"), *INBOX.glob("*.parquet")],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def save_upload(uploaded_file) -> Path:
    INBOX.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded_file.name).suffix.lower()
    target = INBOX / f"base_atual{suffix}"
    temporary = INBOX / f".uploading{suffix}"
    with temporary.open("wb") as destination:
        shutil.copyfileobj(uploaded_file, destination)
    for old in INBOX.glob("base_atual.*"):
        if old != target:
            old.unlink(missing_ok=True)
    os.replace(temporary, target)
    return target


@st.cache_data(show_spinner=False)
def load_processed_dataset(path: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return load_dataset(Path(path))


def render_dashboard(data: pd.DataFrame) -> None:
    filtered = data.copy()
    filters = st.columns(3)
    for column, container, label in (
        ("city", filters[0], "Cidade"),
        ("property_type", filters[1], "Tipo"),
        ("status", filters[2], "Status"),
    ):
        if column in filtered:
            options = sorted(filtered[column].dropna().astype(str).unique())
            chosen = container.multiselect(label, options)
            if chosen:
                filtered = filtered[filtered[column].astype(str).isin(chosen)]

    price = filtered["price_brl"] if "price_brl" in filtered else pd.Series(dtype=float)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Imoveis", f"{len(filtered):,}".replace(",", "."))
    metric_columns[1].metric(
        "Preco mediano", money(price.median(), compact=True) if len(price) else "-"
    )
    metric_columns[2].metric(
        "Preco medio", money(price.mean(), compact=True) if len(price) else "-"
    )
    price_m2 = filtered.get("price_per_m2", pd.Series(dtype=float))
    metric_columns[3].metric("Preco medio / m2", money(price_m2.mean()) if len(price_m2) else "-")

    left, right = st.columns(2)
    if {"neighborhood", "price_per_m2"}.issubset(filtered.columns):
        by_neighborhood = (
            filtered.groupby("neighborhood", as_index=False)
            .agg(preco_m2=("price_per_m2", "mean"), anuncios=("price_per_m2", "size"))
            .query("anuncios >= 5")
            .nlargest(12, "preco_m2")
        )
        chart = (
            alt.Chart(by_neighborhood)
            .mark_bar(cornerRadiusEnd=5, color="#22c55e")
            .encode(
                x=alt.X("preco_m2:Q", title="Preco medio por m2 (R$)"),
                y=alt.Y("neighborhood:N", sort="-x", title=None),
                tooltip=["neighborhood", alt.Tooltip("preco_m2:Q", format=",.0f"), "anuncios"],
            )
            .properties(title="Bairros mais valorizados", height=360)
        )
        left.altair_chart(chart, width="stretch")

    if {"property_type", "price_brl"}.issubset(filtered.columns):
        by_type = (
            filtered.groupby("property_type", as_index=False)
            .agg(preco_mediano=("price_brl", "median"), anuncios=("price_brl", "size"))
        )
        chart = (
            alt.Chart(by_type)
            .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, color="#38bdf8")
            .encode(
                x=alt.X("property_type:N", title=None),
                y=alt.Y("preco_mediano:Q", title="Preco mediano (R$)"),
                tooltip=["property_type", alt.Tooltip("preco_mediano:Q", format=",.0f"), "anuncios"],
            )
            .properties(title="Preco por tipo de imovel", height=360)
        )
        right.altair_chart(chart, width="stretch")

    if {"listing_date", "price_brl"}.issubset(filtered.columns):
        monthly = filtered.dropna(subset=["listing_date"]).copy()
        monthly["mes"] = monthly["listing_date"].dt.to_period("M").dt.to_timestamp()
        monthly = monthly.groupby("mes", as_index=False).agg(preco_medio=("price_brl", "mean"))
        trend = (
            alt.Chart(monthly)
            .mark_line(point=True, color="#f59e0b")
            .encode(
                x=alt.X("mes:T", title="Mes"),
                y=alt.Y("preco_medio:Q", title="Preco medio (R$)", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("mes:T", format="%m/%Y"), alt.Tooltip("preco_medio:Q", format=",.0f")],
            )
            .properties(title="Evolucao mensal do preco medio", height=300)
        )
        st.altair_chart(trend, width="stretch")

    st.subheader("Amostra da base tratada")
    st.dataframe(filtered.head(200), width="stretch", hide_index=True)


def large_money(value: float) -> str:
    if abs(value) >= 1_000_000_000_000:
        return f"R$ {value / 1_000_000_000_000:.2f} tri".replace(".", ",")
    if abs(value) >= 1_000_000_000:
        return f"R$ {value / 1_000_000_000:.1f} bi".replace(".", ",")
    if abs(value) >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f} mi".replace(".", ",")
    return money(value)


def render_credit_dashboard(data: pd.DataFrame) -> None:
    filtered = data
    filter_columns = st.columns(4)
    for column, container, label in (
        ("uf", filter_columns[0], "UF"),
        ("cliente", filter_columns[1], "Cliente"),
        ("segmento", filter_columns[2], "Segmento"),
        ("modalidade", filter_columns[3], "Modalidade"),
    ):
        if column in filtered:
            options = sorted(filtered[column].dropna().astype(str).unique())
            chosen = container.multiselect(label, options)
            if chosen:
                filtered = filtered[filtered[column].astype(str).isin(chosen)]

    active = float(filtered["carteira_ativa"].sum())
    default = float(filtered["carteira_inadimplencia"].sum())
    problematic = float(filtered["ativo_problematico"].sum())
    operations = filtered["numero_de_operacoes"].sum(skipna=True)
    default_rate = default / active * 100 if active else 0

    metrics = st.columns(5)
    metrics[0].metric("Carteira ativa", large_money(active))
    metrics[1].metric("Inadimplencia", large_money(default))
    metrics[2].metric("Taxa inadimplencia", f"{default_rate:.2f}%".replace(".", ","))
    metrics[3].metric("Ativo problematico", large_money(problematic))
    metrics[4].metric("Operacoes", f"{operations / 1_000_000:.1f} mi".replace(".", ","))

    left, right = st.columns(2)
    by_uf = (
        filtered.groupby("uf", as_index=False)
        .agg(
            carteira_ativa=("carteira_ativa", "sum"),
            inadimplencia=("carteira_inadimplencia", "sum"),
        )
    )
    by_uf["taxa_inadimplencia"] = (
        by_uf["inadimplencia"] / by_uf["carteira_ativa"] * 100
    ).fillna(0)
    by_uf = by_uf.nlargest(12, "carteira_ativa")
    uf_chart = (
        alt.Chart(by_uf)
        .mark_bar(cornerRadiusEnd=4, color="#38bdf8")
        .encode(
            x=alt.X("carteira_ativa:Q", title="Carteira ativa (R$)"),
            y=alt.Y("uf:N", sort="-x", title=None),
            tooltip=[
                "uf",
                alt.Tooltip("carteira_ativa:Q", format=",.0f"),
                alt.Tooltip("taxa_inadimplencia:Q", format=".2f"),
            ],
        )
        .properties(title="Maiores carteiras por UF", height=360)
    )
    left.altair_chart(uf_chart, width="stretch")

    by_segment = (
        filtered.groupby("segmento", as_index=False)
        .agg(
            carteira_ativa=("carteira_ativa", "sum"),
            inadimplencia=("carteira_inadimplencia", "sum"),
        )
    )
    by_segment["taxa_inadimplencia"] = (
        by_segment["inadimplencia"] / by_segment["carteira_ativa"] * 100
    ).fillna(0)
    segment_chart = (
        alt.Chart(by_segment)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#f59e0b")
        .encode(
            x=alt.X("segmento:N", title=None, sort="-y"),
            y=alt.Y("taxa_inadimplencia:Q", title="Taxa de inadimplencia (%)"),
            tooltip=[
                "segmento",
                alt.Tooltip("taxa_inadimplencia:Q", format=".2f"),
                alt.Tooltip("carteira_ativa:Q", format=",.0f"),
            ],
        )
        .properties(title="Inadimplencia por segmento", height=360)
    )
    right.altair_chart(segment_chart, width="stretch")

    by_modality = (
        filtered.groupby("modalidade", as_index=False)
        .agg(
            carteira_ativa=("carteira_ativa", "sum"),
            inadimplencia=("carteira_inadimplencia", "sum"),
            ativo_problematico=("ativo_problematico", "sum"),
        )
    )
    by_modality["taxa_inadimplencia"] = (
        by_modality["inadimplencia"] / by_modality["carteira_ativa"] * 100
    ).fillna(0)
    by_modality = by_modality.nlargest(12, "carteira_ativa")
    modality_chart = (
        alt.Chart(by_modality)
        .mark_circle(color="#22c55e", opacity=0.8)
        .encode(
            x=alt.X("carteira_ativa:Q", title="Carteira ativa (R$)"),
            y=alt.Y("taxa_inadimplencia:Q", title="Taxa de inadimplencia (%)"),
            size=alt.Size("ativo_problematico:Q", title="Ativo problematico"),
            tooltip=[
                "modalidade",
                alt.Tooltip("carteira_ativa:Q", format=",.0f"),
                alt.Tooltip("taxa_inadimplencia:Q", format=".2f"),
            ],
        )
        .properties(title="Risco e volume por modalidade", height=340)
    )
    st.altair_chart(modality_chart, width="stretch")

    st.subheader("Amostra da base de credito tratada")
    display_columns = [
        column
        for column in (
            "data_base",
            "uf",
            "segmento",
            "cliente",
            "porte",
            "modalidade",
            "numero_de_operacoes",
            "carteira_ativa",
            "carteira_inadimplencia",
            "taxa_inadimplencia_pct",
            "ativo_problematico",
        )
        if column in filtered
    ]
    st.dataframe(filtered[display_columns].head(200), width="stretch", hide_index=True)


st.title("Hermes Analytics")
st.caption("Analise automatica local, insights com Hermes e saidas prontas para Power BI.")

with st.sidebar:
    st.header("Fonte de dados")
    uploaded = st.file_uploader("Envie CSV ou Parquet", type=["csv", "parquet"])
    use_hermes = st.toggle(
        "Gerar narrativa com Hermes",
        value=os.getenv("HERMES_AUTO_INSIGHTS", "1") == "1",
        help="O processamento numerico continua local mesmo se o Hermes falhar.",
    )
    force = st.button("Reprocessar agora", width="stretch")
    st.divider()
    st.caption(f"Pasta monitorada: {INBOX}")
    st.caption("Atualizacao automatica: a cada 5 segundos")
    hermes_mode = "API remota" if os.getenv("HERMES_API_URL") else "Executavel local"
    st.caption(f"Modo Hermes: {hermes_mode}")

if uploaded is not None:
    current = save_upload(uploaded)
    st.toast(f"Base salva: {current.name}")


@st.fragment(run_every="5s")
def monitor() -> None:
    source = active_file()
    if source is None:
        st.warning("Nenhuma base encontrada. Execute o gerador de exemplo ou envie um arquivo.")
        return
    try:
        with st.spinner("Verificando e processando a base..."):
            manifest = process_dataset(
                source,
                OUTPUT,
                STATE,
                ROOT,
                use_hermes=use_hermes,
                force=force,
            )
        status = "Base alterada e reprocessada" if manifest["changed"] else "Base sincronizada"
        st.success(
            f"{status} | {manifest['rows']} linhas | "
            f"{manifest['processed_at']} | Insights: {manifest['insight_source']}"
        )
        if manifest.get("hermes_error"):
            with st.expander("Detalhe da integracao Hermes"):
                st.warning(manifest["hermes_error"])

        profile = json.loads(Path(manifest["profile_path"]).read_text(encoding="utf-8"))
        insights = Path(manifest["insights_path"]).read_text(encoding="utf-8")
        fact_path = Path(manifest["fact_path"])
        data = load_processed_dataset(str(fact_path), fact_path.stat().st_mtime_ns)

        tabs = st.tabs(["Dashboard", "Insights", "Power BI", "Qualidade"])
        with tabs[0]:
            if manifest.get("domain") == "credito_scr":
                render_credit_dashboard(data)
            else:
                render_dashboard(data)
        with tabs[1]:
            st.markdown(insights.replace("R$", r"R\$"))
        with tabs[2]:
            st.write(
                "Conecte o Power BI a pasta abaixo. Os CSVs usam UTF-8 com BOM e o arquivo "
                "Parquet preserva tipos de dados."
            )
            st.code(str(OUTPUT.resolve()), language=None)
            files = sorted(OUTPUT.glob("*.parquet")) + sorted(OUTPUT.glob("*.csv"))
            if files:
                selected_name = st.selectbox(
                    "Arquivo para download",
                    [path.name for path in files],
                )
                selected = next(path for path in files if path.name == selected_name)
                if st.checkbox("Preparar arquivo para download", key="prepare_download"):
                    st.download_button(
                        f"Baixar {selected.name}",
                        data=selected.read_bytes(),
                        file_name=selected.name,
                        mime="application/octet-stream",
                        key=str(selected),
                    )
        with tabs[3]:
            st.json(profile["quality"])
            st.write("Colunas detectadas:", ", ".join(profile["column_names"]))
    except Exception as exc:
        st.exception(exc)


monitor()
