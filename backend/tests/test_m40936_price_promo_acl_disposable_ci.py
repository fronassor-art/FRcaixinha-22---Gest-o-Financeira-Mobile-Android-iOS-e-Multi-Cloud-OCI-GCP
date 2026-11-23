"""M40936: source assertions and non-CI refusal, no PostgreSQL contact."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/tests/m40936_price_promo_acl_rehearsal_disposable.py"
CI = ROOT / ".github/workflows/frfinance-m40936-price-promo-acl-disposable-ci.yml"
DOC = ROOT / "docs/FR_FINANCE_M40936_PRICE_PROMO_ACL_GUC_NO_GO.md"
SQL011 = ROOT / "backend/migrations/011_platform_license_catalog.sql"
SQL112 = ROOT / "backend/migrations/112_frfinance_master_independent_saas_prices.sql"
SQL113 = ROOT / "backend/migrations/113_frfinance_saas_new_admin_promotions.sql"


def test_disposable_target_is_required_before_postgresql_import():
    proc = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        env={"PATH": os.environ.get("PATH", "")},
        text=True, capture_output=True, timeout=12,
    )
    assert proc.returncode == 2
    assert "M40936_STATUS=BLOCKED_RuntimeError" in proc.stdout
    assert "M40936_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in proc.stdout
    source = RUNNER.read_text(encoding="utf-8")
    assert source.index("require_disposable()\n        from m39067_postgres18_disposable_runtime") < source.index(
        "with restricted_connection() as conn:"
    )
    for required in (
        "CI_M40936_DISPOSABLE", "m40900_sql113_acl_fence_disposable",
        "require_disposable as prior", "m40560_saas_role_dataplane_disposable",
        "m39067_postgres18_disposable_runtime", "M40936_MASTER_SQL_RELEASE=NO_GO",
        "M40936_ORIGINAL_DB_PRIVILEGES=NOT_ATTESTED",
        "M40936_GUC_FORGED_PRICE_SELECT=STILL_EXPOSED_NO_GO",
    ):
        assert required in source


def test_all_historical_price_and_promotion_insert_grants_are_accounted_for():
    price_old = SQL011.read_text(encoding="utf-8")
    price_new = SQL112.read_text(encoding="utf-8")
    promo = SQL113.read_text(encoding="utf-8")
    src = RUNNER.read_text(encoding="utf-8")
    assert "GRANT INSERT(plan_tier,monthly_price,changed_by,reason)" in price_old
    assert "GRANT INSERT (annual_price)" in price_new
    assert "GRANT INSERT(campaign_id,revision,plan_tier,billing_period" in promo
    for name in ("plan_tier", "monthly_price", "changed_by", "reason", "annual_price"):
        assert '"' + name + '"' in src
    assert "REVOKE INSERT (" in src
    assert "REVOKE INSERT ON " in src
    assert "has_column_privilege" in src
    assert "FORGED_MASTER_PRICE_WRITE" in src
    assert "FORGED_MASTER_PROMOTION_WRITE" in src
    assert "BEFORE_ACL_PRICE_AND_PROMO_WRITES=CONFIRMED" in src
    assert "LEGACY_PRICE_SELECT_PRESERVED=PASS" in src
    assert "SQL011 synthetic fixture" in src


def test_no_installation_or_local_postgresql_side_effects():
    source = RUNNER.read_text()
    ast.parse(source)
    for forbidden in (
        "127.0.0.1:5433", "frcaixinha_aistudio_dev", "frc_ai_owner",
        "subprocess.Popen(", "os.system(", "pg_ctl", "pg_dump",
        "CREATE DATABASE", "DROP DATABASE", "ALTER SYSTEM",
    ):
        assert forbidden not in source
    assert "M40936_MIGRATIONS=NONE" in source
    assert "M40936_SERVICE_RESTARTS=NONE" in source
    assert "M40936_PRODUCTION=BLOCKED" in source


def test_ci_only_pg18_and_off_flags():
    yaml = CI.read_text()
    for entry in (
        "postgres:18", "55433:5432", "CI_M40936_DISPOSABLE: '1'",
        "CI_M40900_DISPOSABLE: '1'", "CI_M40560_DISPOSABLE: '1'",
        "FRCAIXINHA_CI_ISOLATED: '1'", "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'", "ATIVACAO_REAL: 'OFF'",
        "contents: read", "m40936_price_promo_acl_rehearsal_disposable.py",
    ):
        assert entry in yaml
    doc = DOC.read_text()
    for needed in (
        "M40570", "M40730", "M40900", "SQL011", "SQL112",
        "SQL113", "NO-GO", "PRODUCTION=BLOCKED", "MIGRATIONS=NONE",
    ):
        assert needed in doc


def test_money_mode_stays_blocked():
    from app.m40840_financial_sql_release_no_go import (
        FinancialSQLReleaseBlocked, require_nonproduction_financial_sql,
    )
    with pytest.raises(FinancialSQLReleaseBlocked):
        require_nonproduction_financial_sql({
            "ENVIRONMENT": "production", "PIX_REAL": "OFF",
            "PAGAMENTOS_REAIS": "OFF", "ATIVACAO_REAL": "OFF",
        })
