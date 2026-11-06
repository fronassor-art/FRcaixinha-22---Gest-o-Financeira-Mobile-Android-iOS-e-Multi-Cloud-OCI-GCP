"""M21800 safe local Pix TEST evidence with an authenticated GET."""
from datetime import datetime, timezone
from pathlib import Path
import json
import stat
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import aistudio_mp_pix_test_attestation as att
from aistudio_mp_pix_sandbox_lab import new_case

ORD="ORD01JP84C939T20S0P1DN382FQ6K"
PAY="PAY01JP84C939T20S0P1DN6FCMWQC"

def good():
    c = new_case()
    c.update(phase="CHECKED",order_id=ORD,payment_id=PAY)
    r = dict(order_id=ORD,payment_id=PAY,order_status="processed",
             payment_status="processed",bank_reconciled=False,
             ledger_written=False,financial_effect_applied=False,
             real_payment_authorized=False)
    return c,r

def test_proof_no_payment_ids_or_production_claims():
    c,r=good()
    data=att.attest(c,r,datetime.now(timezone.utc))
    att.validate(data)
    for secret in (ORD,PAY,c["reference"],c["idempotency_key"],"APP_USR"):
        assert secret not in json.dumps(data)
    assert data["bank_reconciled"] is False
    assert data["seller_oauth_bound"] is False

@pytest.mark.parametrize("change",[
    {"order_id":"ORD01UNKNOWN000000000"},
    {"payment_id":"PAY01UNKNOWN000000000"},
    {"order_status":"action_required"},
    {"payment_status":"action_required"},
    {"bank_reconciled":True},
    {"ledger_written":True},
    {"financial_effect_applied":True},
    {"real_payment_authorized":True},
])
def test_not_approved_get_rejected(change):
    c,r=good()
    r.update(change)
    with pytest.raises(att.LabBlocked):
        att.attest(c,r,datetime.now(timezone.utc))

def test_not_checked_case_rejected():
    c,r=good()
    c["phase"]="CREATED"
    with pytest.raises(att.LabBlocked):
        att.attest(c,r,datetime.now(timezone.utc))

@pytest.mark.parametrize("field,value",[
    ("environment","PRODUCAO"),("amount_brl","150.00"),
    ("bank_reconciled",True),("ledger_written",True),
    ("real_money_enabled",True),("seller_oauth_bound",True),
    ("provider_order_status","action_required"),
    ("verified_at_utc","2026-11-06T16:00:00"),
])
def test_tampered_proof_rejected(field,value):
    c,r=good()
    data=att.attest(c,r,datetime.now(timezone.utc))
    data[field]=value
    with pytest.raises(att.LabBlocked):
        att.validate(data)

def test_create_and_read_private_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(att,"ensure_private_dir",lambda:None)
    c,r=good()
    data=att.attest(c,r,datetime.now(timezone.utc))
    path=tmp_path/"evidence"
    att.save(data,path)
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    assert att.read(path)==data
    with pytest.raises(att.LabBlocked):
        att.save(data,path)
    path.chmod(0o644)
    with pytest.raises(att.LabBlocked):
        att.read(path)

def test_symlink_not_followed(tmp_path,monkeypatch):
    monkeypatch.setattr(att,"ensure_private_dir",lambda:None)
    c,r=good()
    data=att.attest(c,r,datetime.now(timezone.utc))
    other=tmp_path/"other"
    other.write_text("{}")
    link=tmp_path/"link"
    link.symlink_to(other)
    with pytest.raises(att.LabBlocked):
        att.save(data,link)
    with pytest.raises(att.LabBlocked):
        att.read(link)

def test_no_post_or_financial_api():
    source=Path(att.__file__).read_text()
    assert "run_get(" in source
    assert "run_create(" not in source
    assert "INSERT INTO" not in source
    assert "from fastapi" not in source
