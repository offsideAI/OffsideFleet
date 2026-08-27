# OffsideFleet — every workflow is one command.
# just dev / just test / just lint / just demo-m1

set dotenv-load := true

repo := justfile_directory()

default:
    @just --list

# ---------------------------------------------------------------------------
# Dev environment (run these in YOUR terminal; each blocks)
# ---------------------------------------------------------------------------

# Infra: postgres + egress/model proxy + docker networks. Needs ANTHROPIC_API_KEY.
infra:
    docker compose -f infra/docker-compose.dev.yml up -d --build
    docker build -f runner/agent/Dockerfile -t offsidefleet-agent:dev .
    cd control && uv run python manage.py migrate
    cd control && uv run procrastinate --app=offsidefleet.jobs.app schema --apply

# Control-plane API (terminal 1)
api:
    cd control && uv run python manage.py runserver 0.0.0.0:8000

# Procrastinate worker (terminal 2)
worker:
    cd control && uv run procrastinate --app=offsidefleet.jobs.app worker

# Runner-gateway (terminal 3)
gateway:
    cd runner && FLEET_CONTROL_PLANE_URL=http://host.docker.internal:8000 \
        uv run uvicorn gateway.main:app --port 8100

# Console dev server (terminal 4)
console:
    cd console && npm run dev

# ---------------------------------------------------------------------------
# Checks (safe to run anywhere)
# ---------------------------------------------------------------------------

test: test-control test-runner test-console

test-control:
    cd control && FLEET_TEST_SQLITE=1 uv run pytest

test-runner:
    cd runner && uv run pytest -m "not docker"

test-console:
    cd console && npm run test

# Sandbox-escape + kill-timing suite (needs Docker + `just infra` networks)
test-docker:
    cd runner && uv run pytest -m docker

lint:
    cd control && uv run ruff check . && FLEET_TEST_SQLITE=1 uv run mypy .
    cd runner && uv run ruff check . && uv run mypy .
    cd console && npm run lint && npm run check

# ---------------------------------------------------------------------------
# Demos
# ---------------------------------------------------------------------------

# M1 acceptance: create a run, watch the trace, verify egress-block, kill test.
# Prereqs: just infra + api + worker + gateway running.
demo-m1:
    uv run --with httpx2 python scripts/demo_m1.py
