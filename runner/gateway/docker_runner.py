"""Hardened per-run container execution (M1.S3, ADR-002).

Profile: non-root, read-only rootfs + tmpfs workdir, all capabilities
dropped, no-new-privileges, cpu/mem/pids limits, wall-clock kill, internal
network only (egress solely via the allowlist proxy), no ambient credentials.
"""

import json
import logging
import threading
import time
from typing import Any

import docker
from docker.errors import APIError, NotFound

from .config import config

logger = logging.getLogger("gateway.docker")

_client: docker.DockerClient | None = None


def client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def container_name(run_id: str) -> str:
    return f"fleet-run-{run_id}"


def start_run_container(run_id: str, run_spec: dict[str, Any]) -> str:
    """Start the hardened agent container for a run. Returns container id."""
    spec = dict(run_spec)
    spec["control_plane_url"] = config.control_plane_url

    environment = {
        # The run spec (incl. the run-scoped callback token) is the ONLY
        # credential-bearing material in this container.
        "RUN_SPEC_JSON": json.dumps(spec),
        "FLEET_EGRESS_PROXY_URL": config.egress_proxy_url,
        "FLEET_MODEL_PROXY_URL": config.model_proxy_url,
    }

    cont = client().containers.run(
        image=config.agent_image,
        name=container_name(run_id),
        detach=True,
        environment=environment,
        network=config.agent_network,
        user="65534:65534",
        read_only=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        pids_limit=config.pids_limit,
        mem_limit=config.mem_limit,
        nano_cpus=config.nano_cpus,
        tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
        auto_remove=False,
        labels={"offsidefleet.run_id": run_id},
    )

    # Wall-clock enforcement: SIGKILL at the deadline (15-min default cap).
    timer = threading.Timer(config.run_timeout_seconds, _timeout_kill, args=[run_id])
    timer.daemon = True
    timer.start()

    logger.info("run %s container started (%s)", run_id, cont.short_id)
    return str(cont.id)


def _timeout_kill(run_id: str) -> None:
    try:
        killed = kill_run_container(run_id)
        if killed["found"]:
            logger.warning("run %s hit wall-clock limit; killed", run_id)
    except Exception:
        logger.exception("timeout kill of run %s failed", run_id)


def kill_run_container(run_id: str) -> dict[str, Any]:
    """SIGKILL the run's container. Returns {found, killed_in_ms}."""
    t0 = time.monotonic()
    try:
        cont = client().containers.get(container_name(run_id))
    except NotFound:
        return {"found": False, "killed_in_ms": None}
    try:
        cont.kill()  # SIGKILL by default
    except APIError as exc:
        # Already exited between get() and kill() — that's a successful kill
        # from the caller's perspective.
        if "is not running" not in str(exc):
            raise
    killed_in_ms = int((time.monotonic() - t0) * 1000)
    logger.info("run %s killed in %sms", run_id, killed_in_ms)
    return {"found": True, "killed_in_ms": killed_in_ms}


def run_container_status(run_id: str) -> dict[str, Any]:
    try:
        cont = client().containers.get(container_name(run_id))
    except NotFound:
        return {"found": False, "status": None}
    return {"found": True, "status": cont.status}
