"""M38290-M38329: Brevo-specific DNS candidate audit (no DNS/SMTP/network)."""
from dataclasses import replace
from pathlib import Path
import pytest

from app.brevo_sender_dns_policy import (
    BrevoPublicDnsReport, assess_brevo_public_dns,
)
from app.mail_dns_readiness_readonly import (
    PublicMailDnsSnapshot, DkimDnsObservation, MailDnsObservationBlocked,
)

_CODE="brevo-code:"+"a"*32
_DKIM_TXT=DkimDnsObservation(
    "mail", "TXT", "v=DKIM1; k=rsa; p="+"A"*64,
)
_DKIM_1=DkimDnsObservation("brevo1","CNAME","dkim1.brevo.com")
_DKIM_2=DkimDnsObservation("brevo2","CNAME","dkim2.brevo.com")
_DMARC="v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com"


def snapshot(**changes):
    return replace(PublicMailDnsSnapshot(
        sender_domain="frfinance.com.br",
        spf_txt=(_CODE,),  # Brevo shared IP: no SPF required for domain auth
        dmarc_txt=(_DMARC,),
        dkim=(_DKIM_TXT,),
    ), **changes)


def evaluate(**changes):
    return assess_brevo_public_dns(snapshot(**changes))


def test_single_dkim_txt_dmarc_none_and_absent_spf_are_valid_dns_candidates():
    r=evaluate()
    assert type(r) is BrevoPublicDnsReport
    assert r.mode=="PUBLIC_BREVO_DNS_OBSERVATION_ONLY"
    assert r.brevo_code_record_observed
    assert r.spf_optional
    assert r.spf_status=="ABSENT_OPTIONAL_ON_SHARED_BREVO"
    assert r.dmarc_status=="MONITOR_OR_PARTIAL_ACCEPTED"
    assert r.dmarc_rua_observed
    assert r.dkim_mode=="ONE_TXT_PUBLISHED_CANDIDATE"
    assert r.public_dns_candidates_complete
    assert r.blockers==(
        "BREVO_ACCOUNT_DOMAIN_NOT_AUTHENTICATED_BY_DNS_SNAPSHOT",
        "BREVO_SMTP_TLS_AND_SEND_RECEIPT_NOT_ATTESTED",
        "BREVO_DKIM_SIGNATURE_AND_DMARC_ALIGNMENT_NOT_ATTESTED",
        "REAL_RECIPIENT_OWNERSHIP_AND_CONSENT_NOT_ATTESTED",
    )
    for field in (
        "brevo_account_authenticated","brevo_code_matched_to_account",
        "dkim_signature_verified","dmarc_alignment_verified",
        "smtp_tls_login_verified","real_email_delivery_verified",
        "domain_ownership_authenticated","real_email_authorized",
        "real_user_activation_authorized","real_pix_authorized",
        "production_authorized","network_queries_performed_by_policy",
        "cloud_mutations_performed","database_mutations_performed",
    ):
        assert getattr(r,field) is False


def test_two_cname_dkim_is_acceptable_dns_candidate_without_provider_proof():
    r=evaluate(dkim=(_DKIM_1,_DKIM_2))
    assert r.dkim_mode=="TWO_CNAME_PUBLISHED_CANDIDATES"
    assert r.public_dns_candidates_complete
    assert r.brevo_account_authenticated is False


@pytest.mark.parametrize("dmarc", [
    "v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com",
    "v=DMARC1; p=quarantine; rua=mailto:rua@dmarc.brevo.com",
    "v=DMARC1; p=reject; rua=mailto:rua@dmarc.brevo.com",
    "v=DMARC1; p=quarantine; pct=50; rua=mailto:rua@dmarc.brevo.com",
])
def test_brevo_accepts_monitor_or_enforced_dmarc(dmarc):
    r=evaluate(dmarc_txt=(dmarc,))
    assert r.public_dns_candidates_complete
    assert r.dmarc_status in ("MONITOR_OR_PARTIAL_ACCEPTED","ENFORCING")


@pytest.mark.parametrize("spf", [
    "v=spf1 -all",
    "v=spf1 include:spf.brevo.com ~all",
    "v=spf1 a mx -all",
])
def test_optional_well_formed_spf_does_not_block_dkim_alignment(spf):
    r=evaluate(spf_txt=(_CODE,spf))
    assert r.public_dns_candidates_complete
    assert r.spf_status=="SINGLE_LIMITED_RECORD_OBSERVED"


@pytest.mark.parametrize("records,problem", [
    ((),"BREVO_CODE_NOT_OBSERVED_OR_INVALID"),
    (("brevo-code:a",),"BREVO_CODE_NOT_OBSERVED_OR_INVALID"),
    (("brevo-code:badcode","brevo-code:anothercode"),"BREVO_CODE_DUPLICATE"),
])
def test_missing_invalid_or_duplicate_brevo_code_is_not_proof(records,problem):
    r=evaluate(spf_txt=records)
    assert not r.public_dns_candidates_complete
    assert problem in r.blockers
    assert not r.brevo_code_record_observed


@pytest.mark.parametrize("dmarc,problem", [
    ((),"BREVO_DMARC_NOT_OBSERVED"),
    (("v=DMARC1; p=none","v=DMARC1; p=reject"),"BREVO_DMARC_DUPLICATE"),
    (("v=DMARC1; p=invalid; rua=mailto:rua@dmarc.brevo.com",),"BREVO_DMARC_INVALID"),
    (("v=DMARC1; p=none; p=reject; rua=mailto:rua@dmarc.brevo.com",),"BREVO_DMARC_INVALID"),
    (("v=DMARC1; p=none; pct=bad; rua=mailto:rua@dmarc.brevo.com",),"BREVO_DMARC_INVALID"),
    (("v=DMARC1; p=none",),"BREVO_DMARC_RUA_NOT_OBSERVED"),
])
def test_incomplete_or_unsafe_dmarc_is_not_dns_ready(dmarc,problem):
    r=evaluate(dmarc_txt=dmarc)
    assert not r.public_dns_candidates_complete
    assert problem in r.blockers


@pytest.mark.parametrize("dkim,mode", [
    ((),"NOT_QUERIED"),
    ((_DKIM_1,),"INCOMPLETE_OR_MIXED"),
    ((_DKIM_1,_DKIM_TXT),"INCOMPLETE_OR_MIXED"),
    ((_DKIM_TXT,_DKIM_TXT),"RAISE"),
    ((DkimDnsObservation("mail","MISSING",None),),"INCOMPLETE_OR_MIXED"),
    ((DkimDnsObservation("mail","TXT","v=DKIM1; p=abcd"),),"INCOMPLETE_OR_MIXED"),
    ((DkimDnsObservation("mail","TXT","v=DKIM1; p="),),"INCOMPLETE_OR_MIXED"),
    ((DkimDnsObservation("brevo1","CNAME","localhost"),_DKIM_2),"RAISE"),
])
def test_dkim_forms_unverified_when_missing_mixed_or_invalid(dkim,mode):
    if mode=="RAISE":
        with pytest.raises(MailDnsObservationBlocked):
            evaluate(dkim=dkim)
    else:
        r=evaluate(dkim=dkim)
        assert r.dkim_mode==mode
        assert not r.public_dns_candidates_complete


@pytest.mark.parametrize("spf,expected", [
    ((_CODE,"v=spf1 +all"),"BREVO_EXISTING_SPF_POLICY_REVIEW"),
    ((_CODE,"v=spf1 ?all"),"BREVO_EXISTING_SPF_POLICY_REVIEW"),
    ((_CODE,"v=spf1 -all","v=spf1 ~all"),"BREVO_EXISTING_SPF_DUPLICATED"),
    ((_CODE,"v=spf1 include:spf.brevo.com"),"BREVO_EXISTING_SPF_POLICY_REVIEW"),
])
def test_existing_unsafe_spf_is_reported_but_not_required_for_auth(spf,expected):
    r=evaluate(spf_txt=spf)
    assert r.spf_optional
    assert not r.public_dns_candidates_complete
    assert expected in r.blockers


@pytest.mark.parametrize("bad", [
    None,False,{},[],object(),
])
def test_wrong_input_types_are_denied(bad):
    with pytest.raises(MailDnsObservationBlocked):
        assess_brevo_public_dns(bad)


def test_different_sender_domain_is_not_allowed():
    with pytest.raises(MailDnsObservationBlocked):
        evaluate(sender_domain="otherdomain.com.br")


def test_no_secrets_provider_authorization_or_dns_results_leaked():
    r=evaluate(spf_txt=(_CODE,"note=SENSITIVE_VALUE"))
    assert r.public_dns_candidates_complete
    assert _CODE not in repr(r)
    assert "SENSITIVE_VALUE" not in repr(r)
    assert not r.production_authorized


def test_cli_keeps_explicit_live_approval_and_does_not_print_legacy_false_blockers():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/scripts/aistudio_mail_dns_readonly.py").read_text()
    assert "assess_brevo_public_dns(snapshot)" in src
    assert 'expected_approval=(' in src
    assert '"AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY" if args.resolver=="system"' in src
    assert '"AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY"' in src
    assert 'args.approval!=expected_approval' in src
    assert 'print("M38329_SPF_OPTIONAL_FOR_SHARED_BREVO=TRUE")' in src
    assert 'print("M38329_DKIM_MODE="+brevo.dkim_mode)' in src
    assert "for blocker in brevo.blockers:" in src
    assert "for blocker in report.blockers:" not in src
    assert 'print("M38329_PROVIDER_AUTHENTICATED=NOT_VERIFIED")' in src


def test_provider_policy_module_is_pure_read_only():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/app/brevo_sender_dns_policy.py").read_text()
    assert "PUBLIC_BREVO_DNS_OBSERVATION_ONLY" in src
    for forbidden in (
        "import oci","import smtplib","import requests",
        "asyncpg.connect(","psycopg.connect(","INSERT INTO ",
        "UPDATE public.","send_message(","sendmail(","dns.resolver",
        "os.environ","get_secret_bundle(",
    ):
        assert forbidden not in src
