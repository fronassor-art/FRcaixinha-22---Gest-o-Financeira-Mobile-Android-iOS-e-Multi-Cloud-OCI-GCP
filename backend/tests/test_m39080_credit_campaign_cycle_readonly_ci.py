"""FR Finance M39080 — offline tests, no database connections."""
from contextlib import nullcontext
from pathlib import Path
from uuid import UUID

import pytest

from backend.scripts.frfinance_m39080_credit_campaign_cycle_readonly import (
    audit,
    eligibility_state,
    original_database_identity,
)
from backend.scripts.frfinance_m39026_credit_only_preflight import DB, OWNER, DATA_DIRECTORY


@pytest.mark.parametrize(("tenants", "open_cycles", "current", "members", "expected"), [
    (1, 1, 1, 1, "PASS_READY_TO_TEST_INTERNAL_GRANTS"),
    (1, 0, 0, 2, "BLOCKED_NO_OPEN_CYCLE"),
    (1, 2, 2, 2, "BLOCKED_MULTIPLE_OPEN_CYCLES"),
    (1, 1, 0, 2, "BLOCKED_CYCLE_DATES_INCONSISTENT"),
    (1, 1, 1, 0, "BLOCKED_NO_ELIGIBLE_ACTIVE_MEMBERS"),
    (0, 0, 0, 0, "BLOCKED_NO_ACTIVE_TENANT"),
    (2, 1, 1, 2, "BLOCKED_SELECT_TENANT_SAFELY"),
])
def test_eligibility_fail_closed(tenants, open_cycles, current, members, expected):
    assert eligibility_state(tenants, open_cycles, current, members) == expected


class FakeCursor:
    def __init__(self, one=None, many=None):
        self.one, self.many = one, many
    def fetchone(self):
        return self.one
    def fetchall(self):
        return self.many


class OriginalReadOnlyDB:
    def __init__(self, *, tenants=1, open_cycles=1, current=1,
                 members=1, records=(0, 0, 0, 0)):
        self.tenants = tenants
        self.cycles = (open_cycles, current)
        self.members = members
        self.records = records
        self.queries = []
        self.tenant_id = UUID("11111111-1111-4111-8111-111111111111")
    def transaction(self):
        return nullcontext()
    def execute(self, sql, parameters=None):
        self.queries.append((sql, parameters))
        if sql == "SET TRANSACTION READ ONLY":
            return FakeCursor()
        if "current_setting('data_directory')" in sql:
            return FakeCursor((
                DB, OWNER, OWNER, "127.0.0.1", 5433,
                DATA_DIRECTORY, 180006, "on",
            ))
        if "JOIN pg_catalog.pg_namespace" in sql:
            return FakeCursor((6, 6))
        if "FROM pg_catalog.pg_trigger" in sql:
            return FakeCursor((5,))
        if "SELECT id FROM public.tenants" in sql:
            return FakeCursor(many=[(self.tenant_id,)] * self.tenants)
        if "FROM public.cycles WHERE tenant_id" in sql:
            return FakeCursor(self.cycles)
        if "FROM public.memberships " in sql:
            return FakeCursor((self.members,))
        if "SELECT (SELECT count(*) FROM public.special_credit_grants" in sql:
            return FakeCursor(self.records)
        raise AssertionError("Unexpected SQL: " + sql[:150])


@pytest.mark.parametrize(("open_cycles", "current", "members", "expected"), [
    (1, 1, 2, "PASS_READY_TO_TEST_INTERNAL_GRANTS"),
    (0, 0, 2, "BLOCKED_NO_OPEN_CYCLE"),
    (1, 1, 0, "BLOCKED_NO_ELIGIBLE_ACTIVE_MEMBERS"),
])
def test_actual_read_only_audit_without_personal_details(
    open_cycles, current, members, expected, capsys
):
    conn = OriginalReadOnlyDB(
        open_cycles=open_cycles, current=current, members=members
    )
    assert audit(conn) == expected
    output = capsys.readouterr().out
    assert str(conn.tenant_id) not in output
    assert "M39080_ELIGIBLE_MEMBERS=" in output
    assert conn.queries[0][0] == "SET TRANSACTION READ ONLY"
    assert all(
        sql.startswith(("SELECT", "SET TRANSACTION"))
        for sql, _ in conn.queries
    )


def test_existing_active_grant_not_silently_recreated(capsys):
    conn = OriginalReadOnlyDB(records=(1, 1, 1, 2))
    assert audit(conn) == "PASS_READY_TO_TEST_INTERNAL_GRANTS"
    assert "M39080_EXISTING_RECORDS=REVIEW_BEFORE_NEW_WRITES" in capsys.readouterr().out


def test_wrong_postgresql_identity_blocks_before_customer_counts():
    conn = OriginalReadOnlyDB()
    def wrong_identity():
        return FakeCursor((
            "frcaixinha_22", OWNER, OWNER, "127.0.0.1", 5432,
            DATA_DIRECTORY, 180006, "on",
        ))
    original = conn.execute
    conn.execute = lambda sql, parameters=None: (
        wrong_identity()
        if "current_setting('data_directory')" in sql
        else original(sql, parameters)
    )
    assert not original_database_identity(conn)
    with pytest.raises(RuntimeError, match="NOT_FR_FINANCE_ORIGINAL_PG18"):
        audit(conn)


def test_source_never_mutates_database_or_exposes_member_identity():
    source = (Path(__file__).resolve().parents[1] / "scripts" /
        "frfinance_m39080_credit_campaign_cycle_readonly.py").read_text()
    for required in (
        "verify_original()", "SET TRANSACTION READ ONLY",
        "default_transaction_read_only=on", "port=5433",
        "DATA_DIRECTORY", "M39080_DATABASE_WRITES=NONE",
        "M39080_USER_IDENTITIES_PRINTED=NONE",
    ):
        assert required in source
    for forbidden in (
        "INSERT INTO", "UPDATE public.", "DELETE FROM", "CREATE TABLE",
        "DROP TABLE", "ALTER TABLE", "grant(tenant", "publish(tenant",
        "print(tenant_id)", "print(password)", "print(members)",
    ):
        assert forbidden not in source
