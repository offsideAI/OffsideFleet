"""Console-facing run endpoints (M1 subset of API_SURFACE.md).

No auth in M1 (local dev only); real auth + tenancy middleware land in M7,
but every query is already workspace-scoped by construction.
"""

import logging

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from fleet_core.models import default_workspace

from . import dispatch as dispatch_mod
from . import gateway_client
from .blueprint_m1 import M1_BLUEPRINT_IR
from .models import Run, RunState, TriggerKind, ledger
from .serializers import (
    CreateRunRequestSerializer,
    RunSerializer,
    RunStepSerializer,
    RunStepWithPayloadsSerializer,
)

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
def runs(request: Request) -> Response:
    ws = default_workspace()
    if request.method == "POST":
        body = CreateRunRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        run, token = dispatch_mod.create_run(
            ws,
            M1_BLUEPRINT_IR,
            trigger_kind=TriggerKind.MANUAL,
            input_text=body.validated_data["input"],
        )
        dispatch_mod.enqueue(run, token)
        return Response(RunSerializer(run).data, status=202)

    qs = Run.objects.filter(workspace=ws).order_by("-created_at")[:50]
    return Response({"runs": RunSerializer(qs, many=True).data})


@api_view(["GET"])
def run_detail(request: Request, run_id: str) -> Response:
    ws = default_workspace()
    run = get_object_or_404(Run, pk=run_id, workspace=ws)
    return Response(RunSerializer(run).data)


@api_view(["GET"])
def run_steps(request: Request, run_id: str) -> Response:
    ws = default_workspace()
    run = get_object_or_404(Run, pk=run_id, workspace=ws)
    include_payloads = request.query_params.get("include") == "payloads"
    serializer_cls = RunStepWithPayloadsSerializer if include_payloads else RunStepSerializer
    steps = run.steps.all()
    return Response(
        {"run": RunSerializer(run).data, "steps": serializer_cls(steps, many=True).data}
    )


@api_view(["POST"])
def run_kill(request: Request, run_id: str) -> Response:
    ws = default_workspace()
    run = get_object_or_404(Run, pk=run_id, workspace=ws)

    if run.is_terminal:
        # Idempotent: killing a finished run is a safe no-op.
        return Response({"state": run.state, "killed_in_ms": None})

    if run.state == RunState.QUEUED:
        run.transition(RunState.KILLED)
        ledger(ws.id, "run.killed", actor_kind="user", run=run, payload={"was": "queued"})
        return Response({"state": run.state, "killed_in_ms": 0})

    # Running: tell the gateway to SIGKILL the container.
    try:
        result = gateway_client.kill_run(str(run.id))
    except gateway_client.GatewayError as exc:
        logger.error("kill of run %s failed at gateway: %s", run_id, exc)
        return Response({"detail": f"gateway kill failed: {exc}"}, status=502)
    run.transition(RunState.KILLED)
    ledger(
        ws.id,
        "run.killed",
        actor_kind="user",
        run=run,
        payload={"killed_in_ms": result.get("killed_in_ms")},
    )
    return Response({"state": run.state, "killed_in_ms": result.get("killed_in_ms")})
