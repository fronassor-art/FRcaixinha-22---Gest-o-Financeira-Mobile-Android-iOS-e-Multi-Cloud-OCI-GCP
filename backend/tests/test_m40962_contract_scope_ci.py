"""M40962: contract A/B consistency and canonical read boundary, offline."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4, UUID
import os
import pytest

from app.contract_review_binding_v22 import ContractReviewSnapshot, review_fingerprint, review_matches
from app.canonical_contract_store import ContractBodyUnavailable, _read_immutable_document

BODY="Texto sintético de teste.\n"
NOW=datetime(2026,11,24,12,tzinfo=timezone.utc)
DIGEST=sha256(BODY.encode()).hexdigest()

def snapshot(kind="SAAS_LICENSE"):
    kw=dict(kind=kind,document_id=uuid4(),version="2.2",body_sha256=DIGEST,
            issuer_id=uuid4(),recipient_id=uuid4(),nonce=uuid4(),issued_at=NOW,
            published_at=NOW-timedelta(days=1),expires_at=NOW+timedelta(minutes=2),state="PUBLISHED")
    if kind=="SAAS_LICENSE":
        return ContractReviewSnapshot(**kw,recipient_role="TENANT_ADMIN",offer_id=uuid4(),price_version_id=uuid4())
    return ContractReviewSnapshot(**kw,recipient_role="TENANT_MEMBER",tenant_id=uuid4(),cycle_id=uuid4(),policy_version_id=uuid4())

def matches(s,fp=None,body=BODY,now=NOW):
    return review_matches(expected=s,presented_fingerprint=fp or review_fingerprint(s),body=body,now=now)

@pytest.mark.parametrize("kind",["SAAS_LICENSE","MEMBER_ADHESION"])
def test_exact_published_context_only(kind):
    s=snapshot(kind)
    assert matches(s)
    assert len(review_fingerprint(s))==64
    assert not matches(s,body=BODY+" ")
    assert not matches(s,body=BODY.replace("\n","\r\n"))
    assert not matches(s,now=s.expires_at)
    assert not matches(s,now=s.issued_at-timedelta(microseconds=1))
    assert not matches(s,now=NOW.replace(tzinfo=None))
    assert not matches(s,fp="f"*64)
    assert not matches(s,body="é"*40000)

@pytest.mark.parametrize("kind,field",[
    ("SAAS_LICENSE","offer_id"),("SAAS_LICENSE","price_version_id"),
    ("MEMBER_ADHESION","tenant_id"),("MEMBER_ADHESION","cycle_id"),
    ("MEMBER_ADHESION","policy_version_id"),
    ("SAAS_LICENSE","recipient_id"),("MEMBER_ADHESION","recipient_id"),
    ("SAAS_LICENSE","issuer_id"),("MEMBER_ADHESION","issuer_id"),
    ("SAAS_LICENSE","document_id"),("MEMBER_ADHESION","nonce")])
def test_old_review_not_valid_for_changed_binding(kind,field):
    s=snapshot(kind)
    assert not matches(replace(s,**{field:uuid4()}),fp=review_fingerprint(s))

@pytest.mark.parametrize("kind,change",[
    ("SAAS_LICENSE",{"tenant_id":uuid4()}),("SAAS_LICENSE",{"cycle_id":uuid4()}),
    ("SAAS_LICENSE",{"recipient_role":"MASTER"}),("SAAS_LICENSE",{"offer_id":None}),
    ("MEMBER_ADHESION",{"offer_id":uuid4()}),("MEMBER_ADHESION",{"cycle_id":None}),
    ("MEMBER_ADHESION",{"recipient_role":"TENANT_ADMIN"}),
    ("MEMBER_ADHESION",{"tenant_id":UUID(int=0)}),
    ("SAAS_LICENSE",{"state":"DRAFT"}),("MEMBER_ADHESION",{"state":"RETIRED"}),
    ("SAAS_LICENSE",{"version":"\n2.2"}),("SAAS_LICENSE",{"body_sha256":"F"*64}),
    ("SAAS_LICENSE",{"document_id":"not-a-uuid"}),("SAAS_LICENSE",{"expires_at":NOW}),
    ("MEMBER_ADHESION",{"published_at":NOW+timedelta(seconds=1)})])
def test_invalid_scope_closed(kind,change):
    s=replace(snapshot(kind),**change)
    with pytest.raises(ValueError):
        review_fingerprint(s)
    assert not review_matches(expected=s,presented_fingerprint="0"*64,body=BODY,now=NOW)

def test_document_kind_not_interchangeable():
    a=snapshot()
    b=snapshot("MEMBER_ADHESION")
    assert not matches(b,fp=review_fingerprint(a))
    assert not matches(a,fp=review_fingerprint(b))
    assert not matches(replace(a,version="2.3"),fp=review_fingerprint(a))

def test_fifo_never_blocks_or_delivers(tmp_path):
    doc=uuid4()
    os.mkfifo(tmp_path/(str(doc)+".txt"),0o400)
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(doc,DIGEST,str(tmp_path))

def test_hard_link_not_a_canonical_artifact(tmp_path):
    doc=uuid4()
    other=tmp_path/"other"
    other.write_bytes(BODY.encode())
    other.chmod(0o400)
    os.link(other,tmp_path/(str(doc)+".txt"))
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(doc,DIGEST,str(tmp_path))

def test_short_reads_reconstruct_exact_body(tmp_path,monkeypatch):
    doc=uuid4()
    p=tmp_path/(str(doc)+".txt")
    p.write_bytes(BODY.encode())
    p.chmod(0o400)
    original=os.read
    monkeypatch.setattr(os,"read",lambda fd,n: original(fd,min(n,3)))
    assert _read_immutable_document(doc,DIGEST,str(tmp_path))==BODY

def test_mutated_file_during_read_rejected(tmp_path,monkeypatch):
    doc=uuid4()
    p=tmp_path/(str(doc)+".txt")
    p.write_bytes(BODY.encode())
    p.chmod(0o400)
    original=os.read
    changed=False
    def read(fd,n):
        nonlocal changed
        data=original(fd,n)
        if not changed:
            changed=True
            p.chmod(0o600)
        return data
    monkeypatch.setattr(os,"read",read)
    with pytest.raises(ContractBodyUnavailable):
        _read_immutable_document(doc,DIGEST,str(tmp_path))
