"""M24400 — No implicit contractual consent in invited identity registration.

This suite runs on Termux with no PostgreSQL, secret, HTTP or OCI access.
DB-atomic invite acceptance is separately tested on disposable GitHub PG18.
"""
import inspect
import json
from pathlib import Path

from app.invite_registration_ci import (
    _valid_cpf, register_new_invited_identity_ci,
)

ROOT=Path(__file__).resolve().parents[2]


def test_consent_is_explicit_and_default_deny():
    sig=inspect.signature(register_new_invited_identity_ci)
    assert sig.parameters["consent"].default is False
    assert sig.parameters["accepted_document_sha256"].default is None
    code=(ROOT/"backend/app/invite_registration_ci.py").read_text()
    assert "consent is not True" in code
    assert 're.fullmatch(r"[0-9a-f]{64}", accepted_document_sha256)' in code
    assert code.index("consent is not True")<code.index("pwd_hash=hash_password_secure(password)")


def test_contract_version_is_published_and_bound_to_invitation():
    code=(ROOT/"backend/app/invite_registration_ci.py").read_text()
    assert "SELECT sha256 FROM public.contract_documents" in code
    assert "published_at IS NOT NULL" in code
    assert "doc[0] != accepted_document_sha256" in code
    assert "expected[0] != document_id" in code
    assert 'str(document_id)+accepted_document_sha256' in code
    assert "with conn.transaction():" in code
    assert "CI_INVITED_IDENTITY_REGISTERED" in code


def test_verified_identity_cpf_checksum_rejects_obviously_wrong_values():
    assert _valid_cpf("12345678909") is True
    assert _valid_cpf("12345678900") is False
    assert _valid_cpf("11111111111") is False
    assert _valid_cpf("1234567890") is False
    assert _valid_cpf("1234567890a") is False


def test_no_public_registration_and_no_new_privilege_grants():
    code=(ROOT/"backend/app/invite_registration_ci.py").read_text()
    router=(ROOT/"backend/app/routers/invitations.py").read_text()
    assert "_ci_only(conn)" in code
    assert "register_new_invited_identity_ci" not in router
    assert "Convites ainda não implementados" in router
    assert "status.HTTP_503_SERVICE_UNAVAILABLE" in router
    assert "GRANT" not in code
    assert "create_instance" not in code and "oci" not in code.lower()


def test_contract_backlog_stays_historical_not_falsely_promoted():
    d=json.loads(
        (ROOT/"docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json").read_text()
    )
    for identifier in ("3.1","3.5","6.1","6.1-A"):
        clause=next(x for x in d["clauses"] if x["id"]==identifier)
        assert clause["review_state"]=="AWAITING_CLAUSE_EVIDENCE"
        assert clause["production_verified"] is False
    assert d["production_release_authorized"] is False
