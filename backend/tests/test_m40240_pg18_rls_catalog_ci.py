"""M40240: static-only contract of FR Finance's catalog-only RLS preflight."""
from pathlib import Path
import re

from backend.scripts.frfinance_m38794_project_isolation import (
    FINANCE_PGDATA, FINANCE_DB, FINANCE_OWNER,
)

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sql").read_text()
SHELL=(ROOT/"backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sh").read_text()
MIGRATION=(ROOT/"backend/migrations/110_fr_finance_special_credit_offline.sql").read_text()


def test_original_cluster_identity_is_hardcoded_and_readonly():
    assert FINANCE_PGDATA in SQL
    assert FINANCE_DB in SQL
    assert FINANCE_OWNER in SQL
    for phrase in ("current_database()","current_user","session_user",
                   "inet_server_addr()", "inet_server_port()",
                   "current_setting('data_directory')",
                   "current_setting('server_version_num')",
                   "current_setting('transaction_read_only')",
                   "BEGIN READ ONLY;", "ROLLBACK;"):
        assert phrase in SQL
    assert "M40240_AUTHENTICATED_RLS_DATA_PLANE=NOT_TESTED" in SQL


def test_exact_six_special_credit_rls_tables_from_migration_110():
    expected = (
        "special_credit_grants", "special_credit_campaigns",
        "special_credit_recipients", "special_credit_preferences",
        "special_credit_outbox", "special_credit_audit",
    )
    tables = set(re.findall(r"^\s*\('((?:special_credit_[a-z_]+))'\),?$",
                            SQL, flags=re.M))
    assert tables == set(expected)
    for table in expected:
        assert "ALTER TABLE public." + table + " ENABLE ROW LEVEL SECURITY;" in MIGRATION
        assert "ALTER TABLE public." + table + " FORCE ROW LEVEL SECURITY;" in MIGRATION


def test_exact_sixteen_migration_policies():
    source = set(re.findall(r"^CREATE POLICY (\w+) ON public\.(\w+)", MIGRATION, re.M))
    listed = set((name, table) for table, name in re.findall(
        r"\('(special_credit_[a-z_]+)','(sc_[a-z_]+)'\)", SQL))
    assert len(listed) == 16
    assert listed == source
    assert "M40240_POLICY_CATALOG=PASS_16_OF_16_NAMED_POLICIES" in SQL


def test_roles_no_bypass_and_fail_closed_on_first_missing_catalog():
    for role in ("frc_ai_app", "frc_ai_auth", "frc_ai_verifier"):
        assert role in SQL
    assert "NOT rolsuper AND NOT rolbypassrls" in SQL
    assert SQL.count("SELECT 1 / CASE WHEN") == 7
    assert SQL.count("THEN 1 ELSE 0 END") == 7
    assert "M40240_LIVE_POLICY_CATALOG=PASS_METADATA_ONLY" in SQL
    assert "M40240_STATUS=PASS_LIVE_RLS_CATALOG_ONLY" in SHELL


def test_sql_has_no_dml_ddl_queries_or_secret_access():
    stripped = re.sub(r"(?m)^--.*$", "", SQL)
    # Ignore SQL string literals and psql diagnostic messages, never SQL verbs.
    stripped = re.sub(r"(?m)^\s*\\echo[^\n]*$", "", stripped)
    stripped = re.sub(r"'(?:''|[^'])*'", "''", stripped)

    for pattern in (
        r"\b(?:INSERT|UPDATE|DELETE|TRUNCATE|CREATE|ALTER|DROP|GRANT|REVOKE|COPY)\b",
        r"\\(?:!|copy|gexec|include|i|setenv|o)\b",
        r"\bFROM\s+(?:public\.(?!pg_|pg_catalog)|users|sessions|memberships)\b",
        r"\bpg_read_file\b",
    ):
        assert re.search(pattern, stripped, flags=re.I) is None, pattern


def test_shell_environment_password_isolation_and_no_restart():
    assert "env -i" in SHELL
    assert "PGOPTIONS=" in SHELL and "default_transaction_read_only=on" in SHELL
    assert '"$PREFIX/bin/psql"' in SHELL
    assert " -X -W -q -t -A -v ON_ERROR_STOP=1" in SHELL
    for argument in ("-h 127.0.0.1 -p 5433",
                     "-U frc_ai_owner", "-d frcaixinha_aistudio_dev"):
        assert argument in SHELL
    for secret in ("PGPASSWORD", "api.env", "DATABASE_URL", "AUTH_DATABASE_URL"):
        assert secret not in SHELL
    for command in ("pg_ctl start", "pg_ctl restart", "pg_ctl stop",
                    "psql -c", "psql -f /root", "pg_resetwal", "&& sudo"):
        assert command not in SHELL
