"""M38370–M38409: redacted public sender intake diagnosis and DNS stage isolation."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import os
import stat
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/aistudio_mail_dns_readonly.py"


def _cli():
    spec = importlib.util.spec_from_file_location("mail_dns_m38370", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifest(monkeypatch, tmp_path, *, sender=None):
    mod = _cli()
    path = tmp_path / "private" / "provider.json"
    from backend.scripts.aistudio_provider_intake import (
        initialize, save_public_field,
    )
    # Tests may import this script by path, but the writer and reader
    # both use the same strictly permissioned public-metadata format.
    initialize(path)
    if sender is not None:
        save_public_field(path, "FR_FINANCE_EMAIL_FROM", sender)
    monkeypatch.setattr(mod,"_default_file",lambda:path)
    return mod,path


def test_diagnose_no_manifest_no_network(tmp_path,monkeypatch,capsys):
    mod=_cli()
    monkeypatch.setattr(mod,"_default_file",lambda:tmp_path/"missing"/"file.json")
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *args:
                        pytest.fail("unexpected DNS query"))
    result=mod.main(["diagnose"])
    out=capsys.readouterr().out
    assert result==2
    assert "M38409_PREFLIGHT=PUBLIC_INTAKE_MISSING_OR_INVALID" in out
    assert "M38409_NETWORK_QUERIES=NONE" in out
    assert "M38409_EMAIL_REAL=OFF" in out
    assert "M38409_PRODUCTION=BLOCKED" in out


def test_diagnose_present_manifest_without_sender_field(monkeypatch,tmp_path,capsys):
    mod,path=_manifest(monkeypatch,tmp_path)
    assert path.is_file()
    assert mod.main(["diagnose"])==2
    out=capsys.readouterr().out
    assert "M38409_PREFLIGHT=EMAIL_FROM_NOT_CONFIGURED" in out
    assert "M38409_NETWORK_QUERIES=NONE" in out


def test_diagnose_sender_not_on_approved_domain(monkeypatch,tmp_path,capsys):
    mod,path=_manifest(monkeypatch,tmp_path,sender="contato@outraempresa.com.br")
    assert mod.main(["diagnose"])==2
    assert "M38409_PREFLIGHT=EMAIL_FROM_DOMAIN_MISMATCH" in capsys.readouterr().out


def test_diagnose_private_manifest_file_must_remain_mode_0600(
    monkeypatch,tmp_path,capsys,
):
    mod,path=_manifest(monkeypatch,tmp_path,sender="contato@frfinance.com.br")
    path.chmod(0o644)
    assert mod.main(["diagnose"])==2
    out=capsys.readouterr().out
    assert "M38409_PREFLIGHT=PUBLIC_INTAKE_MISSING_OR_INVALID" in out
    assert "contato@frfinance.com.br" not in out


def test_diagnose_ready_with_mock_python_dns_import(monkeypatch,tmp_path,capsys):
    mod,path=_manifest(monkeypatch,tmp_path,sender="contato@frfinance.com.br")
    fake_pkg=types.ModuleType("dns")
    fake_pkg.__path__=[]
    fake_resolver=types.ModuleType("dns.resolver")
    fake_pkg.resolver=fake_resolver
    monkeypatch.setitem(sys.modules,"dns",fake_pkg)
    monkeypatch.setitem(sys.modules,"dns.resolver",fake_resolver)
    assert mod.main(["diagnose"])==0
    out=capsys.readouterr().out
    assert "M38409_PREFLIGHT=READY_FOR_EXPLICIT_PUBLIC_DNS_READ" in out
    assert "M38409_NETWORK_QUERIES=NONE" in out
    assert "contato@frfinance.com.br" not in out


@pytest.mark.parametrize("params",[
    ["diagnose","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"],
    ["diagnose","--selector","mail"],
    ["diagnose","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY","--selector","mail"],
])
def test_diagnose_never_permits_approval_or_selector(
    monkeypatch,capsys,params,
):
    mod=_cli()
    called=[]
    monkeypatch.setattr(mod,"_read_source_domain",lambda:called.append("intake"))
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *a:called.append("dns"))
    assert mod.main(params)==2
    assert called==[]
    assert "M38409_DIAGNOSE=BLOCKED_INVALID_ARGUMENTS" in capsys.readouterr().out


def test_intake_failure_keeps_legacy_error_and_adds_safe_phase(
    monkeypatch,capsys,
):
    mod=_cli()
    monkeypatch.setattr(mod,"_read_source_domain",lambda: (_ for _ in ()).throw(
        RuntimeError("SECRET_FROM_PRIVATE_FILE")))
    monkeypatch.setattr(mod,"_local_preflight",lambda:"EMAIL_FROM_NOT_CONFIGURED")
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *args:
                        pytest.fail("DNS must not run after intake failure"))
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==2
    out=capsys.readouterr().out
    assert "M38289_MAIL_DNS=BLOCKED_INPUT_OR_DNS_QUERY" in out
    assert "M38409_FAILURE_STAGE=PUBLIC_INTAKE" in out
    assert "M38409_PREFLIGHT=EMAIL_FROM_NOT_CONFIGURED" in out
    assert "SECRET" not in out


def test_dns_resolver_failure_has_distinct_safe_phase(monkeypatch,capsys):
    mod=_cli()
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    def failure(*args):
        raise RuntimeError("SENSITIVE_PROVIDER_DNS_EXCEPTION")
    monkeypatch.setattr(mod,"_collect_public_dns",failure)
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==2
    out=capsys.readouterr().out
    assert "M38409_FAILURE_STAGE=DNS_RESOLVER" in out
    assert "M38409_PREFLIGHT=PUBLIC_INTAKE_ACCEPTED" in out
    assert "M38409_PROVIDER_STATUS=NOT_ATTESTED" in out
    assert "SENSITIVE" not in out
    assert "M38289_PRODUCTION=BLOCKED" in out


def test_policy_failure_has_distinct_phase(monkeypatch,capsys):
    mod=_cli()
    monkeypatch.setattr(mod,"_read_source_domain",lambda:"frfinance.com.br")
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *args:object())
    monkeypatch.setattr(mod,"assess_public_mail_dns",lambda *args:(
        _ for _ in ()).throw(ValueError("SENSITIVE_DNS_CONTENT")))
    assert mod.main(["live","AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"])==2
    out=capsys.readouterr().out
    assert "M38409_FAILURE_STAGE=DNS_RESPONSE_POLICY" in out
    assert "SENSITIVE" not in out


def test_unapproved_live_exits_before_intake_and_network(monkeypatch,capsys):
    mod=_cli()
    seen=[]
    monkeypatch.setattr(mod,"_read_source_domain",lambda:seen.append("intake"))
    monkeypatch.setattr(mod,"_collect_public_dns",lambda *args:seen.append("dns"))
    assert mod.main(["live"])==2
    assert seen==[]
    assert "BLOCKED_OPERATOR_APPROVAL_OR_SELECTOR" in capsys.readouterr().out


def test_static_contract_keeps_diagnostics_read_only():
    source=SCRIPT.read_text()
    for pattern in (
        '"diagnose"', 'M38409_FAILURE_STAGE=',
        '"PUBLIC_INTAKE"', '"DNS_RESOLVER"',
        '"DNS_RESPONSE_POLICY"', 'M38409_NETWORK_QUERIES=NONE',
        'M38409_BANK_ORIGINAL=UNTOUCHED',
    ):
        assert pattern in source
    for forbidden in (
        "smtplib.SMTP(", "send_message(", "INSERT INTO", "UPDATE public.",
        "oci.core.ComputeClient(", "requests.post(", "httpx.post(",
    ):
        assert forbidden not in source
