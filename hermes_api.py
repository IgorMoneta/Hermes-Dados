from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from hermes_analytics.hermes_client import run_hermes_local  # noqa: E402


class AnalysisRequest(BaseModel):
    profile: dict[str, Any] = Field(description="Perfil analitico agregado da base")


class AnalysisResponse(BaseModel):
    available: bool
    text: str
    error: str | None = None


app = FastAPI(
    title="Hermes Analytics Local Bridge",
    description="Ponte protegida entre o sistema publicado e o Hermes local.",
    docs_url=None,
    redoc_url=None,
)


def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("HERMES_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="HERMES_API_TOKEN nao configurado no servidor.")
    prefix = "Bearer "
    supplied = authorization[len(prefix) :] if authorization and authorization.startswith(prefix) else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Token invalido.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalysisResponse, dependencies=[Depends(require_token)])
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    if len(request.profile) > 100:
        raise HTTPException(status_code=413, detail="Perfil analitico acima do limite.")
    result = run_hermes_local(request.profile, ROOT)
    return AnalysisResponse(
        available=result.available,
        text=result.text,
        error=result.error,
    )
