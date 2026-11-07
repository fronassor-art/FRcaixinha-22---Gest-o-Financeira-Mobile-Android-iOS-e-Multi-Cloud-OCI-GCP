"""M25200 — texto UTF-8 exato contra SHA de versão publicada, sem gravar."""
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.contract_text_integrity import (
    MAX_CONTRACT_TEXT_BYTES, exact_utf8_sha256, verify_contract_body_digest,
)
from app.dependencies import AuthenticatedSession
from app.models import InvitationContractTextIntegrityRequest
from app.routers.invitations import preview_contract_text_integrity


BODY = "Termo de adesão fictício M25200 — cláusula 1.\nAceito apenas em teste.\n"


def session(role, tenant=None, is_master=False):
    return AuthenticatedSession(
        str(uuid4()), role, str(tenant) if tenant else None,
        "test-only@example.com", "Pessoa CI fictícia", is_master,
    )


def payload(role, tenant=None, document=None, text=BODY):
    return InvitationContractTextIntegrityRequest(
        target_role=role, tenant_id=tenant or uuid4(),
        required_document_id=document or uuid4(),
        contract_text=text,
    )


class OnlySelect:
    def __init__(self, *, active=True, digest=None):
        self.active = active
        self.digest = digest
        self.queries = []

    async def fetchval(self, sql, *args):
        assert sql.startswith("SELECT ")
        assert "INSERT" not in sql.upper()
        assert "UPDATE" not in sql.upper()
        assert "DELETE" not in sql.upper()
        assert len(args) == 1
        self.queries.append((sql, args[0]))
        if "public.tenants" in sql:
            assert "status='ATIVO'" in sql
            return self.active
        if "public.contract_documents" in sql:
            assert "document_kind='TENANT_MEMBERSHIP'" in sql
            assert "published_at IS NOT NULL" in sql
            return self.digest
        raise AssertionError("Consulta inesperada")


@pytest.mark.asyncio
async def test_exact_body_published_hash_match_never_authorizes_acceptance():
    tenant, document = uuid4(), uuid4()
    digest = sha256(BODY.encode("utf-8")).hexdigest()
    db = OnlySelect(digest=digest)
    result = await preview_contract_text_integrity(
        payload("TENANT_MEMBER", tenant, document), session("TENANT_ADMIN", tenant), db,
    )
    assert result["status"] == "BLOCKED"
    assert result["source"] == "POSTGRESQL_RLS"
    assert result["document_published_verified"] is True
    assert result["exact_utf8_document_digest_matched"] is True
    assert result["canonical_document_hosted"] is False
    assert result["body_rendered_for_invitee"] is False
    assert result["target_role"] == "TENANT_MEMBER"
    assert [q[1] for q in db.queries] == [tenant, document]
    for key in (
        "consent_verified", "acceptance_recorded", "invitation_created",
        "email_sent", "user_created", "membership_changed",
        "writes_performed", "activation_authorized",
    ):
        assert result[key] is False
    for value in (BODY, digest, str(tenant), str(document), "test-only@example.com"):
        assert value not in str(result)
    assert "TRANSACTIONAL_ACCEPTANCE_NOT_IMPLEMENTED" in result["blocking_gates"]


@pytest.mark.asyncio
@pytest.mark.parametrize("altered", [
    BODY.replace("\n", "\r\n"),
    BODY + " ",
    BODY.replace("adesão", "adesão"),
    BODY.replace("Aceito", "Não aceito"),
])
async def test_crlf_space_unicode_normalization_and_content_changes_fail(altered):
    tenant = uuid4()
    db = OnlySelect(digest=exact_utf8_sha256(BODY))
    result = await verify_contract_body_digest(
        session=session("TENANT_ADMIN", tenant),
        payload=payload("TENANT_MEMBER", tenant, text=altered),
        conn=db,
    )
    assert result["exact_utf8_document_digest_matched"] is False
    assert "EXACT_UTF8_DOCUMENT_DIGEST_NOT_MATCHED" in result["blocking_gates"]
    assert result["status"] == "BLOCKED"


@pytest.mark.asyncio
async def test_missing_document_or_inactive_tenant_denies_digest():
    tenant = uuid4()
    for db in (
        OnlySelect(active=True, digest=None),
        OnlySelect(active=False, digest=exact_utf8_sha256(BODY)),
    ):
        result = await verify_contract_body_digest(
            session=session("TENANT_ADMIN", tenant),
            payload=payload("TENANT_MEMBER", tenant),
            conn=db,
        )
        assert result["exact_utf8_document_digest_matched"] is False
        assert result["document_published_verified"] is False
        assert result["status"] == "BLOCKED"
    assert len(db.queries) == 1


@pytest.mark.asyncio
async def test_cross_tenant_member_and_fake_master_denied_before_select():
    tenant = uuid4()
    cases = [
        (session("TENANT_ADMIN", tenant), payload("TENANT_MEMBER", uuid4())),
        (session("TENANT_MEMBER", tenant), payload("TENANT_MEMBER", tenant)),
        (session("MASTER", is_master=False), payload("TENANT_ADMIN", tenant)),
        (session("MASTER", is_master=True), payload("TENANT_MEMBER", tenant)),
    ]
    for actor, body in cases:
        db = OnlySelect(digest=exact_utf8_sha256(BODY))
        with pytest.raises(HTTPException) as exc:
            await preview_contract_text_integrity(body, actor, db)
        assert exc.value.status_code == 403
        assert db.queries == []


@pytest.mark.asyncio
async def test_master_admin_intent_remains_blocked_after_exact_match():
    body = payload("TENANT_ADMIN")
    db = OnlySelect(digest=exact_utf8_sha256(BODY))
    result = await preview_contract_text_integrity(
        body, session("MASTER", is_master=True), db,
    )
    assert result["exact_utf8_document_digest_matched"] is True
    assert result["activation_authorized"] is False
    assert "MASTER_MFA_NOT_ATTESTED" in result["blocking_gates"]
    assert "INDEPENDENT_APPROVAL_NOT_ATTESTED" in result["blocking_gates"]


def test_utf8_bytes_exact_and_input_size_are_enforced():
    assert exact_utf8_sha256(BODY) == sha256(BODY.encode("utf-8")).hexdigest()
    assert exact_utf8_sha256("á") != exact_utf8_sha256("a")
    assert exact_utf8_sha256("abc\r\n") != exact_utf8_sha256("abc\n")
    for invalid in ("", "á" * MAX_CONTRACT_TEXT_BYTES, "A" * (MAX_CONTRACT_TEXT_BYTES + 1), "\ud800"):
        with pytest.raises(HTTPException) as exc:
            exact_utf8_sha256(invalid)
        assert exc.value.status_code == 422
    assert exact_utf8_sha256("A" * MAX_CONTRACT_TEXT_BYTES)


def test_request_does_not_allow_absent_body_and_invalid_ids():
    correct = {
        "target_role": "TENANT_MEMBER",
        "tenant_id": str(uuid4()),
        "required_document_id": str(uuid4()),
        "contract_text": BODY,
    }
    assert InvitationContractTextIntegrityRequest.model_validate(correct).contract_text == BODY
    for key in ("tenant_id", "required_document_id", "contract_text"):
        invalid = dict(correct)
        invalid.pop(key)
        with pytest.raises(ValidationError):
            InvitationContractTextIntegrityRequest.model_validate(invalid)
    with pytest.raises(ValidationError):
        InvitationContractTextIntegrityRequest.model_validate(
            {**correct, "target_role": "MASTER"}
        )


def test_route_uses_session_and_rls_not_ci_executor_or_db_writes():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    router = (root / "backend/app/routers/invitations.py").read_text()
    service = (root / "backend/app/contract_text_integrity.py").read_text()
    assert '@router.post("/preflight/contract-text")' in router
    assert "Depends(get_current_session)" in router
    assert "Depends(get_rls_db_connection)" in router
    assert "prepare_invitation_ci" not in router
    assert "register_new_invited_identity_ci" not in router
    assert "INSERT INTO " not in service
    assert "UPDATE public" not in service
    assert "DELETE FROM public" not in service
    assert "hmac.compare_digest" in service
    assert "contract_text" not in service.split('return {', 1)[1]
