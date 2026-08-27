# OffsideFleet agent-loop image. Runs hardened (non-root, RO rootfs, no caps,
# egress only via proxy, no ambient credentials) — flags enforced by the
# gateway at `docker run` time, not here.
#
# Build from the REPO ROOT (context needs packages/ir):
#   docker build -f runner/agent/Dockerfile -t offsidefleet-agent:dev .
FROM python:3.12-slim

RUN pip install --no-cache-dir "anthropic>=1.0" "httpx2>=0.1"

WORKDIR /app
COPY runner/agent/ /app/agent/
# Shared price table (single source of truth: packages/ir/prices.json).
COPY packages/ir/prices.json /app/agent/prices.json

USER 65534:65534
ENTRYPOINT ["python", "-m", "agent.loop"]
