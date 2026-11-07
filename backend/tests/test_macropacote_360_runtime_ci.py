"""M360: fingerprints do fonte no import; nao provam SHA completo de runtime."""
import hashlib
import importlib
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app, backend_m360_feature_contract
from app.routers import ledger
import app.ledger_keyset as keyset

main = importlib.import_module("app.main")
ROOT = Path(__file__).resolve().parents[2]


def test_m360_contract_and_import_fingerprints_only():
    body = backend_m360_feature_contract()
    assert body["product"] == "FR Caixinha"
    assert body["workstream"] == "AI_STUDIO"
    assert body["contract"] == "FR_CAIXINHA_M360_KEYSET_V1"
    assert body["page_max"] == 50
    assert body["keyset_read_only"] is True
    assert body["tenant_admin_only"] is True
    assert body["runtime_git_sha_verified"] is False
    for key in ("real_payments_enabled", "bank_reconciled", "financial_closing_authorized"):
        assert body[key] is False
    assert body["source_fingerprints_at_import"] == {
        "main_py": hashlib.sha256(Path(main.__file__).read_bytes()).hexdigest(),
        "ledger_py": hashlib.sha256(Path(ledger.__file__).read_bytes()).hexdigest(),
        "ledger_keyset_py": hashlib.sha256(Path(keyset.__file__).read_bytes()).hexdigest(),
    }


def test_m360_http_no_cache_and_no_secrets():
    with TestClient(app) as client:
        response = client.get("/api/health/features/m360")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == backend_m360_feature_contract()
    for sensitive in ("password", "access_token", "database_url", "cpf", "api_key"):
        assert sensitive not in response.text.lower()


def test_termux_shell_is_readonly_and_explicitly_disclaims_full_sha():
    text = (ROOT / "backend/scripts/aistudio_360_checkpoint_readonly.sh").read_text()
    assert "aistudio_320_checkpoint_readonly.sh" in text
    assert "FR_CAIXINHA_M360_KEYSET_V1" in text
    assert "M360_SOURCE_FINGERPRINTS_MATCH=PASS" in text
    assert "M360_RUNTIME_FULL_GIT_SHA=NAO_COMPROVADO" in text
    for forbidden in ("pg_restore", "git reset", "git clean", "git push",
                      "DROP TABLE", "psql -c", "curl -X POST", "pg_ctl stop"):
        assert forbidden not in text
