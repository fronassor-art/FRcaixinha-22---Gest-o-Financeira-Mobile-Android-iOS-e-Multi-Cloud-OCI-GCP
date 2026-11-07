"""M25400 — canonical contract bytes via RLS, no acceptance, no DB writes."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import os

import pytest
from fastapi import HTTPException

from app.canonical_contract_store import (
    ContractBodyUnavailable, _read_immutable_document,
    load_published_contract_body,
)
from app.dependencies import AuthenticatedSession
from app.models import InvitationContractReadinessRequest
from app.routers.invitations import fetch_canonical_contract_content


BODY = "Contrato sintético de homologação v1\nCláusula 2.\n"
DIGEST = sha256(BODY.encode("utf-8")).hexdigest()


def actor(role="TENANT_ADMIN", tenant=None, master=False):
    return AuthenticatedSession(
        str(uuid4()), role, str(tenant) if tenant else None,
        "test@example.com", "Conta sintética", master,
    )


def request(tenant, document, role="TENANT_MEMBER"):
    return InvitationContractReadinessRequest(
        target_role=role, tenant_id=tenant, required_document_id=document,
    )


def store(tmp_path: Path, document, text=BODY, digest=DIGEST):
    root = tmp_path / "contracts"
    root.mkdir()
    root.chmod(0o700)
    file = root / (str(document) + ".txt")
    file.write_bytes(text.encode("utf-8"))
    file.chmod(0o400)
    return str(root)


class SelectOnly:
    def __init__(self, document, active=True, digest=DIGEST):
        self.document = document
        self.active = active
        self.digest = digest
        self.calls = []
    async def fetchval(self, sql, *args):
        assert "SELECT EXISTS" in sql
        assert "public.tenants" in sql
        assert "status='ATIVO'" in sql
        self.calls.append(("tenant", args))
        return self.active
    async def fetchrow(self, sql, *args):
        assert "SELECT id,version_label,sha256,published_at" in sql
        assert "published_at IS NOT NULL" in sql
        self.calls.append(("document", args))
        if self.digest is None:
            return None
        return {
            "id": self.document, "version_label": "1.0",
            "sha256": self.digest,
            "published_at": datetime(2026, 11, 7, tzinfo=timezone.utc),
        }


@pytest.mark.asyncio
async def test_published_file_is_delivered_identically_but_no_acceptance(tmp_path):
    tenant, document = uuid4(), uuid4()
    root = store(tmp_path, document)
    conn = SelectOnly(document)
    response = await fetch_canonical_contract_content(
        request(tenant, document), actor(tenant=tenant), conn,
    ) if False else await load_published_contract_body(
        session=actor(tenant=tenant), payload=request(tenant, document),
        conn=conn, content_root=root,
    )
    assert response["contract_text"] == BODY
    assert response["sha256"] == DIGEST
    assert response["integrity_verified"] is True
    assert response["body_available"] is True
    assert response["scope"] == "AI_STUDIO_CANONICAL_CONTRACT_BODY"
    for flag in ("acceptance_recorded","invitation_created",
                 "activation_authorized","writes_performed"):
        assert response[flag] is False
    assert conn.calls == [("tenant", (tenant,)), ("document", (document,))]


@pytest.mark.asyncio
async def test_same_route_injects_configured_store(tmp_path, monkeypatch):
    tenant, document = uuid4(), uuid4()
    monkeypatch.setenv("FR_FINANCE_CANONICAL_CONTRACT_DIR", store(tmp_path, document))
    response = await fetch_canonical_contract_content(
        request(tenant, document), actor(tenant=tenant), SelectOnly(document),
    )
    assert response["contract_text"] == BODY


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_text", [
    BODY + " ",
    BODY.replace("\n", "\r\n"),
    BODY.replace("Cláusula", "Clausula"),
])
async def test_modified_files_fail_closed_and_expose_no_text(tmp_path, bad_text):
    tenant, document = uuid4(), uuid4()
    root = store(tmp_path, document, bad_text)
    with pytest.raises(HTTPException) as exc:
        await load_published_contract_body(
            session=actor(tenant=tenant), payload=request(tenant, document),
            conn=SelectOnly(document), content_root=root,
        )
    assert exc.value.status_code == 503
    assert BODY not in str(exc.value.detail)
    assert str(document) not in str(exc.value.detail)


@pytest.mark.asyncio
async def test_inactive_tenant_and_unpublished_document_no_file_read(tmp_path):
    tenant, document = uuid4(), uuid4()
    root = store(tmp_path, document)
    for kwargs, expected_calls in (
        ({"active": False}, ["tenant"]),
        ({"digest": None}, ["tenant", "document"]),
    ):
        db = SelectOnly(document, **kwargs)
        with pytest.raises(HTTPException) as exc:
            await load_published_contract_body(
                session=actor(tenant=tenant), payload=request(tenant, document),
                conn=db, content_root=root,
            )
        assert exc.value.status_code == 404
        assert [key for key, _ in db.calls] == expected_calls


@pytest.mark.asyncio
async def test_cross_tenant_and_member_denied_without_query(tmp_path):
    tenant, other, document = uuid4(), uuid4(), uuid4()
    root = store(tmp_path, document)
    for user, data in (
        (actor(tenant=tenant), request(other, document)),
        (actor("TENANT_MEMBER", tenant), request(tenant, document)),
        (actor("MASTER", master=False), request(tenant, document, "TENANT_ADMIN")),
        (actor("MASTER", master=True), request(tenant, document)),
    ):
        db = SelectOnly(document)
        with pytest.raises(HTTPException) as exc:
            await load_published_contract_body(
                session=user, payload=data, conn=db, content_root=root,
            )
        assert exc.value.status_code == 403
        assert not db.calls


@pytest.mark.asyncio
async def test_valid_master_scope_can_only_read_admin_preparation(tmp_path):
    tenant, document = uuid4(), uuid4()
    root = store(tmp_path, document)
    value = await load_published_contract_body(
        session=actor("MASTER", master=True),
        payload=request(tenant, document, "TENANT_ADMIN"),
        conn=SelectOnly(document),
        content_root=root,
    )
    assert value["contract_text"] == BODY
    assert value["activation_authorized"] is False


def test_rejects_unconfigured_or_unsafe_directory(tmp_path):
    document = uuid4()
    root = store(tmp_path, document)
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(document, DIGEST, "")
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(document, DIGEST, "relative/path")
    Path(root).chmod(0o777)
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(document, DIGEST, root)


def test_rejects_world_writable_and_symlink_file(tmp_path):
    document = uuid4()
    root = store(tmp_path, document)
    file = Path(root) / (str(document) + ".txt")
    file.chmod(0o644)
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(document, DIGEST, root)
    file.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_text(BODY, encoding="utf-8")
    file.symlink_to(outside)
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(document, DIGEST, root)


def test_rejects_missing_or_oversize_body(tmp_path):
    document = uuid4()
    root = store(tmp_path, document)
    file = Path(root) / (str(document) + ".txt")
    file.unlink()
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(document, DIGEST, root)
    file.write_bytes(b"A" * 70000)
    file.chmod(0o400)
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(document, DIGEST, root)


def test_body_read_routes_require_rls_not_ci_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    route = (root / "backend/app/routers/invitations.py").read_text()
    service = (root / "backend/app/canonical_contract_store.py").read_text()
    assert '@router.post("/preflight/contract-content")' in route
    assert "Depends(get_rls_db_connection)" in route
    assert "Depends(get_current_session)" in route
    assert "prepare_invitation_ci" not in route
    assert "register_new_invited_identity_ci" not in route
    assert "UPDATE public" not in service
    assert "INSERT INTO public" not in service
