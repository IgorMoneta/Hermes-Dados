from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .analyzer import (
    build_analysis_tables,
    clean_data,
    create_analysis_profile,
    detect_domain,
    deterministic_insights,
)
from .hermes_client import run_hermes


@contextmanager
def processing_lock(state_dir: Path, timeout_seconds: int = 300):
    lock_path = state_dir / "processing.lock"
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > timeout_seconds * 2:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError("Outro processamento ainda esta em andamento.")
            time.sleep(0.25)
    try:
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def manifest_artifacts_exist(manifest: dict[str, Any]) -> bool:
    required = ("profile_path", "insights_path", "fact_path")
    return all(manifest.get(key) and Path(manifest[key]).is_file() for key in required)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(
                path, sep=None, engine="python", encoding="utf-8-sig", decimal=","
            )
        except UnicodeDecodeError:
            return pd.read_csv(path, sep=None, engine="python", encoding="latin-1")
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError("Formato nao suportado. Use CSV ou Parquet.")


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    raise TypeError(f"Tipo nao serializavel: {type(value)!r}")


def process_dataset(
    source_path: Path,
    output_dir: Path,
    state_dir: Path,
    project_dir: Path,
    use_hermes: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    digest = file_digest(source_path)
    manifest_path = state_dir / "manifest.json"

    with processing_lock(state_dir):
        if manifest_path.exists() and not force:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                manifest = {}
            if (
                manifest.get("source") == str(source_path)
                and manifest.get("sha256") == digest
                and manifest_artifacts_exist(manifest)
            ):
                return {**manifest, "changed": False}

        staging_dir = state_dir / f"staging-{uuid.uuid4().hex}"
        staging_dir.mkdir()
        try:
            raw = load_dataset(source_path)
            domain = detect_domain(raw)
            clean, quality = clean_data(raw, domain)
            profile = create_analysis_profile(clean, quality, domain)
            tables = build_analysis_tables(clean, domain)

            staged_files: list[tuple[Path, Path]] = []
            for name, table in tables.items():
                staged = staging_dir / f"{name}.csv"
                table.to_csv(
                    staged, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d"
                )
                staged_files.append((staged, output_dir / staged.name))

            fact_name = "fato_credito" if domain == "credito_scr" else "fato_imoveis"
            staged_parquet = staging_dir / f"{fact_name}.parquet"
            clean.to_parquet(staged_parquet, index=False)
            parquet_path = output_dir / staged_parquet.name
            staged_files.append((staged_parquet, parquet_path))

            fallback = deterministic_insights(profile)
            hermes = run_hermes(profile, project_dir) if use_hermes else None
            insight_text = hermes.text if hermes and hermes.available else fallback
            insight_source = "Hermes Agent" if hermes and hermes.available else "Motor local"
            hermes_error = hermes.error if hermes else None

            staged_profile = staging_dir / "perfil_analitico.json"
            staged_profile.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2, default=_json_default),
                encoding="utf-8",
            )
            staged_insights = staging_dir / "insights.md"
            staged_insights.write_text(insight_text, encoding="utf-8")
            staged_files.extend(
                [
                    (staged_profile, output_dir / staged_profile.name),
                    (staged_insights, output_dir / staged_insights.name),
                ]
            )

            for staged, target in staged_files:
                os.replace(staged, target)

            manifest = {
                "source": str(source_path),
                "sha256": digest,
                "processed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "rows": len(clean),
                "columns": len(clean.columns),
                "domain": domain,
                "fact_path": str(parquet_path.resolve()),
                "output_dir": str(output_dir.resolve()),
                "profile_path": str((output_dir / "perfil_analitico.json").resolve()),
                "insights_path": str((output_dir / "insights.md").resolve()),
                "insight_source": insight_source,
                "hermes_error": hermes_error,
                "changed": True,
                "hermes": asdict(hermes) if hermes else None,
            }
            atomic_write_text(
                manifest_path,
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            return manifest
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)
