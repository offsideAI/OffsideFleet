"""Run creation and dispatch to the runner-gateway."""

import logging
from typing import Any

from django.conf import settings

from fleet_core.models import Workspace

from . import gateway_client
from .models import Run, RunState, TriggerKind, ledger

logger = logging.getLogger(__name__)


def create_run(
    workspace: Workspace,
    blueprint_ir: dict[str, Any],
    *,
    trigger_kind: str = TriggerKind.MANUAL,
    input_text: str = "",
) -> tuple[Run, str]:
    """Create a queued Run and mint its callback token.

    Returns (run, callback_token). The clear token exists only in memory here
    and in the runner container's env — never persisted (only its hash is).
    """
    token = Run.mint_callback_token()
    run = Run.objects.create(
        workspace=workspace,
        blueprint_ir=blueprint_ir,
        trigger_kind=trigger_kind,
        input_text=input_text,
        callback_token_hash=Run.hash_token(token),
    )
    ledger(workspace.id, "run.created", run=run, payload={"trigger_kind": trigger_kind})
    return run, token


def build_run_spec(run: Run, callback_token: str) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "blueprint_ir": run.blueprint_ir,
        "input_text": run.input_text,
        "callback_token": callback_token,
        "control_plane_url": None,  # gateway fills its own reachable URL
    }


def enqueue(run: Run, callback_token: str) -> None:
    """Enqueue dispatch via Procrastinate. The token rides in the job payload
    (job table is control-plane-internal), not in the Run row."""
    from offsidefleet.jobs import dispatch_run

    dispatch_run.defer(run_id=str(run.id), callback_token=callback_token)


def dispatch(run_id: str, callback_token: str) -> None:
    """Procrastinate task body: hand the run to the gateway."""
    run = Run.objects.get(pk=run_id)
    if run.state != RunState.QUEUED:
        logger.info("run %s no longer queued (state=%s); skipping dispatch", run_id, run.state)
        return
    spec = build_run_spec(run, callback_token)
    try:
        gateway_client.start_run(str(run.id), spec)
    except gateway_client.GatewayError as exc:
        run.transition(RunState.FAILED, error={"kind": "dispatch", "message": str(exc)})
        ledger(run.workspace_id, "run.dispatch_failed", run=run, payload={"error": str(exc)})
        raise
    logger.info("run %s dispatched to gateway %s", run_id, settings.RUNNER_GATEWAY_URL)
