"""Procrastinate app for the control plane.

Standalone Procrastinate (not the Django contrib) so the job queue schema is
managed by `procrastinate schema --apply` and tests can use the in-memory
connector without a Postgres dependency.

Worker: uv run procrastinate --app=offsidefleet.jobs.app worker
"""

import os

from environs import Env
from procrastinate import App, PsycopgConnector

env = Env()
env.read_env()


def _conninfo() -> str:
    db_url = env.str("DATABASE_URL", default="")
    if db_url:
        return db_url
    return "postgresql://{user}:{password}@{host}:{port}/{name}".format(
        user=env.str("FLEET_DB_USER", default="fleet"),
        password=env.str("FLEET_DB_PASSWORD", default="fleet"),
        host=env.str("FLEET_DB_HOST", default="localhost"),
        port=env.str("FLEET_DB_PORT", default="5432"),
        name=env.str("FLEET_DB_NAME", default="fleet"),
    )


app = App(connector=PsycopgConnector(conninfo=_conninfo()))


@app.task(name="fleet_runs.dispatch_run", retry=3)
def dispatch_run(run_id: str, callback_token: str) -> None:
    """Dispatch a queued Run to the runner-gateway."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "offsidefleet.settings")
    import django

    django.setup()

    from fleet_runs.dispatch import dispatch

    dispatch(run_id, callback_token)
