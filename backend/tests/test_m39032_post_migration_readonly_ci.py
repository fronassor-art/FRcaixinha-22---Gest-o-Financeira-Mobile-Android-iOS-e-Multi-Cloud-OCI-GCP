"""FR Finance M39032: regression tests of READ ONLY post-migration proof."""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import re

import pytest

from backend.scripts import frfinance_m39032_post_migration_readonly as m


class Result:
    def __init__(self, data):
        self.data = data

    def fetchone(self):
        return self.data

    def fetchall(self):
        return self.data


class FakePg18:
    def __init__(self, **changes):
        self.changes = changes
        self.queries = []

    def transaction(self):
        return nullcontext()

    def execute(self, query, parameters=None):
        self.queries.append((query, parameters))
        assert query.lstrip().startswith(("SELECT", "SET TRANSACTION READ ONLY"))
        if query.startswith("SET TRANSACTION"):
            return Result(None)
        if "current_database(),current_user,session_user" in query:
            return Result((m.DB, m.OWNER, m.OWNER, "127.0.0.1", 5433,
                           m.DATA_DIRECTORY, 180006))
        if "FROM pg_catalog.pg_tables" in query:
            return Result((self.changes.get("total", 53),))
        if "FROM pg_class c JOIN pg_namespace" in query:
            r = [(name, "r", True, True) for name in m.SPECIAL]
            if self.changes.get("rls_off"):
                r[0] = (m.SPECIAL[0], "r", True, False)
            return Result(r)
        if "FROM pg_policies" in query:
            policies = [
                (name, policy)
                for name, expected in m.EXPECTED_POLICIES.items()
                for policy in expected
            ]
            if self.changes.get("missing_policy"):
                policies.pop()
            return Result(policies)
        if "FROM pg_trigger" in query:
            r = [
                (table, trigger, "O", function, "public")
                for trigger, (table, function) in m.EXPECTED_TRIGGERS.items()
            ]
            if self.changes.get("disabled_trigger"):
                row = r[0]
                r[0] = (row[0], row[1], "D", row[3], row[4])
            return Result(r)
        if "FROM pg_roles" in query:
            if self.changes.get("unsafe_roles"):
                return Result([("frc_ai_app", False, True),
                               ("frc_ai_auth", False, False)])
            return Result([("frc_ai_app", False, False),
                           ("frc_ai_auth", False, False)])
        if "has_table_privilege" in query:
            if self.changes.get("outbox_delete") and parameters[0].endswith("outbox"):
                return Result((True, True, True, False))
            return Result((True, True, False, False))
        if "has_column_privilege" in query:
            table, col = parameters
            v = col in m.ALLOWED_UPDATE_COLUMNS.get(table.removeprefix("public."), ())
            if self.changes.get("forbidden_update") and col == "tenant_id":
                v = True
            return Result((v,))
        if "pg_get_expr(d.adbin,d.adrelid)" in query:
            return Result(("'BLOCKED_EXTERNAL'::character varying",))
        if "SELECT pg_get_constraintdef(oid)" in query:
            if self.changes.get("unsafe_outbox"):
                return Result([("CHECK (state = ANY(ARRAY['SENT']))",)])
            return Result([(
                "CHECK ((state)::text = ANY(ARRAY['BLOCKED_EXTERNAL',"
                "'DISPATCH_REVIEW','CANCELLED']))",
            )])
        raise AssertionError("Unexpected query: " + query)


def test_m39032_only_reads_catalog_and_attests_53_tables(capsys):
    conn = FakePg18()
    m.audit(conn)
    out = capsys.readouterr().out
    assert "M39032_STATUS=PASS" in out
    assert "M39032_SPECIAL_TABLES=6_OF_6" in out
    assert "M39032_POLICIES=16_OF_16" in out
    assert "M39032_TRIGGERS=5_OF_5" in out
    assert "M39032_EXTERNAL_OUTBOX=BLOCKED_EXTERNAL" in out
    assert "M39032_SQL110_111=ALREADY_APPLIED_DO_NOT_REPEAT" in out
    assert all(query.lstrip().startswith(("SELECT", "SET TRANSACTION READ ONLY"))
               for query, _ in conn.queries)


@pytest.mark.parametrize("changes,reason", [
    ({"total": 52}, "EXPECTED_53_PUBLIC_TABLES"),
    ({"rls_off": True}, "SPECIAL_CREDIT_RLS_NOT_FORCED"),
    ({"missing_policy": True}, "POLICY_SET_DRIFT"),
    ({"disabled_trigger": True}, "TRIGGER_OR_FUNCTION_DRIFT"),
    ({"unsafe_roles": True}, "RUNTIME_ROLE_PRIVILEGE_DRIFT"),
    ({"outbox_delete": True}, "TABLE_PRIVILEGE_DRIFT"),
    ({"forbidden_update": True}, "FORBIDDEN_COLUMN_UPDATE"),
    ({"unsafe_outbox": True}, "EXTERNAL_OUTBOX_STATE_CONSTRAINT_UNSAFE"),
])
def test_m39032_fails_closed_on_security_drift(changes, reason):
    with pytest.raises(RuntimeError, match=reason):
        m.audit(FakePg18(**changes))


def test_expectations_match_migration_source_without_reapplying():
    root = Path(__file__).resolve().parents[2]
    sql110 = (root/"backend/migrations/110_fr_finance_special_credit_offline.sql").read_text()
    sql111 = (root/"backend/migrations/111_frfinance_special_credit_integrity_guards.sql").read_text()
    policies = set(re.findall(r"CREATE POLICY (\w+)", sql110))
    assert policies == set().union(*m.EXPECTED_POLICIES.values())
    triggers = set(re.findall(r"CREATE TRIGGER (\w+)", sql111))
    assert triggers == set(m.EXPECTED_TRIGGERS)
    source = (root/"backend/scripts/frfinance_m39032_post_migration_readonly.py").read_text()
    assert "SET TRANSACTION READ ONLY" in source
    assert "default_transaction_read_only=on" in source
    assert "AI_STUDIO_APPROVED_SHA" not in source  # validated in imported verify_repo()
    assert "verify_repo()" in source
    assert "M39032_SQL110_111=ALREADY_APPLIED_DO_NOT_REPEAT" in source
    assert "LOCAL_AUTHORIZED" not in source
