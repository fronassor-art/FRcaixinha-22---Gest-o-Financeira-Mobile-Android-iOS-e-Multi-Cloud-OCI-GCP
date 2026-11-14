"""M39026: CI para preflight do crédito sem tocar no banco do Termux."""
from __future__ import annotations

from contextlib import nullcontext

import pytest

from backend.scripts import frfinance_m39026_credit_only_preflight as m


class Rows:
    def __init__(self, data):
        self.data = data

    def fetchone(self):
        return self.data

    def fetchall(self):
        return self.data


class FakeCatalog:
    def __init__(self, tables=47, roles=None, overrides=None):
        self.tables = tables
        self.roles = roles if roles is not None else [
            ("frc_ai_app", False, False, True),
            ("frc_ai_auth", False, False, True),
        ]
        self.overrides = overrides or {}
        self.executed = []

    def transaction(self):
        return nullcontext()

    def execute(self, query, params=None):
        self.executed.append((query, params))
        assert query.lstrip().startswith(("SELECT", "SET TRANSACTION READ ONLY"))
        if query.startswith("SET TRANSACTION"):
            return Rows(None)
        if "current_database(),current_user,session_user" in query:
            return Rows((m.DB, m.OWNER, m.OWNER, "127.0.0.1", 5433,
                         m.DATA_DIRECTORY, 180006))
        if "FROM pg_roles" in query:
            return Rows(self.roles)
        if "pg_catalog.pg_tables" in query:
            return Rows((self.tables,))
        if "information_schema.columns" in query:
            return Rows([(table, name, dtype)
                         for table, spec in m.REQUIRED.items()
                         for name, dtype in spec.items()
                         if (table, name) not in self.overrides.get("missing", set())])
        if "unnest(%s::text[])" in query:
            assert len(params[0]) == 6
            return Rows([(x in self.overrides.get("existing", set()),)
                         for x in params[0]])
        if "FROM pg_trigger" in query:
            return Rows((len(self.overrides.get("triggers", set())),))
        if "to_regclass('public.uq_special_active_member_cycle')" in query:
            return Rows((self.overrides.get("index", False),))
        raise AssertionError("Unexpected SQL query")


def test_credit_only_passes_with_47_tables_and_no_credit_objects(capsys):
    db = FakeCatalog()
    m.audit(db)
    out = capsys.readouterr().out
    assert "M39026_STATUS=PASS" in out
    assert "M39026_CREDIT_TABLES=ABSENT_6_OF_6" in out
    assert any("host(inet_server_addr())" in query for query, _ in db.executed)
    assert all("inet_server_addr()::text" not in query for query, _ in db.executed)
    assert "M39026_SQL_110_111=READY_FOR_SEPARATELY_APPROVED" in out
    assert all(q.lstrip().startswith(("SELECT", "SET TRANSACTION READ ONLY"))
               for q, _ in db.executed)


@pytest.mark.parametrize("overrides,expected", [
    ({"existing": {"special_credit_grants"}}, "CREDIT_TABLE_ALREADY_EXISTS_OR_PARTIAL"),
    ({"triggers": {"sc_m39020_grant_transition"}}, "CREDIT_TRIGGER_COLLISION"),
    ({"index": True}, "CREDIT_INDEX_COLLISION"),
    ({"missing": {("memberships", "user_id")}}, "BASELINE_COLUMN_INCOMPATIBLE"),
])
def test_credit_preflight_rejects_partial_or_incompatible_schema(overrides, expected):
    with pytest.raises(RuntimeError, match=expected):
        m.audit(FakeCatalog(overrides=overrides))


def test_credit_preflight_rejects_unexpected_old_schema_size():
    with pytest.raises(RuntimeError, match="EXPECTED_47_PRE_CREDIT_TABLES_FOUND_48"):
        m.audit(FakeCatalog(tables=48))


def test_credit_preflight_rejects_unsafe_app_role():
    with pytest.raises(RuntimeError, match="APPLICATION_ROLE_ISOLATION_INVALID"):
        m.audit(FakeCatalog(roles=[
            ("frc_ai_app", False, True, True), ("frc_ai_auth", False, False, True),
        ]))


def test_preflight_never_mutates_catalog_or_checks_irrelevant_old_business_rules():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" /
           "frfinance_m39026_credit_only_preflight.py").read_text()
    assert "repo-check" in src
    assert "local-readonly" in src  # explicit exclusion, not an invocation
    assert '"local-readonly"],' not in src
    assert "M20700 invalid minimum constraints" not in src
    assert "frfinance.m39020_migration_mode" not in src  # no apply
    assert "pg_dump" not in src
    assert "CREATE TABLE" not in src
    assert "ALTER TABLE" not in src
    assert "AI_STUDIO_APPROVED_SHA" in src
