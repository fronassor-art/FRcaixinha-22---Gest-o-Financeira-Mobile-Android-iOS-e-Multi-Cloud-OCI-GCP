"""M38030-M38049 offline: link alone cannot control an existing account."""
from pathlib import Path
from uuid import uuid4
import pytest
from app import account_lifecycle
ROOT=Path(__file__).resolve().parents[2]
CODE=(ROOT/"backend/app/account_lifecycle.py").read_text()
FUNC=CODE.split("def accept_existing_identity_ci(",1)[1].split("def prepare_password_reset_ci(",1)[0]

class NeverTouchDatabase:
    def execute(self,*args,**kwargs):
        raise AssertionError("SQL accessed without mandatory proof")
    def transaction(self):
        raise AssertionError("Transaction opened without mandatory proof")

@pytest.mark.parametrize("password",[None,"",False,0,{},[],b"example"])
def test_password_required_before_transaction(monkeypatch,password):
    monkeypatch.setattr(account_lifecycle,"_ci_only",lambda conn:None)
    assert account_lifecycle.accept_existing_identity_ci(
        NeverTouchDatabase(),token="ci-only",user_id=uuid4(),document_id=uuid4(),
        consent=True,accepted_document_sha256="a"*64,account_password=password) is None

@pytest.mark.parametrize("consent",[None,False,"yes",0])
def test_explicit_consent_still_mandatory(monkeypatch,consent):
    monkeypatch.setattr(account_lifecycle,"_ci_only",lambda conn:None)
    assert account_lifecycle.accept_existing_identity_ci(
        NeverTouchDatabase(),token="ci-only",user_id=uuid4(),document_id=uuid4(),
        consent=consent,accepted_document_sha256="a"*64,
        account_password="synthetic-password") is None

@pytest.mark.parametrize("digest",[None,"","A"*64,"a"*63,1])
def test_exact_version_still_mandatory(monkeypatch,digest):
    monkeypatch.setattr(account_lifecycle,"_ci_only",lambda conn:None)
    assert account_lifecycle.accept_existing_identity_ci(
        NeverTouchDatabase(),token="ci-only",user_id=uuid4(),document_id=uuid4(),
        consent=True,accepted_document_sha256=digest,
        account_password="synthetic-password") is None

def test_existing_account_password_is_verified_under_transaction_lock():
    assert "account_password: str | None = None" in FUNC
    assert "type(account_password) is not str" in FUNC
    assert "verify_password_secure(account_password, credential[0])" in FUNC
    assert "SELECT password_hash FROM public.credentials WHERE user_id=%s FOR UPDATE" in FUNC
    assert FUNC.index("with conn.transaction():") < FUNC.index("SELECT password_hash FROM public.credentials")
    assert FUNC.index("verify_password_secure(account_password, credential[0])") < FUNC.index("INSERT INTO public.memberships")
    assert "user[2] is None" in FUNC
    assert "invitation[9] != document_id" in FUNC
    assert "consent is not True" in FUNC

def test_public_invites_and_real_registration_remain_disabled():
    router=(ROOT/"backend/app/routers/invitations.py").read_text()
    assert "accept_existing_identity_ci" not in router
    assert "register_new_invited_identity_ci" not in router
    assert "Convites ainda não implementados" in router
    assert "FRCAIXINHA_CI_ISOLATED" in CODE
    assert "frcaixinha_ci" in CODE
    assert "5432" in CODE
    assert "GRANT " not in FUNC
