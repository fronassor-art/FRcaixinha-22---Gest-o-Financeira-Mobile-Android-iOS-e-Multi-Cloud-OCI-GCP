"""M40850: block production-target downgrade and privileged cached DSNs.

Pure DSN syntax and mocked pool tests. No network, database, migrations or I/O.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from app.m40800_financial_dsn_guard import (
    FinancialDSNBlocked, require_financial_dsn_shape,
)
from app import database as db

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"backend/app/database.py"
GUARD=ROOT/"backend/app/m40800_financial_dsn_guard.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40850-dsn-downgrade-no-go-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40850_DSN_DOWNGRADE_CACHE_NO_GO.md"

CRED="ci-synthetic-credential-not-real"
BASE=f"postgresql://frc_ai_app:{CRED}@127.0.0.1:5433/frcaixinha_aistudio_dev"
REMOTE=f"postgresql://frc_ai_app:{CRED}@pg.frfinance.com.br:5432/frfinance_prod?sslmode=verify-full"


@pytest.mark.parametrize("mode", ["development","dev","homologation","staging","ci","test"])
def test_production_db_rejected_in_any_nonproduction_mode(mode):
    with pytest.raises(FinancialDSNBlocked, match="M40850_UNTRUSTED_NONPROD_DB_TARGET"):
        require_financial_dsn_shape(REMOTE, {"ENVIRONMENT":mode})


@pytest.mark.parametrize("user", ["postgres","root","frc_ai_owner","frc_ai_auth","frc_ai_verifier"])
@pytest.mark.parametrize("host", ["127.0.0.1:5433","pg.staging.invalid:5432"])
def test_privileged_or_wrong_boundary_role_denied_anywhere(user,host):
    url=f"postgresql://{user}:{CRED}@{host}/frcaixinha_aistudio_dev"
    with pytest.raises(FinancialDSNBlocked, match="M40850_UNTRUSTED_NONPROD_DB_TARGET"):
        require_financial_dsn_shape(url, {"ENVIRONMENT":"staging"})


@pytest.mark.parametrize("database", [
    "postgres", "template0", "template1", "frcaixinha_2_2",
    "frcaixinha_2_2_prod", "frfinance_prod", "frfinance_production"
])
def test_forbidden_database_identity_in_nonprod(database):
    url=f"postgresql://frc_ai_app:{CRED}@pg.staging.invalid:5432/{database}"
    with pytest.raises(FinancialDSNBlocked):
        require_financial_dsn_shape(url, {"ENVIRONMENT":"development"})


@pytest.mark.parametrize("wrong", [
    f"postgresql://frc_ai_auth:{CRED}@127.0.0.1:5433/frcaixinha_aistudio_dev",
    f"postgresql://frc_ai_app:{CRED}@127.0.0.1:5433/frcaixinha_other",
    f"postgresql://frc_ai_app:{CRED}@localhost:5433/frcaixinha_other",
])
def test_loopback_fr_finance_port_is_not_cross_project_fallback(wrong):
    with pytest.raises(FinancialDSNBlocked):
        require_financial_dsn_shape(wrong, {"ENVIRONMENT":"test"})


def test_nontermux_known_frfinance_app_dsn_stays_unattested():
    assert require_financial_dsn_shape(BASE, {"ENVIRONMENT":"development"}) == "NONPRODUCTION_UNATTESTED"


@pytest.mark.asyncio
async def test_cached_pool_cannot_skip_late_dsn_guard(monkeypatch):
    fake=object()
    monkeypatch.setattr(db,"_db_pool",fake)
    monkeypatch.setattr(db.settings,"DATABASE_URL",REMOTE)
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.delenv("FRCAIXINHA_TERMUX_LOCAL_API",raising=False)
    for flag in ("PIX_REAL","PAGAMENTOS_REAIS","ATIVACAO_REAL"):
        monkeypatch.setenv(flag,"OFF")
    with pytest.raises(FinancialDSNBlocked, match="M40850_UNTRUSTED_NONPROD_DB_TARGET"):
        await db.get_db_pool()
    assert db._db_pool is fake


@pytest.mark.asyncio
async def test_cached_pool_with_matching_nonprod_target_is_only_syntax_accepted(monkeypatch):
    fake=object()
    monkeypatch.setattr(db,"_db_pool",fake)
    monkeypatch.setattr(db.settings,"DATABASE_URL",BASE)
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("FRCAIXINHA_TERMUX_LOCAL_API","1")
    for flag in ("PIX_REAL","PAGAMENTOS_REAIS","ATIVACAO_REAL"):
        monkeypatch.setenv(flag,"OFF")
    assert await db.get_db_pool() is fake


@pytest.mark.asyncio
@pytest.mark.parametrize("cleared_dsn", ["", "not-a-postgresql-dsn"])
async def test_cached_pool_cannot_bypass_guard_when_dsn_cleared_or_invalid(monkeypatch, cleared_dsn):
    """M40943: an already-cached pool cannot outlive a valid DSN setting."""
    fake = object()
    monkeypatch.setattr(db, "_db_pool", fake)
    monkeypatch.setattr(db.settings, "DATABASE_URL", cleared_dsn)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("FRCAIXINHA_TERMUX_LOCAL_API", "1")
    for flag in ("PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"):
        monkeypatch.setenv(flag, "OFF")
    with pytest.raises(FinancialDSNBlocked, match="M40800_UNSAFE_FINANCIAL_DSN"):
        await db.get_db_pool()
    assert db._db_pool is fake


def test_existing_production_hard_gate_still_precedes_cache():
    s=SOURCE.read_text(encoding="utf-8")
    assert s.index("require_nonproduction_financial_sql(os.environ)") < s.index("if _db_pool is not None and settings.DATABASE_URL")
    assert s.index("if _db_pool is not None:") < s.index("if _db_pool is None:")
    assert "M40840_FINANCIAL_SQL_NO_GO" in (
        ROOT/"backend/app/m40840_financial_sql_release_no_go.py"
    ).read_text()
    assert "M40850_UNTRUSTED_NONPROD_DB_TARGET" in GUARD.read_text()


def test_workflow_and_scope_no_go():
    yaml=WORKFLOW.read_text()
    doc=DOC.read_text()
    for s in ("PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
              "ATIVACAO_REAL: 'OFF'", "contents: read",
              "test_m40850_dsn_downgrade_ci.py"):
        assert s in yaml
    for s in ("M40570","M40730","GUC","NO-GO","PRODUCTION=BLOCKED"):
        assert s in doc
