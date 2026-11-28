"""M38170–M38209: public API HTTPS health probe, CI mock, never network."""
from dataclasses import replace
from pathlib import Path
import json
import socket

import pytest

from app.public_api_health_attestation import (
    MAX_RESPONSE_BYTES, PublicApiHealthBlocked,
    PublicApiHealthObservation, probe_public_api_health,
)

ORIGIN = "https://app.frfinance.com.br"
BODY = {
    "status": "ONLINE",
    "app": "FR Finance",
    "framework": "FastAPI (Python)",
    "database_backend": "PostgreSQL com Row-Level Security (RLS)",
    "database_configured": False,
    "environment": "sandbox-development",
}
HEADERS = (
    ("Content-Type", "application/json"),
    ("Cache-Control", "no-store"),
    ("Pragma", "no-cache"),
    ("X-Content-Type-Options", "nosniff"),
)


def response(*, payload=None, headers=HEADERS, status=200, body=None):
    if body is None:
        body = json.dumps(BODY if payload is None else payload).encode("utf-8")
    return (status, headers, body)


def dns(*ips):
    def resolver(host, port, *, type):
        assert host == "app.frfinance.com.br"
        assert port == 443 and type == socket.SOCK_STREAM
        return [
            (socket.AF_INET6 if ":" in ip else socket.AF_INET,
             socket.SOCK_STREAM, 6, "", (ip, 443))
            for ip in ips
        ]
    return resolver


def test_public_pinned_dns_and_health_contract_are_observable_not_release():
    calls = []
    def exchange(host, ip):
        calls.append((host, ip))
        return response()
    report = probe_public_api_health(
        ORIGIN, resolver=dns("93.184.215.14"), exchange=exchange,
    )
    assert calls == [("app.frfinance.com.br", "93.184.215.14")]
    assert type(report) is PublicApiHealthObservation
    assert report.http_get_observed
    assert report.public_dns_and_tls_observed
    assert report.health_contract_observed
    assert report.cache_protection_observed
    assert report.environment_claim == "sandbox-development"
    assert report.database_configured_claim is False
    for field in (
        "actual_database_verified", "deployment_sha_verified",
        "production_auth_verified", "cloud_vm_identity_verified",
        "provider_attested", "production_authorized",
        "real_user_activation_authorized", "real_pix_authorized",
        "writes_performed",
    ):
        assert getattr(report, field) is False


def test_multiple_public_dns_pinned_ips_must_all_pass():
    calls = []
    def exchange(host,ip):
        calls.append(ip)
        return response()
    probe_public_api_health(
        ORIGIN, resolver=dns("93.184.215.14", "1.1.1.1"),
        exchange=exchange,
    )
    assert calls == ["1.1.1.1", "93.184.215.14"]


@pytest.mark.parametrize("bad", [
    "http://app.frfinance.com.br",
    "https://localhost",
    "https://127.0.0.1",
    "https://169.254.169.254",
    "https://app.frfinance.com.br:8443",
    "https://app.frfinance.com.br/api/health",
    "https://app.frfinance.com.br?token=secret",
    "https://app.frfinance.com.br#fragment",
    "https://foo:bar@app.frfinance.com.br",
    "https://app.frfinance.com.br@localhost",
    "https://app.frfinance.com.br/",
    "",
    None,
])
def test_noncanonical_or_private_origins_have_zero_network(bad):
    called = []
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            bad,
            resolver=lambda *a,**k: called.append("dns"),
            exchange=lambda *a: called.append("http"),
        )
    assert not called


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.1", "192.168.0.1", "172.16.1.1",
    "169.254.169.254", "100.100.100.200", "::1", "fe80::1",
    "fd00::1", "224.0.0.1", "2001:db8::1",
])
def test_private_or_metadata_dns_rejected_before_any_http(ip):
    calls = []
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            ORIGIN,resolver=dns(ip),
            exchange=lambda *a: calls.append(a) or response(),
        )
    assert calls == []


def test_mixed_private_public_dns_denied_with_zero_http():
    called = []
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            ORIGIN,resolver=dns("93.184.215.14","10.0.0.4"),
            exchange=lambda *a: called.append(a) or response(),
        )
    assert not called


@pytest.mark.parametrize("ip_count",[5,6,12])
def test_large_dns_sets_denied_before_http(ip_count):
    addresses = [f"93.184.215.{i}" for i in range(10,10+ip_count)]
    called = []
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            ORIGIN,resolver=dns(*addresses),
            exchange=lambda *a: called.append(a) or response(),
        )
    assert not called


@pytest.mark.parametrize("bad_status",[301,302,303,307,308,401,403,404,429,500,503,204,True,"200",0])
def test_no_redirect_or_error_can_pass(bad_status):
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            ORIGIN,resolver=dns("93.184.215.14"),
            exchange=lambda *a: response(status=bad_status),
        )


@pytest.mark.parametrize("header,bad", [
    ("Content-Type","text/html"),
    ("Content-Type","application/javascript"),
    ("Content-Type","application/json; charset=iso-8859-1"),
    ("Cache-Control","public, max-age=3600"),
    ("Cache-Control","private"),
    ("Pragma","cache"),
    ("X-Content-Type-Options",""),
    ("X-Content-Type-Options","off"),
])
def test_weakened_response_headers_are_denied(header,bad):
    headers=tuple((k,bad if k==header else v) for k,v in HEADERS)
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            ORIGIN,resolver=dns("93.184.215.14"),
            exchange=lambda *a: response(headers=headers),
        )


@pytest.mark.parametrize("header",["Content-Type","Cache-Control","Pragma","X-Content-Type-Options"])
def test_missing_or_duplicate_security_header_denied(header):
    missing=tuple((k,v) for k,v in HEADERS if k!=header)
    duplicate=HEADERS + tuple((k,v) for k,v in HEADERS if k==header)
    for headers in (missing,duplicate):
        with pytest.raises(PublicApiHealthBlocked):
            probe_public_api_health(
                ORIGIN,resolver=dns("93.184.215.14"),
                exchange=lambda *a: response(headers=headers),
            )


def test_any_compressed_or_oversized_body_is_denied():
    for item in (
        response(headers=HEADERS+(("Content-Encoding","gzip"),)),
        response(body=b"x"*(MAX_RESPONSE_BYTES+1)),
        response(body=b""),
        response(body=b'{"status": "ONLINE", "status": "ONLINE"}'),
    ):
        with pytest.raises(PublicApiHealthBlocked):
            probe_public_api_health(
                ORIGIN,resolver=dns("93.184.215.14"),exchange=lambda *a:item,
            )


@pytest.mark.parametrize("field,bad", [
    ("status","OK"),("app","FRcaixinha"),("framework","Flask"),
    ("database_backend","SQLite"),("database_configured",1),
    ("database_configured","true"),("environment","production"),
    ("environment","staging"),("environment",None),
])
def test_fake_health_or_promoted_environment_denied(field,bad):
    payload={**BODY,field:bad}
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            ORIGIN,resolver=dns("93.184.215.14"),
            exchange=lambda *a:response(payload=payload),
        )


def test_mixed_db_claims_across_two_public_ip_addresses_denied():
    calls = []
    def exchange(host,ip):
        calls.append(ip)
        return response(payload={**BODY,"database_configured":len(calls)==2})
    with pytest.raises(PublicApiHealthBlocked):
        probe_public_api_health(
            ORIGIN,resolver=dns("93.184.215.14","1.1.1.1"),
            exchange=exchange,
        )
    assert len(calls)==2


def test_bad_dns_or_certificate_failure_never_leaks_details():
    def failure(*a):
        raise RuntimeError("SENSITIVE_PROVIDER_TOKEN_IN_ERROR_MESSAGE")
    with pytest.raises(PublicApiHealthBlocked) as exc:
        probe_public_api_health(
            ORIGIN,resolver=dns("93.184.215.14"),exchange=failure,
        )
    assert "SENSITIVE" not in str(exc.value)
    assert "TOKEN" not in str(exc.value)


def test_code_contains_fixed_get_no_auth_no_redirect_and_no_cloud():
    src=(Path(__file__).resolve().parents[2]/
         "backend/app/public_api_health_attestation.py").read_text()
    assert "GET /api/health HTTP/1.1" in src
    assert "server_hostname=hostname" in src
    assert "socket.create_connection((ip, 443)" in src
    assert "MAX_RESPONSE_BYTES = 8192" in src
    assert "_resolve_public(hostname, resolver)" in src
    for forbidden in (
        "smtplib", "requests.get(", "httpx.get(", "Authorization:",
        "Cookie:", "get_secret_bundle(", "psycopg.connect(",
        "asyncpg.connect(", "INSERT INTO", "UPDATE public.",
        "oci.core.ComputeClient", "urllib.request.urlopen",
    ):
        assert forbidden not in src


def test_existing_public_manifest_cli_guard_remains_explicit(tmp_path):
    from subprocess import run
    import os,sys
    root=Path(__file__).resolve().parents[2]
    cmd=[sys.executable,str(root/"backend/scripts/aistudio_provider_intake.py")]
    env={**os.environ,"HOME":str(tmp_path),"PYTHONPATH":str(root/"backend")}
    assert run(cmd+["init"],env=env,capture_output=True,timeout=10).returncode==0
    assert run(cmd+["set","APP_URL",ORIGIN],env=env,capture_output=True,timeout=10).returncode==0
    for args in (
        ["probe-api-health"],
        ["probe-api-health","APP_URL"],
        ["probe-api-health","SMTP_HOST","AUTHORIZE_PUBLIC_HEALTH_READ_ONLY"],
        ["probe-api-health","APP_URL","AUTHORIZE_PUBLIC_TLS_ONLY"],
    ):
        outcome=run(cmd+args,env=env,capture_output=True,timeout=10)
        assert outcome.returncode==2
        assert "M38209_PUBLIC_HEALTH_GET=PASS" not in outcome.stdout.decode("utf-8")
