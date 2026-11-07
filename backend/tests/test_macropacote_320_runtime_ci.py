"""M320 runtime e checkpoint: sem PII, env ou segredo."""
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app, backend_m320_feature_contract

ROOT=Path(__file__).resolve().parents[2]


def test_contract_is_loaded_without_database_or_credentials():
    assert backend_m320_feature_contract()=={
        "product":"FR Caixinha",
        "workstream":"AI_STUDIO",
        "contract":"FR_CAIXINHA_M320_EMPTY_LEDGER_V1",
        "account_directory_read_only":True,
        "account_directory_max_accounts":500,
        "tenant_admin_only":True,
        "empty_ledger_balance_values_hidden":True,
        "financial_closing_authorized":False,
        "real_payments_enabled":False,
        "bank_reconciled":False,
        "runtime_git_sha_verified":False,
    }


def test_http_readiness_and_no_auth():
    with TestClient(app) as client:
        response=client.get("/api/health/features/m320")
        assert response.status_code==200
        assert response.json()==backend_m320_feature_contract()
        assert response.headers["cache-control"]=="no-store"
        assert response.headers["pragma"]=="no-cache"
        unauthorized=client.get(
            "/api/v1/tenants/00000000-0000-4000-8000-000000000001/ledger/accounts/directory"
        )
        assert unauthorized.status_code==401


def test_shell_gate_does_not_modify_git_or_pg():
    shell=(ROOT/"backend/scripts/aistudio_320_checkpoint_readonly.sh").read_text()
    assert "aistudio_300_checkpoint_readonly.sh" in shell
    assert "FR_CAIXINHA_M320_EMPTY_LEDGER_V1" in shell
    assert "5433" not in shell or "aistudio_300_checkpoint" in shell
    assert "M320_DIRETORIO_SEM_SESSAO_401=PASS" in shell
    for bad in ("pg_restore","pg_ctl stop","psql -c","git push","git reset",
                "git clean","DROP TABLE","kill -","curl -X POST"):
        assert bad not in shell
