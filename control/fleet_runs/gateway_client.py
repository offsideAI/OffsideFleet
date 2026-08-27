"""HTTP client for the runner-gateway internal API (ADR-004)."""

from typing import Any

import httpx2 as httpx
from django.conf import settings


class GatewayError(Exception):
    pass


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.RUNNER_GATEWAY_URL,
        headers={"Authorization": f"Bearer {settings.INTERNAL_API_SECRET}"},
        timeout=10.0,
    )


def start_run(run_id: str, run_spec: dict[str, Any]) -> None:
    with _client() as client:
        resp = client.post(f"/internal/runs/{run_id}/start", json=run_spec)
        if resp.status_code != 202:
            raise GatewayError(f"gateway start returned {resp.status_code}: {resp.text}")


def kill_run(run_id: str) -> dict[str, Any]:
    with _client() as client:
        resp = client.post(f"/internal/runs/{run_id}/kill")
        if resp.status_code != 200:
            raise GatewayError(f"gateway kill returned {resp.status_code}: {resp.text}")
        return dict(resp.json())
