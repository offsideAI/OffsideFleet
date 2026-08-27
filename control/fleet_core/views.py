import subprocess
from functools import lru_cache

from django.http import HttpRequest, JsonResponse


@lru_cache(maxsize=1)
def _git_sha() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            ).stdout.strip()
            or "unknown"
        )
    except Exception:
        return "unknown"


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok", "sha": _git_sha()})
