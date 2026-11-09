"""M280: fingerprint nao sensivel do FastAPI carregado na memoria; sem banco real."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, backend_runtime_contract, health_check

ROOT = Path(__file__).resolve().parents[2]


def test_health_identifies_only_aistudio():
    payload = health_check()
    assert payload["app"] == "FR Finance"
    assert "2.2" not in payload["app"]


def test_runtime_endpoint_reports_loaded_caps_and_explicit_non_authorization():
    payload = backend_runtime_contract()
    assert payload == {
        "project": "FRCAIXINHA_AI_STUDIO_MOBILE",
        "runtime_contract": "AI_STUDIO_M280_RUNTIME_V1",
        "ledger_account_limit": 500,
        "ledger_transaction_limit": 500,
        "ledger_entry_limit": 100,
        "financial_closing_authorized": False,
        "bank_reconciled": False,
        "runtime_git_sha_verified": False,
    }
    assert all(
        "password" not in key and "token" not in key and
        "database_url" not in key and "private" not in key
        for key in payload
    )


def test_runtime_route_has_no_cache_and_no_auth_or_database_write():
    with TestClient(app) as client:
        response = client.get("/api/health/runtime")
        assert response.status_code == 200
        assert response.json() == backend_runtime_contract()
        assert response.headers.get("cache-control") == "no-store"
        assert response.headers.get("pragma") == "no-cache"


def test_local_script_never_includes_restart_or_database_mutation():
    script = (ROOT / "backend/scripts/aistudio_280_runtime_readonly.sh").read_text()
    assert "AI_STUDIO_M280_RUNTIME_V1" in script
    assert "frcaixinha_aistudio_pg18" in script
    assert "5433" in script
    assert "8000" in script
    assert "git rev-parse HEAD" in script
    for dangerous in ("kill -", "pg_ctl stop", "DROP DATABASE", "CREATE ROLE",
                      "pg_restore", "psql -c", "curl -X POST", "git push"):
        assert dangerous not in script
