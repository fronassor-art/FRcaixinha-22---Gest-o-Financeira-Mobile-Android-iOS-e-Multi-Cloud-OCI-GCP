"""FR Finance M38450–M38489: public DNS transport triage without TXT output."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.mail_dns_transport_readonly import (
    DnsTransportObservation, diagnose_dns_transport, is_transport_complete,
)

ROOT=Path(__file__).resolve().parents[2]
CLI=ROOT/"backend/scripts/aistudio_mail_dns_transport_probe.py"
HOSTS=("frfinance.com.br","_dmarc.frfinance.com.br")


def _cli():
    spec=importlib.util.spec_from_file_location("fr_dns_transport_ci",CLI)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResolver:
    def __init__(self, statuses=None, calls=None):
        self.statuses=statuses or {}
        self.calls=calls if calls is not None else []

    def resolve(self,domain,record_type,raise_on_no_answer):
        self.calls.append((domain,record_type,raise_on_no_answer))
        status=self.statuses.get(domain,"RECORDS")
        if isinstance(status,Exception):
            raise status
        if status=="NOANSWER":
            return SimpleNamespace(rrset=None)
        return SimpleNamespace(rrset=object())


def _error(kind):
    return type(kind,(Exception,),{})("SENSITIVE_EXTERNAL_DNS_EXCEPTION")


def test_root_and_dmarc_are_only_queries():
    calls=[]
    report=diagnose_dns_transport("SYSTEM",lambda mode:FakeResolver(calls=calls))
    assert calls==[
        ("frfinance.com.br","TXT",False),
        ("_dmarc.frfinance.com.br","TXT",False),
    ]
    assert report.mode=="SYSTEM"
    assert report.resolver_status=="CONFIGURED_FOR_QUERY"
    assert report.root_txt_status=="TXT_ANSWER_OBSERVED"
    assert report.dmarc_txt_status=="TXT_ANSWER_OBSERVED"
    assert is_transport_complete(report)
    assert report.queries_requested==2
    assert not report.third_party_resolver_selected
    for field in (
        "record_values_printed","domain_authenticated_by_provider",
        "email_delivery_verified","actual_dkim_verified",
        "production_authorized","real_user_activation_authorized",
        "real_pix_authorized","database_mutations_performed",
        "cloud_mutations_performed",
    ):
        assert getattr(report,field) is False


@pytest.mark.parametrize("status,want",[
    ("NXDOMAIN","DNS_NAME_NOT_FOUND"),
    ("NoAnswer","DNS_NO_TXT_ANSWER"),
    ("Timeout","DNS_QUERY_TIMEOUT"),
    ("LifetimeTimeout","DNS_QUERY_TIMEOUT"),
    ("NoNameservers","DNS_SERVERS_UNAVAILABLE_OR_REFUSED"),
    ("NoRootSOA","DNS_SERVER_PROTOCOL_ERROR"),
    ("YXDOMAIN","DNS_NAME_TOO_LONG"),
    ("DNSException","DNS_PROTOCOL_ERROR"),
    ("OSError","SYSTEM_NETWORK_ERROR"),
    ("gaierror","SYSTEM_NETWORK_RESOLUTION_ERROR"),
    ("SecretExternalFailure","DNS_ERROR_UNCLASSIFIED"),
])
def test_all_dns_exceptions_have_fixed_redacted_status(status,want):
    report=diagnose_dns_transport(
        "SYSTEM",lambda m:FakeResolver({HOSTS[0]:_error(status)}),
    )
    assert report.root_txt_status==want
    assert "SENSITIVE" not in repr(report)
    assert "SENSITIVE" not in report.root_txt_status
    assert not report.production_authorized


@pytest.mark.parametrize("status,want",[
    ("NoResolverConfiguration","SYSTEM_RESOLVER_NOT_CONFIGURED"),
    ("NoNameservers","DNS_SERVERS_UNAVAILABLE_OR_REFUSED"),
    ("Timeout","DNS_QUERY_TIMEOUT"),
    ("OSError","SYSTEM_NETWORK_ERROR"),
    ("BogusPythonException","DNS_ERROR_UNCLASSIFIED"),
])
def test_factory_failure_makes_zero_dns_queries(status,want):
    def fail(_):
        raise _error(status)
    report=diagnose_dns_transport("SYSTEM",fail)
    assert report.resolver_status==want
    assert report.root_txt_status=="NOT_QUERIED"
    assert report.dmarc_txt_status=="NOT_QUERIED"
    assert report.queries_requested==0
    assert not is_transport_complete(report)


def test_malformed_resolver_does_not_trigger_any_query():
    report=diagnose_dns_transport("SYSTEM",lambda m:object())
    assert report.resolver_status=="DNS_ERROR_UNCLASSIFIED"
    assert report.queries_requested==0
    assert not is_transport_complete(report)


@pytest.mark.parametrize("mode",["CLOUDFLARE","GOOGLE"])
def test_public_resolver_mode_is_still_untrusted(mode):
    report=diagnose_dns_transport(mode,lambda m:FakeResolver())
    assert report.third_party_resolver_selected is True
    assert report.queries_requested==2
    assert not report.domain_authenticated_by_provider
    assert not report.production_authorized


@pytest.mark.parametrize("mode",["","BAD","cloudflare",None,True])
def test_wrong_input_cannot_inject_other_names(mode):
    with pytest.raises(ValueError):
        diagnose_dns_transport(mode,lambda m:FakeResolver())


@pytest.mark.parametrize("status",["NXDOMAIN","NoAnswer"])
def test_missing_dns_answers_distinguished_from_transport_outage(status):
    response=("NOANSWER" if status=="NoAnswer" else _error(status))
    report=diagnose_dns_transport(
        "SYSTEM",lambda m:FakeResolver({HOSTS[1]:response}),
    )
    assert is_transport_complete(report)
    assert report.dmarc_txt_status in ("DNS_NO_TXT_ANSWER","DNS_NAME_NOT_FOUND")
    assert not report.domain_authenticated_by_provider


@pytest.mark.parametrize("status",["Timeout","NoNameservers","UnknownError"])
def test_real_transport_failures_are_not_marked_completed(status):
    report=diagnose_dns_transport(
        "SYSTEM",lambda m:FakeResolver({HOSTS[1]:_error(status)}),
    )
    assert report.queries_requested==2
    assert report.root_txt_status=="TXT_ANSWER_OBSERVED"
    assert not is_transport_complete(report)


def test_cli_offline_uses_no_intake_dns_or_provider(capsys,monkeypatch):
    mod=_cli()
    calls=[]
    monkeypatch.setattr(mod,"_local_preflight",lambda:calls.append("intake"))
    monkeypatch.setattr(mod,"_resolver_factory",lambda mode:calls.append("dns"))
    assert mod.main(["offline"])==0
    assert calls==[]
    out=capsys.readouterr().out
    assert "M38489_MODE=OFFLINE_NO_NETWORK" in out
    assert "M38489_PRODUCTION=BLOCKED" in out


@pytest.mark.parametrize("command",[
    ["system"],
    ["system","NOT_APPROVED"],
    ["cloudflare","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"],
    ["google","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"],
    ["offline","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"],
])
def test_cli_denies_unknown_or_cross_provider_approval_before_network(
    command,capsys,monkeypatch,
):
    mod=_cli()
    calls=[]
    monkeypatch.setattr(mod,"_local_preflight",lambda:calls.append("intake"))
    monkeypatch.setattr(mod,"_resolver_factory",lambda mode:calls.append("dns"))
    assert mod.main(command)==2
    assert calls==[]
    assert "BLOCKED_" in capsys.readouterr().out


def test_system_resolver_live_with_mock_only(capsys,monkeypatch):
    mod=_cli()
    calls=[]
    monkeypatch.setattr(mod,"_local_preflight",
                        lambda:"READY_FOR_EXPLICIT_PUBLIC_DNS_READ")
    monkeypatch.setattr(mod,"_resolver_factory",
                        lambda mode:FakeResolver(calls=calls))
    assert mod.main(["system","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==0
    assert len(calls)==2
    out=capsys.readouterr().out
    assert "M38489_RESOLVER=SYSTEM" in out
    assert "M38489_ROOT_TXT=TXT_ANSWER_OBSERVED" in out
    assert "M38489_DMARC_TXT=TXT_ANSWER_OBSERVED" in out
    assert "M38489_THIRD_PARTY_DNS=FALSE" in out
    assert "M38489_TRANSPORT_COMPLETED=TRUE" in out
    assert "M38489_BREVO_DOMAIN_AUTH=NOT_ATTESTED" in out
    assert "M38489_EMAIL_REAL=OFF" in out
    assert "M38489_PRODUCTION=BLOCKED" in out


def test_system_noresolverconfig_reports_reason_without_error_message(capsys,monkeypatch):
    mod=_cli()
    monkeypatch.setattr(mod,"_local_preflight",
                        lambda:"READY_FOR_EXPLICIT_PUBLIC_DNS_READ")
    def fail(mode):
        raise _error("NoResolverConfiguration")
    monkeypatch.setattr(mod,"_resolver_factory",fail)
    assert mod.main(["system","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==2
    out=capsys.readouterr().out
    assert "M38489_RESOLVER_STATUS=SYSTEM_RESOLVER_NOT_CONFIGURED" in out
    assert "M38489_QUERIES_ATTEMPTED=0" in out
    assert "SENSITIVE" not in out
    assert "M38489_PRODUCTION=BLOCKED" in out


@pytest.mark.parametrize("mode",["cloudflare","google"])
def test_explicit_public_provider_comparison_is_no_mutation(mode,capsys,monkeypatch):
    mod=_cli()
    passed=[]
    monkeypatch.setattr(mod,"_local_preflight",
                        lambda:"READY_FOR_EXPLICIT_PUBLIC_DNS_READ")
    def factory(which):
        passed.append(which)
        return FakeResolver()
    monkeypatch.setattr(mod,"_resolver_factory",factory)
    assert mod.main([mode,"AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY"])==0
    assert passed==[mode.upper()]
    out=capsys.readouterr().out
    assert "M38489_THIRD_PARTY_DNS=TRUE" in out
    assert "M38489_EMAIL_REAL=OFF" in out
    assert "M38489_PIX_REAL=OFF" in out
    assert "M38489_PRODUCTION=BLOCKED" in out


def test_bad_local_preflight_denies_dns_queries(capsys,monkeypatch):
    mod=_cli()
    calls=[]
    monkeypatch.setattr(mod,"_local_preflight",lambda:"EMAIL_FROM_NOT_CONFIGURED")
    monkeypatch.setattr(mod,"_resolver_factory",lambda mode:calls.append(mode))
    assert mod.main(["system","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==2
    assert calls==[]
    out=capsys.readouterr().out
    assert "M38489_PROBE=BLOCKED_LOCAL_PREFLIGHT" in out
    assert "M38489_PREFLIGHT=EMAIL_FROM_NOT_CONFIGURED" in out
    assert "M38489_NETWORK_QUERIES=NONE" in out


def test_script_never_prints_server_ip_or_txt_content():
    source=CLI.read_text()
    policy=(ROOT/"backend/app/mail_dns_transport_readonly.py").read_text()
    for forbidden in (
        "print(resolver.nameservers", "print(answer", "print(error",
        "print(str(exc)", "print(ip", "get_secret_bundle(",
        "sendmail(", "smtplib", "psycopg.connect(", "oci.core.ComputeClient(",
        "INSERT INTO", "UPDATE public.",
    ):
        assert forbidden not in source+policy
    assert 'resolver.nameservers=[PUBLIC_DNS_IP[mode]]' in source
    assert "configure=(mode==\"SYSTEM\")" in source
    assert 'AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY' in source
    assert "M38489_PRODUCTION=BLOCKED" in source
