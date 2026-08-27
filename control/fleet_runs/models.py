"""Run, RunStep and LedgerEntry — the replay-grade execution spine (M1.S2).

RunStep and LedgerEntry are append-only (⛔ in DATA_MODEL.md): a Postgres
trigger rejects UPDATE/DELETE (migration 0002). Costs are stored in
micro-USD (1e-6 USD) — cents are too coarse for per-step LLM costs.
"""

import hashlib
import secrets
import uuid
from typing import Any

from django.db import models
from django.utils import timezone


class RunState(models.TextChoices):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    KILLED = "killed"
    BUDGET_STOPPED = "budget_stopped"


# Legal transitions of the run state machine. Terminal states have no exits.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    RunState.QUEUED: frozenset({RunState.RUNNING, RunState.KILLED, RunState.FAILED}),
    RunState.RUNNING: frozenset(
        {RunState.SUCCEEDED, RunState.FAILED, RunState.KILLED, RunState.BUDGET_STOPPED}
    ),
    RunState.SUCCEEDED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.KILLED: frozenset(),
    RunState.BUDGET_STOPPED: frozenset(),
}

TERMINAL_STATES = frozenset(
    {RunState.SUCCEEDED, RunState.FAILED, RunState.KILLED, RunState.BUDGET_STOPPED}
)


class IllegalTransition(Exception):
    def __init__(self, current: str, requested: str):
        self.current = current
        self.requested = requested
        super().__init__(f"illegal run state transition {current} -> {requested}")


class TriggerKind(models.TextChoices):
    CHAT = "chat"
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    AGENT = "agent"


class Run(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey("fleet_core.Workspace", on_delete=models.PROTECT)
    # Agent/BlueprintVersion FKs arrive in M2; M1 records the hard-coded blueprint inline.
    blueprint_ir = models.JSONField()
    trigger_kind = models.CharField(max_length=16, choices=TriggerKind.choices)
    input_text = models.TextField(blank=True)
    state = models.CharField(max_length=16, choices=RunState.choices, default=RunState.QUEUED)
    error = models.JSONField(null=True, blank=True)
    cost_microusd_total = models.BigIntegerField(default=0)
    tokens_in_total = models.BigIntegerField(default=0)
    tokens_out_total = models.BigIntegerField(default=0)
    # sha256 of the run-scoped callback token; the token itself only travels
    # to the runner container (never persisted in clear).
    callback_token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "-created_at"]),
            models.Index(fields=["workspace", "state"]),
        ]

    # --- state machine -----------------------------------------------------

    def transition(self, new_state: str, *, error: dict[str, Any] | None = None) -> None:
        """Move the run to `new_state`, enforcing legality atomically.

        Uses a guarded UPDATE so concurrent transitions can't race past the
        state machine; raises IllegalTransition if the move is not allowed.
        """
        allowed = LEGAL_TRANSITIONS[self.state]
        if new_state not in allowed:
            raise IllegalTransition(self.state, new_state)

        updates: dict[str, Any] = {"state": new_state}
        now = timezone.now()
        if new_state == RunState.RUNNING:
            updates["started_at"] = now
        if new_state in TERMINAL_STATES:
            updates["ended_at"] = now
        if error is not None:
            updates["error"] = error

        moved = type(self).objects.filter(pk=self.pk, state=self.state).update(**updates)
        if not moved:
            self.refresh_from_db(fields=["state"])
            raise IllegalTransition(self.state, new_state)
        for field, value in updates.items():
            setattr(self, field, value)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    # --- callback token ----------------------------------------------------

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def mint_callback_token(cls) -> str:
        return secrets.token_urlsafe(32)

    def check_callback_token(self, token: str) -> bool:
        return secrets.compare_digest(self.hash_token(token), self.callback_token_hash)


class StepKind(models.TextChoices):
    SYSTEM = "system"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    MEMORY_RETRIEVAL = "memory_retrieval"
    POLICY_CHECK = "policy_check"
    BUDGET_CHECK = "budget_check"


class RunStep(models.Model):
    """Append-only, replay-grade trace step (verbatim payloads, seeds, clocks)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey("fleet_core.Workspace", on_delete=models.PROTECT)
    run = models.ForeignKey(Run, on_delete=models.PROTECT, related_name="steps")
    step_index = models.IntegerField()
    kind = models.CharField(max_length=24, choices=StepKind.choices)
    provider = models.CharField(max_length=40, blank=True)
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    rng_seed = models.BigIntegerField(null=True, blank=True)
    clock_reads = models.JSONField(default=list, blank=True)
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    cost_microusd = models.BigIntegerField(default=0)
    price_table_version = models.CharField(max_length=40, blank=True)
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "step_index"], name="uniq_run_step_index"),
        ]
        indexes = [models.Index(fields=["workspace", "run"])]
        ordering = ["step_index"]


class LedgerEntry(models.Model):
    """Immutable audit log. Every privileged action lands here."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey("fleet_core.Workspace", on_delete=models.PROTECT)
    actor_kind = models.CharField(max_length=16)  # user | agent | system
    actor_id = models.CharField(max_length=64, blank=True)
    action = models.CharField(max_length=64)
    run = models.ForeignKey(Run, null=True, blank=True, on_delete=models.PROTECT)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "-created_at"]),
            models.Index(fields=["workspace", "run"]),
        ]


def ledger(
    workspace_id: uuid.UUID,
    action: str,
    *,
    actor_kind: str = "system",
    actor_id: str = "",
    run: Run | None = None,
    payload: dict[str, Any] | None = None,
) -> LedgerEntry:
    return LedgerEntry.objects.create(
        workspace_id=workspace_id,
        action=action,
        actor_kind=actor_kind,
        actor_id=actor_id,
        run=run,
        payload=payload or {},
    )
