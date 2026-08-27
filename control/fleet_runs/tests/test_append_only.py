"""DB-level append-only enforcement (⛔ tables). Postgres-only; CI runs these."""

import pytest
from django.db import transaction
from django.db.utils import InternalError

from conftest import requires_postgres
from fleet_core.models import Workspace
from fleet_runs.models import LedgerEntry, Run, RunStep, ledger


@requires_postgres
@pytest.mark.django_db
def test_runstep_rows_reject_update_and_delete(workspace: Workspace) -> None:
    run = Run.objects.create(
        workspace=workspace,
        blueprint_ir={},
        trigger_kind="manual",
        callback_token_hash=Run.hash_token("t"),
    )
    step = RunStep.objects.create(
        workspace=workspace, run=run, step_index=0, kind="system", clock_reads=[]
    )
    with pytest.raises(InternalError), transaction.atomic():
        RunStep.objects.filter(pk=step.pk).update(kind="model_call")
    with pytest.raises(InternalError), transaction.atomic():
        step.delete()


@requires_postgres
@pytest.mark.django_db
def test_ledger_rows_reject_update_and_delete(workspace: Workspace) -> None:
    entry = ledger(workspace.id, "test.action")
    with pytest.raises(InternalError), transaction.atomic():
        LedgerEntry.objects.filter(pk=entry.pk).update(action="tampered")
    with pytest.raises(InternalError), transaction.atomic():
        entry.delete()
