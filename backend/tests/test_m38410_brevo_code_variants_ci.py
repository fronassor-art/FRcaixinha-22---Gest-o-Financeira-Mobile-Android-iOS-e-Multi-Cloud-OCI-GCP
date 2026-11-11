"""M38410-M38449: Brevo TXT public DNS code accepts both official shapes.

Provider documentation has examples of brevo-code:<value> AND
brevo-code=<value>. Neither is an authenticated proof of account control.
"""
from dataclasses import replace
import importlib.util
from pathlib import Path
import pytest

from app.brevo_sender_dns_policy import assess_brevo_public_dns
from app.mail_dns_readiness_readonly import (
    DkimDnsObservation, PublicMailDnsSnapshot,
)

ROOT=Path(__file__).resolve().parents[2]
TXT_DKIM="k=rsa;p="+"A"*64
DMARC="v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com"


def snapshot(root_records):
    return PublicMailDnsSnapshot(
        sender_domain="frfinance.com.br",
        spf_txt=tuple(root_records),
        dmarc_txt=(DMARC,),
        dkim=(DkimDnsObservation("mail","TXT",TXT_DKIM),),
    )


@pytest.mark.parametrize("code", [
    "brevo-code:"+"a"*32,
    "brevo-code="+"a"*32,
    "BREVO-CODE:"+"b"*12,
    "Brevo-Code="+"a"*64,
    "brevo-code=abc123def456",
])
def test_official_brevo_txt_variants_are_observed_as_syntax_not_ownership(code):
    r=assess_brevo_public_dns(snapshot((code,)))
    assert r.brevo_code_record_observed
    assert r.public_dns_candidates_complete
    assert not r.brevo_code_matched_to_account
    assert not r.brevo_account_authenticated
    assert not r.real_email_authorized
    assert not r.production_authorized
    assert code not in repr(r)


@pytest.mark.parametrize("codes", [
    ("brevo-code:"+"a"*32, "brevo-code="+"b"*32),
    ("BREVO-CODE="+"a"*32, "Brevo-Code:"+"b"*32),
    ("brevo-code="+"a"*32, "brevo-code="+"a"*32),
])
def test_duplicate_mixed_delimiter_codes_are_detected_and_never_trusted(codes):
    r=assess_brevo_public_dns(snapshot(codes))
    assert not r.brevo_code_record_observed
    assert "BREVO_CODE_DUPLICATE" in r.blockers
    assert not r.public_dns_candidates_complete
    assert not r.real_email_authorized


@pytest.mark.parametrize("code", [
    "brevo-code=",
    "brevo-code:",
    "brevo-code:abc",
    "brevo-code=abc",
    "brevo-code=wrong word",
    "brevo-code::"+"a"*32,
    "brevo-code=="+"a"*32,
])
def test_malformed_public_brevo_code_is_never_a_positive_observation(code):
    r=assess_brevo_public_dns(snapshot((code,)))
    assert not r.brevo_code_record_observed
    assert "BREVO_CODE_NOT_OBSERVED_OR_INVALID" in r.blockers
    assert not r.public_dns_candidates_complete


def _load_cli():
    spec=importlib.util.spec_from_file_location(
        "aistudio_mail_dns_m38410",ROOT/"backend/scripts/aistudio_mail_dns_readonly.py"
    )
    assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("delimiter", [":","="])
def test_full_live_cli_mock_observes_both_code_forms_without_dns_or_emails(
    delimiter,monkeypatch,capsys,
):
    cli=_load_cli()
    called=[]
    value="brevo-code"+delimiter+"abcd0123def45678"
    monkeypatch.setattr(cli,"_read_source_domain",lambda:"frfinance.com.br")
    def fake_dns(domain,selectors):
        called.append((domain,selectors))
        return snapshot((value,))
    monkeypatch.setattr(cli,"_collect_public_dns",fake_dns)
    assert cli.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY",
                     "--selector","mail"])==0
    out=capsys.readouterr().out
    assert called==[("frfinance.com.br",("mail",))]
    assert "M38329_BREVO_CODE_RECORD=TRUE" in out
    assert "M38329_DNS_SHAPE_COMPLETE=TRUE" in out
    assert "M38329_PROVIDER_AUTHENTICATED=NOT_VERIFIED" in out
    assert "M38289_REAL_EMAIL=OFF" in out
    assert "M38289_PRODUCTION=BLOCKED" in out
    assert value not in out
    assert TXT_DKIM not in out


def test_stage_diagnostic_remains_available_to_inspect_live_failure():
    src=(ROOT/"backend/scripts/aistudio_mail_dns_readonly.py").read_text()
    for marker in ("M38409_FAILURE_STAGE=", "DNS_RESOLVER", "DNS_RESPONSE_POLICY",
                   "READY_FOR_EXPLICIT_PUBLIC_DNS_READ"):
        assert marker in src
    assert "print(record_value)" not in src
    assert "send_message(" not in src


def test_public_policy_remains_without_runtime_network_or_mutation():
    src=(ROOT/"backend/app/brevo_sender_dns_policy.py").read_text()
    assert 'brevo-code[:=]' in src
    for forbidden in ("import dns.resolver","import smtplib","import requests",
                      "send_message(","psycopg.connect(", "UPDATE public."):
        assert forbidden not in src
