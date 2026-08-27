"""API + callback tests for the M1 run surface."""

from typing import Any
from unittest import mock

import pytest
from rest_framework.test import APIClient

from fleet_core.models import Workspace, default_workspace
from fleet_runs import dispatch as dispatch_mod
from fleet_runs.blueprint_m1 import M1_BLUEPRINT_IR
from fleet_runs.models import LedgerEntry, Run, RunState, RunStep


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def workspace(db: None) -> Workspace:
    # The M1 API scopes everything to the default workspace (real tenancy: M7).
    return default_workspace()


def make_run(workspace: Workspace) -> tuple[Run, str]:
    return dispatch_mod.create_run(workspace, M1_BLUEPRINT_IR, input_text="hello")


STEP: dict[str, Any] = {
    "step_index": 0,
    "kind": "model_call",
    "provider": "anthropic",
    "request_payload": {"model": "claude-opus-5", "messages": []},
    "response_payload": {"content": [{"type": "text", "text": "hi"}]},
    "tokens_in": 10,
    "tokens_out": 5,
    "cost_microusd": 175,
    "price_table_version": "offsidefleet.prices.v1",
    "duration_ms": 900,
    "clock_reads": ["2026-08-26T00:00:00Z"],
}


@pytest.mark.django_db
class TestCreateRun:
    def test_create_enqueues_and_ledgers(self, client: APIClient) -> None:
        with mock.patch.object(dispatch_mod, "enqueue") as enq:
            resp = client.post("/api/v1/runs", {"input": "do a thing"}, format="json")
        assert resp.status_code == 202
        assert resp.data["state"] == RunState.QUEUED
        enq.assert_called_once()
        run = Run.objects.get(pk=resp.data["id"])
        assert run.blueprint_ir["identity"]["name"] == "Pathfinder"
        assert LedgerEntry.objects.filter(run=run, action="run.created").exists()

    def test_clear_token_not_persisted(self, workspace: Workspace) -> None:
        run, token = make_run(workspace)
        assert token not in run.callback_token_hash
        assert run.check_callback_token(token)


@pytest.mark.django_db
class TestCallbacks:
    def test_append_steps_requires_token(self, client: APIClient, workspace: Workspace) -> None:
        run, _ = make_run(workspace)
        resp = client.post(
            f"/internal/callbacks/runs/{run.id}/steps", {"steps": [STEP]}, format="json"
        )
        assert resp.status_code == 401

        resp = client.post(
            f"/internal/callbacks/runs/{run.id}/steps",
            {"steps": [STEP]},
            format="json",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
        assert resp.status_code == 401
        assert RunStep.objects.count() == 0

    def test_append_steps_and_rollups(self, client: APIClient, workspace: Workspace) -> None:
        run, token = make_run(workspace)
        steps = [STEP, {**STEP, "step_index": 1, "kind": "system", "cost_microusd": 0}]
        resp = client.post(
            f"/internal/callbacks/runs/{run.id}/steps",
            {"steps": steps},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 201
        run.refresh_from_db()
        assert run.steps.count() == 2
        assert run.cost_microusd_total == 175
        assert run.tokens_in_total == 20

    def test_state_transitions_via_callback(self, client: APIClient, workspace: Workspace) -> None:
        run, token = make_run(workspace)
        resp = client.post(
            f"/internal/callbacks/runs/{run.id}/state",
            {"state": "running"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        resp = client.post(
            f"/internal/callbacks/runs/{run.id}/state",
            {"state": "succeeded"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        run.refresh_from_db()
        assert run.state == RunState.SUCCEEDED
        assert LedgerEntry.objects.filter(run=run, action="run.succeeded").exists()

    def test_late_report_after_kill_is_noop(self, client: APIClient, workspace: Workspace) -> None:
        run, token = make_run(workspace)
        run.transition(RunState.KILLED)
        resp = client.post(
            f"/internal/callbacks/runs/{run.id}/state",
            {"state": "failed"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        run.refresh_from_db()
        assert run.state == RunState.KILLED


@pytest.mark.django_db
class TestKill:
    def test_kill_queued_run(self, client: APIClient, workspace: Workspace) -> None:
        run, _ = make_run(workspace)
        resp = client.post(f"/api/v1/runs/{run.id}/kill")
        assert resp.status_code == 200
        run.refresh_from_db()
        assert run.state == RunState.KILLED
        assert LedgerEntry.objects.filter(run=run, action="run.killed").exists()

    def test_kill_running_run_calls_gateway(self, client: APIClient, workspace: Workspace) -> None:
        run, _ = make_run(workspace)
        run.transition(RunState.RUNNING)
        with mock.patch(
            "fleet_runs.views.gateway_client.kill_run", return_value={"killed_in_ms": 412}
        ) as kill:
            resp = client.post(f"/api/v1/runs/{run.id}/kill")
        kill.assert_called_once_with(str(run.id))
        assert resp.status_code == 200
        assert resp.data["killed_in_ms"] == 412
        run.refresh_from_db()
        assert run.state == RunState.KILLED

    def test_kill_terminal_run_is_idempotent(self, client: APIClient, workspace: Workspace) -> None:
        run, _ = make_run(workspace)
        run.transition(RunState.RUNNING)
        run.transition(RunState.SUCCEEDED)
        resp = client.post(f"/api/v1/runs/{run.id}/kill")
        assert resp.status_code == 200
        assert resp.data["state"] == RunState.SUCCEEDED


@pytest.mark.django_db
class TestTraceEndpoint:
    def test_payloads_on_demand(self, client: APIClient, workspace: Workspace) -> None:
        run, token = make_run(workspace)
        client.post(
            f"/internal/callbacks/runs/{run.id}/steps",
            {"steps": [STEP]},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        lite = client.get(f"/api/v1/runs/{run.id}/steps")
        assert lite.status_code == 200
        assert "request_payload" not in lite.data["steps"][0]

        full = client.get(f"/api/v1/runs/{run.id}/steps?include=payloads")
        assert full.data["steps"][0]["request_payload"]["model"] == "claude-opus-5"
