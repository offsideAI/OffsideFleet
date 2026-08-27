"""Control-plane callback client. All traffic leaves via the egress proxy."""

import logging
import os
from typing import Any

import httpx2 as httpx

logger = logging.getLogger("agent.callback")


class CallbackClient:
    def __init__(self, control_plane_url: str, run_id: str, token: str):
        proxy = os.environ.get("FLEET_EGRESS_PROXY_URL")
        self._client = httpx.Client(
            base_url=control_plane_url,
            headers={"Authorization": f"Bearer {token}"},
            proxy=proxy,
            timeout=30.0,
        )
        self._run_id = run_id

    def append_steps(self, steps: list[dict[str, Any]]) -> None:
        resp = self._client.post(
            f"/internal/callbacks/runs/{self._run_id}/steps", json={"steps": steps}
        )
        resp.raise_for_status()

    def set_state(self, state: str, error: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"state": state}
        if error is not None:
            payload["error"] = error
        resp = self._client.post(
            f"/internal/callbacks/runs/{self._run_id}/state", json=payload
        )
        resp.raise_for_status()

    def close(self) -> None:
        self._client.close()
