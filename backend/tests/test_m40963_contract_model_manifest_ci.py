"""M40963: public draft-model manifest is GET-only, DB-free and digest-bound."""
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.contract_models import contract_model_manifest, router

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "docs" / "FR_Finance_Caderno_Mestre_V2_2_2026-11-24.md"
EXPECTED_KINDS = {
    "SAAS_LICENSE": ("## CONTRATO A — ", "## CONTRATO B — "),
    "MEMBER_ADHESION": ("## CONTRATO B — ", "## Matriz de responsabilidades contratuais"),
}


def _expected_body(kind: str) -> str:
    source = MASTER.read_text(encoding="utf-8")
    start, end = EXPECTED_KINDS[kind]
    return source[source.index(start):source.index(end)]


def test_manifest_binds_exact_master_text_and_never_enables_acceptance():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    for kind in EXPECTED_KINDS:
        response = client.get(f"/api/v1/public/contract-models/v2.2/{kind}")
        assert response.status_code == 200
        body = response.json()
        assert body == contract_model_manifest(kind)
        assert body["sha256"] == sha256(_expected_body(kind).encode("utf-8")).hexdigest()
        assert body["state"] == "DRAFT_ONLY"
        assert body["acceptance_enabled"] is False
        assert "body" not in body
        assert "tenant_id" not in body
        assert "recipient_id" not in body
        assert "nonce" not in body


def test_manifest_rejects_unknown_kind_and_mutation_methods():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    url = "/api/v1/public/contract-models/v2.2/SAAS_LICENSE"
    assert client.get(url + "-OTHER").status_code == 404
    assert client.post(url, json={"accept": True}).status_code == 405
    assert client.put(url, json={"accept": True}).status_code == 405
    assert client.delete(url).status_code == 405


def test_manifest_is_pure_and_does_not_import_database_or_identity_dependencies():
    import inspect
    import app.routers.contract_models as module

    source = inspect.getsource(module)
    assert "get_rls_db_connection" not in source
    assert "get_current_session" not in source
    assert "nonce" not in source.lower()
    assert "signature" not in source.lower()
    assert contract_model_manifest("SAAS_LICENSE")["acceptance_enabled"] is False
