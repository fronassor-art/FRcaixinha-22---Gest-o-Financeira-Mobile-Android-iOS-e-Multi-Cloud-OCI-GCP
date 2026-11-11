"""M39001 — full read-only access readiness, never send SMTP or modify PG18."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/frfinance_m39001_mail_readiness_nosend.py"
spec=importlib.util.spec_from_file_location("frfinance_m39001", SCRIPT)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PUBLIC={
    "APP_URL":"https://frfinance.com.br",
    "SMTP_HOST":"smtp-relay.brevo.com",
    "SMTP_PORT":"587",
    "SMTP_USER":"ci@example.com",
    "FR_FINANCE_EMAIL_FROM":"notificacoes@frfinance.com.br",
}
ENV={
    **PUBLIC,
    "AUTH_DATABASE_URL":"postgresql://frc_ai_auth:synthetic-not-real@127.0.0.1:5433/frcaixinha_aistudio_dev",
    "FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64":"eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
    "FR_FINANCE_ACCESS_HMAC_KEY":"synthetic-only-key-not-for-any-actual-email-0000",
    "SMTP_PASSWORD":"synthetic-provider-key-not-for-use",
    "FR_FINANCE_ACCESS_MAIL_ENABLE":"OFF",
    "FR_FINANCE_ACCESS_MAIL_WORKER":"OFF",
    "FR_FINANCE_REAL_PIX":"OFF",
}


def test_existing_original_env_can_be_inspected_without_activating_mail(monkeypatch):
    import app.access_delivery_pg18 as access
    calls=[]
    real=access.require_reviewed_config
    def checked(e):
        calls.append(dict(e))
        return real(e)
    monkeypatch.setattr(m, "require_reviewed_config", checked)
    config=m.original_runtime_readonly(dict(ENV), PUBLIC)
    assert config.smtp.host=="smtp-relay.brevo.com"
    assert config.smtp.app_origin=="https://frfinance.com.br"
    assert calls[0]["FR_FINANCE_ACCESS_MAIL_ENABLE"]=="REVIEWED_SINGLE_DB"
    assert ENV["FR_FINANCE_ACCESS_MAIL_ENABLE"]=="OFF"
    assert ENV["FR_FINANCE_ACCESS_MAIL_WORKER"]=="OFF"
    assert ENV["FR_FINANCE_REAL_PIX"]=="OFF"


@pytest.mark.parametrize("change", [
    {"FR_FINANCE_ACCESS_MAIL_ENABLE":"REVIEWED_SINGLE_DB"},
    {"FR_FINANCE_ACCESS_MAIL_WORKER":"EXPLICITLY_APPROVED"},
    {"FR_FINANCE_REAL_PIX":"ON"},
    {"APP_URL":"https://evil.example.com"},
    {"SMTP_HOST":"other.example.com"},
    {"FR_FINANCE_EMAIL_FROM":"spoof@example.com"},
])
def test_any_active_worker_payment_or_intake_mismatch_fails_closed(change):
    from frfinance_m38996_stage_existing_mail_config import StageBlocked
    with pytest.raises(StageBlocked):
        m.original_runtime_readonly({**ENV, **change}, PUBLIC)


class FakeHTTP:
    def __init__(self, *, status=200, url="https://frfinance.com.br",
                 body=b"<html><title>FR Finance</title></html>"):
        self.status=status
        self.url=url
        self.body=body
    def __enter__(self): return self
    def __exit__(self, *_): return None
    def geturl(self): return self.url
    def read(self, n=-1): return self.body if n==-1 else self.body[:n]


def test_https_needs_exact_origin_and_real_frfinance_html(monkeypatch):
    monkeypatch.setattr(m, "urlopen", lambda *_args, **_kwargs: FakeHTTP())
    result=m.check_public_html("https://frfinance.com.br")
    assert result=="FR_FINANCE_HTML_OBSERVED_NOT_DEPLOYMENT_ATTESTED"
    monkeypatch.setattr(m, "urlopen", lambda *_args, **_kwargs: FakeHTTP(
        url="https://attacker.example.com", body=b"FR Finance"
    ))
    assert m.check_public_html("https://frfinance.com.br")=="HTTPS_NOT_ATTESTED"
    monkeypatch.setattr(m, "urlopen", lambda *_args, **_kwargs: FakeHTTP(
        body=b"<html>Unrelated website</html>"
    ))
    assert m.check_public_html("https://frfinance.com.br")=="HTTPS_RESPONDED_APP_UNVERIFIED"


def test_api_route_probe_requires_post_methods_for_all_four(monkeypatch):
    import json
    ok={"paths":{x:{"post":{"summary":"CI"}} for x in m.ROUTES}}
    monkeypatch.setattr(m,"urlopen",lambda *_a, **_kw: FakeHTTP(body=json.dumps(ok).encode()))
    assert m.check_original_api_routes()=="ACCESS_ROUTES_LOADED_NOT_ENABLED"
    ok["paths"].pop("/api/v1/invitations/verify-email")
    monkeypatch.setattr(m,"urlopen",lambda *_a, **_kw: FakeHTTP(body=json.dumps(ok).encode()))
    assert m.check_original_api_routes()=="ACCESS_ROUTES_NOT_ALL_LOADED"


def test_readiness_only_reads_local_published_config_without_leaking_values(monkeypatch,capsys):
    monkeypatch.setattr(m,"_guard_original",lambda:None)
    monkeypatch.setattr(m,"_load_env",lambda:([],dict(ENV)))
    monkeypatch.setattr(m,"_verify_original_dsn",lambda _:None)
    monkeypatch.setattr(m,"_load_public",lambda:dict(PUBLIC))
    async def no_sql_write(_): pass
    monkeypatch.setattr(m,"original_db_readonly",no_sql_write)
    monkeypatch.setattr(m,"check_original_api_routes",lambda:"ACCESS_ROUTES_LOADED_NOT_ENABLED")
    monkeypatch.setattr(m,"check_public_html",lambda _:"HTTPS_UNREACHABLE_OR_UNVERIFIED")
    assert m.main()==0
    out=capsys.readouterr().out
    assert "M39001_ORIGINAL_CONFIG=PASS" in out
    assert "M39001_ORIGINAL_PG18_047_048=PASS" in out
    assert "M39001_SMTP_MESSAGES=NONE" in out
    assert "M39001_DATABASE_MUTATIONS=NONE" in out
    assert "M39001_PUBLIC_HTTPS=HTTPS_UNREACHABLE_OR_UNVERIFIED" in out
    assert "synthetic-not-real" not in out
    assert ENV["SMTP_PASSWORD"] not in out


def test_no_real_smtp_no_db_creation_and_no_worker_activation_in_probe():
    src=SCRIPT.read_text()
    for unwanted in (
        "smtplib", "submit_access_message(", "dispatch_one(",
        "CREATE DATABASE", "createdb", "initdb", "pg_ctl",
        ".write_text(", ".write_bytes(", "os.environ.update(",
        "FR_FINANCE_ACCESS_MAIL_WORKER=EXPLICITLY_APPROVED",
    ):
        assert unwanted not in src, unwanted
    assert "original_db_readonly" in src
    assert "verify_existing_schema(config)" in src
    assert "verify_existing_redemption_schema(config)" in src
