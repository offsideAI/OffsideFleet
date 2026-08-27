"""Gateway API tests with the Docker layer mocked."""

from typing import Any
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from gateway.main import app

AUTH = {"Authorization": "Bearer dev-internal-secret"}

SPEC: dict[str, Any] = {
    "run_id": "11111111-1111-1111-1111-111111111111",
    "blueprint_ir": {"model": {"id": "claude-opus-5"}},
    "input_text": "hi",
    "callback_token": "tok",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_start_requires_auth(client: TestClient) -> None:
    resp = client.post(f"/internal/runs/{SPEC['run_id']}/start", json=SPEC)
    assert resp.status_code == 401
    resp = client.post(
        f"/internal/runs/{SPEC['run_id']}/start",
        json=SPEC,
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_start_spawns_container(client: TestClient) -> None:
    with mock.patch("gateway.main.docker_runner.start_run_container", return_value="cid") as start:
        resp = client.post(f"/internal/runs/{SPEC['run_id']}/start", json=SPEC, headers=AUTH)
    assert resp.status_code == 202
    assert resp.json()["container_id"] == "cid"
    start.assert_called_once()
    # The spec (with callback token) is passed through verbatim.
    assert start.call_args.args[1]["callback_token"] == "tok"


def test_start_run_id_mismatch(client: TestClient) -> None:
    resp = client.post("/internal/runs/other-id/start", json=SPEC, headers=AUTH)
    assert resp.status_code == 400


def test_kill_found(client: TestClient) -> None:
    with mock.patch(
        "gateway.main.docker_runner.kill_run_container",
        return_value={"found": True, "killed_in_ms": 120},
    ):
        resp = client.post(f"/internal/runs/{SPEC['run_id']}/kill", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["killed_in_ms"] == 120


def test_kill_idempotent_when_gone(client: TestClient) -> None:
    with mock.patch(
        "gateway.main.docker_runner.kill_run_container",
        return_value={"found": False, "killed_in_ms": None},
    ):
        resp = client.post(f"/internal/runs/{SPEC['run_id']}/kill", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["found"] is False
