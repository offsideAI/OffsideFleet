"""The thin agent loop v0 (M1.S4, ADR-001).

Owns the seams that ARE the product: replay-grade trace capture (verbatim
request/response, seeds, clock reads), cost metering per step, and — from
M4/M5 — budget checks and tool brokering between steps.

M1 shape: system step -> one Anthropic Messages call (via the model
reverse-proxy; no API key in this container) -> completion step.
"""

import json
import logging
import os
import random
import sys
import time
from datetime import UTC, datetime
from typing import Any

import anthropic

from .callback import CallbackClient
from .costs import cost_microusd, price_table_version

logger = logging.getLogger("agent.loop")

MAX_ITERATIONS = 20  # loop guard; budget enforcement proper lands in M5


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class TraceRecorder:
    """Buffers replay-grade steps and flushes them to the control plane."""

    def __init__(self, callback: CallbackClient):
        self._callback = callback
        self._next_index = 0

    def record(
        self,
        kind: str,
        *,
        provider: str = "",
        request_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
        rng_seed: int | None = None,
        clock_reads: list[str] | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: int = 0,
        duration_ms: int = 0,
    ) -> None:
        step = {
            "step_index": self._next_index,
            "kind": kind,
            "provider": provider,
            "request_payload": request_payload,
            "response_payload": response_payload,
            "rng_seed": rng_seed,
            "clock_reads": clock_reads or [],
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_microusd": cost,
            "price_table_version": price_table_version(),
            "duration_ms": duration_ms,
        }
        self._next_index += 1
        self._callback.append_steps([step])


def build_messages(ir: dict[str, Any], input_text: str) -> list[dict[str, Any]]:
    user_text = input_text or "Introduce yourself in one sentence."
    return [{"role": "user", "content": user_text}]


def model_client() -> anthropic.Anthropic:
    # base_url -> model reverse-proxy; it injects the real key at egress.
    # The SDK requires *an* api_key value; this placeholder is not a secret.
    return anthropic.Anthropic(
        base_url=os.environ.get("FLEET_MODEL_PROXY_URL", "http://fleet-egress-proxy:8889"),
        api_key="brokered-by-egress-proxy",
        max_retries=2,
    )


def execute(spec: dict[str, Any]) -> None:
    run_id = spec["run_id"]
    ir = spec["blueprint_ir"]
    callback = CallbackClient(spec["control_plane_url"], run_id, spec["callback_token"])
    trace = TraceRecorder(callback)

    callback.set_state("running")

    rng_seed = random.SystemRandom().getrandbits(63)
    rng = random.Random(rng_seed)  # noqa: S311 — replay-deterministic RNG for agent use
    _ = rng  # unused in M1; tools/memory will draw from it

    trace.record(
        "system",
        request_payload={"blueprint_ir": ir, "input_text": spec.get("input_text", "")},
        rng_seed=rng_seed,
        clock_reads=[_now_iso()],
    )

    model_id = ir["model"]["id"]
    messages = build_messages(ir, spec.get("input_text", ""))
    request_body: dict[str, Any] = {
        "model": model_id,
        "max_tokens": ir["model"].get("maxTokens", 1024),
        "system": ir.get("systemPrompt", ""),
        "messages": messages,
    }

    client = model_client()
    t0 = time.monotonic()
    clock_start = _now_iso()
    try:
        response = client.messages.create(**request_body)
    except anthropic.APIError as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        trace.record(
            "model_call",
            provider="anthropic",
            request_payload=request_body,
            response_payload={"error": str(exc)},
            clock_reads=[clock_start, _now_iso()],
            duration_ms=duration_ms,
        )
        callback.set_state("failed", error={"kind": "model_call", "message": str(exc)})
        return

    duration_ms = int((time.monotonic() - t0) * 1000)
    response_verbatim = json.loads(response.to_json())
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    step_cost = cost_microusd(model_id, tokens_in, tokens_out)

    trace.record(
        "model_call",
        provider="anthropic",
        request_payload=request_body,
        response_payload=response_verbatim,
        clock_reads=[clock_start, _now_iso()],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=step_cost,
        duration_ms=duration_ms,
    )

    final_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    trace.record(
        "system",
        response_payload={"final_output": final_text, "stop_reason": response.stop_reason},
        clock_reads=[_now_iso()],
    )
    callback.set_state("succeeded")
    callback.close()
    logger.info("run %s completed", run_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    spec = json.loads(os.environ["RUN_SPEC_JSON"])
    try:
        execute(spec)
    except Exception as exc:  # last-resort: report failure before dying
        logger.exception("run %s crashed", spec.get("run_id"))
        try:
            cb = CallbackClient(
                spec["control_plane_url"], spec["run_id"], spec["callback_token"]
            )
            cb.set_state("failed", error={"kind": "crash", "message": str(exc)})
        except Exception:
            logger.exception("could not report crash")
        sys.exit(1)


if __name__ == "__main__":
    main()
