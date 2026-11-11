"""M38330-M38369: Brevo actual DKIM TXT shapes and CLI preview wiring."""
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from app.brevo_sender_dns_policy import (
    assess_brevo_public_dns, looks_like_brevo_dkim_txt,
)
from app.mail_dns_readiness_readonly import (
    DkimDnsObservation, PublicMailDnsSnapshot,
)

ROOT=Path(__file__).resolve().parents[2]
KEY="A"*64
BREVO_CODE="brevo-code:"+"b"*32
DMARC="v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com"


def snapshot(value, selector="mail"):
    return PublicMailDnsSnapshot(
        sender_domain="frfinance.com.br",
        spf_txt=(BREVO_CODE,),
        dmarc_txt=(DMARC,),
        dkim=(DkimDnsObservation(selector,"TXT",value),),
    )


@pytest.mark.parametrize("record",[
    "k=rsa;p="+KEY,
    "k=rsa; p="+KEY,
    "k = rsa; p = "+KEY,
    "v=DKIM1; k=rsa; p="+KEY,
    "v=dkim1;k=RSA;p="+KEY,
    "v=DKIM1; p="+KEY,
    "k=rsa;p="+KEY+"; t=s",
])
def test_documented_brevo_one_txt_dkim_alternative_is_candidate(record):
    assert looks_like_brevo_dkim_txt(record)
    r=assess_brevo_public_dns(snapshot(record))
    assert r.dkim_mode=="ONE_TXT_PUBLISHED_CANDIDATE"
    assert r.public_dns_candidates_complete
    assert not r.brevo_account_authenticated
    assert not r.dkim_signature_verified
    assert not r.real_email_authorized


@pytest.mark.parametrize("record",[
    "random-non-dkim-record",
    "p="+KEY,
    "",
    "https://frfinance.com.br",
    "v=SPF1 -all",
    None,
    True,
    "v=DKIM1;p="+KEY+"; p="+KEY,
    "v=DKIM1;p="+KEY+"; v=DKIM1",
    "v=DKIM1;k=ed25519;p="+KEY,
    "k=ed25519;p="+KEY,
    "v=DKIM1;p=abcd",
    "k=rsa;p=short",
    "k=rsa;p="+KEY+"?",
    "v=DKIM1; p="+KEY+"; x=unknown",
])
def test_non_brevo_or_incomplete_dkim_cannot_complete_candidate(record):
    # A missing / malformed record never proves provider readiness.
    if record is None or type(record) is bool or record=="":
        assert not looks_like_brevo_dkim_txt(record)
        return
    r=assess_brevo_public_dns(snapshot(record))
    assert r.dkim_mode=="INCOMPLETE_OR_MIXED"
    assert not r.public_dns_candidates_complete
    assert not r.production_authorized


@pytest.mark.parametrize("record",[
    "k=rsa;p="+KEY,
    "v=DKIM1; k=rsa; p="+KEY,
    "k=rsa;p=short",
    "v=DKIM1;p=short",
])
def test_dkim_classifier_includes_malformed_dkim_for_safe_diagnosis(record):
    assert looks_like_brevo_dkim_txt(record)


def _load_cli():
    path=ROOT/"backend/scripts/aistudio_mail_dns_readonly.py"
    spec=spec_from_file_location("aistudio_mail_dns_readonly_testonly",path)
    assert spec and spec.loader
    mod=module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_live_operator_flow_mock_dns_one_txt_no_credentials_or_smtp(
    monkeypatch,capsys,
):
    mod=_load_cli()
    calls=[]
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    def fake_dns(domain,selectors):
        calls.append((domain,selectors))
        return snapshot("k=rsa;p="+KEY)
    monkeypatch.setattr(mod,"_collect_public_dns",fake_dns)
    result=mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY",
                     "--selector","mail"])
    out=capsys.readouterr().out
    assert result==0
    assert calls==[("frfinance.com.br",("mail",))]
    assert "M38329_DKIM_MODE=ONE_TXT_PUBLISHED_CANDIDATE" in out
    assert "M38329_DNS_SHAPE_COMPLETE=TRUE" in out
    assert "M38289_DKIM_RECORDS=1" in out
    assert "M38329_PROVIDER_AUTHENTICATED=NOT_VERIFIED" in out
    assert "M38289_EMAIL_DELIVERY=NOT_ATTESTED" in out
    assert "M38289_REAL_EMAIL=OFF" in out
    assert "M38289_PRODUCTION=BLOCKED" in out
    assert "k=rsa" not in out
    assert BREVO_CODE not in out
    assert KEY not in out


def test_mock_live_two_cname_and_mixed_status(capsys,monkeypatch):
    mod=_load_cli()
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    def fake_dns(domain,selectors):
        assert selectors==("brevo1","brevo2")
        return replace(snapshot("k=rsa;p="+KEY),dkim=(
            DkimDnsObservation("brevo1","CNAME","dkim1.brevo.com"),
            DkimDnsObservation("brevo2","CNAME","dkim2.brevo.com"),
        ))
    monkeypatch.setattr(mod,"_collect_public_dns",fake_dns)
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY",
                     "--selector","brevo1","--selector","brevo2"])==0
    out=capsys.readouterr().out
    assert "M38329_DKIM_MODE=TWO_CNAME_PUBLISHED_CANDIDATES" in out
    assert "M38289_DKIM_RECORDS=2" in out
    assert "M38289_REAL_EMAIL=OFF" in out


def test_live_without_selector_does_not_claim_dkim(capsys,monkeypatch):
    mod=_load_cli()
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    def fake_dns(domain,selectors):
        assert selectors==()
        return replace(snapshot("k=rsa;p="+KEY),dkim=())
    monkeypatch.setattr(mod,"_collect_public_dns",fake_dns)
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==0
    out=capsys.readouterr().out
    assert "M38329_DKIM_MODE=NOT_QUERIED" in out
    assert "M38329_DNS_SHAPE_COMPLETE=FALSE" in out


def test_missing_approval_stops_before_dns(capsys,monkeypatch):
    mod=_load_cli()
    calls=[]
    monkeypatch.setattr(mod,"_read_source_domain",lambda:calls.append("read"))
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *a:calls.append("dns"))
    assert mod.main(["live","NOT_APPROVED","--selector","mail"])==2
    assert not calls
    assert "BLOCKED_OPERATOR_APPROVAL_OR_SELECTOR" in capsys.readouterr().out


def test_live_dns_exception_is_redacted_and_production_blocked(
    monkeypatch,capsys,
):
    mod=_load_cli()
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    def blocked(*args):
        raise RuntimeError("SENSITIVE_DNS_RECORD_SHOULD_NEVER_LEAK")
    monkeypatch.setattr(mod,"_collect_public_dns",blocked)
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY",
                     "--selector","mail"])==2
    out=capsys.readouterr().out
    assert "M38289_MAIL_DNS=BLOCKED_INPUT_OR_DNS_QUERY" in out
    assert "M38289_PRODUCTION=BLOCKED" in out
    assert "SENSITIVE_" not in out


def test_real_dns_reader_uses_new_candidate_recognition():
    src=(ROOT/"backend/scripts/aistudio_mail_dns_readonly.py").read_text()
    assert "looks_like_brevo_dkim_txt(r)" in src
    assert "assess_brevo_public_dns(snapshot)" in src
    assert 'args.approval!="AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"' in src
    assert "send_message(" not in src
    assert "smtplib.SMTP" not in src


def test_operator_cannot_reach_other_domains_or_run_unapproved_selectors(
    monkeypatch,capsys,
):
    mod=_load_cli()
    called=[]
    monkeypatch.setattr(mod,"_read_source_domain",lambda:called.append("read"))
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *a:called.append("dns"))
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY",
                     "--selector","bad.selector"])==2
    assert not called
    assert "BLOCKED_OPERATOR_APPROVAL_OR_SELECTOR" in capsys.readouterr().out
