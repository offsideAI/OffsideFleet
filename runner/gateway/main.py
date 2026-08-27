"""FastAPI runner-gateway (ADR-004): intentionally dumb — starts and kills
hardened containers, holds no business logic and no DB connection.

Run: uv run uvicorn gateway.main:app --port 8100
"""

import logging
import secrets
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from . import docker_runner
from .config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

app = FastAPI(title="OffsideFleet runner-gateway", docs_url=None, redoc_url=None)


def require_internal_auth(request: Request) -> None:
    header = request.headers.get("Authorization", "")
    token = header.removeprefix("Bearer ")
    if not secrets.compare_digest(token, config.internal_api_secret):
        raise HTTPException(status_code=401, detail="invalid internal secret")


Auth = Annotated[None, Depends(require_internal_auth)]


class RunSpec(BaseModel):
    run_id: str
    blueprint_ir: dict[str, Any]
    input_text: str = ""
    callback_token: str
    control_plane_url: str | None = None


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    try:
        docker_runner.client().ping()
        docker_ok = True
    except Exception:
        docker_ok = False
    return {"status": "ok" if docker_ok else "degraded", "docker": docker_ok}


@app.post("/internal/runs/{run_id}/start", status_code=202)
def start_run(run_id: str, spec: RunSpec, _: Auth) -> dict[str, Any]:
    if spec.run_id != run_id:
        raise HTTPException(status_code=400, detail="run_id mismatch")
    try:
        container_id = docker_runner.start_run_container(run_id, spec.model_dump())
    except Exception as exc:
        logger.exception("failed to start run %s", run_id)
        raise HTTPException(status_code=502, detail=f"container start failed: {exc}") from exc
    return {"container_id": container_id}


@app.post("/internal/runs/{run_id}/kill")
def kill_run(run_id: str, _: Auth) -> dict[str, Any]:
    result = docker_runner.kill_run_container(run_id)
    if not result["found"]:
        # Container already gone: report success-with-note so kill is idempotent.
        return {"found": False, "killed_in_ms": None}
    return result


@app.get("/internal/runs/{run_id}/status")
def run_status(run_id: str, _: Auth) -> dict[str, Any]:
    return docker_runner.run_container_status(run_id)
