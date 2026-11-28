"""FR Finance M38250-M38289: DNS mail integrity is NOT deliverability proof."""
from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys

import pytest

from app.mail_dns_readiness_readonly import (
    DkimDnsObservation,MailDnsObservationBlocked,
    PublicMailDnsSnapshot,assess_public_mail_dns,
)

DOMAIN="frfinance.com.br"
SPF="v=spf1 include:spf.brevo.com ~all"
DMARC="v=DMARC1; p=quarantine; pct=100"
DKIM1=DkimDnsObservation("brevo1","CNAME","dkim1.examplemail.net")
DKIM2=DkimDnsObservation("brevo2","TXT","v=DKIM1; k=rsa; p=YWJjZA==")


def fixture(**changes):
    base=PublicMailDnsSnapshot(
        sender_domain=DOMAIN,spf_txt=(SPF,),dmarc_txt=(DMARC,),
        dkim=(DKIM1,DKIM2),
    )
    return replace(base,**changes)


def report(**changes):
    return assess_public_mail_dns(fixture(**changes))


def test_all_synthetic_dns_observations_cannot_enable_email():
    r=report()
    assert r.mode=="PUBLIC_MAIL_DNS_READ_ONLY_OBSERVATION"
    assert r.sender_domain==DOMAIN
    assert r.spf_record_present and r.spf_policy_limited
    assert r.dmarc_record_present
    assert r.dmarc_policy=="QUARANTINE"
    assert r.dkim_selectors_observed==2
    assert r.dkim_records_present==2
    assert r.blockers==(
        "MAIL_BREVO_SENDER_NOT_INDEPENDENTLY_VERIFIED",
        "MAIL_SMTP_STARTTLS_AUTH_NOT_TESTED",
        "MAIL_PROVIDER_DELIVERY_BOUNCE_NOT_ATTESTED",
        "MAIL_EMAIL_OWNERSHIP_AND_CONSENT_NOT_ATTESTED",
    )
    for field in (
        "authenticated_sender_domain_control","provider_dkim_verified",
        "provider_smtp_authenticated","actual_message_delivery_verified",
        "real_email_send_authorized","user_activation_authorized",
        "production_authorized","cloud_mutations_performed",
        "database_mutations_performed",
    ):
        assert getattr(r,field) is False


def test_spf_missing_denied_as_operational_proof():
    r=report(spf_txt=())
    assert not r.spf_record_present
    assert "MAIL_SPF_RECORD_NOT_OBSERVED" in r.blockers


def test_duplicate_spf_denied_as_operational_proof():
    r=report(spf_txt=(SPF,"v=spf1 -all"))
    assert not r.spf_record_present
    assert "MAIL_MULTIPLE_SPF_RECORDS" in r.blockers


@pytest.mark.parametrize("policy",[
    "v=spf1 +all",
    "v=spf1 ?all",
    "v=spf1 include:brevo.invalid",
    "v=spf1",
    "v=spf1 include:spf.brevo.com +all",
    "v=spf1 include:spf.brevo.com -all redirect=elsewhere",
])
def test_nonlimited_or_unsafe_spf_is_not_certified(policy):
    r=report(spf_txt=(policy,))
    assert not r.spf_policy_limited
    assert "MAIL_SPF_POLICY_NEEDS_REVIEW" in r.blockers


@pytest.mark.parametrize("policy,expected",[
    ("v=DMARC1; p=reject","REJECT"),
    ("v=DMARC1; p=quarantine; pct=100","QUARANTINE"),
    ("v=DMARC1; p=none","MONITOR_OR_PARTIAL"),
    ("v=DMARC1; p=quarantine; pct=50","MONITOR_OR_PARTIAL"),
    ("v=DMARC1; p=reject; pct=0","MONITOR_OR_PARTIAL"),
    ("v=DMARC1; p=garbage","INVALID"),
    ("v=DMARC1; p=reject; p=none","INVALID"),
    ("v=DMARC1; p=reject; pct=101","INVALID"),
    ("v=DMARC1; p=reject; pct=NaN","INVALID"),
    ("v=DMARC1","INVALID"),
])
def test_dmarc_policy_states_are_not_misreported(policy,expected):
    r=report(dmarc_txt=(policy,))
    assert r.dmarc_policy==expected
    if expected in ("MONITOR_OR_PARTIAL","INVALID"):
        assert "MAIL_DMARC_POLICY_NOT_ENFORCING_OR_INVALID" in r.blockers


@pytest.mark.parametrize("records,blocker",[
    ((),"MAIL_DMARC_RECORD_NOT_OBSERVED"),
    ((DMARC,"v=DMARC1; p=reject"),"MAIL_MULTIPLE_DMARC_RECORDS"),
])
def test_missing_or_duplicate_dmarc(records,blocker):
    r=report(dmarc_txt=records)
    assert not r.dmarc_record_present
    assert blocker in r.blockers


def test_unprovided_dkim_selectors_never_claim_provider_keys():
    r=report(dkim=())
    assert r.dkim_selectors_observed==0
    assert r.dkim_records_present==0
    assert "MAIL_TWO_DKIM_SELECTORS_NOT_ATTESTED" in r.blockers


@pytest.mark.parametrize("kind,value",[
    ("MISSING",None),
    ("TXT","v=DKIM1; k=rsa"),
    ("TXT","p=YWJjZA=="),
    ("TXT","v=DKIM1; p="),
])
def test_missing_or_incorrect_dkim_is_not_verified(kind,value):
    r=report(dkim=(DKIM1,DkimDnsObservation("brevo2",kind,value)))
    assert r.dkim_records_present==1
    assert "MAIL_TWO_DKIM_SELECTORS_NOT_ATTESTED" in r.blockers


@pytest.mark.parametrize("changed",[
    {"selector":"BREVO1"},
    {"selector":"bad.label"},
    {"selector":"a"*64},
    {"selector":""},
    {"record_kind":"OTHER"},
    {"record_kind":None},
    {"record_value":"127.0.0.1"},
    {"record_value":"localhost"},
    {"record_value":"not a domain"},
])
def test_malformed_cname_selector_denied(changed):
    bad=replace(DKIM1,**changed)
    with pytest.raises(MailDnsObservationBlocked):
        report(dkim=(bad,DKIM2))


@pytest.mark.parametrize("bad",[
    {"sender_domain":"localhost"},
    {"sender_domain":"frfinance.com.br\nBcc:spoof"},
    {"sender_domain":"FRFINANCE.COM.BR"},
    {"sender_domain":"frfinance.com.br/evil"},
    {"sender_domain":"127.0.0.1"},
    {"sender_domain":None},
    {"spf_txt":["v=spf1 ~all"]},
    {"spf_txt":("v=spf1\nsecret ~all",)},
    {"spf_txt":("v=spf1 ~all",)*41},
    {"dmarc_txt":["v=DMARC1; p=reject"]},
    {"dmarc_txt":("v=DMARC1; p=reject\nbad",)},
    {"dkim":[DKIM1,DKIM2]},
    {"dkim":(DKIM1,DKIM1)},
    {"dkim":(DKIM1,DKIM2,DKIM1)},
    {"dkim":(DKIM1,"brevo2")},
])
def test_invalid_or_untrusted_snapshot_denied(bad):
    with pytest.raises(MailDnsObservationBlocked):
        report(**bad)


def test_malformed_txt_payload_and_secret_never_in_report():
    r=report(spf_txt=("random_public_api_key=SENSITIVE_PROVIDER_KEY",SPF),
             dmarc_txt=("some-other-record",DMARC))
    assert r.spf_record_present
    assert r.dmarc_record_present
    assert "SENSITIVE_PROVIDER_KEY" not in repr(r)
    assert r.production_authorized is False


def _cli(tmp_path,*args):
    root=Path(__file__).resolve().parents[2]
    script=root/"backend/scripts/aistudio_mail_dns_readonly.py"
    env={**os.environ,"HOME":str(tmp_path),"PYTHONPATH":str(root/"backend")}
    return subprocess.run([sys.executable,str(script),*args],
                          cwd=root,env=env,text=True,capture_output=True,
                          timeout=12,check=False)


def test_cli_offline_does_not_require_dns_library_or_intake(tmp_path):
    r=_cli(tmp_path)
    assert r.returncode==0
    assert "M38289_MODE=OFFLINE_NO_DNS_REQUESTS" in r.stdout
    assert "M38289_PRODUCTION=BLOCKED" in r.stdout


@pytest.mark.parametrize("args",[
    ("live",),
    ("live","NO"),
    ("live","AUTHORIZE_PUBLIC_TLS_ONLY"),
    ("offline","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"),
    ("offline","--selector","brevo1"),
    ("live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY","--selector","BAD"),
    ("live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY","--selector","bad.selector"),
    ("live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY",
     "--selector","brevo1","--selector","brevo1"),
    ("live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY",
     "--selector","brevo1","--selector","brevo2","--selector","brevo3"),
])
def test_unauthorized_or_invalid_actions_never_query_dns(tmp_path,args):
    r=_cli(tmp_path,*args)
    assert r.returncode==2
    assert "READ_ONLY_OBSERVATION" not in r.stdout


def test_live_requires_existing_sender_metadata_without_network(tmp_path):
    r=_cli(tmp_path,"live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY")
    assert r.returncode==2
    assert "M38289_MAIL_DNS=BLOCKED_INPUT_OR_DNS_QUERY" in r.stdout


def test_script_requires_explicit_command_and_only_standard_public_dns():
    root=Path(__file__).resolve().parents[2]
    script=(root/"backend/scripts/aistudio_mail_dns_readonly.py").read_text()
    assert 'expected_approval=(' in script
    assert '"AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY" if args.resolver=="system"' in script
    assert '"AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY"' in script
    assert 'args.approval!=expected_approval' in script
    assert 'SENDER_DOMAIN = "frfinance.com.br"' in script
    assert 'resolver.resolve(name, record_type, raise_on_no_answer=False)' in script
    for forbidden in (
        "smtplib","sendmail(","send_message(","starttls(","login(",
        "get_secret_bundle(","asyncpg.connect(","psycopg.connect(",
        "INSERT INTO","UPDATE public.","requests.post(","httpx.post(",
        "oci.core.ComputeClient(","oci.vault.",
    ):
        assert forbidden not in script
