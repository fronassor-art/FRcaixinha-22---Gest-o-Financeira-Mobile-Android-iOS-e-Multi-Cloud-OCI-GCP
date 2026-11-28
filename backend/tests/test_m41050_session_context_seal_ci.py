"""Offline guards for the M41050 ticket-bound SQL/RLS context prototype."""
from __future__ import annotations

import asyncio
from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
RUNNER = ROOT / "backend" / "tests" / "m41050_sql_sealed_context_pg18_disposable.py"
WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41050-signed-session-context-pg18-ci.yml"
DOC = ROOT / "docs" / "FR_FINANCE_M41050_SQL_SIGNED_SESSION_CONTEXT_NO_GO.md"
sys.path.insert(0, str(APP))
from m41050_session_context_seal_prototype import (
    InvalidSessionCapability,
    install_session_capability,
    validate_session_capability,
)

SOURCE = RUNNER.read_text(encoding="utf-8")


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.active = True

    def is_in_transaction(self):
        return self.active

    async def fetchval(self, query, value):
        self.calls.append((query, value))
        return value


def test_only_opaque_capability_shape_is_accepted():
    assert validate_session_capability("a" * 64) == "a" * 64
    for value in (
        None, 1, b"a" * 64, "A" * 64, "a" * 63, "a" * 65,
        "g" * 64, "a" * 32 + "\n" + "a" * 31,
    ):
        with pytest.raises(InvalidSessionCapability):
            validate_session_capability(value)


def test_installation_is_parameterized_and_transaction_local():
    connection = FakeConnection()
    asyncio.run(install_session_capability(connection, "c" * 64))
    assert connection.calls == [(
        "SELECT pg_catalog.set_config('app.session_capability', $1, true)",
        "c" * 64,
    )]


def test_bad_connection_is_denied_without_leaking_capability():
    with pytest.raises(InvalidSessionCapability):
        asyncio.run(install_session_capability(object(), "c" * 64))


def test_runner_fails_closed_before_psycopg_or_database_access():
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, check=False, timeout=8,
    )
    assert result.returncode == 2
    assert "M41050_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M41050_LOCAL_DATABASE_CONNECTIONS=NONE" in result.stdout
    assert "import psycopg" not in SOURCE.split("def connect(", 1)[0]
    main_body = SOURCE.split("def main()", 1)[1]
    assert main_body.index("require_disposable()") < main_body.index("run(dsn)")


def test_fixture_reuses_existing_proof_and_has_no_second_signer_key():
    for marker in (
        "m40700_request_proof_disposable",
        "bootstrap_m40700",
        "issue_bound_v2(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        "REVOKE EXECUTE ON FUNCTION m40650.m40680_consume",
        "m40650.m40680_consume",
        "CREATE TABLE m41050.session_caps",
        "CREATE FUNCTION m41050.bind_ticket",
        "CREATE FUNCTION m41050.current_claims",
        "M41050_FORGED_GUCS_WITHOUT_CAPABILITY=DENIED",
        "M41050_FORGED_MASTER_GUCS_WITH_MEMBER_CAPABILITY=DENIED",
        "M41050_TENANT_CROSSING=DENIED",
        "M41050_BIND_TICKET_REPLAY=DENIED",
        "M41050_CONCURRENT_TICKET_BIND_SINGLE_CAPABILITY=PASS",
        "M41050_REVOKED_SESSION_CAPABILITY=DENIED",
        "M41050_MASTER_SESSION_TICKET=DENIED",
        "M41050_PRODUCTION=BLOCKED",
    ):
        assert marker in SOURCE
    assert "CREATE TABLE m41050.key_material" not in SOURCE
    assert "CREATE EXTENSION" not in SOURCE


def test_workflow_and_document_preserve_no_go_and_never_target_local_sql():
    yml = WORKFLOW.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "postgres:18", "55439:5432", "CI_M41050_DISPOSABLE: '1'",
        "CI_M41060_DISPOSABLE: '1'",
        "CI_M40700_DISPOSABLE: '1'", "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'", "ATIVACAO_REAL: 'OFF'",
        "contents: read", "m41050_sql_sealed_context_pg18_disposable.py",
    ):
        assert marker in yml
    for forbidden in (
        "127.0.0.1:5433", "backend/migrations/", "pg_ctl", "pg_dump",
        "PAGAMENTOS_REAIS: 'ON'", "ATIVACAO_REAL: 'ON'",
    ):
        assert forbidden not in yml
    for marker in (
        "CP26-0019", "CP26-0003", "CP26-0004", "CP26-0061",
        "M40570", "M40700", "M40710", "M40840", "M40930",
        "MIGRATIONS=NONE", "PRODUCTION=BLOCKED",
    ):
        assert marker in doc


def test_no_real_application_route_or_migration_is_wired():
    for forbidden in ("get_rls_db_connection", "CREATE MIGRATION", "backend/migrations/"):
        assert forbidden not in SOURCE
