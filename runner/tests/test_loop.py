"""Agent-loop trace capture with the SDK and callbacks mocked: verifies the
replay-grade shape of what the loop records (M1.S4 acceptance)."""

import json
import os
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from agent import costs, loop

REPO_PRICES = Path(__file__).parents[2] / "packages" / "ir" / "prices.json"


@pytest.fixture(autouse=True)
def use_repo_prices() -> None:
    os.environ["FLEET_PRICES_PATH"] = str(REPO_PRICES)
    costs.price_table.cache_clear()


class FakeUsage:
    input_tokens = 812
    output_tokens = 96


class FakeBlock:
    type = "text"
    text = "Hello from Pathfinder."


class FakeResponse:
    usage = FakeUsage()
    content = [FakeBlock()]
    stop_reason = "end_turn"

    def to_json(self) -> str:
        return json.dumps(
            {
                "content": [{"type": "text", "text": FakeBlock.text}],
                "usage": {"input_tokens": 812, "output_tokens": 96},
                "stop_reason": "end_turn",
            }
        )


SPEC: dict[str, Any] = {
    "run_id": "run-1",
    "blueprint_ir": {
        "identity": {"name": "Pathfinder"},
        "model": {"provider": "anthropic", "id": "claude-opus-5", "maxTokens": 1024},
        "systemPrompt": "You are Pathfinder.",
    },
    "input_text": "Say hi",
    "callback_token": "tok",
    "control_plane_url": "http://cp.test",
}


def run_loop_with_fakes() -> tuple[list[dict[str, Any]], list[tuple[str, Any]]]:
    steps: list[dict[str, Any]] = []
    states: list[tuple[str, Any]] = []

    fake_cb = mock.Mock()
    fake_cb.append_steps.side_effect = lambda s: steps.extend(s)
    fake_cb.set_state.side_effect = lambda state, error=None: states.append((state, error))

    fake_client = mock.Mock()
    fake_client.messages.create.return_value = FakeResponse()

    with (
        mock.patch("agent.loop.CallbackClient", return_value=fake_cb),
        mock.patch("agent.loop.model_client", return_value=fake_client),
    ):
        loop.execute(SPEC)
    return steps, states


def test_trace_is_replay_grade() -> None:
    steps, states = run_loop_with_fakes()

    assert [s["kind"] for s in steps] == ["system", "model_call", "system"]
    assert [s["step_index"] for s in steps] == [0, 1, 2]

    system_step = steps[0]
    assert system_step["request_payload"]["blueprint_ir"]["identity"]["name"] == "Pathfinder"
    assert isinstance(system_step["rng_seed"], int)
    assert system_step["clock_reads"], "clock reads must be recorded"

    model_step = steps[1]
    assert model_step["provider"] == "anthropic"
    # Verbatim request AND response payloads (replay inputs).
    assert model_step["request_payload"]["model"] == "claude-opus-5"
    assert model_step["request_payload"]["messages"] == [{"role": "user", "content": "Say hi"}]
    assert model_step["response_payload"]["usage"]["input_tokens"] == 812
    assert len(model_step["clock_reads"]) == 2
    # Cost: 812 * 5 + 96 * 25 microUSD.
    assert model_step["cost_microusd"] == 812 * 5 + 96 * 25
    assert model_step["price_table_version"] == "offsidefleet.prices.v1"

    assert states == [("running", None), ("succeeded", None)]


def test_model_error_reports_failed_state() -> None:
    import anthropic

    fake_cb = mock.Mock()
    states: list[tuple[str, Any]] = []
    fake_cb.set_state.side_effect = lambda state, error=None: states.append((state, error))

    fake_client = mock.Mock()
    fake_client.messages.create.side_effect = anthropic.APIConnectionError(
        request=mock.Mock()
    )

    with (
        mock.patch("agent.loop.CallbackClient", return_value=fake_cb),
        mock.patch("agent.loop.model_client", return_value=fake_client),
    ):
        loop.execute(SPEC)

    assert states[0][0] == "running"
    assert states[1][0] == "failed"
    assert states[1][1]["kind"] == "model_call"
