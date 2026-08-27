# ARCHITECTURE.md — OffsideFleet

Every load-bearing choice is an ADR: context → options → decision → consequences. Decisions marked **DECIDED** were resolved in the Phase 1 interview (see DECISIONS.md); two are **DECISION NEEDED** and must be resolved before their milestone starts (both have recommendations and neither blocks M1).

## System diagram

```
                    ┌─────────────────────────────────────────────┐
                    │ CLIENTS                                     │
                    │  SvelteKit console (M1+) · fleet CLI (M10)  │
                    │  Browser extension (M13) · Public API (M16) │
                    └────────────────────┬────────────────────────┘
                                         │ HTTPS + X-Workspace-Id (selector only)
        ┌────────────────────────────────▼─────────────────────────────────┐
        │ CONTROL PLANE — DO App Platform (containers from registry)       │
        │  Django 5 + DRF: workspaces, blueprints/versions (JSON IR),      │
        │  agents, conversations, runs, triggers, budgets, policies,       │
        │  ledger, secrets, billing                                        │
        │  Procrastinate workers: run dispatch, cron triggers, emails,     │
        │  Stripe usage reconciliation                                     │
        │  SSE hub: chat streaming to clients                              │
        └───────┬──────────────────────────────────────┬───────────────────┘
                │ DO Managed Postgres 16 (+pgvector)    │ internal API (shared-secret,
                │ single DB, shared schema,             │ private network)
                │ workspace_id on every tenant row      ▼
        ┌───────┴──────────────────────────────────────────────────────────┐
        │ DATA PLANE — dedicated runner droplet                            │
        │  FastAPI runner-gateway: start/kill runs, health                 │
        │  Per-run hardened containers (non-root, RO rootfs, caps dropped, │
        │  cpu/mem/pids/15-min limits, no ambient creds)                   │
        │   └─ thin agent loop (Python): model ⇄ tool steps, trace writer, │
        │      pre/post budget checks, kill + replay hooks                 │
        │  Egress proxy: allowlist (Anthropic, tool hosts, control plane)  │
        └───────┬──────────────────────────────┬───────────────────────────┘
                │ TOOL PLANE (in-process)      │ MODEL PLANE
                ▼                              ▼
        Fleet-native MCP broker         Provider abstraction
        per-agent allowlists,           Anthropic (M1) → OpenAI/Google/
        secret injection at call time,  open-weights (M9); price tables;
        audit → Ledger                  replay-mode stub
```

---

## ADR-001 · Runtime ownership: own a thin agent loop — **DECIDED**
**Context:** The loop is where trace capture, budget enforcement, kill points, and replay hooks live. PRD §13.3 left own-vs-SDK open.
**Options:** (a) own thin loop; (b) provider agent SDK; (c) framework (LangGraph-class).
**Decision:** (a). A few hundred lines of Python directly over provider SDKs.
**Consequences:** We maintain the loop and its provider translation forever (mitigated by M9 conformance suite). In exchange, every ops seam is ours — no framework fighting the exact features that are the product. Multi-provider (M9) is an interface we design, not an SDK migration.

## ADR-002 · Sandbox technology v1: hardened containers + egress allowlist — **DECIDED**
**Context:** PRD treats isolation as a Phase-1 architecture gate. v1 blueprints are declarative-only, so containers run *our* loop code; the live threats are prompt-injected tool misuse and data egress, not hostile-code escape.
**Options:** (a) hardened Docker + egress proxy; (b) gVisor from day one; (c) Firecracker-class microVMs.
**Decision:** (a): non-root, read-only rootfs, all caps dropped, no-new-privileges, seccomp, cpu/mem/pids/15-min limits, per-run tmpfs, no ambient credentials; egress only via allowlist proxy (SSRF-guarded).
**Consequences:** Right-sized now; **tripwire** — gVisor-class isolation is mandatory before any arbitrary user code executes (template SDK code steps; evaluated at M15.S3 and recorded in DECISIONS.md). The sandbox-escape test suite (TESTING.md) runs in CI from M1.

## ADR-003 · Blueprint format: TypeScript-first DSL → canonical JSON IR — **DECIDED**
**Context:** Founder chose TS-first over YAML; but the MVP hero is a visual builder and the runtime is Python.
**Options:** (a) TS DSL compiling to a canonical JSON IR; (b) TS programs executed by a Node runner; (c) builder emits TS source.
**Decision:** (a). The JSON IR (JSON-Schema-validated, `schemaVersion`ed, shared test vectors for TS and Python) is canonical; the visual builder edits IR directly; `defineAgent` TS SDK (M10) serializes to IR. Declarative-only in v1 — no arbitrary code in blueprints.
**Consequences:** Builder and code authoring have full parity via the IR; runtime stays Python. The IR schema is now a first-class public contract — breaking changes need migrations from M2 onward.

## ADR-004 · Control/data plane split: Django/DRF control, FastAPI runner-gateway — **DECIDED**
**Context:** PRD §13.2. Console/state CRUD-heavy vs execution latency-sensitive and isolation-critical.
**Options:** (a) Django control + FastAPI gateway; (b) Django everywhere; (c) FastAPI everywhere.
**Decision:** (a). Django+DRF+Procrastinate own all state and jobs; the gateway is a thin async service that only starts/kills containers and relays traces — it holds no business logic and no DB connection (talks to the control plane's internal API).
**Consequences:** Two services, one honest boundary that doubles as the blast-radius line. The gateway stays intentionally dumb; any temptation to put logic there is an architecture smell.

## ADR-005 · Deploy topology: App Platform control plane + runner droplet — **DECIDED** (founder choice)
**Context:** App Platform cannot spawn sibling containers, so the sandbox can't live there; founder chose App Platform over the two-droplet default for the web tier.
**Options:** (a) 2 droplets; (b) DOKS; (c) App Platform + runner droplet.
**Decision:** (c). Control plane (web + worker components) on App Platform from the container registry; data plane on a dedicated droplet; DO Managed Postgres 16 with pgvector.
**Consequences:** Zero-ops deploys for the web tier; two deploy models to maintain (registry images for both, but different pipelines); App Platform constraints (no compose, log/exec ergonomics) accepted. Scale path: runner droplet pool, then DOKS when scheduling demands it.

## ADR-006 · Tenancy: selector header + three-layer server-side enforcement — **DECIDED**
**Context:** Founder proposed a frontend tenantID header; literal form is an IDOR vulnerability. Hard invariant: zero cross-tenant incidents.
**Options:** (a) trust header; (b) selector header + server-side membership auth + layered enforcement; (c) subdomain-per-tenant.
**Decision:** (b). `X-Workspace-Id` selects among the session user's memberships (403 otherwise) in middleware; ORM tenant-scoped managers (unscoped querysets forbidden by lint/test); runner receives only its run's workspace data; adversarial CI isolation suite (forged header, foreign IDs, unauthenticated) auto-covers every endpoint and blocks merge. Postgres RLS added in Phase B as a fourth layer.
**Consequences:** The suite is a standing CI cost and the invariant's proof. Org layer (M12) extends the same model upward.

## ADR-007 · Budget enforcement: pre-call estimate + post-call meter — **DECIDED**
**Context:** Invariant: budget hard-stops never overrun by >1 run-step (PRD §11), at every price point.
**Options:** (a) post-only; (b) pre+post; (c) pre-call worst-case reservation.
**Decision:** (b). Pre-call: estimated cost (prompt tokens × price + max_tokens ceiling) must fit remaining budget or the step is refused; post-call: actual cost decrements under row-level locking.
**Consequences:** ~1 fd over post-only; the invariant becomes a property test. Concurrent runs contend on the budget row — acceptable at MVP scale, revisit with a token-bucket if contention shows.

## ADR-008 · Tool plane: Fleet-native MCP broker — **DECIDED**
**Context:** Consolidation veto removed Offside Router as the mandated tool plane; the security story (model never holds credentials; every call audited) must survive.
**Options:** (a) Fleet-native broker; (b) Router as external dependency; (c) direct MCP connections, broker later.
**Decision:** (a). MCP client + broker in the runtime path: deny-by-default per-agent allowlists, secret injection at call time only, verbatim tool I/O into RunSteps, every call ledgered. Router can later be consumed as just another MCP server.
**Consequences:** We own tool integrations (cost accepted: M4 + M11 budgets exist for exactly this). No external uptime dependency in the security path.

## ADR-009 · Replay strategy: replay-complete traces from M1, engine in M6 (inside MVP) — **DECIDED** (founder override; dissent on record)
**Context:** Founder pulled the replay engine into the MVP against recommendation.
**Options:** (a) record-only now, engine Phase B; (b) engine in MVP.
**Decision:** (b), with guardrails: RunStep schema is replay-complete from M1 (verbatim I/O, seeds, clock reads, provider tags); replay mode stubs the model and tool planes from the recording with no-network enforcement and first-divergence reporting; a **fallback gate at M5 exit** (pre-agreed) drops back to (a) if M6 tracks >150%.
**Consequences:** Highest-risk item inside the ship gate; in exchange, every recorded run is a regression fixture from day one and "flight recorder you can re-fly" is a launch differentiator.

## ADR-010 · Secrets: two-tier; customer secrets plaintext at rest — **DECIDED** (founder override; dissent + tripwire on record)
**Context:** Platform secrets belong in DO env config. Founder chose plaintext Postgres rows for customer tool credentials over envelope encryption.
**Options:** (a) envelope encryption (per-workspace data keys, DO-env master key); (b) plaintext rows; (c) Vault-class service.
**Decision:** (b), with hard boundaries that hold regardless of at-rest format: workspace-scoped rows; decrypted/read only inside the broker at call time; never in runner env, model context, traces, or logs (structural redaction, CI grep test). **Tripwire (M7.S5):** before the first external-partner credential, land (a) (~1 fd) or founder re-accepts plaintext on the record.
**Consequences:** Until the tripwire: SQL injection, backup leakage, or admin compromise yields working third-party credentials. Documented in RISKS.md as the top standing security risk.

## ADR-011 · Memory: pgvector semantic memory; embedding provider — **DECISION NEEDED** (blocks M3, not M1)
**Context:** Founder added semantic memory to the MVP. Anthropic ships no embeddings API; an external embedding provider is unavoidable.
**Options:** (a) **Voyage AI** (Anthropic-recommended; strong retrieval quality; one more vendor); (b) OpenAI `text-embedding-3-small` (cheap, ubiquitous; ironic before M9 but contractually fine); (c) open-weights embeddings self-hosted (no vendor, ops cost).
**Recommendation:** (a) Voyage — retrieval quality is the persona-illusion's ceiling, price difference is noise at MVP volume.
**Consequences of deferral:** none before M3; embedding vectors are provider-tagged in `MemoryChunk` so a later switch re-embeds incrementally.

## ADR-012 · Chat transport: SSE now, WebSockets at M14 — **DECIDED**
**Context:** 1:1 chat needs server→client streaming; shared channels (M14) need bidirectional realtime + presence.
**Options:** (a) SSE now, WS later; (b) WS now.
**Decision:** (a). SSE through the control plane for chat/run streaming (App-Platform-friendly, no connection-state service); WS layer is an explicit M14.S1 task.
**Consequences:** One transport migration at M14, contained to the realtime layer; chat persistence/trace pipeline is transport-agnostic by design.

## ADR-013 · Web search provider — **DECISION NEEDED** (blocks M4.S3, not M1–M3)
**Context:** Platform-keyed search is a launch tool; per-call cost feeds run metering.
**Options:** (a) **Exa** (research-grade results, neural search; pricier); (b) Brave Search API (cheap, conventional).
**Recommendation:** (a) Exa — the dogfood fleet is research-digest-shaped and result quality is the visible product surface; revisit cost at Phase B with real volume.
**Consequences of deferral:** none before M4; the tool interface hides the provider.
