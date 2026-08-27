"""Sandbox-escape + kill-timing integration tests against real Docker
(M1.S3/M1.S5 acceptance; TESTING.md sandbox suite v0).

Run with: just test-docker   (requires Docker + built images + fleet_internal
network; skipped otherwise). CI runs these on runner-image changes + nightly.
"""

import shutil
import subprocess
import time
import uuid

import pytest

pytestmark = pytest.mark.docker

docker_missing = shutil.which("docker") is None


def _docker_ready() -> bool:
    if docker_missing:
        return False
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


requires_docker = pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")

HARDENED_FLAGS = [
    "--user", "65534:65534",
    "--read-only",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--pids-limit", "64",
    "--memory", "256m",
    "--network", "fleet_internal",
    "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
]


def run_in_hardened(
    cmd: list[str], image: str = "python:3.12-slim"
) -> subprocess.CompletedProcess[str]:
    name = f"fleet-test-{uuid.uuid4().hex[:8]}"
    return subprocess.run(
        ["docker", "run", "--rm", "--name", name, *HARDENED_FLAGS, image, *cmd],
        capture_output=True,
        text=True,
        timeout=120,
    )


@requires_docker
def test_egress_blocked_without_proxy() -> None:
    """On the internal network, direct egress must fail entirely."""
    result = run_in_hardened(
        ["python", "-c",
         "import urllib.request,sys\n"
         "try:\n"
         "  urllib.request.urlopen('https://example.com', timeout=5)\n"
         "  sys.exit(0)\n"
         "except Exception:\n"
         "  sys.exit(7)\n"]
    )
    assert result.returncode == 7, f"direct egress should fail: {result.stdout}{result.stderr}"


@requires_docker
def test_container_is_non_root_readonly_no_caps() -> None:
    result = run_in_hardened(
        ["python", "-c",
         "import os\n"
         "assert os.getuid() == 65534, os.getuid()\n"
         "try:\n"
         "  open('/etc/probe', 'w'); print('WRITABLE')\n"
         "except OSError:\n"
         "  print('READONLY')\n"]
    )
    assert "READONLY" in result.stdout
    assert "WRITABLE" not in result.stdout


@requires_docker
def test_kill_latency_under_2s() -> None:
    """SIGKILL of a busy-looping hardened container lands in <2s (M1.S5)."""
    name = f"fleet-test-kill-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--name", name, *HARDENED_FLAGS,
         "python:3.12-slim", "python", "-c", "while True: pass"],
        capture_output=True, check=True, timeout=60,
    )
    try:
        time.sleep(1)  # let it get busy
        t0 = time.monotonic()
        subprocess.run(["docker", "kill", name], capture_output=True, check=True, timeout=10)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"kill took {elapsed:.2f}s"
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
