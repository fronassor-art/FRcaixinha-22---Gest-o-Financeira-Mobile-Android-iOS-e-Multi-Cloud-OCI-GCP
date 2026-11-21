"""FR Finance M38490–M38529: opt-in DNS public fallback, no OS changes.

Mocked DNS data exercises the real collector and CLI. NO network in CI.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/aistudio_mail_dns_readonly.py"
_CODE="brevo-code="+"b"*32
_DMARC="v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com"
_KEY="A"*64


def _load():
    spec=importlib.util.spec_from_file_location("aistudio_m38490_dns",SCRIPT)
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeTxt:
    def __init__(self,value):
        self.strings=(value.encode("ascii"),)


class FakeCname:
    def __init__(self,name):
        self.target=types.SimpleNamespace(to_text=lambda omit_final_dot:name)


class FakeResult:
    def __init__(self,records):
        self.rrset=(object() if records else None)
        self.records=records
    def __iter__(self):
        return iter(self.records)


def fake_dns(monkeypatch, *, error=None, records=None):
    """Install synthetic dns package without calling network."""
    calls=[]
    made=[]
    package=types.ModuleType("dns")
    package.__path__=[]
    resolver_mod=types.ModuleType("dns.resolver")
    exception_mod=types.ModuleType("dns.exception")

    class NoAnswer(Exception): pass
    class NXDOMAIN(Exception): pass
    resolver_mod.NoAnswer=NoAnswer
    resolver_mod.NXDOMAIN=NXDOMAIN
    package.resolver=resolver_mod
    package.exception=exception_mod

    class Resolver:
        def __init__(self, *, configure=True):
            made.append(self)
            self.configure=configure
            self.nameservers=[]
            if error=="CONFIG" and configure:
                raise RuntimeError("PRIVATE_RESOLVER_FAILURE_MUST_NOT_PRINT")
        def resolve(self,name,record_type,raise_on_no_answer=False):
            calls.append((name,record_type,raise_on_no_answer,self.configure,
                          tuple(self.nameservers)))
            if error=="TIMEOUT":
                raise RuntimeError("SENSITIVE_DNS_TIMEOUT")
            rows=(records or {
                ("frfinance.com.br","TXT"):[FakeTxt(_CODE)],
                ("_dmarc.frfinance.com.br","TXT"):[FakeTxt(_DMARC)],
                ("mail._domainkey.frfinance.com.br","CNAME"):[],
                ("mail._domainkey.frfinance.com.br","TXT"):
                    [FakeTxt("k=rsa;p="+_KEY)],
            }).get((name,record_type),[])
            return FakeResult(rows)
    resolver_mod.Resolver=Resolver
    monkeypatch.setitem(sys.modules,"dns",package)
    monkeypatch.setitem(sys.modules,"dns.resolver",resolver_mod)
    monkeypatch.setitem(sys.modules,"dns.exception",exception_mod)
    return calls,made


@pytest.mark.parametrize("mode,expected",[
    ("cloudflare","1.1.1.1"),
    ("google","8.8.8.8"),
])
def test_explicit_provider_uses_only_approved_ip_without_system_config(
    monkeypatch,mode,expected,
):
    mod=_load()
    calls,made=fake_dns(monkeypatch)
    report=mod._collect_public_dns("frfinance.com.br",(),resolver_mode=mode)
    assert len(made)==1
    assert made[0].configure is False
    assert made[0].nameservers==[expected]
    assert calls==[
        ("frfinance.com.br","TXT",False,False,(expected,)),
        ("_dmarc.frfinance.com.br","TXT",False,False,(expected,)),
    ]
    assert report.sender_domain=="frfinance.com.br"
    assert report.dkim==()
    assert report.spf_txt==(_CODE,)
    assert report.dmarc_txt==(_DMARC,)


def test_system_mode_remains_default_without_third_party_fallback(monkeypatch):
    mod=_load()
    calls,made=fake_dns(monkeypatch,error="CONFIG")
    with pytest.raises(mod.MailDnsObservationBlocked):
        mod._collect_public_dns("frfinance.com.br",())
    assert calls==[]
    assert len(made)==1
    assert made[0].configure is True


def test_provider_override_can_bypass_missing_system_configuration(monkeypatch):
    mod=_load()
    calls,made=fake_dns(monkeypatch,error="CONFIG")
    result=mod._collect_public_dns(
        "frfinance.com.br",(),resolver_mode="cloudflare",
    )
    assert len(calls)==2
    assert made[0].configure is False
    assert result.spf_txt==(_CODE,)


@pytest.mark.parametrize("mode",[
    "external","8.8.4.4","https://1.1.1.1",None,True,
])
def test_direct_collector_does_not_accept_other_resolvers(mode,monkeypatch):
    mod=_load()
    calls,made=fake_dns(monkeypatch)
    with pytest.raises(mod.MailDnsObservationBlocked):
        mod._collect_public_dns("frfinance.com.br",(),resolver_mode=mode)
    assert not calls and not made


@pytest.mark.parametrize("domain",[
    "localhost","127.0.0.1","169.254.169.254","frfinance.com.br.attacker.test",
    "other.example","FRFINANCE.COM.BR",None,
])
def test_direct_collector_rejects_unapproved_domain_before_dns(
    domain,monkeypatch,
):
    mod=_load()
    calls,made=fake_dns(monkeypatch)
    with pytest.raises(mod.MailDnsObservationBlocked):
        mod._collect_public_dns(domain,(),resolver_mode="cloudflare")
    assert not calls and not made


@pytest.mark.parametrize("selectors",[
    ("../../metadata",),
    ("MAIL",),
    ("mail", "mail"),
    ("mail","brevo1","brevo2"),
    ("foo.bar",),
    ["mail"],
    None,
])
def test_direct_collector_rejects_unapproved_selectors_before_dns(
    selectors,monkeypatch,
):
    mod=_load()
    calls,made=fake_dns(monkeypatch)
    with pytest.raises(mod.MailDnsObservationBlocked):
        mod._collect_public_dns("frfinance.com.br",selectors,
                                resolver_mode="cloudflare")
    assert not calls and not made


@pytest.mark.parametrize("args",[
    ["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY","--resolver","cloudflare"],
    ["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY","--resolver","google"],
    ["live","AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY"],
    ["live","AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY","--resolver","system"],
    ["offline","--resolver","cloudflare"],
    ["diagnose","--resolver","google"],
])
def test_cross_mode_authorizations_do_not_read_manifest_or_network(
    args,monkeypatch,capsys,
):
    mod=_load()
    calls=[]
    monkeypatch.setattr(mod,"_read_source_domain",lambda:calls.append("intake"))
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *a,**kw:calls.append("dns"))
    assert mod.main(args)==2
    assert not calls
    assert "BLOCKED" in capsys.readouterr().out


@pytest.mark.parametrize("mode,ip",[
    ("cloudflare","1.1.1.1"),("google","8.8.8.8")
])
def test_full_live_command_approved_external_provider_no_secret_output(
    mode,ip,monkeypatch,capsys,
):
    mod=_load()
    calls,made=fake_dns(monkeypatch)
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    result=mod.main([
        "live","AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY",
        "--resolver",mode,"--selector","mail",
    ])
    out=capsys.readouterr().out
    assert result==0
    assert made[0].configure is False
    assert made[0].nameservers==[ip]
    assert len(calls)==4
    assert {c[0] for c in calls}=={
        "frfinance.com.br", "_dmarc.frfinance.com.br",
        "mail._domainkey.frfinance.com.br",
    }
    assert "M38529_RESOLVER_MODE="+mode.upper() in out
    assert "M38529_THIRD_PARTY_PUBLIC_DNS=TRUE" in out
    assert "M38329_BREVO_CODE_RECORD=TRUE" in out
    assert "M38329_DKIM_MODE=ONE_TXT_PUBLISHED_CANDIDATE" in out
    assert "M38329_PROVIDER_AUTHENTICATED=NOT_VERIFIED" in out
    assert "M38289_REAL_EMAIL=OFF" in out
    assert "M38289_REAL_ACTIVATION=OFF" in out
    assert "M38289_PIX_REAL=OFF" in out
    assert "M38289_PRODUCTION=BLOCKED" in out
    assert _CODE not in out and _KEY not in out


def test_system_default_preserves_prior_two_argument_monkeypatch_contract(
    monkeypatch,capsys,
):
    mod=_load()
    called=[]
    from app.mail_dns_readiness_readonly import PublicMailDnsSnapshot
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    def old_collector(domain,selectors):
        called.append((domain,selectors))
        return PublicMailDnsSnapshot(
            sender_domain=domain,spf_txt=(_CODE,),
            dmarc_txt=(_DMARC,),dkim=(),
        )
    monkeypatch.setattr(mod,"_collect_public_dns",old_collector)
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==0
    assert called==[("frfinance.com.br",())]
    assert "M38529_RESOLVER_MODE=SYSTEM" in capsys.readouterr().out


def test_external_provider_failures_are_sanitized(monkeypatch,capsys):
    mod=_load()
    fake_dns(monkeypatch,error="TIMEOUT")
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    rc=mod.main([
        "live","AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY",
        "--resolver","cloudflare",
    ])
    out=capsys.readouterr().out
    assert rc==2
    assert "M38409_FAILURE_STAGE=DNS_RESOLVER" in out
    assert "M38529_RESOLVER_MODE=CLOUDFLARE" in out
    assert "SENSITIVE" not in out
    assert "M38289_REAL_EMAIL=OFF" in out
    assert "M38289_PRODUCTION=BLOCKED" in out


def test_source_never_auto_falls_back_or_writes_system_dns():
    src=SCRIPT.read_text()
    assert "configure=(resolver_mode==\"system\")" in src
    assert 'resolver.nameservers=[_APPROVED_DNS_IPS[resolver_mode]]' in src
    assert 'AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY' in src
    for forbidden in (
        "open('/etc/resolv.conf","write_text('/etc/resolv.conf",
        "os.system(","subprocess.run(","smtplib.SMTP(","sendmail(",
        "psycopg.connect(","INSERT INTO","UPDATE public.",
        "oci.core.ComputeClient(","requests.post(",
    ):
        assert forbidden not in src
