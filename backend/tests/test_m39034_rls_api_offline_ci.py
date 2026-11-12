"""M39034: CI unit proof for PG18 real-role RLS and offline API boundary."""
from __future__ import annotations

from contextlib import nullcontext

import pytest

from backend.scripts import frfinance_m39034_rls_api_offline as m


class Rows:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value


class FakePg:
    def __init__(self, *, table_count=53, rls_enabled=True,
                 context_leak=False, bad_role=False, identity_ok=True):
        self.table_count = table_count
        self.rls_enabled = rls_enabled
        self.context_leak = context_leak
        self.bad_role = bad_role
        self.identity_ok = identity_ok
        self.role_switched = False
        self.queries = []

    def transaction(self):
        return nullcontext()

    def execute(self, query, args=None):
        self.queries.append((query, args))
        assert query.lstrip().startswith(
            ("SELECT", "SET TRANSACTION READ ONLY", "SET LOCAL ROLE")
        ), "Mutation attempted"
        if query == "SET TRANSACTION READ ONLY":
            return Rows(None)
        if query == "SET LOCAL ROLE frc_ai_app":
            self.role_switched = True
            return Rows(None)
        if "current_database(),session_user" in query:
            return Rows((
                m.DB if self.identity_ok else "not_original", m.OWNER,
                "127.0.0.1", 5433, m.DATA_DIRECTORY, 180006, "on",
            ))
        if "FROM pg_catalog.pg_tables" in query:
            return Rows((self.table_count,))
        if "SELECT current_user,session_user" in query:
            return Rows((
                "no_role" if self.bad_role else "frc_ai_app", m.OWNER,
            ))
        if "SELECT current_setting('transaction_read_only')" in query:
            return Rows(("on",))
        if "row_security_active" in query:
            return Rows((self.rls_enabled,))
        if "SELECT count(*) FROM public.special_credit_" in query:
            return Rows((1 if self.context_leak else 0,))
        if "SELECT set_config" in query:
            return Rows((args[1],))
        raise AssertionError("Unrecognized statement: " + query)


def test_m39034_readonly_app_role_rls_six_tables(capsys):
    f = FakePg()
    m.audit_local_rls(f)
    output = capsys.readouterr().out
    assert "M39034_PG18_ORIGINAL=PASS" in output
    assert "M39034_RLS_ACTIVE=6_OF_6" in output
    assert "M39034_PG_READ_ONLY=PASS" in output
    assert "M39034_NO_CONTEXT_VISIBILITY=0_OF_6" in output
    assert f.role_switched is True
    assert len([q for q,_ in f.queries if "row_security_active" in q])==6
    assert len([q for q,_ in f.queries
                if "SELECT count(*) FROM public.special_credit_" in q])==12


@pytest.mark.parametrize("settings,error",[
    ({"table_count":52}, "POST_MIGRATION_TABLE_COUNT_NOT_53"),
    ({"rls_enabled":False}, "RLS_NOT_ACTIVE_FOR_APP"),
    ({"context_leak":True}, "RLS_NO_CONTEXT_VISIBILITY"),
    ({"bad_role":True}, "APPLICATION_ROLE_NOT_ACTIVE"),
    ({"identity_ok":False}, "ORIGINAL_PG18_READONLY_IDENTITY_INVALID"),
])
def test_m39034_blocks_if_pg18_rls_or_identity_unsafe(settings,error):
    with pytest.raises(RuntimeError,match=error):
        m.audit_local_rls(FakePg(**settings))


def test_m39034_real_fastapi_router_requires_auth_and_sandbox_off(monkeypatch,capsys):
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX","YES")
    m.audit_api_offline()
    out=capsys.readouterr().out
    assert "M39034_API_ANONYMOUS_DENIED=PASS" in out
    assert "M39034_API_SANDBOX_OFF=PASS" in out
    assert "M39034_API_NETWORK_CALLS=NONE" in out
    assert __import__("os").environ["FR_FINANCE_SPECIAL_CREDIT_SANDBOX"] == "YES"


def test_m39034_never_runs_post_migration_sql_or_external_network():
    from pathlib import Path
    script=(Path(__file__).resolve().parents[1]/"scripts"/
            "frfinance_m39034_rls_api_offline.py").read_text()
    assert "verify_repo()" in script
    assert "default_transaction_read_only=on" in script
    assert "SET TRANSACTION READ ONLY" in script
    assert "SET LOCAL ROLE frc_ai_app" in script
    assert "row_security_active" in script
    assert "M39034_SQL110_111=ALREADY_APPLIED_DO_NOT_REPEAT" in script
    assert "psycopg.connect" in script
    assert "TestClient" in script
    assert "pg_dump" not in script
    assert "CREATE TABLE" not in script
    assert "DROP TABLE" not in script
    assert "INSERT INTO" not in script
