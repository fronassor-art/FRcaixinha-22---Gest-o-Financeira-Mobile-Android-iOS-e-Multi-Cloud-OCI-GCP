"""M300: metadados carregados, sem conexão, PII ou aprovação financeira."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app, backend_feature_gates, health_check
ROOT = Path(__file__).resolve().parents[2]
def test_product_and_runtime_identity():
    assert health_check()["app"] == "FR Caixinha"
    assert backend_feature_gates() == {
        "product": "FR Caixinha",
        "workstream": "AI_STUDIO",
        "feature_contract": "FR_CAIXINHA_M300_RUNTIME_V1",
        "ledger_account_journal_page_max": 50,
        "bank_reconciled": False,
        "financial_closing_authorized": False,
        "real_payments_enabled": False,
        "master_tenant_ledger_allowed": False,
        "runtime_git_sha_verified": False,
    }
def test_feature_endpoint_without_db_and_without_caching():
    with TestClient(app) as client:
        response = client.get("/api/health/features")
        assert response.status_code == 200
        assert response.json() == backend_feature_gates()
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert all("secret" not in k.lower() and "token" not in k.lower()
                   for k in response.json())
def test_checkpoint_is_readonly_and_tied_to_ai_studio_cluster():
    source=(ROOT/"backend/scripts/aistudio_300_checkpoint_readonly.sh").read_text()
    assert "FR_CAIXINHA_M300_RUNTIME_V1" in source
    assert "frcaixinha_aistudio_pg18" in source
    assert "5433" in source and "8000" in source
    assert "git rev-parse HEAD" in source
    for forbidden in ("pg_restore","pg_dump","kill -","git push",
                      "DROP DATABASE","ALTER ROLE","source api.env"):
        assert forbidden not in source
