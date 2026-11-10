"""M37500: catalog invariants and staging-only SQL, never a DB apply."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "backend/migration_catalog_ai_studio.json"
FILES = {
    "066": ROOT / "backend/staging_migrations/066_release_gate_evidence_quarantine_ci_only.sql",
    "067": ROOT / "backend/staging_migrations/067_mail_delivery_quarantine_ci_only.sql",
    "068": ROOT / "backend/staging_migrations/068_payment_reconciliation_hold_ci_only.sql",
}


@pytest.fixture(scope="module")
def catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_catalog_109_namespaces_and_no_unregistered_new_sql(catalog):
    assert len(catalog["entries"]) == 109
    assert len({entry["id"] for entry in catalog["entries"]}) == 109
    assert len({entry["source_path"] for entry in catalog["entries"]}) == 109
    assert all(path.is_file() for path in FILES.values())


@pytest.mark.parametrize("number", ["066", "067", "068"])
def test_each_staging_migration_registered_and_hash_locked(catalog, number):
    path = FILES[number]
    item, = [e for e in catalog["entries"] if e["id"] == "staging_migrations:" + number]
    assert item["source_path"] == str(path.relative_to(ROOT))
    assert item["classification"] == "STAGING_ONLY_NEEDS_PORT"
    assert item["do_not_apply_source_to_termux"] is True
    assert item["requires_local_equivalent_before_use"] is True
    sha = subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()
    assert sha == item["source_blob_sha"]


@pytest.mark.parametrize("number", ["066", "067", "068"])
def test_each_sql_requires_disposable_db_and_ci_flag(number):
    sql = FILES[number].read_text(encoding="utf-8")
    for required in (
        "current_database() <> 'frcaixinha_staging'",
        "session_user <> 'postgres'",
        "current_setting('is_superuser') <> 'on'",
        "current_setting('frfinance.m37500_ci', true)",
        "FORCE ROW LEVEL SECURITY",
        "REVOKE ALL", "BEFORE UPDATE OR DELETE", "BEFORE TRUNCATE",
    ):
        assert required in sql
    for forbidden in ("ALTER SYSTEM", "CREATE USER", "CREATE ROLE",
                      "SECURITY DEFINER", "GRANT ALL", "DROP TABLE",
                      "CREATE EXTENSION", "COPY ", "dblink"):
        assert forbidden not in sql
    assert re.search(r"BEGIN;.*COMMIT;", sql, re.S)


def test_first_migration_defines_immutable_trigger_reused_by_next_two():
    sql = FILES["066"].read_text(encoding="utf-8")
    assert "CREATE FUNCTION public.fr_m37500_quarantine_immutable_ci()" in sql
    for number in ("067", "068"):
        assert "public.fr_m37500_quarantine_immutable_ci()" in FILES[number].read_text()


def test_new_schema_never_has_real_execution_flags_set():
    combined = "\n".join(path.read_text() for path in FILES.values())
    assert "CHECK (NOT real_activation_authorized)" in combined
    assert "CHECK (NOT pix_real_authorized)" in combined
    assert "CHECK (NOT real_mail_sent)" in combined
    assert "CHECK (NOT ledger_written)" in combined
    assert "CHECK (NOT real_gate_verified)" in combined


def test_migration_preflight_script_readonly_runs(capsys):
    path = ROOT / "backend/scripts/aistudio_m37500_migration_preflight.py"
    spec = importlib.util.spec_from_file_location("m37500_migrate", path)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.main() == 0
    output = capsys.readouterr().out
    assert "M37500_MIGRATION_PREFLIGHT=PASS" in output
    assert "M37500_SOURCE_MIGRATION_REGISTERED=YES" in output
    assert "M37500_ORIGINAL_POSTGRES_TOUCHED=NO" in output
