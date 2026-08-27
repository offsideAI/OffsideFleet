"""Django settings for the OffsideFleet control plane."""

from pathlib import Path
from typing import Any

from environs import Env

env = Env()
env.read_env()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY: str = env.str("DJANGO_SECRET_KEY", default="dev-only-insecure-key")
DEBUG: bool = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "fleet_core",
    "fleet_runs",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "offsidefleet.urls"
WSGI_APPLICATION = "offsidefleet.wsgi.application"

TEMPLATES: list[dict[str, Any]] = []

# DATABASE_URL takes precedence (CI/prod); FLEET_DB_* pieces are the dev default.
from urllib.parse import urlparse  # noqa: E402

_db_url = env.str("DATABASE_URL", default="")
if _db_url:
    _parsed = urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _parsed.path.lstrip("/"),
            "USER": _parsed.username or "",
            "PASSWORD": _parsed.password or "",
            "HOST": _parsed.hostname or "localhost",
            "PORT": str(_parsed.port or 5432),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.str("FLEET_DB_NAME", default="fleet"),
            "USER": env.str("FLEET_DB_USER", default="fleet"),
            "PASSWORD": env.str("FLEET_DB_PASSWORD", default="fleet"),
            "HOST": env.str("FLEET_DB_HOST", default="localhost"),
            "PORT": env.str("FLEET_DB_PORT", default="5432"),
        }
    }

# Test runs may use sqlite (no Postgres locally); PG-only behaviors are skipped there
# and covered in CI, which runs against Postgres.
if env.bool("FLEET_TEST_SQLITE", default=False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": None,
}

CORS_ALLOWED_ORIGINS = env.list("FLEET_CORS_ORIGINS", default=["http://localhost:5173"])

USE_TZ = True
TIME_ZONE = "UTC"

# --- OffsideFleet-specific settings ---

# Runner-gateway internal API (ADR-004): control plane -> gateway.
RUNNER_GATEWAY_URL: str = env.str("FLEET_RUNNER_GATEWAY_URL", default="http://localhost:8100")
# Shared secret for control-plane <-> gateway calls. Dev default; set for real deploys.
INTERNAL_API_SECRET: str = env.str("FLEET_INTERNAL_API_SECRET", default="dev-internal-secret")

# Path to the shared price table (packages/ir is the single source of truth).
PRICES_PATH: Path = Path(
    env.str("FLEET_PRICES_PATH", default=str(BASE_DIR.parent / "packages" / "ir" / "prices.json"))
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{{"ts":"{asctime}","level":"{levelname}",'
                '"logger":"{name}","msg":"{message}"}}'
            ),
            "style": "{",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": env.str("FLEET_LOG_LEVEL", default="INFO")},
}
