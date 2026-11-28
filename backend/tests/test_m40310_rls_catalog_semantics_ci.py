"""FR Finance M40310 — original RLS catalog semantic inventory, offline CI only.

Validates M40240's same read-only SELECT script against migrations SQL110/111.
No database connection, credentials, user records, schema mutation or OCI.
A passing catalog check is NOT a proof of authenticated RLS data-plane behavior.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sql").read_text()
M110 = (ROOT / "backend/migrations/110_fr_finance_special_credit_offline.sql").read_text()
M111 = (ROOT / "backend/migrations/111_frfinance_special_credit_integrity_guards.sql").read_text()
SHELL = (ROOT / "backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sh").read_text()

METHODS = {"SELECT": "r", "INSERT": "a", "UPDATE": "w"}
EXPECTED_TABLES = {
    "special_credit_grants",
    "special_credit_campaigns",
    "special_credit_recipients",
    "special_credit_preferences",
    "special_credit_outbox",
    "special_credit_audit",
}


def m110_policies():
    return {
        (table, name, METHODS[operation.upper()])
        for name, table, operation in re.findall(
            r"CREATE POLICY\s+(\w+)\s+ON\s+public\.(\w+)"
            r"\s+FOR\s+(SELECT|INSERT|UPDATE)\s+TO\s+frc_ai_app",
            M110, flags=re.I,
        )
    }


def sql_expected_policies():
    return set(re.findall(
        r"\('(special_credit_[a-z_]+)','(sc_[a-z_]+)','([raw])'\)", SQL
    ))


def sql_expected_triggers():
    return set(re.findall(
        r"\('(special_credit_[a-z_]+)','(sc_m39020_[a-z_]+)',"
        r"'(sc_m39020_[a-z_]+)'\)", SQL
    ))


def m111_triggers():
    return {
        (table, trigger, function)
        for trigger, table, function in re.findall(
            r"CREATE TRIGGER\s+(\w+)\s+BEFORE\s+(?:INSERT|UPDATE)\s+"
            r"ON\s+public\.(\w+)\s+FOR EACH ROW\s+EXECUTE FUNCTION"
            r"\s+public\.(\w+)\s*\(\s*\)",
            M111, flags=re.I,
        )
    }


def test_migration_and_extended_policy_matrix_identical():
    assert len(m110_policies()) == 16
    assert sql_expected_policies() == m110_policies()
    assert {table for table, _, _ in sql_expected_policies()} == EXPECTED_TABLES


@pytest.mark.parametrize("policy", sorted(m110_policies()))
def test_each_real_policy_has_expected_command(policy):
    assert policy in sql_expected_policies()


def test_no_extra_policy_or_unscoped_role_can_pass():
    for guard in (
        "polcmd=operation",
        "polpermissive IS TRUE",
        "polroles=ARRAY[app_role_oid]",
        "operation='a' OR polqual IS NOT NULL",
        "operation='r' OR polwithcheck IS NOT NULL",
        "pg_catalog.pg_get_expr(p.polqual,p.polrelid)",
        "pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)",
        "count(*)=16",
        "FROM pg_catalog.pg_policy p",
        "JOIN pg_catalog.pg_namespace n",
        "M40310_POLICY_SHAPE=PASS_16_COMMAND_ROLE_CONTEXT_NO_EXTRA_POLICY",
    ):
        assert guard in SQL, guard


@pytest.mark.parametrize("setting", (
    "app.current_tenant_id",
    "app.current_user_id",
    "app.current_role",
))
def test_role_identity_scoping_required_in_policy_expressions(setting):
    assert "(q||w) LIKE '%" + setting + "%'" in SQL


def test_sql111_triggers_are_exactly_the_original_five():
    expected = sql_expected_triggers()
    assert len(expected) == 5
    assert expected == m111_triggers()
    assert "t.tgenabled='O'" in SQL
    assert "t.tgisinternal IS FALSE" in SQL
    assert "t.tgfoid" in SQL
    assert "fnsp.nspname='public'" in SQL
    assert "M40310_SQL111_TRIGGERS=PASS_5_ENABLED_INTEGRITY_TRIGGERS" in SQL


@pytest.mark.parametrize("privilege", ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"))
def test_application_role_has_no_dangerous_table_grant(privilege):
    guard = "NOT pg_catalog.has_table_privilege('frc_ai_app',c.oid,'" + privilege + "')"
    assert guard in SQL


def test_readonly_original_cluster_single_transaction_no_live_attestation():
    assert SQL.count("BEGIN READ ONLY;") == 1
    assert SQL.count("\nROLLBACK;") == 1
    assert SQL.count("SELECT 1 / CASE WHEN") == 7
    assert SQL.count("THEN 1 ELSE 0 END") == 7
    assert SQL.index("M40310_POLICY_SHAPE") < SQL.index("\nROLLBACK;")
    assert SQL.index("M40310_SQL111_TRIGGERS") < SQL.index("\nROLLBACK;")
    assert SQL.index("M40310_APP_PRIVILEGES") < SQL.index("\nROLLBACK;")
    for literal in (
        "M40310_STATUS=PASS_EXTENDED_CATALOG_METADATA_ONLY",
        "M40310_AUTHENTICATED_RLS_ENFORCEMENT=NOT_TESTED",
        "M40310_REAL_SESSIONS=NONE",
        "M40310_MIGRATIONS=NONE",
        "M40310_PRODUCTION=BLOCKED",
    ):
        assert literal in SQL


def test_extended_check_never_reads_rows_or_modifies_cluster():
    extra = SQL.split("-- M40310:",1)[1]
    extra = re.sub(r"(?m)^--.*$", "", extra)
    assert re.search(r"\b(FROM|JOIN)\s+public\.", extra, re.I) is None
    assert re.search(r"\b(?:INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|COPY)\s+",extra,re.I) is None
    assert "SET ROLE" not in extra
    assert "set_config(" not in extra
    assert "PGPASSWORD" not in SHELL and "env -i" in SHELL
    assert "-h 127.0.0.1 -p 5433" in SHELL
    assert "-d frcaixinha_aistudio_dev" in SHELL
    assert "M40240_STATUS=PASS_LIVE_RLS_CATALOG_ONLY" in SHELL


def test_catalog_existence_alone_is_not_data_plane_proof():
    assert "M40310_AUTHENTICATED_RLS_ENFORCEMENT=NOT_TESTED" in SQL
    assert "M40310_PRODUCTION=BLOCKED" in SQL
    assert "M40310_REAL_SESSIONS=NONE" in SQL
