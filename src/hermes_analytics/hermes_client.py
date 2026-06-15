from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HermesResult:
    available: bool
    text: str
    error: str | None = None


def _remote_error_message(exc: Exception, api_url: str) -> str:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, socket.gaierror):
        return (
            "Nao foi possivel localizar o endereco da API remota do Hermes. "
            "A URL do Cloudflare Tunnel pode ter expirado; reinicie "
            "INICIAR_HERMES_ONLINE.bat e atualize HERMES_API_URL nos Secrets "
            f"do Streamlit. URL configurada: {api_url}"
        )
    if isinstance(reason, (ConnectionRefusedError, ConnectionResetError)):
        return (
            "A API remota do Hermes recusou a conexao. Confirme que a API local "
            "e o Cloudflare Tunnel continuam em execucao."
        )
    if isinstance(reason, TimeoutError):
        return (
            "A API remota do Hermes excedeu o tempo limite. Confirme a conexao "
            "e aumente HERMES_TIMEOUT_SECONDS se necessario."
        )
    return f"Falha na API remota do Hermes: {exc}"


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


def run_hermes_local(
    profile: dict[str, Any],
    cwd: Path,
    timeout_seconds: int | None = None,
) -> HermesResult:
    executable = shutil.which("hermes")
    if not executable:
        return HermesResult(False, "", "CLI do Hermes nao encontrado.")
    if timeout_seconds is None:
        timeout_seconds = int(
            os.getenv(
                "HERMES_LOCAL_TIMEOUT_SECONDS",
                os.getenv("HERMES_TIMEOUT_SECONDS", "60"),
            )
        )

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
        "hermes-cli",
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


def run_hermes_remote(
    profile: dict[str, Any],
    api_url: str,
    api_token: str,
    timeout_seconds: int,
) -> HermesResult:
    endpoint = f"{api_url.rstrip('/')}/analyze"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"profile": profile}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Hermes-Analytics/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return HermesResult(False, "", f"API Hermes retornou HTTP {exc.code}: {detail[-500:]}")
    except json.JSONDecodeError:
        return HermesResult(False, "", "A API remota do Hermes retornou JSON invalido.")
    except (urllib.error.URLError, TimeoutError) as exc:
        return HermesResult(False, "", _remote_error_message(exc, api_url))

    if not payload.get("available") or not payload.get("text"):
        return HermesResult(False, "", payload.get("error") or "API Hermes sem resposta valida.")
    return HermesResult(True, str(payload["text"]))


def run_hermes(
    profile: dict[str, Any],
    cwd: Path,
    timeout_seconds: int | None = None,
) -> HermesResult:
    if timeout_seconds is None:
        timeout_seconds = int(os.getenv("HERMES_TIMEOUT_SECONDS", "20"))

    api_url = os.getenv("HERMES_API_URL", "").strip()
    api_token = os.getenv("HERMES_API_TOKEN", "").strip()
    if api_url:
        if not api_token:
            return HermesResult(False, "", "HERMES_API_TOKEN nao configurado.")
        return run_hermes_remote(profile, api_url, api_token, timeout_seconds)
    return run_hermes_local(profile, cwd, timeout_seconds)
