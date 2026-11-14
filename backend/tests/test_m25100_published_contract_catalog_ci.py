"""M25100 — seleção de versão publicada sem criar convites, aceitar ou enviar."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies import AuthenticatedSession
from app.models import InvitationContractCatalogRequest
from app.routers.invitations import preview_published_contract_catalog


def session(role, tenant=None, is_master=False):
    return AuthenticatedSession(
        str(uuid4()), role, str(tenant) if tenant else None,
        "tester@example.com", "CI ficticio", is_master,
    )


def payload(role, tenant=None):
    return InvitationContractCatalogRequest(
        target_role=role, tenant_id=tenant or uuid4()
    )


class SelectOnly:
    def __init__(self, *, active=True, records=()):
        self.active = active
        self.records = records
        self.queries = []

    async def fetchval(self, sql, *args):
        assert sql.startswith("SELECT EXISTS(")
        assert "public.tenants" in sql and "status='ATIVO'" in sql
        assert len(args) == 1
        self.queries.append(("tenant", args))
        return self.active

    async def fetch(self, sql, *args):
        assert sql.startswith("SELECT ")
        assert not args
        assert "FROM public.contract_documents" in sql
        assert "document_kind='TENANT_MEMBERSHIP'" in sql
        assert "published_at IS NOT NULL" in sql
        assert "LIMIT 20" in sql
        assert "source_reference" not in sql
        assert "recipient" not in sql
        self.queries.append(("documents", args))
        return self.records


@pytest.mark.asyncio
async def test_admin_can_preview_published_versions_without_acceptance_or_delivery():
    tenant, doc = uuid4(), uuid4()
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    conn = SelectOnly(records=[
        dict(id=doc, version_label="2026.11", sha256="a" * 64,
             published_at=now),
    ])
    report = await preview_published_contract_catalog(
        payload("TENANT_MEMBER", tenant),
        session("TENANT_ADMIN", tenant), conn,
    )
    assert report["source"] == "POSTGRESQL_RLS"
    assert report["status"] == "BLOCKED"
    assert report["tenant_active_verified"] is True
    assert report["documents"] == [
        dict(document_id=str(doc), version="2026.11",
             sha256="a" * 64, published_at=now.isoformat()),
    ]
    assert report["contract_body_available"] is False
    for field in (
        "invitation_created", "acceptance_recorded", "delivery_verified",
        "activation_authorized", "writes_performed",
    ):
        assert report[field] is False
    assert "CONTRACT_BODY_DISPLAY_AND_DIGEST_VERIFICATION_REQUIRED" in report["blocking_gates"]
    assert conn.queries == [("tenant", (tenant,)), ("documents", ())]


@pytest.mark.asyncio
async def test_inactive_tenant_never_loads_published_documents():
    tenant = uuid4()
    conn = SelectOnly(active=False)
    report = await preview_published_contract_catalog(
        payload("TENANT_MEMBER", tenant),
        session("TENANT_ADMIN", tenant), conn,
    )
    assert report["status"] == "BLOCKED"
    assert report["documents"] == []
    assert conn.queries == [("tenant", (tenant,))]


@pytest.mark.asyncio
async def test_admin_cannot_read_other_tenant_before_any_sql():
    tenant, other = uuid4(), uuid4()
    conn = SelectOnly()
    with pytest.raises(HTTPException) as err:
        await preview_published_contract_catalog(
            payload("TENANT_MEMBER", other),
            session("TENANT_ADMIN", tenant), conn,
        )
    assert err.value.status_code == 403
    assert conn.queries == []


@pytest.mark.asyncio
async def test_member_and_fake_master_denied_before_any_sql():
    for candidate in (
        session("TENANT_MEMBER", uuid4()),
        session("MASTER", is_master=False),
    ):
        conn = SelectOnly()
        with pytest.raises(HTTPException) as err:
            await preview_published_contract_catalog(
                payload("TENANT_ADMIN", uuid4()),
                candidate, conn,
            )
        assert err.value.status_code == 403
        assert not conn.queries


@pytest.mark.asyncio
async def test_master_role_safely_previews_admin_document_metadata_only():
    conn = SelectOnly()
    report = await preview_published_contract_catalog(
        payload("TENANT_ADMIN"), session("MASTER", is_master=True), conn,
    )
    assert report["target_role"] == "TENANT_ADMIN"
    assert report["status"] == "BLOCKED"
    assert "MASTER_MFA_NOT_ATTESTED" in report["blocking_gates"]
    assert "INDEPENDENT_APPROVAL_NOT_ATTESTED" in report["blocking_gates"]
    assert report["documents"] == []
    assert [op for op, _ in conn.queries] == ["tenant", "documents"]


def test_catalog_payload_rejects_absent_or_invalid_tenant_and_master():
    valid = {"target_role": "TENANT_MEMBER", "tenant_id": str(uuid4())}
    assert InvitationContractCatalogRequest.model_validate(valid).tenant_id
    for invalid in (
        {"target_role": "TENANT_MEMBER"},
        {"target_role": "MASTER", "tenant_id": str(uuid4())},
        {"target_role": "TENANT_ADMIN", "tenant_id": "not-a-uuid"},
    ):
        with pytest.raises(ValidationError):
            InvitationContractCatalogRequest.model_validate(invalid)


def test_catalog_code_has_no_mutations_no_secrets_or_public_registration():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    route = (root / "backend/app/routers/invitations.py").read_text()
    service = (root / "backend/app/invitation_preflight.py").read_text()
    assert '@router.post("/preflight/contract-catalog")' in route
    assert "Depends(get_current_session)" in route
    assert "Depends(get_rls_db_connection)" in route
    assert "prepare_invitation_ci" not in route
    assert "register_new_invited_identity_ci" not in route
    assert "INSERT INTO public" not in service
    assert "UPDATE public" not in service
    assert "DELETE FROM public" not in service
