# ROADMAP.md — OffsideFleet

**Status:** v1.0 — interview complete (2026-08-26). Every milestone = one epic (1:1). Every epic breaks down into **Stories**, each with a **Business case**, **Tasks**, and **Acceptance criteria**. Companion docs: `DECISIONS.md` (all interview decisions + dissents), `/plan/*` (Phase 2 review artifacts).

**Timeline assumption:** solo founder, ~4 focused days (fd)/week, starting ~Sept 2026. Dates follow arithmetically from estimates — consequences, not promises. Unacceptable dates are fixed by reordering milestones, not shrinking estimates.

**Locked decisions baked in** (see DECISIONS.md): Fleet is standalone · Fleet-native MCP tool broker · hero = roster of named agents + 1:1 chat + schedules · own thin agent loop · TS DSL → JSON IR blueprints · request-scoped 15-min runs · semantic memory in MVP · full deterministic replay in MVP (dissent on record) · hardened containers + egress allowlist · two-tier secrets (plaintext + tripwire, dissent on record) · selector-header + 3-layer tenancy · pre+post budget enforcement · App Platform + runner droplet · all three Stripe tiers at launch · 4-invariant pager.

---

# Phase A — MVP: "The Roster" (~65 fd ≈ 16 weeks → ships ~mid-late Jan 2027)

The MVP in one paragraph: a user signs into a workspace, creates several **named agents** — each with an identity (name, avatar, persona) and specific functionality (Anthropic model, system prompt, scoped MCP tools, budget) — talks to each agent in a dedicated 1:1 chat where the agent **remembers prior conversations**, and schedules any of them to run autonomously. Every interaction is a traced, per-step-costed, budgeted, **deterministically replayable**, killable Run. Stripe meters usage across three tiers from day one.

---

## M1 · Epic: Runtime Spine (walking skeleton) — 8 fd · confidence: medium

**Goal:** One hard-coded Blueprint executes one sandboxed Run on DigitalOcean with a visible step-level trace. Kill works. Everything after this milestone decorates this spine.

### M1.S1 — Control-plane skeleton, tooling, CI
**Business case:** Every later story lands on this foundation; CI + typing from commit one is the difference between a platform and a demo that rots.
**Tasks:**
- Monorepo layout (`control/` Django, `runner/` FastAPI, `console/` SvelteKit, `packages/ir` shared schema)
- Django 5 + DRF + Postgres 16 (DO managed, pgvector enabled) + Procrastinate wiring
- Ruff + mypy strict, eslint/prettier + TS strict, pre-commit hooks
- `justfile`: `just dev`, `just test`, `just lint`, `just demo-m1`
- GitHub Actions CI: lint + typecheck + tests block merge
**Acceptance criteria:**
- `just dev` boots the API locally against a local Postgres; `/healthz` returns 200 with git SHA
- CI is green and demonstrably blocks a PR containing a type error
- Conventional-commit lint active

### M1.S2 — Run/RunStep model with replay-grade trace schema
**Business case:** The Run trace is the hero surface AND (per the replay-in-MVP decision) the replay input; getting the schema replay-complete now means every run ever recorded is replayable later.
**Tasks:**
- `Run`, `RunStep`, `LedgerEntry` tables (see /plan/DATA_MODEL.md): state machine `queued → running → succeeded|failed|killed`
- RunStep captures verbatim model request/response, tool I/O, token counts, computed cost, monotonic step index, wall-clock timestamps, RNG seed
- Procrastinate job: dispatch queued Run to runner-gateway; retries with backoff; terminal-state idempotency
- Illegal state transitions rejected at the model layer
**Acceptance criteria:**
- `POST /api/runs` (internal/dev) creates a queued Run that transitions legally; property test rejects all illegal transitions
- A completed Run's steps contain verbatim payloads sufficient for replay (checklist test asserts presence of every replay-required field)
- LedgerEntry rows are append-only (DB-level `UPDATE`/`DELETE` revoked; test proves it)

### M1.S3 — Runner host: gateway + hardened per-run containers + egress allowlist
**Business case:** Sandboxed execution is the PRD's hard invariant and the credibility basis for "runs untrusted-ish workloads"; it must be architecture, not a hardening task later.
**Tasks:**
- Runner droplet provisioning script (idempotent; Docker, egress proxy, gateway service)
- FastAPI runner-gateway: `POST /runs/{id}/start`, `POST /runs/{id}/kill`, `GET /healthz`; shared-secret auth with control plane
- Container hardening profile: non-root UID, read-only rootfs + per-run tmpfs workdir, all capabilities dropped, `no-new-privileges`, seccomp default, CPU/mem/pids limits, 15-min wall-clock kill
- Egress: containers on an internal network; only route out is the proxy; allowlist = Anthropic API + control-plane callback (+ tool hosts later)
- No ambient credentials: container env contains only run-scoped callback token
**Acceptance criteria:**
- A run container can reach allowlisted hosts and provably cannot reach a non-allowlisted host (automated test asserts the blocked request fails)
- Container runs as non-root with read-only rootfs; resource limits enforced (test exhausts and observes the cap)
- `grep` of container env shows no platform credentials

### M1.S4 — Thin agent loop v0 with trace capture and cost meter
**Business case:** The loop's seams (trace, budget, kill, replay hooks) are the product; owning them from the first line avoids ripping out a framework later.
**Tasks:**
- Python loop: load hard-coded Blueprint IR → Anthropic Messages call → (tool steps arrive in M4) → final output; max-iterations guard
- Trace writer: verbatim request/response per step, streamed back to control plane via callback API
- Cost computation from token usage × model price table (single source of truth in `packages/ir`)
- Structured JSON logging throughout
**Acceptance criteria:**
- `just demo-m1` executes a Run that produces ≥3 persisted RunSteps (system setup, model call, completion) with verbatim payloads and non-zero dollar cost
- Price table is unit-tested against a fixtures file; cost on the step equals tokens × table price exactly

### M1.S5 — Kill switch v0 + minimal trace view
**Business case:** "Kill within 2s" is a headline promise and a pager invariant; wiring it before there's anything worth killing means it's never retrofitted. The trace view is the first pixel of the hero surface.
**Tasks:**
- Kill path: console/API → control plane → gateway → SIGKILL container → Run marked `killed` → LedgerEntry
- SvelteKit console skeleton (Signal Box tokens: Soot/Walnut/Verdigris/Rust/Parchment + Emerald; Fraunces/Hanken Grotesk/IBM Plex Mono; no purple/indigo/cyan) with a run trace page: step list, payload inspection, cost per step
**Acceptance criteria:**
- Killing a live run terminates the container in <2s (integration test measures it); the Run shows `killed` and a ledger entry exists
- Trace page renders a real run's steps with per-step cost in IBM Plex Mono; design tokens contain no forbidden hues

---

## M2 · Epic: Agent Roster & Identity — 6 fd · confidence: high

**Goal:** Many named agents per workspace, each an identity (name, avatar, persona) over an immutably versioned Blueprint.

### M2.S1 — Blueprint / BlueprintVersion / Agent schema with immutable versioning
**Business case:** Versioning + rollback is the "production discipline" differentiator vs no-code toys; immutability makes audit and replay claims true rather than aspirational.
**Tasks:**
- Tables: `Blueprint` (identity container), `BlueprintVersion` (immutable IR snapshot, monotonic version number, author, changelog note), `Agent` (deployed instance pinning a version)
- Any edit = new version row; DB-level immutability on version rows (no UPDATE); rollback = repoint agent to prior version
- IR stored as validated JSONB
**Acceptance criteria:**
- Editing a blueprint creates version N+1; attempting to mutate an existing version fails at the DB layer (test)
- Rollback repoints an Agent in one call and is ledgered
- Every Run records the exact BlueprintVersion it executed

### M2.S2 — JSON IR contract v1
**Business case:** The IR is the canonical contract that the visual builder, the future TS DSL (M10), and the Python runtime all speak — defining it precisely now is what makes "TypeScript-first" viable without a runtime rewrite.
**Tasks:**
- JSON Schema for Blueprint IR v1: identity (name, avatar, persona), model + params, system prompt, tool allowlist + per-tool config, memory config, triggers, budget, policy stubs
- Schema published in `packages/ir` (consumed by console TS and runner Python); versioned with a `schemaVersion` field and migration policy
- Validation errors mapped to actionable field-level messages
**Acceptance criteria:**
- Invalid IR is rejected with field-path errors; valid IR round-trips builder → IR → builder losslessly (property test)
- Python runner and TS console validate against the same schema fixture suite (shared test vectors pass in both)

### M2.S3 — Roster UI: create and edit named agents
**Business case:** This is the front door of the product the founder chose — agents as characters, not config rows; first impression decides activation (<15 min to first reply).
**Tasks:**
- Roster grid: avatar, name, one-line persona, status, last run, spend today
- Create/edit flow: identity (name, avatar picker/upload, persona), model + params, system prompt, budget; writes IR
- Empty state that invites creating the first agent (activation path)
**Acceptance criteria:**
- Create 3 differently-named agents with distinct personas in under 5 minutes total; each appears on the roster with identity rendered
- Form validation surfaces IR schema errors inline
- Roster reflects live status and last-run info

### M2.S4 — Version history & rollback UI
**Business case:** One-click rollback converts "my agent got worse" from a support ticket into a self-serve action — the ops-discipline pitch made tangible.
**Tasks:**
- Version history list per blueprint (author, timestamp, changelog note)
- One-click rollback with confirm; ledger entry
- (Diff view deferred to M10 — note in UI)
**Acceptance criteria:**
- Edit an agent twice, roll back to v1, next run demonstrably uses v1 config (trace shows version id)
- Rollback appears in the Ledger

---

## M3 · Epic: 1:1 Chat Surface + Semantic Memory — 11 fd · confidence: medium

**Goal:** The hero interaction — a dedicated chat per agent that feels like a colleague who remembers you, where every reply is a real traced Run.

### M3.S1 — Conversations & messages persistence
**Business case:** Persistent per-agent threads are the identity illusion's backbone — an agent whose chat resets is a form, not a character.
**Tasks:**
- `Conversation` (per agent, per user) and `Message` tables; ordering by monotonic sequence
- Message ↔ Run linkage (every assistant reply references its Run)
- History pagination API
**Acceptance criteria:**
- Thread survives reload/re-login with stable ordering; each assistant message links to a Run
- 1,000-message thread paginates without degradation (load fixture test)

### M3.S2 — Chat-triggered runs with streaming (SSE)
**Business case:** Sub-second first-token latency in chat is table stakes; doing it through the full run pipeline (not a shortcut path) keeps "every interaction is a traced Run" true.
**Tasks:**
- Send-message endpoint → creates chat-triggered Run → runner streams tokens via control plane SSE to the client
- Trace capture unaffected by streaming (verbatim final payloads persisted)
- "View the work" flip: any reply opens its Run trace side panel; per-reply cost chip
**Acceptance criteria:**
- Replies stream token-by-token; first token p50 < 2.5s on dogfood infra
- Flipping any reply shows its full step trace and per-step cost; the streamed text and persisted trace text are identical (test)
- A run mid-chat is killable; the chat shows the kill gracefully

### M3.S3 — Semantic memory (pgvector) + notes tool
**Business case:** "Agents that remember you" was the founder's explicit addition and the persona differentiator — recall across conversations is what makes a named agent feel real (and drives retention).
**Tasks:**
- Chunk + embed conversation history into `MemoryChunk` (pgvector, embedding provider per /plan ADR-011 — DECISION NEEDED); retrieval injected into loop context with relevance threshold
- Built-in `memory_notes` tool: agent-editable per-agent notes doc, read/write, exposed like any brokered tool and visible in traces
- Memory retrieval recorded as trace steps (what was recalled and why — debuggability)
**Acceptance criteria:**
- Fixture test: a fact stated in a week-old conversation is correctly used in a new conversation's reply
- Notes doc edits appear in the trace and persist across runs
- Memory is workspace/agent-scoped: an agent never retrieves another agent's or workspace's chunks (isolation test)

### M3.S4 — Chat UX polish to Signal Box standard
**Business case:** The chat is the surface design partners will judge in the first 60 seconds; instrument-panel-calm quality here is the "Vercel-grade ergonomics" half of the pitch.
**Tasks:**
- Streaming indicators, error/retry states, kill affordance in-chat, persona header (avatar + name + status)
- Cost chip per reply; day dividers; keyboard ergonomics
**Acceptance criteria:**
- Playwright flow: create agent → chat → streamed reply → flip to trace → kill a long run, all keyboard-accessible, zero forbidden hues
- Error states render for: runner down, budget exhausted, killed mid-stream

---

## M4 · Epic: Tool Broker & Secrets (Fleet-native MCP) — 12 fd · confidence: medium

**Goal:** Agents use real tools; the model never holds credentials; every tool call is audited to the Ledger.

### M4.S1 — MCP client + broker in the runtime path with per-agent allowlists
**Business case:** The broker is the security moat made concrete — one choke point for scoping, audit, and credential injection, owned by us (per the standalone decision).
**Tasks:**
- MCP client in the runner loop; tool registry in control plane; per-agent allowlist enforced at the broker (deny by default)
- Broker-side audit: every call → LedgerEntry (agent, tool, workspace, timestamp, outcome)
- Tool I/O captured verbatim in RunSteps (replay-grade)
**Acceptance criteria:**
- A tool not on the agent's allowlist is refused at the broker, surfaced in the trace, and ledgered (test)
- Every successful tool call produces a ledger row and a replay-complete RunStep

### M4.S2 — Secret storage & injection (per decision: plaintext rows + tripwire) with trace redaction
**Business case:** Credential handling is what a breach post-mortem examines; even under the plaintext-at-rest decision, injection-at-broker-only and redaction-by-construction keep the "model never sees secrets" promise true.
**Tasks:**
- `Secret` table: workspace-scoped rows (per DECISIONS.md: plaintext at rest, dissent + tripwire recorded), never serialized to runner env or model context
- Injection only at the broker at call time; automatic redaction of secret values from traces/logs (structural, not regex-only)
- Tripwire enforcement task: before first external-partner credential (M7 gate), encrypt or founder re-accepts in DECISIONS.md
**Acceptance criteria:**
- CI test greps runner env, model context, traces, and logs for a known test secret → zero hits
- Secrets are workspace-scoped (cross-tenant read attempt fails; test)
- Tripwire is a tracked checklist item on M7, not a comment

### M4.S3 — Keyless launch tools: web search + web fetch
**Business case:** Platform-keyed tools make every new agent useful in minute one — no credential friction between signup and value; they power the dogfood research-digest fleet.
**Tasks:**
- Web search tool (provider per /plan ADR-013 — DECISION NEEDED: Exa vs Brave; platform-keyed, per-call cost metered into run cost)
- Web fetch/read tool: URL → cleaned text; egress-proxied; response-size caps; SSRF protections (deny internal/metadata IP ranges at the proxy)
**Acceptance criteria:**
- An agent completes "summarize today's HN front page" style task in chat; trace shows search + fetch steps with I/O and per-call cost
- Fetch of an internal/private address is blocked (SSRF test)

### M4.S4 — Google Workspace read (OAuth test mode)
**Business case:** Email/calendar context is the highest-value personal data an assistant-like agent can use; test-mode OAuth captures that for dogfood + partners while deferring the CASA verification tax to GA.
**Tasks:**
- Google OAuth app (test mode, ≤100 users; CASA/verification explicitly deferred — GA gate); scopes: Gmail read, Calendar read, Drive read (metadata + files)
- Token storage as Secrets; refresh handling; revocation path
- Gmail/Calendar/Drive read tools via broker
**Acceptance criteria:**
- Agent answers "what's on my calendar tomorrow?" and "summarize unread email from today" from a connected test account
- Tokens never appear in runner env/model context/traces (covered by M4.S2 grep test); refresh survives token expiry (test with short-lived fixture)

### M4.S5 — Outbound email via Resend
**Business case:** Output has to land where humans already look; email delivery turns a scheduled agent from a log entry into a product moment (the digest in your inbox).
**Tasks:**
- Resend integration (platform account, per-workspace sending identity/prefix); email-send tool via broker
- Abuse guards: per-workspace daily send caps, recipient allowlist in MVP (self + verified addresses)
- Sends ledgered with recipient + subject
**Acceptance criteria:**
- A scheduled agent's digest email arrives in the founder's inbox; ledger entry exists
- Sending past the daily cap is refused and surfaced (test)

---

## M5 · Epic: Scheduler, Budgets & Kill Switch — 8 fd · confidence: medium-high

**Goal:** Agents work while you sleep, cannot spend past their cap, and die on command from every surface.

### M5.S1 — Cron triggers + run-now
**Business case:** Autonomy is the wedge's second half — a scheduled agent that produces value unattended is what separates Fleet from a chat toy and drives the "weekly active Fleets" north star.
**Tasks:**
- `Trigger` rows (cron expression, timezone, enabled flag) → Procrastinate periodic scheduling; run-now button/API
- Misfire policy: skip-if-still-running (no pileup) + jitter; documented and tested
- Schedule UI on the agent page (human-readable next-run preview)
**Acceptance criteria:**
- A 2-minute cron fires unattended ≥3 consecutive times producing traced Runs; overlapping fire is skipped, not queued (test)
- Disabling a trigger stops firing within one period

### M5.S2 — Budget engine: pre-call check + post-call meter
**Business case:** Runaway cost is the #1 documented production pain and the top reason for the trust-wedge pricing posture; the ≤1-step overrun invariant is a marketing claim only if it's a property test.
**Tasks:**
- Budgets per Agent and per Workspace (daily + monthly); pre-call estimate (prompt tokens × price + max_tokens ceiling) refused on overshoot; post-call actual decrement
- Budget state in Postgres with row-level locking (concurrent runs can't double-spend)
- Budget-exhausted runs end in a distinct terminal state, surfaced in chat/roster; ledgered
**Acceptance criteria:**
- A $0.05-budget run halts before the step that would overshoot; property test across randomized price/step scenarios proves overrun ≤ 1 run-step, always
- Two concurrent runs against one budget never jointly exceed it (concurrency test)

### M5.S3 — Kill switch hardening across all surfaces
**Business case:** The kill switch is a pager invariant and the demo's mic-drop; it must work from wherever the operator's panic happens to be.
**Tasks:**
- Kill from: chat thread, roster card, run trace page, and API; idempotent; works on queued and running states
- p95 kill latency measured continuously (metric emitted); ledger every kill with actor
**Acceptance criteria:**
- Integration test kills from each surface; p95 enforcement < 2s over 20 trials in CI
- Killing a queued run prevents start; killing a finished run is a safe no-op

### M5.S4 — Failure & budget notifications (email)
**Business case:** Operators trust autonomy only if silence means success; failure/budget emails are the minimum viable "you don't have to watch it" promise.
**Tasks:**
- Email on: run failure, budget exhausted, budget 80% warning; per-workspace notification preferences; deep links to the trace
- Digest suppression (one email per agent per hour max)
**Acceptance criteria:**
- A failing scheduled run produces exactly one email with a working deep link; 5 rapid failures produce 1 email (suppression test)

---

## M6 · Epic: Deterministic Replay — 10 fd · confidence: **low** *(founder-pulled into MVP; dissent + fallback gate on record — re-estimate at M5 exit; fallback = ship recording, defer engine)*

**Goal:** Any Run replayable offline: recorded model/tool responses re-executed for debugging and regression testing.

### M6.S1 — Replay-completeness audit & backfill
**Business case:** Replay is only as good as the recording; auditing now, while the trace schema is young, is 10× cheaper than discovering gaps after partners have history they care about.
**Tasks:**
- Checklist audit of RunStep schema vs replay needs (verbatim I/O, seeds, clock reads, tool nondeterminism, streaming vs final divergence); close gaps
- Property test generator: any completed run's trace passes a "replayable" validator
- Version the trace schema; migration policy for old runs
**Acceptance criteria:**
- Replayability validator passes on 100% of runs produced since M1 (or documents the exact cohort that predates a fixed gap)
- Validator runs in CI on every new run-producing test

### M6.S2 — Replay engine (stubbed model + tool planes)
**Business case:** "Debug an agent like a flight recorder" is the category-defining claim vs both no-code toys and DIY scripts; the engine is that claim, running.
**Tasks:**
- Replay mode of the loop: model plane and tool broker read responses from the recorded trace instead of the network; clock/RNG fed from recording
- Divergence detection: replayed step compared to recorded step; first divergence reported with a structured diff
- No-network guarantee in replay mode (egress disabled)
**Acceptance criteria:**
- Replaying any prior run reproduces an identical trace (hash-equal on normalized steps); proven offline (network disabled in the test harness)
- An intentionally corrupted recording produces a precise first-divergence report, not a crash

### M6.S3 — Replay regression harness + console integration
**Business case:** Replay-as-regression-test turns every good historical run into a free test fixture — prompt changes get CI safety nets, which is a genuinely novel selling point at this price tier.
**Tasks:**
- "Replay this run" button on the trace page (re-executes offline, shows diff vs original)
- Regression harness: pin a set of recorded runs; re-execute against a NEW blueprint version with recorded tool responses; report behavioral diffs
- CI wiring for our own dogfood agents
**Acceptance criteria:**
- Changing a dogfood agent's prompt makes a pinned replay-regression test fail with a readable diff; reverting greens it
- Console replay of a week-old run completes and displays "identical" status

---

## M7 · Epic: Workspaces & Billing — **MVP ships here** — 10 fd · confidence: medium

**Goal:** Multi-tenant hardening + all three Stripe tiers + onboarding polish; design partners onboard.

### M7.S1 — Auth, workspace membership, selector-header enforcement
**Business case:** The forged-header IDOR is the single most likely real-world breach for this architecture; making the selector-never-authorizer rule structural is what "zero cross-tenant incidents" rests on.
**Tasks:**
- Auth (email magic link + OAuth sign-in); `Workspace`, `WorkspaceMembership` tables; `X-Workspace-Id` selector validated against session-derived membership (403 on mismatch), applied in middleware before any view code
- Workspace switcher UI
**Acceptance criteria:**
- Forged/foreign `X-Workspace-Id` returns 403 on every endpoint (adversarial suite, M7.S2, includes this attack)
- A user in two workspaces sees strictly disjoint data when switching (test)

### M7.S2 — ORM tenancy guard + adversarial CI isolation suite
**Business case:** Convention doesn't survive 2am commits; a compile-time-ish guard plus an adversarial suite that blocks merge converts the PRD's hard invariant into a mechanical guarantee.
**Tasks:**
- Tenant-scoped model manager as the only manager on tenant-owned models; lint/test forbidding unscoped querysets outside an allowlisted module
- Adversarial CI suite: for every registered endpoint, attempt cross-tenant read/write with (a) foreign workspace header, (b) foreign object IDs, (c) unauthenticated; assert 401/403/404
- Suite auto-discovers new endpoints (fails if an endpoint lacks isolation coverage)
**Acceptance criteria:**
- Suite runs in CI, blocks merge, and fails loudly when a deliberately vulnerable test endpoint is introduced (canary test)
- Zero endpoints exempt without an explicit, reviewed allowlist entry

### M7.S3 — Stripe: three tiers + metered usage + quota enforcement
**Business case:** All-three-tiers-at-launch is the founder's commercial decision; metering wired to real runs from day one is what makes published-price trust (the GTM research wedge) honest.
**Tasks:**
- Stripe products: Hangar $0 / Squadron $49 / Fleet $199; subscription lifecycle + webhooks (signature-verified)
- `UsageEvent` pipeline: run costs → metered usage reporting (token pass-through + margin); reconciliation job
- Tier quotas (agents count, runs/month) enforced in-product: Hangar hard-stops at cap; upgrade prompts
**Acceptance criteria:**
- Test-mode subscribe/upgrade/cancel on each tier works end-to-end; Stripe usage matches internal ledger within 1% (reconciliation test)
- Exceeding a Hangar quota hard-stops the next run with an upgrade path shown; ledgered

### M7.S4 — Live cost meter, pricing page, onboarding polish
**Business case:** Activation (<15 min signup→first reply, p50) is the funnel's survival metric; the live meter in-product is the trust-wedge differentiator competitors hide in a billing tab.
**Tasks:**
- Workspace cost meter (today/this month, per agent) on the roster; per-run and per-reply costs already surfaced (M3/M5)
- Public pricing page (published rates incl. token margin); onboarding: guided first-agent creation → first chat reply
- Instrument the activation funnel
**Acceptance criteria:**
- Fresh-signup walkthrough (scripted, timed) reaches first agent reply in <15 min including Google OAuth skip-path; funnel events recorded
- Meter totals equal the sum of ledgered run costs (test)

### M7.S5 — Secrets tripwire gate + MVP ship checklist
**Business case:** The plaintext-secrets decision was accepted only with a tripwire; making the gate an explicit story means the risk is re-decided consciously, on the record, before external credentials exist.
**Tasks:**
- Execute the tripwire: either land envelope encryption (~1 fd) or record founder re-acceptance in DECISIONS.md — blocking item for external-partner onboarding
- MVP ship checklist: 4-invariant pager wired (uptime checks + phone alerting), Sentry on both planes, backups verified restorable, demo script `just demo-mvp` runs the full acceptance test
**Acceptance criteria:**
- Tripwire outcome recorded in DECISIONS.md before any non-founder credential is stored
- `just demo-mvp`: build agent → chat with memory recall → schedule → autonomous run → budget hard-stop demo → kill <2s → replay a run → Stripe test subscription — all pass in one scripted session

---

# Phase B — Depth: orchestration, providers, code, tools (~32 fd ≈ 8 weeks → ~mid Mar 2027)

## M8 · Epic: Orchestrations v1 + Approval Nodes — 12 fd · confidence: medium-low

### M8.S1 — Sequential pipeline pattern
**Business case:** The simplest multi-agent value story ("research → write → send") and the on-ramp to every later orchestration sale.
**Tasks:** `Orchestration` + typed step config in IR; pipeline executor (each stage a child Run under a parent Orchestration Run); inter-stage typed payloads; failure policy (halt/continue).
**Acceptance criteria:** A 3-agent pipeline completes with a parent trace linking child runs; a mid-pipeline failure halts per policy and notifies.

### M8.S2 — Supervisor/worker pattern with loop budgets
**Business case:** Supervisor patterns are where agent systems melt down (loops, runaway spend); runtime-enforced recursion/loop budgets are the ops-discipline moat applied to orchestration.
**Tasks:** Supervisor executor (supervisor agent dispatches to workers, reviews results); runtime-enforced max-iterations/max-depth/max-total-spend per orchestration; termination ledger entries.
**Acceptance criteria:** A deliberately non-converging supervisor is stopped by the loop budget (not by luck), with the stop reason in the trace; orchestration-level spend cap honors ≤1-step overrun.

### M8.S3 — Human approval nodes (console + signed email)
**Business case:** Approval gates are the trust antidote to autonomous-agent anxiety — the feature that lets cautious buyers say yes.
**Tasks:** Approval node type (pauses orchestration, snapshot of pending action); console approval queue; signed one-click approve/reject email links (expiring, single-use); resume/cancel semantics; everything ledgered.
**Acceptance criteria:** A pipeline pauses at an approval node; approving from a phone email resumes it; rejecting cancels downstream steps; forged/expired links fail closed (test).

### M8.S4 — Fleet grouping UI
**Business case:** "Fleet" is the brand noun; grouping agents + their orchestration into a named unit unlocks fleet-level status/spend and the eventual agency story.
**Tasks:** `Fleet` model (agents + orchestration + shared budget); fleet dashboard card (status, last run, spend, error rate); fleet-level kill.
**Acceptance criteria:** A fleet shows aggregate spend/status; fleet-level kill terminates all member runs <2s each.

## M9 · Epic: Multi-Provider Model Plane — 6 fd · confidence: high

### M9.S1 — Provider interface hardening
**Business case:** The abstraction was stubbed in Phase A; hardening it before the second provider prevents Anthropic-shaped assumptions from calcifying into the loop.
**Tasks:** Formalize provider interface (messages, tools, streaming, token accounting, price table per provider); conformance test suite any provider must pass; replay compatibility (provider tagged in trace).
**Acceptance criteria:** Anthropic adapter passes the conformance suite; replay of pre-M9 runs still byte-identical.

### M9.S2 — OpenAI + Google adapters
**Business case:** Model choice is a checkbox in every evaluation; two more first-class providers removes the most common disqualifier.
**Tasks:** OpenAI + Google adapters (tool-calling translation, streaming, cost tables); per-agent model/provider selection in IR + builder.
**Acceptance criteria:** The same agent answers correctly via all three providers with accurate per-step costs; conformance suite green for all.

### M9.S3 — Open-weights endpoint support
**Business case:** Cost-sensitive and privacy-sensitive users (and margin experiments) need an OpenAI-compatible open-weights path.
**Tasks:** Generic OpenAI-compatible endpoint adapter (configurable base URL, per-workspace); guardrails for missing capabilities (no tool-calling → declared capability flags).
**Acceptance criteria:** An agent runs against a hosted open-weights endpoint; capability flags prevent silent tool-call failures (test).

## M10 · Epic: Code Blueprints + CLI (TypeScript SDK) — 8 fd · confidence: medium

### M10.S1 — TS SDK: `defineAgent` DSL → IR
**Business case:** This redeems the TypeScript-first decision — typed, autocompleted agent authoring that compiles to the same IR the builder edits.
**Tasks:** `@offsidefleet/sdk` package: typed `defineAgent`/`defineFleet` → IR serialization; schema-locked types generated from the IR JSON Schema; versioned against `schemaVersion`.
**Acceptance criteria:** A TS blueprint compiles to IR that validates and round-trips into the visual builder; type errors catch invalid configs at compile time (fixture suite).

### M10.S2 — `fleet` CLI
**Business case:** CI-deployable agents are the Builder-Bea power path and the wedge into teams with real SDLC.
**Tasks:** CLI: `login`, `deploy`, `diff`, `promote`, `runs`, `kill`; API-token auth (workspace-scoped); CI-friendly output.
**Acceptance criteria:** `fleet deploy` from a repo creates a new BlueprintVersion visible in the console; `fleet diff` shows IR changes vs live.

### M10.S3 — Environment promotion + diff view
**Business case:** Draft→staging→live is the "production discipline" pitch applied to prompts — change management without a change-management product.
**Tasks:** Environment field on Agents (draft/staging/live); promotion flow with confirmation + ledger; IR diff view in console (prompt + config).
**Acceptance criteria:** Promote a draft version through staging to live; diff view renders prompt/config changes; every promotion ledgered.

## M11 · Epic: Tool Pack v2 — 6 fd · confidence: medium-high

### M11.S1 — Slack post + generic authenticated HTTP request
**Business case:** Slack meets operators where they live; the generic HTTP tool makes the platform feel unbounded (any REST API without waiting for us).
**Tasks:** Slack incoming-webhook tool (per-workspace webhook secret); generic HTTP tool (stored header credential, method/URL allowlist per agent, egress-proxied, SSRF-guarded); both ledgered.
**Acceptance criteria:** An agent posts a digest to Slack; the HTTP tool calls an arbitrary allowlisted API with an injected credential that never reaches the model (grep test).

### M11.S2 — GitHub + Notion
**Business case:** The indie-hacker (GitHub) and founder-second-brain (Notion) personas each get their home tool.
**Tasks:** GitHub tool via PAT (repo read, issues, PRs); Notion tool (pages + databases read/write); scoping config per agent.
**Acceptance criteria:** An agent files a GitHub issue and writes a Notion page in one traced run; Slack approval of the M8 kind can gate the write (integration test).

### M11.S3 — Google Sheets write
**Business case:** Sheets is SMB ops' database; append-a-row turns any agent into a tracker/report writer with zero new UI.
**Tasks:** Sheets append/write tool riding the M4 Google OAuth (additional scope); rate limits.
**Acceptance criteria:** A scheduled agent appends a row per run to a live sheet; the M8 demo ("GitHub issue + Sheets row + Slack summary in one run") passes.

---

# Phase C — Surfaces & scale (~38 fd ≈ 10 weeks → ~late May 2027)

## M12 · Epic: Agency Multi-Workspace — 8 fd · confidence: medium

### M12.S1 — Organization layer & cross-workspace console
**Business case:** Fleet-lead Farah (agencies) is the $199 tier's justification; agencies multiply distribution (each brings N clients).
**Tasks:** `Organization` above workspaces; org-level roles; cross-workspace switcher + rollup dashboard.
**Acceptance criteria:** One login manages 3 client workspaces; org admin sees all, client member sees only theirs (isolation suite extended to org level).

### M12.S2 — Per-client cost rollups & exports
**Business case:** Agencies bill clients; per-client cost truth is the feature they can't get from raw API keys.
**Tasks:** Org-level spend rollups per workspace/fleet/agent; CSV/PDF export; month boundaries + timezones handled.
**Acceptance criteria:** Rollup totals reconcile with per-workspace ledgers exactly; export matches the dashboard.

### M12.S3 — Client-visible guardrail reports
**Business case:** "Guardrails I can show the client" converts compliance posture into agency sales collateral.
**Tasks:** Shareable read-only report: policies in force, approvals log, spend caps, kill events for a workspace/fleet over a period.
**Acceptance criteria:** A generated report link renders without auth leaking anything beyond its scope (adversarial test).

## M13 · Epic: Browser Extension Cockpit — 10 fd · confidence: medium

### M13.S1 — Extension scaffold + auth
**Business case:** The cockpit puts fleet awareness one keystroke away all day — presence that a web tab doesn't have.
**Tasks:** Greenfield MV3 extension (standalone; no OffSideKick inheritance per DECISIONS.md); secure session bridge to the API; Signal Box visual language.
**Acceptance criteria:** Sign in from the extension; session survives browser restart; store-listing lint passes.

### M13.S2 — Fleet status + kill switches
**Business case:** The 2-second kill promise is most valuable when it's ambient — panic-button-in-the-toolbar is the promise embodied.
**Tasks:** Popup: roster status, live runs, spend today; per-agent and per-run kill.
**Acceptance criteria:** A run killed from the extension terminates <2s; status reflects within 5s of state change.

### M13.S3 — Approvals in the extension
**Business case:** Approval latency is orchestration throughput; the extension makes approvals a 10-second interruption instead of a context switch.
**Tasks:** Approval queue in popup; approve/reject with the same signed-action backend as email.
**Acceptance criteria:** An M8 approval node approved from the extension resumes its orchestration; audit shows the actor + surface.

## M14 · Epic: Shared Channels (the Buzz vision) — 20 fd · confidence: **low** *(largest epic on the roadmap; re-scope when adjacent)*

### M14.S1 — Channel model + realtime infrastructure
**Business case:** This is the founder's full vision — humans and agents as teammates in shared rooms; everything before it de-risked the runtime it stands on.
**Tasks:** Channels, memberships (humans + agents), threads; WebSocket realtime layer (upgrade from SSE where needed); presence.
**Acceptance criteria:** Two humans converse in a channel in realtime with threading; history + pagination stable under load fixture.

### M14.S2 — Agents as channel members (mention-driven)
**Business case:** Agents responding to @mentions in a shared room is the "hive mind" demo that sells the platform's ceiling.
**Tasks:** @mention → chat-run pipeline with channel context windowing; agent replies attributed to their identity; per-channel tool/budget policy overrides.
**Acceptance criteria:** In a channel with 2 humans + 2 agents, each @mentioned agent replies in-thread with a traced run; unmentioned agents stay silent.

### M14.S3 — Multi-agent turn-taking + channel audit
**Business case:** Without turn-taking discipline, multi-agent rooms melt into loops — the runtime-budget philosophy applied socially is what makes channels shippable at all.
**Tasks:** Agent-to-agent mention rules with depth/turn budgets (runtime-enforced); channel-level spend rollup; channel audit view (who/what/cost per message).
**Acceptance criteria:** Two agents mentioning each other are stopped by the turn budget with the stop visible in-channel; channel cost view reconciles with ledger.

---

# Phase D — Ecosystem (~57 fd ≈ 14 weeks → ~Sep 2027)

## M15 · Epic: Store → Template SDK & Marketplace — 15 fd · confidence: low

### M15.S1 — Curated template packs + install flow
**Business case:** Templates collapse time-to-value (install a working fleet in minutes) and are the distribution surface for everything else.
**Tasks:** Pack format (bundle of blueprint IRs + orchestration + docs); install-into-workspace flow with tool-connection prompts; launch packs: research digest, inbox triage, site monitor.
**Acceptance criteria:** A fresh workspace installs the research-digest pack and reaches a successful scheduled run in <10 minutes.

### M15.S2 — Template SDK + submission pipeline
**Business case:** Third-party templates scale the catalog beyond founder bandwidth — the curation-first instinct kept, the bottleneck removed.
**Tasks:** Template authoring via the M10 TS SDK; submission + review pipeline (automated IR validation, policy lint, manual approval); versioned pack updates.
**Acceptance criteria:** An external author submits a pack that passes automated checks and manual review, then installs cleanly; a malicious-config fixture is auto-rejected.

### M15.S3 — Marketplace hardening (gVisor tripwire likely fires here)
**Business case:** The moment third-party content executes for strangers, the threat model shifts — this story pays the isolation debt scheduled in DECISIONS.md before it's exploitable.
**Tasks:** Execute the gVisor tripwire evaluation (mandatory before any arbitrary code in packs; if packs remain declarative-only, record the re-assessment); abuse reporting; pack revocation.
**Acceptance criteria:** Tripwire decision recorded in DECISIONS.md; a revoked pack stops executing in all workspaces within one scheduling period.

## M16 · Epic: Headless API Tier — 10 fd · confidence: medium

### M16.S1 — Public API + keys
**Business case:** Platform Pete (SaaS teams embedding agents) is a second revenue curve on the same runtime — API-first unlocks it without new product surface.
**Tasks:** Public REST API (agents, runs, chat) with API-key auth (workspace-scoped, rotatable); rate limits; per-key metering into billing.
**Acceptance criteria:** A demo app creates an agent, chats, and streams a reply using only API keys; key revocation cuts access immediately.

### M16.S2 — API docs + versioning policy
**Business case:** Headless products live or die on docs; a versioning promise is what lets customers build on you.
**Tasks:** OpenAPI spec published; docs site; `v1` stability policy + deprecation process.
**Acceptance criteria:** The OpenAPI spec validates against the live API in CI (drift test); quickstart reproduces in <15 minutes.

## M17 · Epic: Voice/Telephony + GTM Pack — 20 fd · confidence: low

### M17.S1 — Voice provider abstraction + telephony
**Business case:** Voice is the highest-value GTM workload (speed-to-lead) and the founder's original product thesis, rebuilt on infrastructure that can now carry it.
**Tasks:** Voice provider interface (Retell-class first); inbound/outbound call handling as Runs (voice steps in traces); per-minute cost metering ($0.35/min posture) into budgets/billing.
**Acceptance criteria:** An inbound test call is answered by an agent and appears as a traced, costed Run; per-minute charges reconcile with the provider invoice.

### M17.S2 — TCPA/consent policy pack
**Business case:** Compliance-as-architecture is the moat claim; voice without a consent gate is a liability, with one it's a differentiator no toy can follow.
**Tasks:** Policy pack: consent ledger, calling-hours/jurisdiction rules, evaluated in the runtime path (fails closed); litigation export.
**Acceptance criteria:** A call attempt without recorded consent is blocked pre-dial and ledgered; export produces a per-call compliance record.

### M17.S3 — GTM fleet templates
**Business case:** The prior PRD ships as content — proof Fleet runs revenue workloads, not demos.
**Tasks:** GTM pack (standalone rebuild, no OffsideGTM code): speed-to-lead voice agent + enrichment agent + sequencer agent as an orchestrated fleet template.
**Acceptance criteria:** Installing the GTM pack and connecting tools yields a fleet that handles a test lead end-to-end (call, enrich, follow-up) under policy.

## M18 · Epic: DAG Editor — 12 fd · confidence: medium

### M18.S1 — Graph execution model
**Business case:** Arbitrary topologies (branch/join/conditional) unlock the workflows the pattern-picker can't express — the ceiling raise for power users.
**Tasks:** Generalize the M8 executor to DAGs (branch, join, conditional edges, per-node policy); IR extension; migration path for existing orchestrations.
**Acceptance criteria:** A 5-node DAG with a branch and a join executes as specified; existing M8 orchestrations run unchanged (regression suite).

### M18.S2 — Canvas editor
**Business case:** The visual DAG editor is the demo-at-a-conference feature and the last piece of "build visually or in code" parity.
**Tasks:** Canvas UI (nodes = agents/approvals/conditions; edges = typed handoffs) editing the orchestration IR; validation (cycles, unreachable nodes, budget presence) with inline errors; simulate-with-replay preview using M6 recordings.
**Acceptance criteria:** Draw the 5-node DAG including an approval gate in the canvas; it validates, saves as IR, executes as drawn; an invalid graph (cycle) is rejected inline.

---

# Reading this honestly

- **Cumulative: ~192 focused days ≈ 48 working weeks** — ~11–12 months solo, ending ~Sep 2027. That is what "nothing is killed" costs; this document's job is to keep that visible.
- The 6-month line (~Feb 2027) falls mid-Phase-B — a consequence of pulling replay into the MVP. Phases C–D are beyond 6 months *by sequencing*, with every item's place and price on the record.
- Within Phases B–D, order is negotiable at each phase boundary; within Phase A it is not (each milestone builds on the last).
- Low-confidence items (M6 replay, M8 orchestration, M14 channels, M15 marketplace, M17 voice) are re-estimated when adjacent, per the 150% honesty rule. **M6 is the highest-risk item inside the MVP**; its pre-agreed fallback (decided at M5 exit) is to ship the MVP with replay-grade recording but defer the engine.
- Standing risk gates from DECISIONS.md: secrets tripwire at M7.S5 · Google CASA verification before GA · gVisor tripwire at M15.S3.
