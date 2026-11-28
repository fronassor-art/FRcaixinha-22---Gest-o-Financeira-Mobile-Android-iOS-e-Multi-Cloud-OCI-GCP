"""M39600 CI-only SQL evidence, never execute against original Termux.

The PostgreSQL16/18 disposable jobs execute the SQL (with rollback).
These tests ensure the source cannot silently change its safety scope.
"""
from pathlib import Path
import re
from fastapi.testclient import TestClient
from app.main import app

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql/m39600_exclusive_cashbox_rls_disposable_ci.sql"
ROUTER=ROOT/"backend/app/routers/exclusive_cashboxes.py"
WORKFLOW=ROOT/".github/workflows/validacao-atualizacao.yml"


def test_exclusive_cashbox_policy_has_hard_ci_identity_and_rollback():
    source=SQL.read_text()
    assert "CI_M39600_DISPOSABLE" in source
    assert "current_database()='frcaixinha_ci'" in source
    assert "inet_server_port()=5432" in source
    assert "session_user='postgres'" in source
    assert "current_setting('frfinance.m39600_ci',true)='DISPOSABLE_ONLY'" in source
    assert source.count("BEGIN;")==1
    assert source.count("ROLLBACK;")==1
    assert not re.search(r"(?mi)^\s*COMMIT\s*;",source)
    assert not re.search(r"(?mi)^\s*(DROP|ALTER|TRUNCATE|CREATE)\s+(?:TABLE|ROLE|DATABASE)\b",source)
    assert "m39600-intent-a" in source and "m39600-intent-b" in source
    assert "live_mode,status" in source
    assert "false,'PENDING'" in source


def test_both_pg16_and_pg18_are_covered_with_same_real_rls_sql():
    workflow=WORKFLOW.read_text()
    assert workflow.count(
        "backend/tests/sql/m39600_exclusive_cashbox_rls_disposable_ci.sql"
    )==2
    assert "PostgreSQL 16 descartavel" in workflow
    assert "PostgreSQL 18 descartavel" in workflow
    assert workflow.count("frfinance.m39600_ci=DISPOSABLE_ONLY")==2
    assert workflow.count("CI_M39600_DISPOSABLE=1")==2
    assert workflow.count('test "$PGDATABASE" = frcaixinha_ci')==2
    assert workflow.count('test "$PGPORT" = 5432')==2


def test_saas_master_cannot_read_ledgers_admin_cannot_read_other_tenant():
    source=SQL.read_text()
    assert "SET LOCAL ROLE frcaixinha_app_role;" in source
    assert "M39600 Master can see a tenant ledger" in source
    assert "M39600 admin A ledger leak" in source
    assert "M39600 admin B tenancy leak" in source
    assert "M39600 member can view exclusive cashboxes" in source
    for table in (
        "public.ledger_transactions",
        "public.saas_payment_intents",
        "public.saas_subscription_preparations",
    ):
        assert source.count(table)>=3


def test_protection_against_cached_financial_evidence():
    source=ROUTER.read_text()
    # M39910 adds two history GETs, M39960 adds two readiness GETs.
    # All six financial read-only endpoints must disable caching.
    assert source.count("_disallow_financial_caching(response)")==6
    assert '@master_router.get("/exclusive-cashbox/review-readiness")' in source
    assert '@tenant_router.get("/admin-exclusive-cashbox/review-readiness")' in source
    assert '@master_router.get("/exclusive-cashbox/history")' in source
    assert '@tenant_router.get("/admin-exclusive-cashbox/history")' in source
    assert 'response.headers["Cache-Control"] = "private, no-store, max-age=0"' in source
    assert 'response.headers["Vary"] = "Authorization"' in source
    assert 'response.headers["Pragma"] = "no-cache"' in source
    assert "settled_balance_cents\": None" in source
    assert "real_payments_enabled\": False" in source
    routes={r.path:r.methods for r in app.routes if hasattr(r,"methods")}
    assert routes["/api/v1/master/exclusive-cashbox"]=={"GET"}
    assert routes["/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox"]=={"GET"}
