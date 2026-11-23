"""M40937: Master release status exposes missing SQL trust without I/O."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.launch_readiness import readiness_manifest
from app.m40840_financial_sql_release_no_go import (
    FinancialSQLReleaseBlocked,
    require_nonproduction_financial_sql,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("mode", ["development", "staging", "production", "ci"])
def test_sql_no_go_is_not_an_env_release_switch(mode):
    data = readiness_manifest({
        "ENVIRONMENT": mode,
        "FR_FINANCE_SQL_TRUST_APPROVED": "true",
        "M40936_DISPOSABLE_CI": "PASS",
        "PIX_REAL": "ON",
        "PAGAMENTOS_REAIS": "ON",
        "ATIVACAO_REAL": "ON",
    })
    sql = data["sql_trust"]
    assert data["status"] == "BLOCKED"
    assert sql["status"] == "NO_GO"
    assert sql["evidence"] == "SOURCE_ONLY_NOT_RUNTIME_ATTESTED"
    for flag in (
        "guc_identity_boundary_verified",
        "app_direct_saas_insert_revoked_verified",
        "independent_master_custody_verified",
        "staging_sql_roles_acl_verified",
        "master_write_operations_enabled",
    ):
        assert sql[flag] is False
    assert {item["code"] for item in sql["blockers"]} == {
        "M40570", "M40730", "M40936",
    }
    assert data["unverified_gates"] == 20
    assert data["real_pix_active"] is False
    assert data["writes_performed"] is False


def test_master_sql_report_contains_no_environment_secrets():
    credential = "NEVER_DISCLOSE_FAKE_SECRET_12345"
    data = readiness_manifest({
        "ENVIRONMENT": "production",
        "DATABASE_URL": f"postgresql://master:{credential}@db.invalid:5432/finance_prod",
        "AUTH_SECRET": credential,
        "FR_FINANCE_SQL_TRUST_APPROVED": credential,
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    })
    assert credential not in str(data)
    assert "postgresql://" not in str(data)


def test_readiness_is_master_only_and_does_not_auto_enable_sql():
    src = (ROOT / "backend/app/routers/master.py").read_text(encoding="utf-8")
    report = (ROOT / "backend/app/launch_readiness.py").read_text(encoding="utf-8")
    assert '@router.get("/launch-readiness")' in src
    assert 'Depends(require_master)' in src
    assert 'M40937' in report
    assert 'sql_trust' in report
    assert '"status": "NO_GO"' in report
    assert "CREATE ROLE " not in report
    assert "asyncpg.connect(" not in report
    assert "os.environ" not in report
    with pytest.raises(FinancialSQLReleaseBlocked):
        require_nonproduction_financial_sql({
            "ENVIRONMENT": "production",
            "PIX_REAL": "OFF",
            "PAGAMENTOS_REAIS": "OFF",
            "ATIVACAO_REAL": "OFF",
        })
