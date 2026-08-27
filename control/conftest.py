import pytest
from django.db import connection

from fleet_core.models import Workspace


@pytest.fixture
def workspace(db: None) -> Workspace:
    return Workspace.objects.create(name="Test WS", slug="test-ws")


requires_postgres = pytest.mark.skipif(
    "sqlite" in connection.settings_dict["ENGINE"],
    reason="Postgres-only behavior (append-only triggers); covered in CI",
)
