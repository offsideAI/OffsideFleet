"""Exhaustive state-machine tests: every (state, state) pair is either legal
and succeeds, or illegal and raises — no pair is untested (M1.S2 acceptance)."""

import pytest

from fleet_core.models import Workspace
from fleet_runs.models import LEGAL_TRANSITIONS, IllegalTransition, Run, RunState


def make_run(workspace: Workspace, state: str) -> Run:
    run = Run.objects.create(
        workspace=workspace,
        blueprint_ir={},
        trigger_kind="manual",
        state=state,
        callback_token_hash=Run.hash_token("t"),
    )
    return run


ALL_STATES = list(RunState.values)


@pytest.mark.django_db
@pytest.mark.parametrize("current", ALL_STATES)
@pytest.mark.parametrize("target", ALL_STATES)
def test_every_transition_pair(workspace: Workspace, current: str, target: str) -> None:
    run = make_run(workspace, current)
    legal = target in LEGAL_TRANSITIONS[current]
    if legal:
        run.transition(target)
        run.refresh_from_db()
        assert run.state == target
    else:
        with pytest.raises(IllegalTransition):
            run.transition(target)
        run.refresh_from_db()
        assert run.state == current


@pytest.mark.django_db
def test_terminal_states_have_no_exits() -> None:
    for state in (
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.KILLED,
        RunState.BUDGET_STOPPED,
    ):
        assert LEGAL_TRANSITIONS[state] == frozenset()


@pytest.mark.django_db
def test_transition_sets_timestamps(workspace: Workspace) -> None:
    run = make_run(workspace, RunState.QUEUED)
    assert run.started_at is None and run.ended_at is None
    run.transition(RunState.RUNNING)
    assert run.started_at is not None and run.ended_at is None
    run.transition(RunState.SUCCEEDED)
    assert run.ended_at is not None


@pytest.mark.django_db
def test_concurrent_transition_loses_cleanly(workspace: Workspace) -> None:
    """Two in-memory copies of one queued run: the second transition attempt
    must observe the DB state and raise, not clobber."""
    run_a = make_run(workspace, RunState.QUEUED)
    run_b = Run.objects.get(pk=run_a.pk)
    run_a.transition(RunState.KILLED)
    with pytest.raises(IllegalTransition):
        run_b.transition(RunState.RUNNING)


def test_callback_token_roundtrip() -> None:
    token = Run.mint_callback_token()
    assert len(token) > 30
    hashed = Run.hash_token(token)
    run = Run(callback_token_hash=hashed)
    assert run.check_callback_token(token)
    assert not run.check_callback_token(token + "x")
