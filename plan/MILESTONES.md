# MILESTONES.md — Phase A (MVP) in execution detail

Seven milestones, strictly sequential. Full story/task breakdown lives in `ROADMAP.md`; this document is the execution contract: scope boundary, the demo script I will literally run at review, effort with confidence, and risks. Per protocol: each milestone starts by restating scope and ends with the demo + founder sign-off before the next begins.

Effort is focused days (fd). Confidence: **high** = estimate ±20%; **medium** = ±50%; **low** = could 2×.

---

## M1 — Runtime Spine · 8 fd · medium
**Scope:** repo + CI + control-plane skeleton; Run/RunStep/Ledger schema (replay-grade); runner droplet + gateway + hardened container + egress allowlist; thin loop v0 (hard-coded blueprint, one Anthropic call); kill v0; minimal trace page.
**Out:** any UI beyond the trace page; tools; chat; schedules; auth (dev-token only).
**Demo (`just demo-m1`):**
1. `just dev` boots; CI shown green on a real PR.
2. Script creates a Run; a container starts on the runner droplet; trace page shows ≥3 steps with verbatim payloads and dollar cost.
3. Egress test: in-container curl to a non-allowlisted host fails; Anthropic succeeds.
4. Second run started, killed mid-flight; terminates <2s (timed output); `killed` state + ledger row shown.
**Risks:** DO droplet/networking yak-shaving (mitigation: provisioning is scripted from hour one); App Platform pipeline quirks (mitigation: control plane runs on a droplet for M1 if App Platform fights back — deploy target is not M1's demo).

## M2 — Agent Roster & Identity · 6 fd · high
**Scope:** Blueprint/Version/Agent schema + immutability; IR v1 JSON Schema (shared TS/Python vectors); roster UI (create/edit named agents); version history + rollback.
**Out:** chat; diff view (M10); TS SDK.
**Demo:**
1. Create 3 named agents with distinct personas/avatars in <5 min; roster renders identity, status, last run.
2. Edit one agent → version 2 shown in history; DB-level immutability test output shown (UPDATE on a version row fails).
3. One-click rollback to v1; next run's trace records v1; rollback in Ledger.
**Risks:** IR schema churn later (mitigation: schemaVersion + migration policy from day one).

## M3 — 1:1 Chat + Semantic Memory · 11 fd · medium
**Scope:** conversations/messages; chat-triggered runs with SSE streaming; per-reply cost chip + trace flip; pgvector memory + notes tool; Signal Box chat polish.
**Out:** shared channels; multi-user threads; embedding provider migration tooling.
**Gate:** ADR-011 (embedding provider) must be decided before M3 starts — recommendation on record: Voyage.
**Demo:**
1. Chat with two agents; replies stream; personas clearly differ.
2. Flip a reply to its trace; per-step costs; kill a long reply mid-stream, chat degrades gracefully.
3. Memory: state a fact in one conversation session; in a fresh session (fixture-aged), the agent uses it; the trace shows the memory-retrieval step.
4. Notes: agent writes to its notes doc via tool; edit visible in trace and persists.
**Risks:** streaming/trace interplay (mitigation: persisted trace is authoritative, stream is presentation); retrieval quality (mitigation: retrieval steps visible in trace = debuggable from day one).

## M4 — Tool Broker & Secrets · 12 fd · medium
**Scope:** MCP broker + per-agent allowlists + ledgered calls; Secret storage per ADR-010 + structural redaction; web search + fetch (SSRF-guarded); Google Workspace read (OAuth test mode); Resend email with send caps.
**Out:** Tool Pack v2 (M11); Google OAuth verification/CASA (GA gate); per-user OAuth beyond test users.
**Gate:** ADR-013 (search provider) decided before M4.S3 — recommendation: Exa.
**Demo:**
1. Agent completes a research task in chat using search+fetch; trace shows brokered calls with I/O and per-call cost.
2. Non-allowlisted tool call refused, surfaced, ledgered.
3. Google: agent answers calendar + unread-email questions from a connected test account.
4. Secret-grep test output: known test secret absent from runner env, model context, traces, logs.
5. Scheduled-style digest email arrives (manually triggered here; schedules are M5).
**Risks:** Google OAuth plumbing (refresh, scopes) — the reason this is the biggest Phase A milestone; SSRF surface (mitigation: proxy-level denylist of private ranges + tests).

## M5 — Scheduler, Budgets & Kill Hardening · 8 fd · medium-high
**Scope:** cron triggers + run-now with skip-if-running; budget engine (pre-check + post-meter, agent+workspace caps, distinct terminal state); kill from all surfaces with p95 <2s measured; failure/budget emails with suppression.
**Out:** webhook/event triggers; Slack alerts (M11).
**Demo:**
1. 2-minute cron fires 3× unattended; traces + digest email land; overlapping fire skipped.
2. $0.05 budget: run hard-stops pre-overshoot; property-test output shown (≤1-step overrun across randomized scenarios).
3. Kill from chat, roster, and trace page; CI timing report p95 <2s.
4. Five rapid failures → exactly one email.
**Exit gate (pre-agreed):** M6 re-estimate. If projected >150% of 10 fd, fallback fires: ship recording, defer engine — founder decision recorded in DECISIONS.md either way.
**Risks:** budget race conditions (mitigation: row-lock + concurrency test in CI).

## M6 — Deterministic Replay · 10 fd · **low** (founder-pulled into MVP; dissent on record)
**Scope:** replay-completeness validator + trace backfill; replay engine (stubbed model/tool planes, no-network, first-divergence reporting); "replay this run" in console; replay-regression harness on dogfood agents in CI.
**Out:** replay across provider versions; replay-as-a-product-feature polish beyond the button.
**Demo:**
1. Replay a run recorded in M4/M5 offline (network disabled in harness); status: identical, hash-equal.
2. Corrupt a recording fixture; replay reports first divergence with structured diff.
3. Change a dogfood agent's prompt; pinned replay-regression test fails in CI with readable diff; revert greens it.
**Risks:** this is the plan's highest-risk milestone — nondeterminism leaks (clock, ordering, streaming); mitigation: replay-grade schema enforced since M1 + validator built FIRST (M6.S1) so gaps surface in day one of the milestone, not day eight.

## M7 — Workspaces & Billing — MVP ships · 10 fd · medium
**Scope:** auth + memberships + selector-header enforcement; ORM tenancy guard + adversarial CI isolation suite (auto-covering every endpoint); Stripe 3 tiers + metered usage + quota hard-stops; live cost meter + pricing page + onboarding (<15 min activation); secrets tripwire gate; pager wiring + ship checklist.
**Out:** org layer (M12); RLS (Phase B); self-serve growth features.
**Demo (`just demo-mvp` — the full MVP acceptance test from PLAN.md):** all nine steps, in one sitting, on the deployed environment — ending with the isolation suite green and a forged-header 403 shown live.
**Gates:** secrets tripwire outcome recorded BEFORE external-partner onboarding; 4-invariant pager fires a real test page.
**Risks:** Stripe metering reconciliation edge cases (mitigation: reconciler job + 1% tolerance test); endpoint-coverage gaps in the isolation suite (mitigation: suite fails on uncovered endpoints by construction).

---

## Phase A totals & buffer honesty

| M | Epic | fd | confidence |
|---|---|---|---|
| M1 | Runtime Spine | 8 | medium |
| M2 | Roster & Identity | 6 | high |
| M3 | Chat + Memory | 11 | medium |
| M4 | Tool Broker & Secrets | 12 | medium |
| M5 | Scheduler & Budgets | 8 | medium-high |
| M6 | Deterministic Replay | 10 | **low** |
| M7 | Workspaces & Billing | 10 | medium |
| **Σ** | | **65 fd** | |

At 4 fd/week: ~16 weeks ≈ **mid-late January 2027** from a ~mid-September 2026 start (holiday-adjusted). No padding is hidden in the estimates; the honest uncertainty is concentrated in M6 (explicit fallback) and M4 (Google OAuth). If any milestone tracks >150%, I say so the day I know, not at review (protocol).

Phase B–D milestone detail graduates from ROADMAP.md into this document at each phase boundary, re-estimated when adjacent.
