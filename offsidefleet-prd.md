# OffsideFleet — PRD v2
## Builder, editor, manager, and orchestrator of cloud AI agents

**Renamed from:** OffsideGTM (the GTM/voice product pivots from vertical app → horizontal platform; GTM agents survive as the flagship template fleet)
**Prepared:** August 2026 · **Entity:** Platform6ix Inc. · **Status:** PRD v2 — pre-implementation; to be refined via the Claude Code interview protocol (see companion prompt file)

---

## 1. One-liner

**OffsideFleet is the fleet console for cloud AI agents: build them visually or in code, edit and version them, run them in sandboxed cloud containers, and orchestrate them into multi-agent workflows — with policy guardrails, observability, and cost control built in from day one.**

Elevator framing: *Kubernetes-grade discipline for AI agents, at Vercel-grade ergonomics, for teams that will never buy IBM.*

## 2. Why this product, why now

- The category has split into two unusable extremes: enterprise heavyweights (IBM watsonx Orchestrate, Camunda, UiPath Maestro, Microsoft Agent 365, Palantir) with procurement-grade friction, and no-code toys (MindStudio-class builders) that collapse in production. Industry's own numbers: ~71% of organizations are deploying agents but only ~11% of use cases reached production; ~95% of AI pilots fail to deliver measurable impact. The gap is production discipline at indie/SMB accessibility.
- MCP has emerged as the de facto tool-connectivity protocol. An MCP-native platform gets an entire tool ecosystem for free — and we already have **Offside Router** (MCP-of-MCPs) as the connectivity layer.
- The failures that kill agent pilots are known and boring: no auditability, tenant leakage, un-debuggable loops, runaway token cost. These are *infrastructure* problems — exactly the kind of problem the portfolio keeps converging on (compliance gate in OffsideGTM, scoped runtime in OpenAgents, orchestration surface in OffSideKick).

## 3. Portfolio consolidation (proposal)

OffsideFleet becomes the **platform**; three existing threads fold into it rather than compete with it:

| Existing thread | Role inside OffsideFleet |
|---|---|
| **OpenAgents** (managed agent-as-a-service runtime, Curated Store + Console) | Becomes the **runtime + Store** layer of Fleet. OpenAgents as a separate brand retires or becomes the store name. |
| **OffSideKick** (Chrome extension + app.offside.ai; manages/orchestrates agents on OffsideAI cloud — DO, FastAPI) | Becomes a **client surface** of Fleet: the extension is the in-browser cockpit; app.offside.ai *is* the Fleet console. |
| **Offside Router** (MCP aggregator) | Becomes the **tool plane**: every Fleet agent gets tools exclusively through Router — one integration point, per-agent tool scoping, centralized audit. |
| **OffsideGTM** (compliance gate, consent ledger, voice playbooks) | Generalizes into the **Policy Engine** (guardrails-as-architecture) and ships as the flagship **GTM Fleet template pack** — proof that Fleet runs real revenue workloads, not demos. |

This resolves the overlap question explicitly; confirm or veto in the interview.

## 4. Personas

| Persona | Who | Job to be done |
|---|---|---|
| **Builder Bea** | Technical solo founder / indie hacker | "Let me define an agent in code or UI, give it tools, and put it in production without building an ops stack" |
| **Operator Omar** | SMB owner / ops lead, semi-technical | "I bought/installed three agents from the Store — show me what they did, what they cost, and let me pause the misbehaving one" |
| **Fleet-lead Farah** | Agency / consultancy running agents for clients | "Multi-tenant workspaces, per-client cost rollups, guardrails I can show the client" |
| (Later) **Platform Pete** | SaaS team embedding agents | API-first: Fleet as headless agent infrastructure |

## 5. Domain model (core nouns)

```
Workspace ─┬─ Blueprint   (versioned agent definition: model, system prompt,
           │               tools[scoped via Router], memory config, triggers,
           │               policy bindings, budget)
           ├─ Agent       (deployed instance of a Blueprint @ version)
           ├─ Fleet       (named group of Agents + an Orchestration)
           ├─ Orchestration (DAG / sequential / supervisor pattern connecting
           │               Agents; handoff rules; human-approval nodes)
           ├─ Run         (single execution: trigger → steps → outcome;
           │               full trace, token/cost meter, artifacts)
           ├─ Trigger     (schedule | webhook | event | manual | agent-to-agent)
           ├─ Policy      (guardrail set: tool allowlists, spend caps, rate
           │               limits, PII rules, approval requirements, kill
           │               conditions) — generalization of the GTM consent gate
           ├─ Ledger      (immutable audit log of actions, approvals, costs)
           └─ Secret      (scoped credentials, never visible to the model)
```

## 6. Modules

### M1 — Builder
- Dual-mode authoring, same underlying Blueprint format:
  - **Visual:** form + canvas (prompt, model, tools, triggers, memory, policy).
  - **Code:** Blueprint-as-YAML/TypeScript in a repo, `fleet deploy` CLI; Git-backed.
- Model-agnostic: Anthropic first-class, OpenAI/Google/open-weights via provider abstraction.
- Test bench: run a Blueprint against sample inputs before deploy; diff outputs across versions.

### M2 — Editor & Versioning
- Every Blueprint change = new immutable version; Agents pin versions; one-click rollback.
- Prompt/config diff view; changelog; environment promotion (draft → staging → live).

### M3 — Manager (Fleet Console)
- Fleet dashboard: status, last run, error rate, spend today, per-agent kill switch.
- Run inspector: full step-level trace (LLM calls, tool calls via Router, retries), token + $ per step.
- Cost controls: budgets per Agent/Fleet/Workspace, hard stops, anomaly alerts. (This is the #1 production pain per the research — treat as a headline feature, not a settings page.)
- Notifications: email/Slack/webhook on failure, approval-needed, budget events.

### M4 — Orchestrator
- Patterns at launch: sequential pipeline, supervisor/worker, and event-driven handoff. (Full DAG editor later.)
- **Human-in-the-loop nodes:** approval gates with mobile-friendly approve/reject — the antidote to the autonomous-agent trust collapse documented in the GTM research.
- Agent-to-agent messaging with typed payloads; loop/recursion budget enforced by runtime, not convention.

### M5 — Runtime (the OpenAgents inheritance)
- Sandboxed per-run containers on DigitalOcean; scoped egress; no cross-tenant reuse.
- Every tool call brokered by **Offside Router** with per-agent scopes — the model never holds raw credentials.
- Deterministic replay of Runs from trace (debugging + regression tests).

### M6 — Policy Engine (the moat, generalized from OffsideGTM)
- Declarative policies bound to Blueprints/Fleets; evaluated **in the runtime path, fails closed** — the same dial-time-gate philosophy, generalized: spend caps, tool allowlists, data-egress rules, jurisdictional rules (the GTM voice/TCPA pack becomes one policy pack among many), mandatory approval conditions, kill conditions.
- Litigation/compliance export per Run or Fleet (Ledger).

### M7 — Store & Templates
- Curated (not open marketplace at first — OpenAgents' curation instinct was right): template packs installable into a Workspace.
- Launch packs: **GTM Fleet** (speed-to-lead voice + enrichment + sequencer agents — the entire prior PRD ships as content), plus 2–3 simpler packs (inbox triage, research digest, site monitor) to prove horizontality.

### M8 — Surfaces
- **Web console** (app.offside.ai, SvelteKit) — primary.
- **OffSideKick Chrome extension** — cockpit: fleet status, approvals, kill switches, plus its local-shell capability as a Fleet client.
- **CLI + API** — Blueprint deploys, CI integration.

## 7. Architecture (proposed, to be pressure-tested in interview)

```
SvelteKit console + Chrome ext (OffSideKick)
        │
Control plane: Django + DRF + Postgres 16 + Procrastinate
  (workspaces, blueprints, versions, policies, billing, ledger)
        │
Data plane: containerized agent runners on DO
  (per-run sandbox; runner SDK in Python; FastAPI runner-gateway —
   aligns with the existing OffsideAI/OffSideKick backend)
        │
Tool plane: Offside Router (MCP aggregator; per-agent scopes, audit)
Model plane: provider abstraction (Anthropic → OpenAI → open-weights)
```

- Control plane vs data plane split is the load-bearing decision: console/state in the house stack (Django/DRF/Procrastinate), execution isolated per tenant per run.
- Multi-tenant shared-schema control plane (OffsideCommerce pattern); strict tenant scoping enforced at the ORM layer + runtime sandbox boundary.
- Open decision: FastAPI vs Django for the runner-gateway (OffSideKick's existing backend is FastAPI — consistency argues FastAPI for the data plane, Django for the control plane).

## 8. Design language

Extend the confirmed **Signal Box** system from OffSideKick (Soot, Walnut, Verdigris, Rust, Parchment + Emerald accent; Fraunces / Hanken Grotesk / IBM Plex Mono) — Fleet and OffSideKick are one product family and should look like it. Per standing rule: no purple, indigo, or cyan anywhere in the UI.

## 9. Pricing (hypothesis — validate in interview)

| Tier | Price | Includes |
|---|---|---|
| **Hangar** (free) | $0 | 1 agent, 100 runs/mo, community templates, hard budget cap |
| **Squadron** | $49/mo | 10 agents, 2,500 runs, all orchestration patterns, Store packs, Slack alerts |
| **Fleet** | $199/mo | 50 agents, 15K runs, multi-workspace (agency mode), policy packs, ledger exports, priority runners |
| Usage | — | Model tokens at metered pass-through + margin; published rates. Voice minutes (GTM pack) $0.35/min as before |

Trust-wedge posture carries over from the GTM research: published pricing, monthly terms, live cost meters in-product.

## 10. MVP cut (Phase 1 — to be finalized in planning phase)

**In:** Workspace + Blueprint (visual builder, single-agent) · versioning + rollback · sandboxed runner (schedule + webhook + manual triggers) · Router-brokered tools (3–5 launch tools) · Run inspector with full trace + cost meter · budgets + kill switch · one Store pack (research digest — smallest credible) · Stripe billing.
**Phase 2:** Orchestrations (sequential + supervisor), approval nodes, CLI/code Blueprints, GTM Fleet pack (voice via Retell behind provider abstraction), Chrome-ext cockpit integration.
**Phase 3:** Full policy-pack system, agency multi-workspace, deterministic replay, DAG editor, headless API tier.

**MVP acceptance test:** a user builds an agent in the visual builder, gives it two Router-scoped tools, schedules it, watches a live Run trace with per-step cost, hits the kill switch mid-run and sees it die within 2s, and exports the Ledger for that run — all inside published-price limits.

## 11. Success metrics

- North star: **weekly active Fleets** (≥1 successful scheduled/triggered Run in the week).
- Activation: signup → first successful Run < 15 minutes (p50).
- Reliability: runner start p95 < 5s; kill-switch enforcement < 2s; zero cross-tenant incidents (hard invariant).
- Cost trust: 100% of Runs show step-level cost; budget hard-stops never overrun by > 1 run-step.
- Business: logo churn < 5%/mo; gross margin ≥ 60% after model pass-through.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Platform giants (OpenAI/Anthropic/Google agent platforms) commoditize the builder | Differentiate on ops discipline (policy, ledger, cost) + MCP-native Router moat + Store distribution, not on authoring UX alone |
| Sandboxing done wrong = tenant breach | Data-plane isolation is a Phase-1 architecture gate, not a hardening task; external review before GA |
| Runaway model costs eat margin | Pass-through + margin pricing; per-run token ceilings enforced in runtime |
| Scope explosion (this PRD touches four prior products) | The Claude Code interview + milestone gates exist precisely to cut this; MVP is single-agent, no orchestration |
| Curation bottleneck on Store | Small launch catalog; template SDK later |

## 13. Open decisions (feed directly into the interview)

1. Portfolio consolidation as proposed in §3 — confirm/veto per thread.
2. Control/data plane split and FastAPI-vs-Django for the runner-gateway.
3. Blueprint format (YAML vs TS-first) and how much of the agent loop is "our runtime" vs delegated to an SDK (e.g., building on an existing agent SDK vs owning the loop).
4. Which 3–5 Router tools ship in MVP.
5. Sandbox technology on DO (gVisor/Firecracker-class vs plain containers + egress proxy for v1).
6. Whether GTM Fleet (with its voice/telephony weight) is Phase 2 or Phase 3.
7. Pricing tiers/quotas.
8. Naming collisions check: "OffsideFleet" trademark/domain sweep.

## 14. Companion artifact

`offsidefleet-claude-code-prompt.md` — the staff-engineer interview → plan → build protocol for Claude Code. Do not start implementation from this PRD directly; the PRD is input to that protocol.
