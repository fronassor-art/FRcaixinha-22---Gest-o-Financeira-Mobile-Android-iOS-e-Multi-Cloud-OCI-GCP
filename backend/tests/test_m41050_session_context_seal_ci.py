"""Offline guards for the M41050 signed SQL-context prototype."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
RUNNER = ROOT / "backend" / "tests" / "m41050_sql_sealed_context_pg18_disposable.py"
WORKFLOW = ROOT / ".github" / "workflows" / "frfinance-m41050-signed-session-context-pg18-ci.yml"
DOC = ROOT / "docs" / "FR_FINANCE_M41050_SQL_SIGNED_SESSION_CONTEXT_NO_GO.md"
sys.path.insert(0, str(APP))
from m41050_session_context_seal_prototype import (
    InvalidSessionClaims,
    SessionClaims,
    canonical_session_claims,
    make_session_proof,
)

SOURCE = RUNNER.read_text(encoding="utf-8")


def sample(role="TENANT_MEMBER", tenant=None):
    if tenant is None and role != "MASTER":
        tenant = uuid4()
    return SessionClaims(
        session_id=uuid4(), user_id=uuid4(), role=role, tenant_id=tenant,
        nonce=uuid4(), expires_epoch=1_800_000_000,
    )


def test_canonical_proof_binds_every_claim_field():
    key = b"k" * 32
    claims = sample()
    proof = make_session_proof(key=key, claims=claims)
    assert len(proof) == 32
    assert proof != make_session_proof(
        key=key, claims=replace(claims, user_id=uuid4())
    )
    assert proof != make_session_proof(
        key=key, claims=replace(claims, tenant_id=uuid4())
    )
    assert proof != make_session_proof(
        key=key, claims=replace(claims, nonce=uuid4())
    )
    assert proof != make_session_proof(
        key=key, claims=replace(claims, expires_epoch=claims.expires_epoch + 1)
    )


@pytest.mark.parametrize("claims", [
    SessionClaims(uuid4(), uuid4(), "MASTER", uuid4(), uuid4(), 1_800_000_000),
    SessionClaims(uuid4(), uuid4(), "TENANT_MEMBER", None, uuid4(), 1_800_000_000),
    SessionClaims(uuid4(), uuid4(), "SUPERUSER", None, uuid4(), 1_800_000_000),
    SessionClaims(uuid4(), uuid4(), [], None, uuid4(), 1_800_000_000),
    SessionClaims(uuid4(), uuid4(), "MASTER", None, uuid4(), 1_800_000_000,
                  scope="WRITE"),
    SessionClaims(uuid4(), uuid4(), "TENANT_ADMIN", uuid4(), uuid4(), True),
])
def test_invalid_roles_tenants_scope_and_expiry_are_rejected(claims):
    with pytest.raises(InvalidSessionClaims):
        canonical_session_claims(claims)


@pytest.mark.parametrize("key", [b"", b"x" * 31, b"x" * 33, "x" * 32, None])
def test_invalid_key_shape_is_rejected(key):
    with pytest.raises(InvalidSessionClaims):
        make_session_proof(key=key, claims=sample())


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
    assert main_body.index("dsn = require_disposable()") < main_body.index("run(dsn)")


def test_fixture_guards_and_scope_boundaries_are_present():
    for marker in (
        "CI_M41050_DISPOSABLE",
        "FRCAIXINHA_CI_ISOLATED",
        "fr_m41050_disposable_ci",
        "m41050_issuer_login",
        "m41050_app_login",
        "M41050_COMPROMISED_ISSUER_SQL_LOGIN_WITHOUT_PROOF=DENIED",
        "M41050_FORGED_GUCS_WITHOUT_CAPABILITY=DENIED",
        "M41050_FORGED_MASTER_GUCS_WITH_MEMBER_CAPABILITY=DENIED",
        "M41050_TENANT_CROSSING=DENIED",
        "M41050_NONCE_REPLAY_SINGLE_ISSUE=PASS",
        "M41050_CONCURRENT_NONCE_SINGLE_ISSUE=PASS",
        "M41050_REVOKED_CAPABILITY=DENIED",
        "M41050_PRODUCTION=BLOCKED",
    ):
        assert marker in SOURCE


def test_workflow_and_document_preserve_no_go_and_never_target_local_sql():
    yml = WORKFLOW.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "postgres:18", "55450:5432", "CI_M41050_DISPOSABLE: '1'",
        "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'", "contents: read",
        "m41050_sql_sealed_context_pg18_disposable.py",
    ):
        assert marker in yml
    for forbidden in (
        "127.0.0.1:5433", "backend/migrations/", "pg_ctl", "pg_dump",
        "PAGAMENTOS_REAIS: 'ON'", "ATIVACAO_REAL: 'ON'",
    ):
        assert forbidden not in yml
    for marker in (
        "CP26-0019", "CP26-0003", "CP26-0004", "CP26-0061",
        "M40570", "M40730", "M40840", "M40930",
        "MIGRATIONS=NONE", "PRODUCTION=BLOCKED",
    ):
        assert marker in doc


def test_no_real_application_route_or_migration_is_wired():
    for forbidden in ("get_rls_db_connection", "CREATE MIGRATION", "backend/migrations/"):
        assert forbidden not in SOURCE
