"""M25000 — leitura documental sob RLS, exclusivamente testes sem banco.

Não emite convites, não usa contas reais e não inicia qualquer conexão.
"""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies import AuthenticatedSession
from app.models import InvitationContractReadinessRequest
from app.invitation_preflight import invitation_contract_readiness
from app.routers.invitations import preview_published_contract_readiness


def actor(role, tenant=None, is_master=False):
    return AuthenticatedSession(
        str(uuid4()), role, str(tenant) if tenant else None,
        "synthetic-actor@example.com", "Synthetic actor", is_master,
    )


class ReadOnlyConn:
    def __init__(self, *, active=True, published=True):
        self.active = active
        self.published = published
        self.queries = []

    async def fetchval(self, statement, argument):
        assert statement.startswith("SELECT EXISTS(")
        assert "$1::uuid" in statement
        assert "INSERT" not in statement.upper()
        assert "UPDATE" not in statement.upper()
        assert "DELETE" not in statement.upper()
        self.queries.append((statement, argument))
        if "public.tenants" in statement:
            assert "status='ATIVO'" in statement
            return self.active
        if "public.contract_documents" in statement:
            assert "document_kind='TENANT_MEMBERSHIP'" in statement
            assert "published_at IS NOT NULL" in statement
            return self.published
        raise AssertionError("Consulta não permitida")


def request(role, tenant=None, document=None):
    return InvitationContractReadinessRequest(
        target_role=role,
        tenant_id=tenant or uuid4(),
        required_document_id=document or uuid4(),
    )


@pytest.mark.asyncio
async def test_admin_reads_published_document_but_cannot_issue_invitation():
    tenant, document = uuid4(), uuid4()
    db = ReadOnlyConn()
    result = await preview_published_contract_readiness(
        request("TENANT_MEMBER", tenant, document),
        actor("TENANT_ADMIN", tenant),
        db,
    )
    assert result["source"] == "POSTGRESQL_RLS"
    assert result["tenant_active_verified"] is True
    assert result["document_published_verified"] is True
    assert result["document_kind"] == "TENANT_MEMBERSHIP"
    assert result["target_role"] == "TENANT_MEMBER"
    assert result["status"] == "BLOCKED"
    assert "RUNTIME_INVITATION_ISSUANCE_DISABLED" in result["blocking_gates"]
    assert "RECIPIENT_EMAIL_OWNERSHIP_NOT_VERIFIED" in result["blocking_gates"]
    assert [entry[1] for entry in db.queries] == [tenant, document]
    for field in (
        "recipient_email_verified", "provider_delivery_verified",
        "activation_authorized", "invitation_created",
        "email_sent", "user_created", "membership_changed",
        "writes_performed",
    ):
        assert result[field] is False
    for forbidden in (str(tenant), str(document), "synthetic-actor@example.com"):
        assert forbidden not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("active,published,missing", [
    (False, True, "ACTIVE_TENANT_NOT_ATTESTED"),
    (True, False, "PUBLISHED_MEMBERSHIP_CONTRACT_NOT_ATTESTED"),
    (False, False, "PUBLISHED_MEMBERSHIP_CONTRACT_NOT_ATTESTED"),
])
async def test_unavailable_tenant_or_document_remains_blocked(active, published, missing):
    tenant = uuid4()
    db = ReadOnlyConn(active=active, published=published)
    result = await invitation_contract_readiness(
        session=actor("TENANT_ADMIN", tenant),
        payload=request("TENANT_MEMBER", tenant),
        conn=db,
    )
    assert result["status"] == "BLOCKED"
    assert result["tenant_active_verified"] is active
    assert result["document_published_verified"] is published
    assert missing in result["blocking_gates"]


@pytest.mark.asyncio
async def test_master_requires_admin_role_and_stays_unapproved():
    db = ReadOnlyConn()
    response = await invitation_contract_readiness(
        session=actor("MASTER", is_master=True),
        payload=request("TENANT_ADMIN"),
        conn=db,
    )
    assert response["document_published_verified"] is True
    assert "MASTER_MFA_NOT_ATTESTED" in response["blocking_gates"]
    assert "INDEPENDENT_APPROVAL_NOT_ATTESTED" in response["blocking_gates"]
    assert "PLATFORM_LICENSE_ACCEPTANCE_NOT_VERIFIED" in response["blocking_gates"]
    for candidate in (
        actor("MASTER", is_master=False),
        actor("TENANT_MEMBER", uuid4()),
    ):
        conn = ReadOnlyConn()
        with pytest.raises(HTTPException) as exc:
            await invitation_contract_readiness(
                session=candidate, payload=request("TENANT_ADMIN"), conn=conn
            )
        assert exc.value.status_code == 403
        assert not conn.queries


@pytest.mark.asyncio
async def test_cross_tenant_denied_before_sql_even_with_valid_contract():
    tenant, other = uuid4(), uuid4()
    db = ReadOnlyConn()
    with pytest.raises(HTTPException) as exc:
        await invitation_contract_readiness(
            session=actor("TENANT_ADMIN", tenant),
            payload=request("TENANT_MEMBER", other),
            conn=db,
        )
    assert exc.value.status_code == 403
    assert not db.queries


def test_contract_request_does_not_accept_email_and_requires_two_uuids():
    valid = {
        "target_role": "TENANT_MEMBER",
        "tenant_id": str(uuid4()),
        "required_document_id": str(uuid4()),
    }
    assert InvitationContractReadinessRequest.model_validate(valid).tenant_id
    for missing in ("tenant_id", "required_document_id"):
        wrong = dict(valid)
        wrong.pop(missing)
        with pytest.raises(ValidationError):
            InvitationContractReadinessRequest.model_validate(wrong)
    for bad_role in ("MASTER", "SOME_ROLE"):
        with pytest.raises(ValidationError):
            InvitationContractReadinessRequest.model_validate(
                {**valid, "target_role": bad_role}
            )


def test_route_reuses_authenticated_rls_dependency_and_no_ci_executor():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    router = (root / "backend/app/routers/invitations.py").read_text()
    service = (root / "backend/app/invitation_preflight.py").read_text()
    models = (root / "backend/app/models.py").read_text()
    assert '@router.post("/preflight/contracts")' in router
    assert "Depends(get_rls_db_connection)" in router
    assert "Depends(get_current_session)" in router
    assert "class InvitationContractReadinessRequest" in models
    assert "target_email" not in models.split(
        "class InvitationContractReadinessRequest", 1
    )[1].split("class ContextSwitchRequest", 1)[0]
    assert "prepare_invitation_ci" not in router
    assert "register_new_invited_identity_ci" not in router
    assert "UPDATE public" not in service
    assert "INSERT INTO public" not in service
