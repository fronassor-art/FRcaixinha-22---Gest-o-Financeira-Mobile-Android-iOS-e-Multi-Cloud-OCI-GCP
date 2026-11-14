"""M24500 — consistent version-hash consent for existing identities (no DB)."""
import inspect
from pathlib import Path

from app.account_lifecycle import accept_existing_identity_ci

ROOT=Path(__file__).resolve().parents[2]


def _function_source():
    code=(ROOT/"backend/app/account_lifecycle.py").read_text()
    start=code.index("def accept_existing_identity_ci(")
    end=code.index("def prepare_password_reset_ci(",start)
    return code[start:end]


def test_default_denies_unacknowledged_or_unversioned_consent():
    sig=inspect.signature(accept_existing_identity_ci)
    assert sig.parameters["consent"].default is False
    assert sig.parameters["accepted_document_sha256"].default is None
    assert sig.parameters["account_password"].default is None
    src=_function_source()
    assert "consent is not True" in src
    assert "type(accepted_document_sha256) is not str" in src
    assert "len(accepted_document_sha256) != 64" in src
    assert "any(ch not in '0123456789abcdef' for ch in accepted_document_sha256)" in src
    assert src.index("consent is not True") < src.index("with conn.transaction():")


def test_exact_published_document_digest_and_invite_binding():
    src=_function_source()
    assert "SELECT sha256 FROM public.contract_documents" in src
    assert "published_at IS NOT NULL" in src
    assert "document[0] != accepted_document_sha256" in src
    assert "invitation[9] != document_id" in src
    assert "accepted_document_sha256+secrets.token_hex(32)" in src


def test_existing_email_must_be_verified_before_membership_insert():
    src=_function_source()
    assert "SELECT email,status,email_verified_at FROM public.users WHERE id=%s FOR UPDATE" in src
    assert "user[2] is None" in src
    assert src.index("user[2] is None") < src.index("INSERT INTO public.memberships")


def test_immutable_acceptance_and_audit_remain_same_transaction():
    src=_function_source()
    assert "with conn.transaction():" in src
    assert "CI_INVITATION_ACCEPTED" in src
    assert "ON CONFLICT (tenant_id,user_id,role)" in src
    assert "UPDATE public.invitations SET accepted_at=now()" in src
    assert src.index("INSERT INTO public.memberships") < src.index("CI_INVITATION_ACCEPTED")


def test_registration_and_existing_identity_share_security_gates():
    src=_function_source()
    registered=(ROOT/"backend/app/invite_registration_ci.py").read_text()
    assert "accepted_document_sha256" in src and "accepted_document_sha256" in registered
    assert "required_document_id" in src and "required_document_id" in registered
    assert "CI_VERIFIED_IDENTITY" in src and "CI_VERIFIED_IDENTITY" in registered


def test_disabled_in_api_no_network_or_sql_changes():
    src=_function_source()
    router=(ROOT/"backend/app/routers/invitations.py").read_text()
    assert "_ci_only(conn)" in src
    assert "accept_existing_identity_ci" not in router
    assert "Convites ainda não implementados" in router
    assert "GRANT " not in src
    assert "oci." not in src and "requests." not in src


def test_m24500_test_is_not_mistaken_for_production_acceptance():
    backlog=(ROOT/"docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json").read_text()
    assert '"production_verified": false' in backlog
    assert '"AWAITING_CLAUSE_EVIDENCE"' in backlog
