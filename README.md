# OffsideFleet

Fleet console for cloud AI agents: build named agents with identities, chat with
them, schedule them, and watch every action as a traced, budgeted, replayable,
killable Run.

**Status:** Milestone 1 (Runtime Spine) — see `ROADMAP.md`, `plan/`, `DECISIONS.md`.

## Layout

| Path | What |
|---|---|
| `control/` | Control plane — Django 5 + DRF + Procrastinate (runs, traces, ledger) |
| `runner/` | Data plane — FastAPI runner-gateway, hardened agent containers, egress+model proxy |
| `console/` | SvelteKit console (Signal Box design language) |
| `packages/ir/` | Shared contracts (price table; Blueprint IR schema from M2) |
| `infra/` | docker-compose dev stack |
| `plan/` | Phase-2 planning artifacts (approved PLAN v1) |

## Dev quickstart

Prereqs: `uv`, `node 22+`, Docker, `just`, and `ANTHROPIC_API_KEY` exported
(the key lives ONLY in the egress proxy — never in agent containers).

```sh
just infra      # postgres + egress/model proxy + networks + migrations + agent image
just api        # terminal 1 — control-plane API :8000
just worker     # terminal 2 — procrastinate worker
just gateway    # terminal 3 — runner-gateway :8100
just console    # terminal 4 — console :5173

just test       # all unit/integration tests
just lint       # ruff + mypy strict + eslint + svelte-check
just test-docker  # sandbox-escape + kill-timing suite (needs Docker)
just demo-m1    # M1 acceptance demo
```
