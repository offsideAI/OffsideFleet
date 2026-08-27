# TESTING.md — OffsideFleet

Test strategy for a product whose pitch is "production discipline." Two suites are **non-negotiable and block merge from the milestone they exist**: tenant-isolation and sandbox-escape. Tests ship in the same milestone as their code (engineering standard) — a story's acceptance criteria in ROADMAP.md are its test list.

## Stack & layout

- **Python:** pytest + pytest-django + pytest-asyncio; factory-boy fixtures; mypy strict as a CI gate (type errors are test failures).
- **TypeScript:** vitest (unit: IR round-trips, SDK, stores), Playwright (console flows), TS strict as a CI gate.
- **Shared contract tests:** the IR JSON Schema and trace schema have one fixture-vector suite executed by BOTH the Python and TS validators — the two stacks can't drift silently.
- **CI (GitHub Actions):** lint → typecheck → unit → integration (Postgres + fake runner) → isolation suite → sandbox suite (on runner-image changes + nightly) → Playwright smoke. All required.

## Unit vs integration split

**Unit (fast, hermetic, run on every save):** IR validation & round-trips; run state machine (property tests on transitions); budget math (pre-call estimator, price tables, ≤1-step-overrun property test across randomized price/step scenarios); trace redaction (structural — a secret placed anywhere in a tool response never survives serialization); cron misfire/skip logic; ledger hash chain; cost = tokens × versioned price table exactness.

**Integration (real Postgres, real Procrastinate, containerized runner or fake-gateway):** run lifecycle end-to-end (create → dispatch → steps → terminal); chat message → run → SSE stream → persisted trace equivalence (streamed text ≡ stored trace text); scheduler fires + skip-if-running under overlap; kill-timing harness (20-trial p95 < 2s — a CI metric, not a one-off); budget concurrency (two runs, one budget, never jointly exceed); Stripe test-mode subscribe/upgrade/cancel + usage reconciliation within 1%; memory recall fixture (aged conversation → correct retrieval, wrong-workspace retrieval impossible).

## Tenant-isolation suite (non-negotiable; blocks merge from M7; grows from M1)

Adversarial by construction, not a checklist:
1. **Endpoint auto-discovery:** the suite enumerates every registered route; any endpoint without isolation coverage FAILS the suite (coverage can't silently lag the surface).
2. **Attacks per endpoint:** (a) forged/foreign `X-Workspace-Id` with a valid session → expect 403; (b) foreign object IDs under the attacker's own workspace header → expect 404; (c) unauthenticated → expect 401; (d) write attempts against foreign objects → expect 403/404 AND no side effects (DB asserted).
3. **Canary:** a deliberately vulnerable test-only endpoint is periodically introduced in CI to prove the suite still catches real holes (a suite that can't fail is decoration).
4. **Data-layer checks:** unscoped-queryset lint; memory_chunks retrieval cross-checked (agent A can never retrieve agent B's or workspace B's chunks); ledger export scoped.
5. **Org extension (M12):** same suite semantics extended to org-role boundaries.

## Sandbox-escape suite (non-negotiable; runs in CI from M1 on runner-image changes + nightly)

Runs against a real container on a CI runner host:
- **Egress:** allowlisted host reachable; non-allowlisted host, private IP ranges, and cloud metadata endpoints (169.254.169.254) all blocked — asserted from inside the container.
- **Privilege:** process is non-root; rootfs read-only (write attempt fails); capability probe empty; `no-new-privileges` effective (setuid binary test).
- **Resources:** memory cap kills a balloon; pids cap stops a fork bomb; 15-min wall-clock kill fires (compressed-clock test hook).
- **Credentials:** container env, mounted fs, and process tree contain no platform secrets and no customer secret material (grep harness with planted canary secrets).
- **Kill:** SIGKILL path from gateway terminates within 2s under load (container busy-looping).
- **Escalation (M15 gate):** before any third-party/arbitrary-code execution, this suite must be re-passed under the gVisor evaluation (ADR-002 tripwire).

## Replay-based regression tests (from M6)

- **Replayability validator:** every run produced by CI tests passes the replay-completeness check (fields, verbatim payloads, seeds, clock reads).
- **Determinism:** replay of a recorded run is hash-identical on normalized traces, executed with networking disabled in the harness (proves no hidden egress).
- **Divergence quality:** corrupted-recording fixtures produce precise first-divergence reports (never crashes).
- **Behavioral regression:** pinned dogfood runs re-executed against NEW blueprint versions with recorded tool/model responses; diffs fail CI with readable output. This suite is also the internal proof of the customer-facing replay feature.

## Load & capacity assumptions (MVP honesty)

Design targets, asserted by a small locust/k6 job before M7 ship — not aspirations:
- **Scale:** ≤20 workspaces, ≤200 agents, ≤2,000 runs/day, **≤25 concurrent runs** (one runner droplet: 8 vCPU / 16GB ≈ 25–30 concurrent hardened containers at 256–512MB each; queueing beyond that is correct behavior, not failure).
- **Latencies:** runner start p95 < 5s (PRD); chat first token p50 < 2.5s; SSE fan-out tested to 50 concurrent streams; kill p95 < 2s always.
- **DB:** run_steps is the growth table (~50–200KB/run with verbatim payloads → low GB/month at MVP scale — fine); payload-on-demand API keeps trace lists cheap; archival/compression is a Phase B concern, noted not built.
- **Failure drills (pre-ship, manual but scripted):** runner droplet reboot mid-run → runs fail cleanly, ledgered, notified; Postgres failover → control plane recovers, no ⛔-table corruption; Stripe webhook outage → reconciler catches up, usage within 1%.

## What we deliberately do NOT test in MVP

Cross-browser matrices beyond Chromium+WebKit smoke; localization; accessibility beyond keyboard-flow assertions in Playwright (full audit at GA); chaos/soak beyond the drills above; multi-region anything. Listed so their absence is a decision, not an oversight.
