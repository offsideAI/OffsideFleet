# DATA_MODEL.md — OffsideFleet

Postgres 16 (DO managed) + pgvector. Single shared schema, multi-tenant. Conventions:

- **Tenancy:** every tenant-owned table carries `workspace_id FK → workspaces` with a composite index `(workspace_id, …)` matching its hot query. Access only via tenant-scoped ORM managers (ADR-006).
- **Keys:** `id UUID PK` (v7 for index locality). Timestamps `created_at`/`updated_at TIMESTAMPTZ` everywhere (omitted below for brevity).
- **Immutability:** tables marked ⛔ are append-only — `UPDATE`/`DELETE` revoked from the app role at the DB level (a narrowly-scoped migration role exists for schema changes only). Enforced-by-grant, tested in CI.
- **Soft delete** (`deleted_at`) on user-facing containers (blueprints, agents, conversations); hard delete never cascades into ⛔ tables.

## Identity & tenancy

### users
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| email | citext UNIQUE | |
| name, avatar_url | text | |
| is_active | bool | |

### workspaces
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| name, slug | text; slug UNIQUE | |
| organization_id | uuid FK NULL | M12; NULL until org layer |
| plan_tier | enum(hangar, squadron, fleet) | denormalized from billing for quota checks |
| settings | jsonb | notification prefs etc. |

### workspace_memberships
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | UNIQUE(workspace_id, user_id) |
| user_id | uuid FK | index (user_id) — membership lookup is the auth hot path |
| role | enum(owner, admin, member) | |

### organizations (M12; created now as empty table? **No** — deferred to its milestone; listed for shape only)

## Blueprints & agents

### blueprints
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | idx (workspace_id, deleted_at) |
| name | text | display identity lives in IR; this is the admin label |
| current_version_id | uuid FK → blueprint_versions | head pointer |
| deleted_at | timestamptz NULL | |

### blueprint_versions ⛔
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | denormalized for tenant scoping of reads |
| blueprint_id | uuid FK | UNIQUE(blueprint_id, version_number) |
| version_number | int | monotonic per blueprint |
| ir | jsonb | validated Blueprint IR (schemaVersion inside) |
| ir_schema_version | text | for migration queries |
| author_id | uuid FK users | |
| changelog | text | |
**Immutability:** append-only; "editing" always inserts version N+1 and repoints `blueprints.current_version_id`.

### agents
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | idx (workspace_id, status) |
| blueprint_id | uuid FK | |
| pinned_version_id | uuid FK blueprint_versions | what actually runs; rollback = repoint |
| environment | enum(draft, staging, live) | M10; default live in MVP |
| status | enum(active, paused, killed) | paused/killed block new runs |
| budget_daily_cents, budget_monthly_cents | int NULL | NULL = workspace default |
| spend_today_cents, spend_month_cents | bigint | cached counters; source of truth = ledger |

### fleets (M8)
`id, workspace_id, name, orchestration_id FK NULL, budget_*` — group of agents via `fleet_members(fleet_id, agent_id)`.

### orchestrations (M8)
`id, workspace_id, fleet_id, ir jsonb (pattern, stages, budgets, approval nodes), version int` — versioned like blueprints when the DAG editor lands (M18).

## Execution

### runs
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | idx (workspace_id, agent_id, created_at DESC) — trace lists; idx (workspace_id, state) — live dashboards |
| agent_id | uuid FK | |
| blueprint_version_id | uuid FK | exact config that ran (replay anchor) |
| orchestration_run_id | uuid FK runs NULL | parent, for M8 child runs |
| trigger_kind | enum(chat, manual, schedule, webhook, agent) | webhook/agent from Phase B |
| trigger_id | uuid FK triggers NULL | |
| conversation_id | uuid FK NULL | chat-triggered runs |
| state | enum(queued, running, succeeded, failed, killed, budget_stopped) | state machine enforced in model layer |
| error | jsonb NULL | |
| cost_cents_total | bigint | denormalized sum of steps |
| token_usage | jsonb | per-provider in/out totals |
| started_at, ended_at | timestamptz | runner p95 metrics derive from these |
| replayable | bool | validator result (M6.S1) |
| replay_of_run_id | uuid FK runs NULL | set on replay executions |

### run_steps ⛔
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | idx (run_id, step_index) UNIQUE |
| run_id | uuid FK | |
| step_index | int | monotonic within run |
| kind | enum(model_call, tool_call, memory_retrieval, policy_check, budget_check, system) | |
| provider | text NULL | model steps: anthropic/openai/…; replay stubbing key |
| request_payload | jsonb | **verbatim** outbound (redacted-by-construction for secrets) |
| response_payload | jsonb | **verbatim** inbound |
| rng_seed | bigint NULL | replay determinism |
| clock_reads | jsonb | timestamps observed by the loop during the step |
| tokens_in, tokens_out | int | model steps |
| cost_cents | bigint | computed at write time from the price table version |
| price_table_version | text | so historical cost is reproducible |
| duration_ms | int | |
**Replay-completeness:** the M6.S1 validator asserts the presence/shape of every field replay needs; CI-enforced on run-producing tests.

### triggers
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id, agent_id | FKs | idx (workspace_id, agent_id) |
| kind | enum(schedule, webhook, event, agent) | MVP: schedule only |
| cron, timezone | text | schedule kind |
| enabled | bool | |
| config | jsonb | webhook secrets etc. (Phase B) |
| last_fired_at | timestamptz | misfire/skip bookkeeping |

## Conversations & memory

### conversations
`id, workspace_id, agent_id, user_id, title, deleted_at` — UNIQUE(workspace_id, agent_id, user_id) in MVP (one 1:1 thread per user-agent pair). idx (workspace_id, agent_id).

### messages
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id, conversation_id | FKs | idx (conversation_id, seq) UNIQUE |
| seq | bigint | monotonic per conversation |
| role | enum(user, agent, system) | |
| content | text | rendered text; the verbatim model I/O lives in run_steps |
| run_id | uuid FK runs NULL | every agent message links to its run |

### memory_chunks
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id, agent_id | FKs | **scoping is the isolation boundary**: retrieval always filters (workspace_id, agent_id) |
| source_kind | enum(conversation, notes) | |
| source_id | uuid | message/notes ref |
| content | text | chunk text |
| embedding | vector(n) | pgvector; dimension per ADR-011 provider |
| embedding_provider, embedding_model | text | incremental re-embedding on provider switch |
Index: HNSW on `embedding` partial per common filters; btree (workspace_id, agent_id).

### agent_notes
`id, workspace_id, agent_id UNIQUE, content text, revision int` — the built-in notes doc; edits appear as tool-call run_steps.

## Policy, audit, secrets

### policies (schema in MVP; engine grows through M8/M17)
`id, workspace_id, name, ir jsonb (rules: tool allowlists, spend caps, approval conditions, kill conditions), enabled` + `policy_bindings(policy_id, target_kind enum(agent, fleet, workspace), target_id)`.

### ledger_entries ⛔
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | idx (workspace_id, created_at DESC); idx (workspace_id, run_id) |
| actor_kind | enum(user, agent, system) | |
| actor_id | uuid NULL | |
| action | text | e.g. run.killed, tool.call, secret.created, billing.quota_stop, version.rollback, approval.granted |
| run_id, agent_id | uuid NULL | correlation |
| payload | jsonb | action detail (secret values structurally excluded) |
| prev_hash, entry_hash | bytea | hash chain per workspace — tamper-evidence for exports |
**Every privileged action lands here** (engineering standard). Export = ordered rows + chain verification.

### secrets
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | UNIQUE(workspace_id, name) |
| name | text | |
| kind | enum(api_key, oauth_token, webhook_url, header_cred) | |
| value | text | **plaintext at rest per ADR-010 (founder override; tripwire M7.S5)** — column named to become `value_ciphertext` without table churn |
| oauth_meta | jsonb NULL | refresh token, expiry, scopes (Google) |
| last_used_at | timestamptz | rotation hygiene |
Read path: broker only. Never serialized into runner env, model context, traces, or logs (CI grep test).

## Billing

### subscriptions
`id, workspace_id UNIQUE, stripe_customer_id, stripe_subscription_id, tier enum(hangar, squadron, fleet), status, current_period_start/end` — Stripe is the source of truth; this is the cache webhooks maintain.

### usage_events ⛔
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| workspace_id | uuid FK | idx (workspace_id, created_at); idx (reported_at NULLS FIRST) — reporter queue |
| run_id | uuid FK | |
| kind | enum(tokens, tool_call, voice_minutes) | voice from M17 |
| quantity | bigint | e.g. token count |
| cost_cents | bigint | pass-through + margin, price-table-versioned |
| stripe_meter_event_id | text NULL | set when reported; reconciliation key |
| reported_at | timestamptz NULL | |

### quota_counters
`workspace_id, period (yyyy-mm), runs_count, agents_count` — cheap tier-quota checks; rebuilt from ledger on drift.

## Migration & integrity strategy

- Forward-only migrations; every migration's reverse tested in CI against a seeded DB (standard), but rollback in prod = roll-forward fix.
- ⛔ tables: append-only grants tested by a CI suite that attempts UPDATE/DELETE as the app role and must fail.
- The IR and trace schemas are versioned (`ir_schema_version`, `price_table_version`, trace validator version); data migrations for old versions are explicit milestones tasks, never implicit.
- pgvector dimension is fixed per embedding provider; provider switch = new column + incremental backfill (ADR-011).
