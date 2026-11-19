"""M40840: real financial pool is denied for production and live flags.

Runs offline only. DB pool is replaced with an inert object. No PostgreSQL I/O.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from app import database as db
from app.m40840_financial_sql_release_no_go import (
    FinancialSQLReleaseBlocked, require_nonproduction_financial_sql,
)

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/app/database.py"
DOC=ROOT/"docs/FR_FINANCE_M40840_FINANCIAL_RLS_PRODUCTION_NO_GO.md"
WORKFLOW=ROOT/".github/workflows/frfinance-m40840-financial-sql-release-no-go-ci.yml"


@pytest.mark.parametrize("mode", ["production", "PRODUCTION", "prod", "live",
    "invalid", "", None, 1])
def test_production_and_unknown_modes_blocked(mode):
    with pytest.raises(FinancialSQLReleaseBlocked, match="M40840_FINANCIAL_SQL_NO_GO"):
        require_nonproduction_financial_sql({"ENVIRONMENT": mode})


@pytest.mark.parametrize("mode", ["development", "test", "staging",
    "homologation", "ci", "local"])
def test_laboratory_modes_are_only_syntax_not_authority(mode):
    assert "NO_SQL_TRUST_ATTESTATION" in require_nonproduction_financial_sql({
        "ENVIRONMENT": mode, "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF", "ATIVACAO_REAL": "OFF",
    })


@pytest.mark.parametrize("flag", ["PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"])
@pytest.mark.parametrize("state", ["ON", "TRUE", "1", "YES", "off", None])
def test_each_live_flag_denied_even_in_staging(flag, state):
    with pytest.raises(FinancialSQLReleaseBlocked):
        require_nonproduction_financial_sql({"ENVIRONMENT": "staging", flag: state})


@pytest.mark.asyncio
async def test_cached_financial_pool_cannot_bypass_production_gate(monkeypatch):
    old=object()
    monkeypatch.setattr(db,"_db_pool",old)
    monkeypatch.setenv("ENVIRONMENT","production")
    for flag in ("PIX_REAL","PAGAMENTOS_REAIS","ATIVACAO_REAL"):
        monkeypatch.setenv(flag,"OFF")
    with pytest.raises(FinancialSQLReleaseBlocked):
        await db.get_db_pool()
    assert db._db_pool is old


@pytest.mark.asyncio
async def test_existing_nonproduction_inert_pool_still_available(monkeypatch):
    old=object()
    monkeypatch.setattr(db,"_db_pool",old)
    monkeypatch.setenv("ENVIRONMENT","development")
    for flag in ("PIX_REAL","PAGAMENTOS_REAIS","ATIVACAO_REAL"):
        monkeypatch.setenv(flag,"OFF")
    assert await db.get_db_pool() is old


@pytest.mark.asyncio
async def test_rls_dependency_denies_prod_before_pool_acquisition(monkeypatch):
    now=datetime.now(timezone.utc)
    principal=SimpleNamespace(
        user_id=str(uuid4()),tenant_id=str(uuid4()),
        role="TENANT_MEMBER", is_master=False,
        verified_session_id=str(uuid4()),
        verified_session_at=now-timedelta(seconds=2),
        verified_session_expires_at=now+timedelta(minutes=10),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    async def fail_pool():
        raise AssertionError("Financial pool must not be accessed")
    monkeypatch.setattr(db,"get_db_pool",fail_pool)
    monkeypatch.setenv("ENVIRONMENT","production")
    for flag in ("PIX_REAL","PAGAMENTOS_REAIS","ATIVACAO_REAL"):
        monkeypatch.setenv(flag,"OFF")
    monkeypatch.setattr(db.settings, "DATABASE_URL",
                        "postgresql://offline-invalid:placeholder@127.0.0.1:5433/test")
    gen=db.get_rls_db_connection(principal)
    with pytest.raises(HTTPException) as denied:
        await gen.__anext__()
    assert denied.value.status_code==503
    await gen.aclose()


def test_source_blocks_before_any_financial_pool_access():
    source=SCRIPT.read_text(encoding="utf-8")
    assert source.count("require_nonproduction_financial_sql(os.environ)") == 2
    assert source.index("require_nonproduction_financial_sql(os.environ)") < source.index("if _db_pool is None:")
    assert source.rindex("require_nonproduction_financial_sql(os.environ)") < source.index("pool = await get_db_pool()")
    assert "M40840" in source


def test_docs_and_workflow_production_no_go():
    yaml=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for x in ("PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
              "ATIVACAO_REAL: 'OFF'","test_m40840_financial_sql_release_ci.py"):
        assert x in yaml
    for x in ("M40570","M40730","NO-GO","PRODUCTION=BLOCKED"):
        assert x in doc
