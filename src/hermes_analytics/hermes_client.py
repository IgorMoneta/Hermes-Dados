from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HermesResult:
    available: bool
    text: str
    error: str | None = None


def build_prompt(profile: dict[str, Any]) -> str:
    compact = json.dumps(profile, ensure_ascii=False, default=str)
    return f"""
Voce e o analista de dados Hermes. Analise o resumo JSON abaixo. A chave
"domain" identifica o dominio da base. Produza uma resposta curta em portugues do Brasil com:
1. cinco insights objetivos, sempre citando numeros;
2. dois alertas de qualidade ou risco;
3. tres recomendacoes para decisao.
Nao invente fatos fora do JSON. Nao use ferramentas nem altere arquivos.

RESUMO_JSON:
{compact}
""".strip()


def run_hermes(
    profile: dict[str, Any],
    cwd: Path,
    timeout_seconds: int = 120,
) -> HermesResult:
    executable = shutil.which("hermes")
    if not executable:
        return HermesResult(False, "", "CLI do Hermes nao encontrado.")

    command = [
        executable,
        "chat",
        "-q",
        build_prompt(profile),
        "-Q",
        "--ignore-rules",
        "--source",
        "tool",
        "--max-turns",
        "1",
        "-t",
        "none",
    ]
    environment = os.environ.copy()
    configured_home = Path(environment.get("HERMES_HOME", "")).expanduser()
    installed_home = Path(executable).resolve().parents[3]
    if not (configured_home / "auth.json").exists() and (installed_home / "auth.json").exists():
        environment["HERMES_HOME"] = str(installed_home)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return HermesResult(False, "", "Hermes excedeu o tempo limite.")
    except OSError as exc:
        return HermesResult(False, "", f"Falha ao iniciar Hermes: {exc}")

    text = "\n".join(
        line
        for line in completed.stdout.splitlines()
        if not line.strip().lower().startswith(("session_id:", "warning: unknown toolsets:"))
    ).strip()
    if completed.returncode != 0 or not text:
        error = completed.stderr.strip() or f"Hermes retornou codigo {completed.returncode}."
        return HermesResult(False, "", error[-1200:])
    return HermesResult(True, text)
