from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


PROPERTY_ALIASES = {
    "price_brl": ("price_brl", "preco", "preço", "price", "valor"),
    "area_m2": ("area_m2", "area", "área", "sqm", "m2"),
    "city": ("city", "cidade", "municipio", "município"),
    "state": ("state", "estado", "uf"),
    "neighborhood": ("neighborhood", "bairro"),
    "property_type": ("property_type", "tipo_imovel", "tipo", "type"),
    "listing_date": ("listing_date", "data_anuncio", "data", "date"),
}

CREDIT_VALUE_COLUMNS = (
    "a_vencer_ate_90_dias",
    "a_vencer_de_91_ate_360_dias",
    "a_vencer_de_361_ate_1080_dias",
    "a_vencer_de_1081_ate_1800_dias",
    "a_vencer_de_1801_ate_5400_dias",
    "a_vencer_acima_de_5400_dias",
    "carteira_a_vencer",
    "vencido_de_15_ate_90_dias",
    "vencido_acima_de_90_dias",
    "carteira_vencida",
    "carteira_ativa",
    "carteira_inadimplencia",
    "ativo_problematico",
)


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [
        str(column).lstrip("\ufeff").strip().lower().replace(" ", "_").replace("-", "_")
        for column in normalized.columns
    ]
    return normalized


def normalize_property_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_columns(frame)
    rename: dict[str, str] = {}
    for canonical, aliases in PROPERTY_ALIASES.items():
        for alias in aliases:
            candidate = alias.lower().replace(" ", "_")
            if candidate in normalized.columns:
                rename[candidate] = canonical
                break
    return normalized.rename(columns=rename)


def detect_domain(frame: pd.DataFrame) -> str:
    columns = set(normalize_columns(frame).columns)
    if {"carteira_ativa", "carteira_inadimplencia", "modalidade", "uf"}.issubset(columns):
        return "credito_scr"
    if {"price_brl", "area_m2"}.issubset(columns):
        return "imoveis"
    return "generico"


def _numeric_br(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    normalized = series.astype("string").str.strip()
    normalized = normalized.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(normalized, errors="coerce")


def clean_credit_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    malformed_rows = int(frame.attrs.get("malformed_rows_skipped", 0))
    data = normalize_columns(frame)
    rows_before = len(data)
    duplicate_rows = int(data.duplicated().sum())
    data = data.drop_duplicates().copy()

    if "data_base" in data:
        data["data_base"] = pd.to_datetime(data["data_base"], errors="coerce")
    for column in CREDIT_VALUE_COLUMNS:
        if column in data:
            data[column] = _numeric_br(data[column]).fillna(0.0)
    if "numero_de_operacoes" in data:
        data["numero_de_operacoes"] = _numeric_br(data["numero_de_operacoes"])
        data.loc[data["numero_de_operacoes"] < 0, "numero_de_operacoes"] = np.nan

    active = data.get("carteira_ativa", pd.Series(0.0, index=data.index)).replace(0, np.nan)
    for source, target in (
        ("carteira_inadimplencia", "taxa_inadimplencia_pct"),
        ("carteira_vencida", "taxa_carteira_vencida_pct"),
        ("ativo_problematico", "taxa_ativo_problematico_pct"),
    ):
        if source in data:
            data[target] = (data[source] / active * 100).fillna(0.0)

    quality = {
        "rows_before": rows_before,
        "rows_after": len(data),
        "duplicate_rows_removed": duplicate_rows,
        "missing_cells": int(data.isna().sum().sum()),
        "operations_unavailable": int(data.get("numero_de_operacoes", pd.Series()).isna().sum()),
        "negative_financial_values": int(
            sum((data[column] < 0).sum() for column in CREDIT_VALUE_COLUMNS if column in data)
        ),
        "malformed_rows_skipped": malformed_rows,
    }
    return data, quality


def clean_data(frame: pd.DataFrame, domain: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if domain == "credito_scr":
        return clean_credit_data(frame)
    if domain == "imoveis":
        return clean_property_data(frame)
    return clean_generic_data(frame)


def clean_generic_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    malformed_rows = int(frame.attrs.get("malformed_rows_skipped", 0))
    data = normalize_columns(frame)
    rows_before = len(data)
    duplicate_rows = int(data.duplicated().sum())
    data = data.drop_duplicates().copy()
    quality = {
        "rows_before": rows_before,
        "rows_after": len(data),
        "duplicate_rows_removed": duplicate_rows,
        "missing_cells": int(data.isna().sum().sum()),
        "malformed_rows_skipped": malformed_rows,
    }
    return data, quality


def clean_property_data(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    malformed_rows = int(frame.attrs.get("malformed_rows_skipped", 0))
    data = normalize_property_columns(frame)
    rows_before = len(data)
    duplicate_rows = int(data.duplicated().sum())
    data = data.drop_duplicates().copy()

    for column in ("price_brl", "area_m2", "bedrooms", "bathrooms", "parking_spaces"):
        if column in data:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    if "listing_date" in data:
        data["listing_date"] = pd.to_datetime(data["listing_date"], errors="coerce")

    invalid_price = int((data.get("price_brl", pd.Series(dtype=float)) <= 0).sum())
    invalid_area = int((data.get("area_m2", pd.Series(dtype=float)) <= 0).sum())
    if "price_brl" in data:
        data.loc[data["price_brl"] <= 0, "price_brl"] = np.nan
    if "area_m2" in data:
        data.loc[data["area_m2"] <= 0, "area_m2"] = np.nan

    if {"price_brl", "area_m2"}.issubset(data.columns):
        calculated = data["price_brl"] / data["area_m2"]
        if "price_per_m2" not in data:
            data["price_per_m2"] = calculated
        else:
            data["price_per_m2"] = pd.to_numeric(data["price_per_m2"], errors="coerce")
            data["price_per_m2"] = data["price_per_m2"].fillna(calculated)

    quality = {
        "rows_before": rows_before,
        "rows_after": len(data),
        "duplicate_rows_removed": duplicate_rows,
        "invalid_price_values": invalid_price,
        "invalid_area_values": invalid_area,
        "missing_cells": int(data.isna().sum().sum()),
        "malformed_rows_skipped": malformed_rows,
    }
    return data, quality


def _safe_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), 2)


def create_profile(data: pd.DataFrame, quality: dict[str, Any]) -> dict[str, Any]:
    numeric = data.select_dtypes(include="number")
    profile: dict[str, Any] = {
        "rows": len(data),
        "columns": len(data.columns),
        "quality": quality,
        "column_names": list(data.columns),
    }

    if "price_brl" in data:
        prices = data["price_brl"].dropna()
        profile["price"] = {
            "total_brl": _safe_float(prices.sum()),
            "mean_brl": _safe_float(prices.mean()),
            "median_brl": _safe_float(prices.median()),
            "min_brl": _safe_float(prices.min()),
            "max_brl": _safe_float(prices.max()),
        }
    if "price_per_m2" in data:
        profile["mean_price_per_m2_brl"] = _safe_float(data["price_per_m2"].mean())
    if "area_m2" in data:
        profile["mean_area_m2"] = _safe_float(data["area_m2"].mean())

    for dimension in ("city", "neighborhood", "property_type", "state", "status"):
        if dimension in data:
            counts = data[dimension].fillna("Nao informado").value_counts().head(10)
            profile[f"top_{dimension}"] = {str(k): int(v) for k, v in counts.items()}

    if "price_brl" in numeric and len(numeric.columns) > 1:
        correlations = (
            numeric.corr(numeric_only=True)["price_brl"]
            .drop("price_brl")
            .dropna()
            .sort_values(key=abs, ascending=False)
            .head(5)
        )
        profile["price_correlations"] = {str(k): round(float(v), 3) for k, v in correlations.items()}

    if {"neighborhood", "price_per_m2"}.issubset(data.columns):
        grouped = (
            data.groupby("neighborhood", dropna=False)
            .agg(listings=("price_per_m2", "size"), mean_price_m2=("price_per_m2", "mean"))
            .query("listings >= 5")
            .sort_values("mean_price_m2", ascending=False)
            .head(10)
        )
        profile["most_expensive_neighborhoods"] = {
            str(index): {
                "listings": int(row["listings"]),
                "mean_price_m2_brl": round(float(row["mean_price_m2"]), 2),
            }
            for index, row in grouped.iterrows()
        }
    return profile


def create_credit_profile(data: pd.DataFrame, quality: dict[str, Any]) -> dict[str, Any]:
    active = float(data["carteira_ativa"].sum())
    default = float(data["carteira_inadimplencia"].sum())
    overdue = float(data["carteira_vencida"].sum())
    problematic = float(data["ativo_problematico"].sum())
    operations = float(data["numero_de_operacoes"].sum(skipna=True))
    profile: dict[str, Any] = {
        "domain": "credito_scr",
        "rows": len(data),
        "columns": len(data.columns),
        "quality": quality,
        "column_names": list(data.columns),
        "reference_date": (
            data["data_base"].max().date().isoformat()
            if "data_base" in data and data["data_base"].notna().any()
            else None
        ),
        "portfolio": {
            "active_brl": round(active, 2),
            "default_brl": round(default, 2),
            "overdue_brl": round(overdue, 2),
            "problematic_brl": round(problematic, 2),
            "operations": int(operations),
            "default_rate_pct": round(default / active * 100, 3) if active else 0,
            "overdue_rate_pct": round(overdue / active * 100, 3) if active else 0,
            "problematic_rate_pct": round(problematic / active * 100, 3) if active else 0,
        },
    }
    for dimension in ("uf", "segmento", "cliente", "porte", "modalidade", "indexador"):
        if dimension not in data:
            continue
        grouped = (
            data.groupby(dimension, dropna=False)
            .agg(
                carteira_ativa=("carteira_ativa", "sum"),
                inadimplencia=("carteira_inadimplencia", "sum"),
                ativo_problematico=("ativo_problematico", "sum"),
            )
            .sort_values("carteira_ativa", ascending=False)
            .head(10)
        )
        grouped["taxa_inadimplencia_pct"] = (
            grouped["inadimplencia"] / grouped["carteira_ativa"] * 100
        ).fillna(0)
        profile[f"top_{dimension}"] = {
            str(index): {
                "carteira_ativa_brl": round(float(row["carteira_ativa"]), 2),
                "inadimplencia_brl": round(float(row["inadimplencia"]), 2),
                "taxa_inadimplencia_pct": round(float(row["taxa_inadimplencia_pct"]), 3),
            }
            for index, row in grouped.iterrows()
        }
    return profile


def create_analysis_profile(
    data: pd.DataFrame, quality: dict[str, Any], domain: str
) -> dict[str, Any]:
    if domain == "credito_scr":
        return create_credit_profile(data, quality)
    if domain == "generico":
        return create_generic_profile(data, quality)
    profile = create_profile(data, quality)
    profile["domain"] = domain
    return profile


def create_generic_profile(
    data: pd.DataFrame, quality: dict[str, Any]
) -> dict[str, Any]:
    numeric = data.select_dtypes(include="number")
    categorical = [
        column
        for column in data.columns
        if data[column].nunique(dropna=True) <= 50
    ]
    profile: dict[str, Any] = {
        "domain": "generico",
        "rows": len(data),
        "columns": len(data.columns),
        "quality": quality,
        "column_names": list(data.columns),
        "numeric_columns": list(numeric.columns),
        "categorical_columns": categorical,
    }
    profile["numeric_summary"] = {
        column: {
            "mean": _safe_float(numeric[column].mean()),
            "median": _safe_float(numeric[column].median()),
            "min": _safe_float(numeric[column].min()),
            "max": _safe_float(numeric[column].max()),
        }
        for column in numeric.columns[:20]
    }
    profile["top_values"] = {
        column: {
            str(value): int(count)
            for value, count in data[column]
            .fillna("Nao informado")
            .astype(str)
            .value_counts()
            .head(10)
            .items()
        }
        for column in categorical[:10]
    }
    return profile


def deterministic_insights(profile: dict[str, Any]) -> str:
    if profile.get("domain") == "credito_scr":
        return credit_insights(profile)
    if profile.get("domain") == "generico":
        return generic_insights(profile)
    def brl(value: float) -> str:
        return f"{value:,.0f}".replace(",", ".")

    price = profile.get("price", {})
    rows = profile.get("rows", 0)
    quality = profile.get("quality", {})
    lines = [
        "### Insights automaticos",
        f"- A base processada possui **{rows:,} registros** e **{profile.get('columns', 0)} colunas**.",
    ]
    if price.get("median_brl") is not None:
        lines.append(
            f"- O preco mediano e **R$ {brl(price['median_brl'])}**; "
            f"a media e **R$ {brl(price.get('mean_brl', 0))}**."
        )
    if profile.get("mean_price_per_m2_brl") is not None:
        lines.append(
            f"- O preco medio por m2 e **R$ {brl(profile['mean_price_per_m2_brl'])}**."
        )
    neighborhoods = profile.get("most_expensive_neighborhoods", {})
    if neighborhoods:
        name, details = next(iter(neighborhoods.items()))
        lines.append(
            f"- **{name}** lidera o preco por m2 entre bairros com volume relevante: "
            f"**R$ {brl(details['mean_price_m2_brl'])}/m2**."
        )
    correlations = profile.get("price_correlations", {})
    if correlations:
        name, value = next(iter(correlations.items()))
        lines.append(f"- A maior correlacao numerica com preco e **{name} ({value:.2f})**.")
    lines.extend(
        [
            "",
            "### Qualidade",
            f"- Duplicatas removidas: **{quality.get('duplicate_rows_removed', 0)}**.",
            f"- Celulas ausentes apos limpeza: **{quality.get('missing_cells', 0)}**.",
            "",
            "### Recomendacoes",
            "- Compare preco por m2 dentro da mesma cidade, bairro e tipo de imovel.",
            "- Investigue anuncios muito acima do intervalo interquartil antes de decidir.",
            "- Atualize a base monitorada e acompanhe a mudanca dos indicadores automaticamente.",
        ]
    )
    return "\n".join(lines)


def generic_insights(profile: dict[str, Any]) -> str:
    quality = profile.get("quality", {})
    numeric = profile.get("numeric_summary", {})
    lines = [
        "### Visao geral da base",
        f"- A base possui **{profile.get('rows', 0):,} registros** e "
        f"**{profile.get('columns', 0)} colunas**.",
        f"- Foram identificadas **{len(profile.get('numeric_columns', []))} colunas numericas** "
        f"e **{len(profile.get('categorical_columns', []))} categoricas**.",
    ]
    if numeric:
        name, values = next(iter(numeric.items()))
        lines.append(
            f"- A coluna **{name}** varia de **{values['min']}** a **{values['max']}**, "
            f"com media **{values['mean']}**."
        )
    lines.extend(
        [
            "",
            "### Qualidade",
            f"- Duplicatas removidas: **{quality.get('duplicate_rows_removed', 0)}**.",
            f"- Celulas ausentes: **{quality.get('missing_cells', 0)}**.",
            f"- Linhas malformadas ignoradas: **{quality.get('malformed_rows_skipped', 0)}**.",
            "",
            "### Recomendacoes",
            "- Defina o significado de cada coluna antes de interpretar correlacoes.",
            "- Compare distribuicoes, valores ausentes e categorias mais frequentes.",
            "- Para indicadores especificos, configure um dominio e regras de negocio da base.",
        ]
    )
    return "\n".join(lines)


def credit_insights(profile: dict[str, Any]) -> str:
    def brl_compact(value: float) -> str:
        if abs(value) >= 1_000_000_000_000:
            return f"R$ {value / 1_000_000_000_000:.2f} tri"
        if abs(value) >= 1_000_000_000:
            return f"R$ {value / 1_000_000_000:.2f} bi"
        return f"R$ {value / 1_000_000:.2f} mi"

    portfolio = profile["portfolio"]
    top_uf = profile.get("top_uf", {})
    largest_uf = next(iter(top_uf.items()), None)
    lines = [
        "### Visao executiva do credito",
        f"- A base SCR possui **{profile['rows']:,} registros** na data-base "
        f"**{profile.get('reference_date', 'nao informada')}**.",
        f"- A carteira ativa totaliza **{brl_compact(portfolio['active_brl'])}**.",
        f"- A inadimplencia soma **{brl_compact(portfolio['default_brl'])}**, equivalente a "
        f"**{portfolio['default_rate_pct']:.2f}%** da carteira ativa.",
        f"- O ativo problematico representa **{portfolio['problematic_rate_pct']:.2f}%**, "
        f"ou **{brl_compact(portfolio['problematic_brl'])}**.",
    ]
    if largest_uf:
        name, values = largest_uf
        lines.append(
            f"- **{name}** concentra a maior carteira entre as UFs: "
            f"**{brl_compact(values['carteira_ativa_brl'])}**."
        )
    lines.extend(
        [
            "",
            "### Qualidade",
            f"- Duplicatas removidas: **{profile['quality']['duplicate_rows_removed']}**.",
            f"- Operacoes marcadas como indisponiveis: "
            f"**{profile['quality']['operations_unavailable']:,}**.",
            "",
            "### Recomendacoes",
            "- Monitore modalidades com taxa de inadimplencia elevada e carteira relevante.",
            "- Compare PF e PJ por UF, porte e segmento antes de definir limites de risco.",
            "- Use os resumos exportados para acompanhar concentracao e qualidade da carteira.",
        ]
    )
    return "\n".join(lines)


def build_powerbi_tables(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tables = {"fato_imoveis": data.copy()}
    dimensions = [
        column
        for column in ("city", "state", "neighborhood", "property_type", "status")
        if column in data
    ]
    for column in dimensions:
        name = f"dim_{column}"
        values = sorted(data[column].dropna().astype(str).unique())
        tables[name] = pd.DataFrame({f"{column}_id": range(1, len(values) + 1), column: values})

    group_columns = [column for column in ("city", "neighborhood", "property_type") if column in data]
    for column in group_columns:
        aggregations: dict[str, tuple[str, str]] = {"anuncios": (column, "size")}
        if "price_brl" in data:
            aggregations["preco_medio_brl"] = ("price_brl", "mean")
            aggregations["preco_mediano_brl"] = ("price_brl", "median")
        if "price_per_m2" in data:
            aggregations["preco_m2_medio_brl"] = ("price_per_m2", "mean")
        tables[f"resumo_{column}"] = (
            data.groupby(column, dropna=False).agg(**aggregations).reset_index()
        )

    if {"listing_date", "price_brl"}.issubset(data.columns):
        monthly = data.dropna(subset=["listing_date"]).copy()
        monthly["mes"] = monthly["listing_date"].dt.to_period("M").astype(str)
        tables["resumo_mensal"] = (
            monthly.groupby("mes")
            .agg(anuncios=("price_brl", "size"), preco_medio_brl=("price_brl", "mean"))
            .reset_index()
        )
    return tables


def build_credit_tables(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tables = {"fato_credito": data.copy()}
    dimensions = (
        "uf",
        "segmento",
        "cliente",
        "cnae_ocupacao",
        "porte",
        "modalidade",
        "submodalidade",
        "origem",
        "indexador",
    )
    for column in dimensions:
        if column in data:
            values = sorted(data[column].dropna().astype(str).unique())
            tables[f"dim_{column}"] = pd.DataFrame(
                {f"{column}_id": range(1, len(values) + 1), column: values}
            )

    for column in ("uf", "segmento", "cliente", "porte", "modalidade", "indexador"):
        if column not in data:
            continue
        summary = (
            data.groupby(column, dropna=False)
            .agg(
                registros=(column, "size"),
                numero_de_operacoes=("numero_de_operacoes", "sum"),
                carteira_ativa=("carteira_ativa", "sum"),
                carteira_vencida=("carteira_vencida", "sum"),
                carteira_inadimplencia=("carteira_inadimplencia", "sum"),
                ativo_problematico=("ativo_problematico", "sum"),
            )
            .reset_index()
        )
        summary["taxa_inadimplencia_pct"] = (
            summary["carteira_inadimplencia"] / summary["carteira_ativa"] * 100
        ).fillna(0)
        summary["taxa_ativo_problematico_pct"] = (
            summary["ativo_problematico"] / summary["carteira_ativa"] * 100
        ).fillna(0)
        tables[f"resumo_{column}"] = summary
    return tables


def build_analysis_tables(data: pd.DataFrame, domain: str) -> dict[str, pd.DataFrame]:
    if domain == "credito_scr":
        return build_credit_tables(data)
    if domain == "generico":
        return build_generic_tables(data)
    return build_powerbi_tables(data)


def build_generic_tables(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    summary_rows = []
    for column in data.columns:
        series = data[column]
        summary_rows.append(
            {
                "coluna": column,
                "tipo": str(series.dtype),
                "preenchidos": int(series.notna().sum()),
                "ausentes": int(series.isna().sum()),
                "valores_unicos": int(series.nunique(dropna=True)),
            }
        )
    return {
        "fato_dados": data.copy(),
        "resumo_colunas": pd.DataFrame(summary_rows),
    }
