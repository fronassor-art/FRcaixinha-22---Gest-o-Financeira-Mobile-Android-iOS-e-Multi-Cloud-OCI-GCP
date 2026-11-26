"""M41060 offline guards for scoped write RLS and idempotency evidence."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "backend" / "tests"
RUNNER = TESTS / "m41050_sql_sealed_context_pg18_disposable.py"
PROOF = TESTS / "m40700_request_proof_disposable.py"
WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41060-write-rls-pg18-ci.yml"
DOC = ROOT / "docs" / "FR_FINANCE_M41060_WRITE_RLS_IDEMPOTENCY_NO_GO.md"
SOURCE = RUNNER.read_text(encoding="utf-8")
PROOF_SOURCE = PROOF.read_text(encoding="utf-8")


def test_runner_fails_closed_without_disposable_ci_identity():
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, check=False, timeout=8,
    )
    assert result.returncode == 2
    assert "M41050_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M41050_TERMUX_PG_5433=NOT_ACCESSED" in result.stdout
    assert "M41050_PRODUCTION=BLOCKED" in result.stdout


def test_signed_action_scope_is_carried_through_one_use_ticket():
    for marker in (
        'WRITE_SCOPE = "WRITE_TEST_ENTRY"',
        "INSERT INTO m40700.ticket_scopes(ticket_digest,scope_name)",
        "JOIN m40700.ticket_scopes AS x",
        "v_scope text",
        "v_expiry,v_scope",
        "expires_at,scope_name",
        "c.scope_name",
        "p_scope IS DISTINCT FROM 'WRITE_TEST_ENTRY'",
        "WRITE_ANYTHING",
        "M41060_UNLISTED_SCOPE=DENIED",
    ):
        assert marker in PROOF_SOURCE + SOURCE


def test_read_write_policy_and_append_only_boundary_are_explicit():
    for marker in (
        "FOR SELECT TO m40650_app",
        "c.scope_name='READ_ENTRIES'",
        "FOR INSERT TO m40650_app",
        "c.scope_name='WRITE_TEST_ENTRY'",
        "c.role_name='TENANT_ADMIN'",
        "m.status='ATIVA'",
        "ON CONFLICT (tenant_id,idempotency_key) DO NOTHING",
        "UNIQUE(tenant_id,idempotency_key)",
        "M41060_READ_SCOPE_CANNOT_WRITE=DENIED",
        "M41060_MEMBER_WRITE=DENIED",
        "M41060_WRITE_CAPABILITY_CANNOT_READ=DENIED",
        "M41060_ADMIN_WRITE_SCOPE_RESOLVED=PASS",
        "M41060_ADMIN_WRITE_SCOPE_RESISTS_LEGACY_GUCS=PASS",
        "def write_authorization_state",
        "M41060_ADMIN_TENANT_WRITE_AND_CROSS_TENANT_DENIAL=PASS",
        "M41060_APPEND_ONLY_SELECT_INSERT_ACL=PASS",
        "M41060_CONCURRENT_IDEMPOTENCY_SINGLE_ROW=PASS",
        "M41060_STATUS=PASS_DISPOSABLE_WRITE_RLS_ONLY",
    ):
        assert marker in SOURCE


def test_ci_and_document_keep_the_proof_synthetic_and_no_go():
    yml = WORKFLOW.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "postgres:18", "55439:5432", "CI_M41060_DISPOSABLE: '1'",
        "CI_M41050_DISPOSABLE: '1'", "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'", "ATIVACAO_REAL: 'OFF'",
        "contents: read", "backend/tests/test_m41060_write_scope_ci.py",
        "m41050_sql_sealed_context_pg18_disposable.py",
    ):
        assert marker in yml
    for forbidden in ("backend/migrations/", "pg_ctl", "127.0.0.1:5433",
                      "PIX_REAL: 'ON'", "PAGAMENTOS_REAIS: 'ON'"):
        assert forbidden not in yml
    for marker in (
        "CP26-0062", "CP26-0061", "M40710", "M40730", "M40840",
        "M40930", "MIGRATIONS=NONE", "PRODUCTION=BLOCKED",
        "nem altera", "PostgreSQL 18 descartável",
    ):
        assert marker in doc
