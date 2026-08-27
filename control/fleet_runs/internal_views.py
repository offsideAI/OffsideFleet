"""Callbacks from the runner (agent loop) into the control plane.

Auth: run-scoped bearer token minted at run creation; only its sha256 is
stored. A token authorizes callbacks for exactly one run.
"""

import logging
from typing import Any

from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Run, RunState, RunStep, ledger

logger = logging.getLogger(__name__)


def _authed_run(request: Request, run_id: str) -> Run | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header.removeprefix("Bearer ")
    run = get_object_or_404(Run, pk=run_id)
    if not run.check_callback_token(token):
        return None
    return run


@api_view(["POST"])
def append_steps(request: Request, run_id: str) -> Response:
    run = _authed_run(request, run_id)
    if run is None:
        return Response({"detail": "invalid run token"}, status=401)

    body: Any = request.data
    if not isinstance(body, dict):
        return Response({"detail": "body must be an object"}, status=400)
    steps_in = body.get("steps", [])
    if not isinstance(steps_in, list) or not steps_in:
        return Response({"detail": "steps must be a non-empty list"}, status=400)

    created = 0
    cost = tokens_in = tokens_out = 0
    with transaction.atomic():
        for s in steps_in:
            RunStep.objects.create(
                workspace_id=run.workspace_id,
                run=run,
                step_index=int(s["step_index"]),
                kind=str(s["kind"]),
                provider=str(s.get("provider", "")),
                request_payload=s.get("request_payload"),
                response_payload=s.get("response_payload"),
                rng_seed=s.get("rng_seed"),
                clock_reads=s.get("clock_reads", []),
                tokens_in=int(s.get("tokens_in", 0)),
                tokens_out=int(s.get("tokens_out", 0)),
                cost_microusd=int(s.get("cost_microusd", 0)),
                price_table_version=str(s.get("price_table_version", "")),
                duration_ms=int(s.get("duration_ms", 0)),
            )
            created += 1
            cost += int(s.get("cost_microusd", 0))
            tokens_in += int(s.get("tokens_in", 0))
            tokens_out += int(s.get("tokens_out", 0))
        Run.objects.filter(pk=run.pk).update(
            cost_microusd_total=F("cost_microusd_total") + cost,
            tokens_in_total=F("tokens_in_total") + tokens_in,
            tokens_out_total=F("tokens_out_total") + tokens_out,
        )
    return Response({"created": created}, status=201)


@api_view(["POST"])
def set_state(request: Request, run_id: str) -> Response:
    run = _authed_run(request, run_id)
    if run is None:
        return Response({"detail": "invalid run token"}, status=401)

    body: Any = request.data
    if not isinstance(body, dict):
        return Response({"detail": "body must be an object"}, status=400)
    new_state = str(body.get("state", ""))
    error = body.get("error")
    if new_state not in RunState.values:
        return Response({"detail": f"unknown state {new_state!r}"}, status=400)

    if run.is_terminal:
        # Kill (or another terminal transition) already landed; the runner's
        # late report is informational only.
        return Response({"state": run.state, "note": "already terminal"})

    from .models import IllegalTransition

    try:
        run.transition(new_state, error=error)
    except IllegalTransition as exc:
        return Response({"detail": str(exc)}, status=409)

    if run.is_terminal:
        ledger(
            run.workspace_id,
            f"run.{new_state}",
            actor_kind="agent",
            run=run,
            payload={"error": error} if error else {},
        )
    return Response({"state": run.state})
