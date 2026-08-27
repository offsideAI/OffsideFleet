# API_SURFACE.md — OffsideFleet

Four surfaces: console REST API (DRF), runner-gateway internal API (FastAPI), webhook ingress (Phase B), CLI (M10). All console requests: session auth + `X-Workspace-Id` selector header (validated against membership, ADR-006). Errors: RFC-7807-style `{type, title, detail, field_errors?}`.

## Console REST API (DRF, `/api/v1`)

### Workspaces & auth
```
POST   /auth/magic-link                 # request sign-in
POST   /auth/session                    # exchange token → session
GET    /me                              # user + memberships
POST   /workspaces                      # create
GET    /workspaces/{id}
PATCH  /workspaces/{id}
GET    /workspaces/{id}/members         # + POST invite, DELETE remove
```

### Agents & blueprints
```
GET    /agents                          # roster (status, last run, spend today)
POST   /agents                          # create (body: blueprint IR) → creates blueprint+v1+agent
GET    /agents/{id}
PATCH  /agents/{id}                     # IR edit → NEW blueprint_version + repoint
POST   /agents/{id}/rollback            # {version_number}
GET    /agents/{id}/versions            # history
POST   /agents/{id}/pause | /resume
POST   /agents/{id}/kill                # kills agent's live runs + pauses
GET    /agents/{id}/triggers            # + POST/PATCH/DELETE (cron in MVP)
POST   /agents/{id}/run                 # run-now → {run_id}
```

### Chat
```
GET    /agents/{id}/conversation                    # messages (paginated, ?before_seq=)
POST   /agents/{id}/conversation/messages           # send → {message_id, run_id}
GET    /runs/{id}/stream                            # SSE: token deltas, step events, terminal state
```

### Runs, traces, replay
```
GET    /runs                            # ?agent_id&state&trigger_kind, paginated
GET    /runs/{id}                       # summary + cost
GET    /runs/{id}/steps                 # full trace (payloads on demand: ?include=payloads)
POST   /runs/{id}/kill
POST   /runs/{id}/replay                # M6 → {replay_run_id}; offline execution
GET    /runs/{id}/ledger.csv            # ledger export for the run (+ /workspaces/{id}/ledger.csv)
```

### Secrets, budgets, billing
```
GET    /secrets                         # names/kinds only — values never returned
POST   /secrets                         # {name, kind, value}
DELETE /secrets/{id}
GET    /integrations/google/connect     # OAuth start → redirect; /callback completes
GET    /budgets                         # workspace + per-agent
PUT    /budgets                         # set caps
GET    /billing/subscription            # tier, period, quotas + usage-to-date
POST   /billing/checkout                # {tier} → Stripe Checkout URL
POST   /billing/portal                  # Stripe customer portal URL
GET    /billing/usage                   # metered usage this period (live cost meter)
```

### Phase B+ additions (sketched, versioned into /api/v1 additively)
`/fleets`, `/orchestrations`, `/orchestrations/{id}/runs`, `/approvals` (+ signed-link endpoints `GET /a/{token}` approve/reject), `/providers`, environment promotion (`POST /agents/{id}/promote`), public API keys (M16 mirrors this surface under key auth).

## Webhook ingress (Phase B — contract fixed now)

```
POST /hooks/{workspace_slug}/{trigger_id}
  Headers: X-Fleet-Signature: hmac-sha256(body, trigger secret), X-Fleet-Timestamp
  Rules: timestamp skew ≤5m (replay protection), per-trigger rate limit,
         body (≤256KB) becomes run input verbatim; 202 {run_id} | 401 | 429
```

## Runner-gateway internal API (FastAPI, private network, shared-secret bearer)

```
POST /internal/runs/{id}/start     # body: {run_spec}  → 202
POST /internal/runs/{id}/kill      # → 200 {killed_at} — SIGKILL path, <2s budget
GET  /internal/runs/{id}/status
GET  /healthz                      # gateway + docker + proxy health (pager input)
```
Runner → control plane callbacks (run-scoped bearer token minted per run, only credential in the container):
```
POST /internal/callbacks/runs/{id}/steps        # append RunStep (batched)
POST /internal/callbacks/runs/{id}/state        # running/succeeded/failed
POST /internal/callbacks/runs/{id}/stream       # token deltas → SSE hub
POST /internal/callbacks/runs/{id}/budget-check # pre-call authorization {estimate_cents} → allow|deny
```
Budget pre-check lives control-plane-side (single source of truth, row locks); the loop calls it before every model/tool step.

## CLI (M10)

```
fleet login | logout | whoami
fleet deploy [path]        # TS DSL → IR → new blueprint version (+ --agent to repoint)
fleet diff [path]          # local IR vs live version
fleet promote <agent> --to staging|live
fleet agents | runs [--agent] [--follow]
fleet kill <run-id>
fleet replay <run-id>
```

## The critical 10 — request/response sketches

**1. Create agent** — `POST /api/v1/agents`
```json
{ "ir": { "schemaVersion": "1", "identity": {"name": "Scout", "avatarSeed": "scout-7", "persona": "Terse research analyst."},
  "model": {"provider": "anthropic", "id": "claude-sonnet-5", "maxTokens": 4096},
  "systemPrompt": "…", "tools": [{"id": "web_search"}, {"id": "web_fetch"}],
  "memory": {"semantic": true}, "budget": {"dailyCents": 200}, "triggers": [] } }
→ 201 { "agent": {"id": "…", "blueprint_id": "…", "version_number": 1, "status": "active"} }
→ 422 field-path errors from IR schema validation
```

**2. Send chat message** — `POST /api/v1/agents/{id}/conversation/messages`
```json
{ "content": "What changed in the HN top 10 since yesterday?" }
→ 202 { "message_id": "…", "run_id": "…", "stream_url": "/api/v1/runs/…/stream" }
```

**3. Run stream (SSE)** — `GET /api/v1/runs/{id}/stream`
```
event: delta          data: {"text": "Since yester"}
event: step           data: {"step_index": 2, "kind": "tool_call", "tool": "web_search", "cost_cents": 1}
event: state          data: {"state": "succeeded", "cost_cents_total": 14}
```

**4. Run trace** — `GET /api/v1/runs/{id}/steps?include=payloads`
```json
{ "run": {"id": "…", "state": "succeeded", "cost_cents_total": 14, "blueprint_version": 3},
  "steps": [ {"step_index": 0, "kind": "system", "duration_ms": 12},
    {"step_index": 1, "kind": "model_call", "provider": "anthropic", "tokens_in": 812, "tokens_out": 96, "cost_cents": 4,
     "request_payload": {…verbatim…}, "response_payload": {…verbatim…}},
    {"step_index": 2, "kind": "tool_call", "tool": "web_search", "request_payload": {…}, "response_payload": {…}, "cost_cents": 1} ] }
```

**5. Kill run** — `POST /api/v1/runs/{id}/kill` → `200 {"state": "killed", "killed_in_ms": 640}` (idempotent; 200 with current state if already terminal)

**6. Run-now** — `POST /api/v1/agents/{id}/run` `{"input": "optional task text"}` → `202 {"run_id": "…"}`

**7. Create secret** — `POST /api/v1/secrets` `{"name": "NOTION_TOKEN", "kind": "api_key", "value": "…"}` → `201 {"id": "…", "name": "NOTION_TOKEN"}` (value never echoed; subsequent GETs return metadata only)

**8. Set budgets** — `PUT /api/v1/budgets`
```json
{ "workspace": {"monthlyCents": 5000}, "agents": [{"agent_id": "…", "dailyCents": 100}] }
→ 200 with effective budgets; enforcement per ADR-007
```

**9. Replay** — `POST /api/v1/runs/{id}/replay` → `202 {"replay_run_id": "…"}`; replay run's summary carries `{"replay_of_run_id": "…", "divergence": null | {"first_step": 4, "diff": {…}}}`

**10. Stripe webhook** — `POST /api/v1/billing/stripe-webhook` (signature-verified) — handles `checkout.session.completed`, `customer.subscription.updated/deleted`, `invoice.*`; updates `subscriptions`, ledgered. Usage reporting is push-based from `usage_events` by a Procrastinate reconciler, not webhook-driven.
