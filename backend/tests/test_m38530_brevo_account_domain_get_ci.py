"""FR Finance M38530-M38569: Brevo account-specific GET attestation offline CI."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import types
from urllib.error import HTTPError

import pytest

from app.brevo_account_domain_attestation import (
    BrevoDomainStatusBlocked,assess_brevo_account_response,DOMAIN,
)

ROOT=Path(__file__).resolve().parents[2]
CLI=ROOT/"backend/scripts/aistudio_brevo_domain_account_readonly.py"
KEY="xkeysib-"+"A"*64


def _report(**changes):
    payload={
        "domain":DOMAIN,
        "verified":True,
        "authenticated":True,
        "dns_records":{
            "brevo_code":{"status":True,"value":"SENSITIVE_BREVO_CODE"},
            "dkim_record":{"status":True,"value":"SECRET_PUBLIC_KEY_MATERIAL"},
            "dmarc_record":{"status":True,"value":"SECRET_RUA_EMAIL"},
        },
        "creator":{"email":"SENSITIVE_OWNER_EMAIL"},
    }
    payload.update(changes)
    return assess_brevo_account_response(payload)


def _load():
    spec=importlib.util.spec_from_file_location("fr_brevo_m38530",CLI)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_provider_says_authenticated_is_only_a_provider_claim():
    r=_report()
    assert r.mode=="BREVO_AUTHENTICATED_GET_ACCOUNT_CLAIM"
    assert r.account_domain_verified and r.account_domain_authenticated
    assert r.brevo_code_status=="REPORTED_VALID"
    assert r.dkim_status=="REPORTED_VALID"
    assert r.dmarc_status=="REPORTED_VALID"
    assert r.blockers==(
        "BREVO_SMTP_STARTTLS_AUTH_NOT_ATTESTED",
        "BREVO_CONTROLLED_DELIVERY_NOT_ATTESTED",
        "BREVO_SIGNATURE_ALIGNMENT_NOT_ATTESTED",
        "REAL_RECIPIENT_OWNERSHIP_AND_CONSENT_NOT_ATTESTED",
    )
    for name in (
        "real_smtp_authenticated","delivery_receipt_verified",
        "dkim_signature_and_alignment_verified",
        "real_email_send_authorized","real_user_activation_authorized",
        "real_pix_authorized","production_authorized",
        "database_mutations_performed","provider_mutations_performed",
    ):
        assert getattr(r,name) is False
    assert "SENSITIVE" not in repr(r)


@pytest.mark.parametrize("verified,authenticated,expected",[
    (False,False,("BREVO_ACCOUNT_DOMAIN_NOT_VERIFIED",
                   "BREVO_ACCOUNT_DOMAIN_NOT_AUTHENTICATED")),
    (True,False,("BREVO_ACCOUNT_DOMAIN_NOT_AUTHENTICATED",)),
    (False,True,("BREVO_ACCOUNT_DOMAIN_NOT_VERIFIED",)),
    (True,True,()),
])
def test_independent_verified_and_authenticated_states(
    verified,authenticated,expected,
):
    r=_report(verified=verified,authenticated=authenticated)
    assert (r.account_domain_verified,r.account_domain_authenticated)==(
        verified,authenticated,
    )
    for code in expected:
        assert code in r.blockers
    assert not r.production_authorized


@pytest.mark.parametrize("missing",["brevo_code","dkim_record","dmarc_record"])
def test_records_not_returned_are_never_assumed_good(missing):
    d={
        "brevo_code":{"status":True},
        "dkim_record":{"status":True},
        "dmarc_record":{"status":True},
    }
    d.pop(missing)
    r=_report(dns_records=d)
    assert "NOT_RETURNED" in (r.brevo_code_status,r.dkim_status,r.dmarc_status)
    assert not r.production_authorized


@pytest.mark.parametrize("key",["brevo_code","dkim_record","dmarc_record"])
def test_any_invalid_record_is_flagged(key):
    d={k:{"status":True} for k in ("brevo_code","dkim_record","dmarc_record")}
    d[key]["status"]=False
    r=_report(dns_records=d)
    assert "REPORTED_INVALID" in (r.brevo_code_status,r.dkim_status,r.dmarc_status)
    assert any("REPORTED_INVALID" in b for b in r.blockers)


@pytest.mark.parametrize("bad",[
    None,[],False,True,123,{"authenticated":True},
    {"domain":DOMAIN,"verified":1,"authenticated":True},
    {"domain":DOMAIN,"verified":True,"authenticated":1},
    {"domain":"attacker.com","verified":True,"authenticated":True},
    {"domain":DOMAIN+".evil","verified":True,"authenticated":True},
    {"domain":"FRFINANCE.COM.BR","verified":True,"authenticated":True},
    {"domain":DOMAIN,"domain_name":"attacker.com",
     "verified":True,"authenticated":True},
    {"domain":DOMAIN,"verified":True,"authenticated":True,
     "dns_records":[]},
    {"domain":DOMAIN,"verified":True,"authenticated":True,
     "dns_records":{"dkim_record":{"status":"true"}}},
])
def test_provider_schema_wrong_domain_and_types_fail_closed(bad):
    if isinstance(bad,dict) and bad.get("dns_records")=={
        "dkim_record":{"status":"true"}
    }:
        r=assess_brevo_account_response(bad)
        assert r.dkim_status=="NOT_RETURNED"
    else:
        with pytest.raises(BrevoDomainStatusBlocked):
            assess_brevo_account_response(bad)


def test_missing_optional_dns_records_must_be_marked_unreturned():
    r=_report(dns_records={})
    assert r.brevo_code_status=="NOT_RETURNED"
    assert r.dkim_status=="NOT_RETURNED"
    assert r.dmarc_status=="NOT_RETURNED"
    assert r.account_domain_authenticated
    assert not r.real_email_send_authorized


def test_api_response_other_fields_are_never_exposed():
    r=_report(
        dns_records={"brevo_code":{"status":True,"value":"secret1"}},
        access_token="SENSITIVE_ACCESS_TOKEN",
        creator={"email":"SENSITIVE_CREATOR_EMAIL"},
    )
    text=repr(r)
    assert "SENSITIVE" not in text
    assert "secret1" not in text
    assert r.dkim_status=="NOT_RETURNED"


def test_offline_cli_makes_no_network_and_never_asks_for_key(capsys,monkeypatch):
    m=_load()
    monkeypatch.setattr(m,"_prompt_api_key",lambda:pytest.fail("key requested"))
    monkeypatch.setattr(m,"_api_get_domain",lambda key:pytest.fail("network"))
    assert m.main(["offline"])==0
    out=capsys.readouterr().out
    assert "M38569_MODE=OFFLINE_NO_NETWORK_NO_API_KEY" in out
    assert "M38569_PRODUCTION=BLOCKED" in out


@pytest.mark.parametrize("args",[
    ["offline","AUTHORIZE_BREVO_DOMAIN_STATUS_GET_ONLY"],
    ["live"],
    ["live","AUTHORIZE_BREVO_DOMAIN_AUTHENTICATE"],
    ["live","AUTHORIZE_BREVO_DOMAIN_STATUS_GET_ONLY","extra"],
])
def test_unauthorized_or_unexpected_args_do_not_request_credentials(
    args,monkeypatch,capsys,
):
    m=_load()
    monkeypatch.setattr(m,"_prompt_api_key",lambda:pytest.fail("key requested"))
    monkeypatch.setattr(m,"_api_get_domain",lambda _:pytest.fail("network"))
    if args[-1]=="extra":
        with pytest.raises(SystemExit):
            m.main(args)
    else:
        assert m.main(args)==2


def test_live_uses_key_in_memory_and_outputs_only_redacted_claims(
    monkeypatch,capsys,
):
    m=_load()
    calls=[]
    monkeypatch.setattr(m,"_prompt_api_key",lambda:KEY)
    def fake_get(key):
        calls.append(key)
        return {"domain":DOMAIN,"verified":True,"authenticated":True,
                "dns_records":{"dkim_record":{"status":True,"value":"SENSITIVE_DKIM"}}}
    monkeypatch.setattr(m,"_api_get_domain",fake_get)
    assert m.main(["live","AUTHORIZE_BREVO_DOMAIN_STATUS_GET_ONLY"])==0
    out=capsys.readouterr().out
    assert calls==[KEY]
    assert "M38569_BREVO_VERIFIED=TRUE" in out
    assert "M38569_BREVO_AUTHENTICATED=TRUE" in out
    assert "M38569_DKIM_STATUS=REPORTED_VALID" in out
    assert "M38569_EMAIL_REAL=OFF" in out
    assert "M38569_REAL_USERS=OFF" in out
    assert "M38569_PRODUCTION=BLOCKED" in out
    assert "SENSITIVE" not in out
    assert KEY not in out


def test_live_does_not_print_network_exception_text(monkeypatch,capsys):
    m=_load()
    monkeypatch.setattr(m,"_prompt_api_key",lambda:KEY)
    def raise_failure(_):
        raise RuntimeError("SENSITIVE_NETWORK_STACK_ERROR")
    monkeypatch.setattr(m,"_api_get_domain",raise_failure)
    assert m.main(["live","AUTHORIZE_BREVO_DOMAIN_STATUS_GET_ONLY"])==2
    out=capsys.readouterr().out
    assert "M38569_BREVO_ACCOUNT=BLOCKED_UNCLASSIFIED" in out
    assert "SENSITIVE" not in out
    assert "M38569_PRODUCTION=BLOCKED" in out


def test_noninteractive_terminal_fails_before_credential(monkeypatch):
    m=_load()
    monkeypatch.setattr(m.sys,"stdin",types.SimpleNamespace(isatty=lambda:False))
    monkeypatch.setattr(m.getpass,"getpass",lambda x:pytest.fail("prompt"))
    with pytest.raises(BrevoDomainStatusBlocked):
        m._prompt_api_key()


@pytest.mark.parametrize("bad",[
    "", "abc", "xkeysib secret", "secret\nInjection: header",
    "x"*513, "🔑"*30,
])
def test_malformed_api_key_never_reaches_network(monkeypatch,bad):
    m=_load()
    with pytest.raises(BrevoDomainStatusBlocked):
        m._api_get_domain(bad)


class FakeResponse:
    def __init__(self,body,status=200,content_type="application/json"):
        self.body=body
        self.status=status
        self.headers={"Content-Type":content_type}
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def getcode(self): return self.status
    def read(self,n): return self.body[:n]


def _fake_http(monkeypatch,response):
    m=_load()
    calls=[]
    class Opener:
        def open(self,request,timeout):
            calls.append((request,timeout))
            if isinstance(response,Exception):
                raise response
            return response
    monkeypatch.setattr(m,"build_opener",lambda *handlers:Opener())
    return m,calls


def test_fixed_get_path_key_header_content_type_and_no_secret_output(monkeypatch):
    body=json.dumps({"domain":DOMAIN,"verified":True,
                     "authenticated":True}).encode()
    m,calls=_fake_http(monkeypatch,FakeResponse(body))
    data=m._api_get_domain(KEY)
    assert data["domain"]==DOMAIN
    assert len(calls)==1
    request,timeout=calls[0]
    assert request.full_url=="https://api.brevo.com/v3/senders/domains/frfinance.com.br"
    assert request.get_method()=="GET"
    assert 1<=timeout<=15
    assert dict(request.header_items()).get("Api-key")==KEY


@pytest.mark.parametrize("response",[
    FakeResponse(b"{}",status=201),
    FakeResponse(b"{}",content_type="text/html"),
    FakeResponse(b"x"*32769),
    FakeResponse(b'{"domain":"frfinance.com.br","verified":true,'
                 b'"authenticated":true,"authenticated":true}'),
    FakeResponse(b'{"domain": '),
])
def test_http_status_size_mime_duplicate_json_are_rejected(monkeypatch,response):
    m,_=_fake_http(monkeypatch,response)
    with pytest.raises(BrevoDomainStatusBlocked):
        m._api_get_domain(KEY)


@pytest.mark.parametrize("status,expected",[
    (401,"M38530_BREVO_CREDENTIALS_UNAUTHORIZED"),
    (403,"M38530_BREVO_CREDENTIALS_UNAUTHORIZED"),
    (404,"M38530_BREVO_DOMAIN_NOT_REGISTERED"),
    (429,"M38530_BREVO_RATE_LIMITED"),
    (500,"M38530_BREVO_PROVIDER_HTTP_FAILURE"),
    (302,"M38530_BREVO_PROVIDER_HTTP_FAILURE"),
])
def test_http_errors_redacted_and_never_print_account_data(
    monkeypatch,status,expected,
):
    m,_=_fake_http(monkeypatch,HTTPError(
        "https://api.brevo.com/v3/senders/domains/frfinance.com.br",
        status,"SENSITIVE_BREVO_ERROR",{},None,
    ))
    with pytest.raises(BrevoDomainStatusBlocked,match=expected):
        m._api_get_domain(KEY)


def test_static_host_prohibits_mutations_redirect_and_unattended_secrets():
    src=CLI.read_text()
    assert 'method="GET"' in src
    assert "_NoRedirect" in src
    assert "HTTPSHandler(context=ssl.create_default_context())" in src
    assert "getpass.getpass" in src
    assert "sys.stdin.isatty()" in src
    assert "https://api.brevo.com/v3/senders/domains/frfinance.com.br" in src
    for forbidden in (
        'method="POST"', 'method="PUT"', 'method="PATCH"',
        'method="DELETE"', "sendmail(", "smtplib.SMTP(",
        "os.environ", "os.getenv", "subprocess.run(",
        "open('/etc/resolv.conf", "psycopg.connect(",
        "INSERT INTO", "UPDATE public.", "get_secret_bundle(",
    ):
        assert forbidden not in src
