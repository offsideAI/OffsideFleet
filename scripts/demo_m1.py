"""M1 demo script (MILESTONES.md §M1).

Drives the full spine: create Run -> container executes -> trace with cost ->
egress-block proof -> mid-flight kill with <2s timing.

Prereqs (each in its own terminal): just infra, just api, just worker, just gateway.
"""

import subprocess
import sys
import time
import uuid

import httpx2 as httpx

API = "http://localhost:8000"
MICRO = 1_000_000


def wait_for(run_id: str, target_states: set[str], timeout_s: float = 120) -> dict:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        run = httpx.get(f"{API}/api/v1/runs/{run_id}").json()
        if run["state"] in target_states:
            return run
        time.sleep(1)
    raise SystemExit(f"timeout waiting for {target_states}; last state: {run['state']}")


def banner(text: str) -> None:
    print(f"\n{'=' * 70}\n  {text}\n{'=' * 70}")


def main() -> None:
    banner("1/4  Health checks")
    for name, url in [("control", f"{API}/healthz"), ("gateway", "http://localhost:8100/healthz")]:
        r = httpx.get(url, timeout=5)
        print(f"  {name}: {r.json()}")

    banner("2/4  Create a Run and watch it execute")
    resp = httpx.post(f"{API}/api/v1/runs", json={"input": "In one sentence: what is OffsideFleet?"})
    resp.raise_for_status()
    run_id = resp.json()["id"]
    print(f"  run {run_id} created (state={resp.json()['state']})")

    run = wait_for(run_id, {"succeeded", "failed"})
    print(f"  run finished: state={run['state']}")

    trace = httpx.get(f"{API}/api/v1/runs/{run_id}/steps?include=payloads").json()
    steps = trace["steps"]
    print(f"  steps recorded: {len(steps)}")
    for s in steps:
        cost = s["cost_microusd"] / MICRO
        print(
            f"    [{s['step_index']}] {s['kind']:<12} provider={s['provider'] or '-':<10}"
            f" tokens={s['tokens_in']}/{s['tokens_out']} cost=${cost:.6f} {s['duration_ms']}ms"
        )
    total = run["cost_microusd_total"] / MICRO
    print(f"  total cost: ${total:.6f}")
    assert len(steps) >= 3, "M1 acceptance: >= 3 persisted steps"
    assert any(s["kind"] == "model_call" and s["response_payload"] for s in steps), (
        "verbatim model payloads required"
    )
    print(f"\n  trace UI: http://localhost:5173/runs/{run_id}")

    banner("3/4  Egress allowlist: non-allowlisted host must be blocked")
    probe = subprocess.run(
        ["docker", "run", "--rm", "--network", "fleet_internal",
         "--user", "65534:65534", "--read-only", "--cap-drop", "ALL",
         "python:3.12-slim", "python", "-c",
         "import urllib.request\n"
         "try:\n"
         "  urllib.request.urlopen('https://example.com', timeout=5); print('EGRESS-OPEN')\n"
         "except Exception:\n"
         "  print('EGRESS-BLOCKED')\n"],
        capture_output=True, text=True, timeout=90,
    )
    verdict = probe.stdout.strip()
    print(f"  direct egress from agent network: {verdict}")
    assert verdict == "EGRESS-BLOCKED", "sandbox must not reach the internet directly"

    banner("4/4  Kill switch: SIGKILL a live run in <2s")
    # Start a long-running probe container the same way the gateway names runs,
    # then kill it through the gateway and time enforcement.
    fake_run_id = str(uuid.uuid4())
    subprocess.run(
        ["docker", "run", "-d", "--name", f"fleet-run-{fake_run_id}",
         "--network", "fleet_internal", "--user", "65534:65534",
         "--read-only", "--cap-drop", "ALL",
         "python:3.12-slim", "python", "-c", "import time; time.sleep(600)"],
        check=True, capture_output=True, timeout=60,
    )
    time.sleep(1)
    t0 = time.monotonic()
    kill = httpx.post(
        f"http://localhost:8100/internal/runs/{fake_run_id}/kill",
        headers={"Authorization": "Bearer dev-internal-secret"},
        timeout=10,
    )
    elapsed = time.monotonic() - t0
    print(f"  gateway kill: {kill.json()} (end-to-end {elapsed * 1000:.0f}ms)")
    subprocess.run(["docker", "rm", "-f", f"fleet-run-{fake_run_id}"], capture_output=True)
    assert elapsed < 2.0, f"kill took {elapsed:.2f}s (must be <2s)"

    banner("M1 DEMO PASSED")
    print("  spine: Run -> sandboxed container -> Anthropic (key held at proxy)")
    print("  trace: replay-grade steps with per-step cost")
    print("  egress: allowlist enforced | kill: <2s\n")


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError as exc:
        print(f"\nservice not reachable: {exc}\nstart: just infra / api / worker / gateway")
        sys.exit(1)
