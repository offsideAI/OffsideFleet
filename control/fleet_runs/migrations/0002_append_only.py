"""DB-level append-only enforcement for RunStep and LedgerEntry (⛔ tables).

Postgres-only: triggers reject UPDATE/DELETE regardless of the connecting
role. On sqlite (local quick tests) this is a no-op; CI runs Postgres and
exercises the enforcement test.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION fleet_reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'append-only table: % on % is forbidden', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER runstep_append_only
    BEFORE UPDATE OR DELETE ON fleet_runs_runstep
    FOR EACH ROW EXECUTE FUNCTION fleet_reject_mutation();

CREATE TRIGGER ledgerentry_append_only
    BEFORE UPDATE OR DELETE ON fleet_runs_ledgerentry
    FOR EACH ROW EXECUTE FUNCTION fleet_reject_mutation();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS runstep_append_only ON fleet_runs_runstep;
DROP TRIGGER IF EXISTS ledgerentry_append_only ON fleet_runs_ledgerentry;
DROP FUNCTION IF EXISTS fleet_reject_mutation();
"""


def apply_forward(apps, schema_editor):  # type: ignore[no-untyped-def]
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD)


def apply_backward(apps, schema_editor):  # type: ignore[no-untyped-def]
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(BACKWARD)


class Migration(migrations.Migration):
    dependencies = [("fleet_runs", "0001_initial")]
    operations = [migrations.RunPython(apply_forward, apply_backward)]
