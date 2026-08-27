# DECISIONS.md — OffsideFleet

Running log of decisions made during the interview → plan → build protocol.
Each entry: date, decision, rationale, and any PRD text it supersedes.

Format:

```
## YYYY-MM-DD — <short title>
**Decision:** …
**Rationale:** …
**Supersedes:** <PRD §/quote, or "nothing — new decision">
```

---

## 2026-08-26 — Portfolio consolidation VETOED; Fleet is standalone
**Decision:** OffsideFleet is built greenfield as a standalone product. OpenAgents, OffSideKick, Offside Router, and OffsideGTM are NOT folded in; they continue (or not) independently, and Fleet carries no inheritance obligations to any of them.
**Rationale:** Founder decision in interview batch 1, Q1.
**Supersedes:** PRD §3 (entire portfolio-consolidation table); §6 M5 "the OpenAgents inheritance" framing; §6 M8 OffSideKick-as-cockpit; §2/§6/§7 references to Router as the mandatory tool plane are now an open question (see follow-up decision on tool plane).
**Open consequence:** GTM Fleet template pack no longer "ships the prior PRD as content" for free.

---

## 2026-08-26 — Tool plane: Fleet-native MCP broker
**Decision:** Fleet ships its own MCP client + credential broker: per-agent tool scoping, audit to Ledger, secrets injected server-side (model never holds raw credentials). No runtime dependency on Offside Router; Router may later be consumed as just another MCP server.
**Rationale:** Preserves the PRD's security invariant and audit moat without re-coupling to a product the consolidation veto decoupled. Follow-up to the veto, interview batch 1.
**Supersedes:** All PRD references to Router as the mandatory tool plane (§2, §5 Blueprint "tools[scoped via Router]", §6 M5, §7 tool plane, §10 "Router-brokered tools").

---

## 2026-08-26 — MVP hero: agent roster + 1:1 chat (Buzz/GrokBot-inspired, scoped)
**Decision:** The MVP centers on creating many named agents with identities (name, avatar, persona) and specific functionalities (tools, triggers). Primary interaction: a dedicated 1:1 chat thread per agent, plus scheduled/triggered runs. Every interaction produces a traced, budgeted, killable Run. NO shared multi-party channels, NO agent-to-agent collaboration surface in MVP (Buzz-style channels are a later phase, if ever).
**Rationale:** Founder wants the block/buzz + GrokBot feel (agents as named characters, not config rows). Roster + 1:1 chat delivers that without building real-time multi-party messaging infra before the runtime is proven.
**Supersedes:** PRD §10 MVP framing of the visual builder as a pure config form; the "console-first, chat-nowhere" implication of §6 M1/M3. The ops spine (trace, cost, kill, budgets) is retained.

---

## 2026-08-26 — Agent powers in MVP: chat + manual + schedule
**Decision:** MVP agents support 1:1 chat, on-demand "run now", and cron schedules. All three produce traced, budgeted, killable Runs. Webhook, event, and agent-to-agent triggers deferred to a later milestone.
**Rationale:** Interview batch 1, Q2b — default accepted. Scheduled autonomy separates this from a character-chat toy; webhook ingress is its own mini-project.
**Supersedes:** PRD §10 "schedule + webhook + manual triggers" for MVP (webhook moved out of MVP).

---

## 2026-08-26 — Design partners: dogfood + named externals
**Decision:** Platform6ix dogfoods Fleet daily (own research/GTM agents), plus 2–3 named external design partners recruited within ~4 weeks of Milestone 1, on a weekly call cadence before Milestone 2 completes.
**Rationale:** Interview batch 1, Q3 — default accepted.
**Supersedes:** nothing — new decision.

---

## 2026-08-26 — No kill list; all nine deferred items live on a phased roadmap
**Decision:** Founder rejected the proposed 6-month negative scope. None of the nine items (voice/telephony, shared multi-party channels, open marketplace/template SDK, headless API tier, DAG editor, byte-exact deterministic replay, agency multi-workspace, browser extension, non-Anthropic providers) is banned. Instead, all are sequenced into ROADMAP.md as named milestone-epics (1:1 mapping), each with acceptance criteria and effort estimates.
**Rationale:** Founder preference for a complete visible roadmap over a negative-scope contract. Staff-engineer caveat, stated in the interview: sequencing reality means several of these items land beyond 6 months for a solo founder; the roadmap makes that explicit rather than hiding it.
**Supersedes:** PRD §10 phase cut (replaced by ROADMAP.md phases); §12 "MVP is single-agent, no orchestration" mitigation retained for Phase A only.

---

## 2026-08-26 — Billing: all three PRD tiers at MVP launch
**Decision:** Hangar ($0), Squadron ($49/mo), Fleet ($199/mo) all wired via Stripe at end of Phase A, with metered token pass-through + margin, per PRD §9. Tier quotas enforced in-product from day one.
**Rationale:** Founder override of the "one paid tier" default, interview batch 1 Q5. Cost: M6 grows from 8 → 10 fd (tier gating, per-tier quota enforcement, pricing page).
**Supersedes:** nothing — confirms PRD §9 as written.

---

## 2026-08-26 — Runtime: own a thin agent loop
**Decision:** Fleet owns the agent loop — hand-rolled Python over provider SDKs (Anthropic first). No agent framework. Trace capture, budget checks, kill points, and replay hooks live inside the loop.
**Rationale:** Interview batch 2 Q1 — default accepted. The ops seams ARE the product; frameworks bury them.
**Supersedes:** PRD §13.3 (question resolved: own the loop).

---

## 2026-08-26 — Blueprint format: TypeScript-first DSL → canonical JSON IR
**Decision:** Blueprints are authored TypeScript-first via a `defineAgent({...})`-style DSL that compiles/serializes to a canonical JSON Blueprint IR. The control plane stores the IR; the visual builder reads/writes the IR directly; the Python runtime executes the IR. Declarative-only in v1 (no arbitrary code embedded in blueprints). Consequence: the TS SDK + CLI may ship earlier than M9 if desired.
**Rationale:** Interview batch 2 Q2 + Q2a. Founder chose TS-first over the YAML default; the JSON-IR reconciliation keeps the visual-builder hero and the Python runner viable.
**Supersedes:** PRD §6 M1 "Blueprint-as-YAML/TypeScript" ambiguity and §13.3 format question (resolved: TS DSL, JSON IR canonical, no YAML).

---

## 2026-08-26 — Runs request-scoped (15-min cap); semantic memory IN MVP
**Decision:** Runs are request-scoped with a hard 15-minute wall-clock cap (per-tier configurability later); true long-running agents deferred (watchers are crons). Memory in MVP: persisted per-agent chat history + agent-editable notes doc + **pgvector semantic memory** so agents recall across conversations.
**Rationale:** Interview batch 2 Q3. Founder added semantic memory to the default — consistent with the named-agents-with-identities hero; an agent that forgets you undermines the persona. Cost: M3 grows 8 → 11 fd.
**Supersedes:** nothing in PRD (memory model was unspecified).

---

## 2026-08-26 — Deterministic replay pulled INTO the MVP
**Decision:** The full deterministic replay engine (formerly M10, Phase B) ships in Phase A as new M6. Trace schema is replay-complete from M1 (verbatim model/tool I/O, seeds, clock reads). Billing/workspaces becomes M7; Phase B renumbers accordingly.
**Rationale:** Founder override, interview batch 2 Q4, against the staff-engineer recommendation ("record now, replay later"). Dissent on record: replay is the lowest-confidence epic on the roadmap and displaces ~2 weeks of Phase A; MVP ship moves ~mid-Dec 2026 → ~mid-Jan 2027. Total roadmap effort unchanged (work moved, not added).
**Supersedes:** PRD §10 which placed deterministic replay in Phase 3; ROADMAP v0.1 Phase B placement.

---

## 2026-08-26 — Sandbox v1: hardened containers + egress allowlist proxy
**Decision:** v1 runner isolation = hardened Docker containers on DO droplets (non-root, read-only rootfs, seccomp/no-new-privs, per-run filesystem, CPU/mem/time limits, no ambient credentials) + egress proxy allowlist. gVisor-class isolation is a scheduled TRIPWIRE: mandatory before any arbitrary user code executes in blueprints (code steps / template SDK, M14-era).
**Rationale:** Interview batch 3 Q1 — default accepted. v1 blueprints are declarative-only, so the container runs our loop code; threat model is prompt-injected tool misuse, not hostile-code escape.
**Supersedes:** PRD §13.5 (question resolved).

---

## 2026-08-26 — Secrets: DO env for platform; customer secrets PLAINTEXT in Postgres (dissent recorded)
**Decision:** Platform secrets (our API keys, DB creds) in DO-managed env config. Customer tool credentials stored as plaintext rows in Postgres, scoped per workspace, injected only at the tool broker (never in runner env, never in model context, redacted from traces).
**Dissent (staff engineer):** Plaintext credentials at rest are below industry baseline; SQL injection, backup leakage, or admin compromise yields working third-party creds for all customers. Envelope encryption is ~1 fd.
**Tripwire (accepted unless founder objects):** Before the first EXTERNAL design partner stores a credential — M7 at the latest — either app-layer envelope encryption lands, or the founder explicitly re-accepts plaintext as a standing risk in this log.
**Supersedes:** PRD §5 "Secret" is weakened from "scoped credentials" with implied protection to scoped-but-plaintext storage.

---

## 2026-08-26 — Tenancy: workspace-selector header + 3-layer server-side enforcement
**Decision:** Frontend sends `X-Workspace-Id` as a SELECTOR only. Backend derives authorization server-side (session → user → workspace memberships; 403 on mismatch), then enforces tenancy at three layers: (1) ORM automatic scoping on `workspace_id` (no unscoped querysets), (2) runner data-scoping (a run's container only receives its own workspace's data), (3) adversarial CI tenant-isolation suite — including the forged-header/IDOR attack — blocking merge. Postgres RLS deferred to Phase B.
**Rationale:** Interview batch 3 Q3. Founder's header idea adopted in its safe form (selector, never authorizer); the literal client-trusted-tenantID variant was identified as an IDOR vulnerability and rejected.
**Supersedes:** nothing — refines PRD §7 "strict tenant scoping enforced at the ORM layer".

---

## 2026-08-26 — Launch tools (M4) + Tool Pack v2 (new M11)
**Decision:** MVP launch tools: web search (platform-keyed), web fetch/read, Google Workspace read (Gmail/Calendar/Drive — OAuth in test mode, ≤100 test users; CASA verification deferred to GA), outbound email via Resend. Plus the built-in memory/notes tool from the semantic-memory decision. Phase B gains **M11 · Tool Pack v2**: Slack post, GitHub (PAT), Notion, generic authenticated HTTP request, Google Sheets write.
**Rationale:** Interview batch 4 Q1 — founder selection + requested 5 additional tools (staff picks). Google tokens are the first concrete customer secrets → plaintext-secrets tripwire (see Secrets entry) activates at first external partner. Cost: M4 10 → 12 fd (OAuth flow); +6 fd Phase B; Phases C/D renumber (+1).
**Supersedes:** PRD §13.4 (question resolved).

---

## 2026-08-26 — Approvals surface (M8): console + signed email links
**Decision:** Approval nodes surface in a console queue and via email with cryptographically signed, mobile-friendly one-click approve/reject links. Slack approvals follow in M11. SMS/push deferred pending volume evidence.
**Rationale:** Interview batch 4 Q2 — default accepted.
**Supersedes:** nothing — refines PRD §6 M4.

---

## 2026-08-26 — Budgets: pre-call check + post-call meter
**Decision:** Before every model/tool call the loop checks estimated cost (prompt tokens × price + max_tokens ceiling) against remaining budget and refuses on overshoot; after every call actual cost decrements the budget. Honors the ≤1-run-step overrun invariant (PRD §11).
**Rationale:** Interview batch 5 Q1 — default accepted.
**Supersedes:** nothing — resolves enforcement-point question.

---

## 2026-08-26 — Deploy topology: App Platform control plane + runner droplet
**Decision:** Control plane (Django/DRF + Procrastinate worker + SvelteKit) on DO App Platform, deployed from the container registry. Data plane on a dedicated droplet: FastAPI runner-gateway spawning hardened per-run containers via the Docker API + egress proxy. DO Managed Postgres 16 with pgvector. DOKS is the scale path when a second runner host is needed. This also resolves PRD §13.2: Django for control plane, FastAPI for runner-gateway.
**Rationale:** Interview batch 5 Q2 — founder chose App Platform over the two-droplet default; staff caveats noted (two deploy models; App Platform constraints on the web tier; sandbox spawning stays on the droplet where App Platform can't do it).
**Supersedes:** PRD §13.2 (question resolved).

---

## 2026-08-26 — Observability: Sentry + structured logs + own Run traces
**Decision:** Sentry on both planes; structured JSON logs via DO; external uptime checks; Fleet's own Run inspector is the deep observability surface. No Prometheus/Grafana/OTel stack in year one.
**Rationale:** Interview batch 5 Q3 — default accepted.
**Supersedes:** nothing — new decision.

---

## 2026-08-26 — On-call: 4-invariant pager
**Decision:** Night pages ONLY for: (1) kill-switch enforcement failure, (2) runner host down / runs not starting, (3) budget enforcement failure or spend anomaly ≥3× daily norm, (4) tenant-isolation alarm. Everything else is a morning queue. Wired via uptime checks + phone-call alerting (Better Stack-class).
**Rationale:** Interview batch 5 Q4 — default accepted. The four pager items are the four product invariants.
**Supersedes:** nothing — new decision.

---

## 2026-08-26 — Phase 1 interview COMPLETE
**Decision:** Founder declared "interview complete." Phase 2 (plan documents) begins. Founder additionally directed: ROADMAP.md to be expanded so every milestone/epic breaks down into Stories and Tasks with Acceptance Criteria and a Business Case per story.
**Rationale:** Protocol gate passed.
**Supersedes:** nothing — process milestone.

---

## 2026-08-26 — Log opened
**Decision:** DECISIONS.md created at start of Phase 1 interview (per protocol).
**Rationale:** Single place to track PRD-invalidating answers and scope changes.
**Supersedes:** nothing — new decision.
