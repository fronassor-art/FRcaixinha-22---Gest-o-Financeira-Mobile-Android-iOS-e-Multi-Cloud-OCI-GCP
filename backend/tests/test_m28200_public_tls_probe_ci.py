"""M28200: security tests for opt-in DNS/TLS diagnostic, without real network."""
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from app.public_https_attestation import (
    PublicTlsProbeBlocked, probe_public_https_origin,
)


def make_answer(*ips):
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET,
             socket.SOCK_STREAM,6,"",(ip,443)) for ip in ips]


def test_public_dns_pinned_ips_and_tls_certificate_only():
    visited=[]
    def resolver(host,port,*,type):
        visited.append(("DNS",host,port,type))
        return make_answer("93.184.215.14")
    def tls(host,ip):
        visited.append(("TLS",host,ip))
        return True
    out=probe_public_https_origin(
        "https://app.frfinance.com.br",resolver=resolver,tls_verify=tls,
    )
    assert visited==[
        ("DNS","app.frfinance.com.br",443,socket.SOCK_STREAM),
        ("TLS","app.frfinance.com.br","93.184.215.14"),
    ]
    assert out.dns_public and out.hostname_certificate_valid
    for attribute in (
        "http_requested","smtp_submission","secret_used",
        "email_ownership_verified","mp_connected",
        "production_ready","user_activation_enabled","pix_enabled",
    ):
        assert getattr(out,attribute) is False


@pytest.mark.parametrize("bad",[
    "http://app.frfinance.com.br",
    "https://localhost",
    "https://127.0.0.1",
    "https://app.frfinance.com.br/path",
    "https://app.frfinance.com.br@localhost",
    "https://app.frfinance.com.br?access_token=test",
    "https://app.frfinance.com.br:8443",
])
def test_nonpublic_or_dangerous_origins_never_resolve(bad):
    called=[]
    def resolver(*args,**kwargs):
        called.append(1)
        raise AssertionError("must not resolve invalid input")
    with pytest.raises(PublicTlsProbeBlocked):
        probe_public_https_origin(bad,resolver=resolver)
    assert not called


@pytest.mark.parametrize("ip",[
    "127.0.0.1","10.0.0.1","172.16.0.1","192.168.0.1",
    "169.254.169.254","100.100.100.200","::1","fe80::1",
    "fd00::1","0.0.0.0","224.0.0.1","2001:db8::1",
])
def test_dns_to_private_or_metadata_network_is_blocked_before_tls(ip):
    calls=[]
    def resolver(*args,**kwargs):
        return make_answer(ip)
    def tls(*args):
        calls.append(args)
        return True
    with pytest.raises(PublicTlsProbeBlocked):
        probe_public_https_origin(
            "https://app.frfinance.com.br",resolver=resolver,tls_verify=tls,
        )
    assert calls==[]


def test_mixed_public_private_dns_answer_never_connects():
    calls=[]
    with pytest.raises(PublicTlsProbeBlocked):
        probe_public_https_origin(
            "https://app.frfinance.com.br",
            resolver=lambda *a,**k:make_answer("93.184.215.14","127.0.0.1"),
            tls_verify=lambda *args:calls.append(args) or True,
        )
    assert calls==[]


@pytest.mark.parametrize("result",[False,None,"true",1])
def test_tls_failure_never_means_approved(result):
    with pytest.raises(PublicTlsProbeBlocked):
        probe_public_https_origin(
            "https://app.frfinance.com.br",
            resolver=lambda *a,**k:make_answer("93.184.215.14"),
            tls_verify=lambda *args:result,
        )


def test_certificate_error_is_redacted_and_not_retried_as_insecure():
    def tls(*args):
        raise RuntimeError("SENSITIVE_INTERNAL_TLS_CREDENTIAL")
    with pytest.raises(PublicTlsProbeBlocked) as e:
        probe_public_https_origin(
            "https://app.frfinance.com.br",
            resolver=lambda *a,**k:make_answer("93.184.215.14"),
            tls_verify=tls,
        )
    assert "SENSITIVE_INTERNAL" not in str(e.value)


def _cli(home,*args):
    root=Path(__file__).resolve().parents[2]
    env=os.environ.copy()
    env["HOME"]=str(home)
    env["PYTHONPATH"]=str(root/"backend")
    return subprocess.run(
        [sys.executable,str(root/"backend/scripts/aistudio_provider_intake.py"),*args],
        env=env,cwd=root,text=True,capture_output=True,timeout=12,check=False,
    )


def test_cli_https_probe_requires_explicit_permission_and_public_manifest(tmp_path):
    assert _cli(tmp_path,"init").returncode==0
    # Neither invalid nor absent field invokes the network.
    assert _cli(tmp_path,"probe-https","APP_URL","AUTHORIZE_PUBLIC_TLS_ONLY").returncode==2
    assert _cli(tmp_path,"probe-https","SMTP_HOST","AUTHORIZE_PUBLIC_TLS_ONLY").returncode==2
    assert _cli(tmp_path,"probe-https","APP_URL","NO").returncode==2
    assert _cli(tmp_path,"next").returncode==0


def test_provider_probe_has_no_http_or_smtp_or_vendor_api_calls():
    root=Path(__file__).resolve().parents[2]
    s=(root/"backend/app/public_https_attestation.py").read_text()
    assert "socket.create_connection((ip,443)" in s
    assert "context.wrap_socket(tcp,server_hostname=hostname)" in s
    assert "not ip.is_global" in s
    for banned in (
        "requests.", "httpx.", "urllib.request", "smtplib", "starttls(",
        "sendmail(", "send_message(", "login(", "get_secret_bundle(",
        "asyncpg.connect(", "psycopg.connect(", "INSERT INTO", "UPDATE public.",
    ):
        assert banned not in s
