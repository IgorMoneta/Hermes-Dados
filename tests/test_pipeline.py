from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from hermes_analytics.pipeline import process_dataset
from hermes_analytics.hermes_client import run_hermes


def test_pipeline_reprocesses_only_when_file_changes(tmp_path: Path) -> None:
    source = tmp_path / "property.csv"
    output = tmp_path / "output"
    state = tmp_path / "state"
    frame = pd.DataFrame(
        {
            "city": ["Sao Paulo", "Sao Paulo", "Curitiba"],
            "neighborhood": ["Centro", "Centro", "Batel"],
            "property_type": ["Apartamento", "Casa", "Apartamento"],
            "listing_date": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "price_brl": [500000, 900000, 750000],
            "area_m2": [50, 120, 70],
        }
    )
    frame.to_csv(source, index=False)

    first = process_dataset(source, output, state, tmp_path, use_hermes=False)
    second = process_dataset(source, output, state, tmp_path, use_hermes=False)
    frame.loc[len(frame)] = ["Curitiba", "Cabral", "Studio", "2026-04-01", 400000, 35]
    frame.to_csv(source, index=False)
    third = process_dataset(source, output, state, tmp_path, use_hermes=False)

    assert first["changed"] is True
    assert second["changed"] is False
    assert third["changed"] is True
    assert third["rows"] == 4
    assert (output / "fato_imoveis.csv").exists()
    assert (output / "fato_imoveis.parquet").exists()
    profile = json.loads((output / "perfil_analitico.json").read_text(encoding="utf-8"))
    assert profile["price"]["median_brl"] == 625000.0


def test_credit_scr_pipeline(tmp_path: Path) -> None:
    source = tmp_path / "scr.csv"
    output = tmp_path / "output"
    state = tmp_path / "state"
    frame = pd.DataFrame(
        {
            "data_base": ["2026-01-31", "2026-01-31"],
            "uf": ["SP", "RJ"],
            "segmento": ["Banco", "Fintech"],
            "cliente": ["PF", "PJ"],
            "porte": ["Pequeno", "Medio"],
            "modalidade": ["Emprestimos", "Financiamentos"],
            "numero_de_operacoes": [100, -1],
            "carteira_ativa": ["1000,00", "500,00"],
            "carteira_vencida": ["100,00", "25,00"],
            "carteira_inadimplencia": ["80,00", "20,00"],
            "ativo_problematico": ["120,00", "30,00"],
        }
    )
    frame.to_csv(source, sep=";", index=False)

    result = process_dataset(source, output, state, tmp_path, use_hermes=False)
    profile = json.loads((output / "perfil_analitico.json").read_text(encoding="utf-8"))

    assert result["domain"] == "credito_scr"
    assert result["rows"] == 2
    assert profile["portfolio"]["active_brl"] == 1500.0
    assert profile["portfolio"]["default_rate_pct"] == 6.667
    assert (output / "fato_credito.parquet").exists()
    assert (output / "resumo_uf.csv").exists()


def test_hermes_uses_installed_home_when_environment_is_missing(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    executable = hermes_home / "hermes-agent" / "venv" / "Scripts" / "hermes.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    (hermes_home / "auth.json").write_text("{}", encoding="utf-8")

    completed = type("Completed", (), {"returncode": 0, "stdout": "OK", "stderr": ""})()
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("hermes_analytics.hermes_client.shutil.which", return_value=str(executable)),
        patch("hermes_analytics.hermes_client.subprocess.run", return_value=completed) as run,
    ):
        result = run_hermes({"domain": "credito_scr"}, tmp_path)

    assert result.available is True
    assert run.call_args.kwargs["env"]["HERMES_HOME"] == str(hermes_home)


def test_missing_artifact_is_recreated(tmp_path: Path) -> None:
    source = tmp_path / "property.csv"
    output = tmp_path / "output"
    state = tmp_path / "state"
    pd.DataFrame(
        {"price_brl": [100000], "area_m2": [50], "city": ["Curitiba"]}
    ).to_csv(source, index=False)

    process_dataset(source, output, state, tmp_path, use_hermes=False)
    (output / "perfil_analitico.json").unlink()
    result = process_dataset(source, output, state, tmp_path, use_hermes=False)

    assert result["changed"] is True
    assert (output / "perfil_analitico.json").exists()


def test_concurrent_processing_keeps_artifacts_available(tmp_path: Path) -> None:
    source = tmp_path / "property.csv"
    output = tmp_path / "output"
    state = tmp_path / "state"
    pd.DataFrame(
        {
            "price_brl": [100000, 200000],
            "area_m2": [50, 80],
            "city": ["Curitiba", "Sao Paulo"],
        }
    ).to_csv(source, index=False)

    def run() -> dict:
        return process_dataset(
            source, output, state, tmp_path, use_hermes=False, force=True
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))

    assert all(result["rows"] == 2 for result in results)
    manifest = json.loads((state / "manifest.json").read_text(encoding="utf-8"))
    assert Path(manifest["profile_path"]).exists()
    assert Path(manifest["insights_path"]).exists()
    assert Path(manifest["fact_path"]).exists()
