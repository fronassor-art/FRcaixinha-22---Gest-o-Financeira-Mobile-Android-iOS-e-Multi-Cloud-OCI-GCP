"""M41070 regression checks for transaction-bound SQL capabilities."""
from __future__ import annotations

import asyncio
from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
RUNNER = ROOT / "backend" / "tests" / "m41070_session_capability_transaction_pg18_disposable.py"
WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41070-transaction-capability-pg18.yml"
DOC = ROOT / "docs" / "FR_FINANCE_M41070_TRANSACTION_BOUND_SESSION_CAPABILITY_NO_GO.md"
sys.path.insert(0, str(APP))
from m41050_session_context_seal_prototype import (
    InvalidSessionCapability,
    install_session_capability,
)

CAPABILITY = "d" * 64
SQL = "SELECT pg_catalog.set_config('app.session_capability', $1, true)"
_MISSING = object()


class FakeConnection:
    def __init__(self, *, active=True, returned=_MISSING, end_during_fetch=False):
        self.active = active
        self.returned = CAPABILITY if returned is _MISSING else returned
        self.end_during_fetch = end_during_fetch
        self.calls = []

    def is_in_transaction(self):
        return self.active

    async def fetchval(self, query, value):
        self.calls.append((query, value))
        if self.end_during_fetch:
            self.active = False
        return self.returned


class NoTransactionCheck:
    async def fetchval(self, query, value):
        raise AssertionError("fetchval must not run without transaction check")


class SyncFetchConnection(FakeConnection):
    def fetchval(self, query, value):
        self.calls.append((query, value))
        return self.returned


def run(coro):
    return asyncio.run(coro)


def test_capability_binds_only_inside_active_asyncpg_transaction():
    connection = FakeConnection()
    run(install_session_capability(connection, CAPABILITY))
    assert connection.calls == [(SQL, CAPABILITY)]


@pytest.mark.parametrize(
    "connection",
    [
        FakeConnection(active=False),
        NoTransactionCheck(),
    ],
)
def test_missing_or_inactive_transaction_fails_before_sql(connection):
    with pytest.raises(InvalidSessionCapability):
        run(install_session_capability(connection, CAPABILITY))
    if isinstance(connection, FakeConnection):
        assert connection.calls == []


@pytest.mark.parametrize(
    "returned",
    ["", "e" * 64, None, 1],
)
def test_unexpected_postgres_bind_value_is_rejected(returned):
    connection = FakeConnection(returned=returned)
    with pytest.raises(InvalidSessionCapability):
        run(install_session_capability(connection, CAPABILITY))
    assert connection.calls == [(SQL, CAPABILITY)]


def test_transaction_ending_during_bind_fails_closed():
    connection = FakeConnection(end_during_fetch=True)
    with pytest.raises(InvalidSessionCapability):
        run(install_session_capability(connection, CAPABILITY))


def test_non_awaitable_driver_call_is_rejected():
    connection = SyncFetchConnection()
    with pytest.raises(InvalidSessionCapability):
        run(install_session_capability(connection, CAPABILITY))


def test_invalid_capability_rejected_without_database_call():
    connection = FakeConnection()
    with pytest.raises(InvalidSessionCapability) as err:
        run(install_session_capability(connection, "secret-" + CAPABILITY))
    assert CAPABILITY not in str(err.value)
    assert connection.calls == []


def test_disposable_runner_fails_closed_before_driver_import():
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=8,
    )
    assert result.returncode == 2
    assert "M41070_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M41070_DATABASE_CONNECTIONS=NONE" in result.stdout
    body = RUNNER.read_text(encoding="utf-8")
    main = body.split("def main()", 1)[1]
    assert main.index("require_disposable()") < main.index("asyncio.run(exercise(dsn))")
    assert "import asyncpg" not in body.split("async def exercise", 1)[0]


def test_document_records_limits_without_promoting_acceptance():
    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "2,310", "M41070_ROUTE_INTEGRATION=NONE",
        "M40570", "M40710", "M40730", "M40928", "M40929",
        "PRODUCTION=BLOCKED", "PENDING_INDEPENDENT_EVIDENCE",
    ):
        assert marker in doc
    assert "production_verified=true" not in doc
