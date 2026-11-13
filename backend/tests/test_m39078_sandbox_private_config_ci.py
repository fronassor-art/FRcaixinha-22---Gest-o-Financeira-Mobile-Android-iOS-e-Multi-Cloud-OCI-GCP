"""M39078: validated private sandbox flag with dry-run and atomic backup.

CI uses temp files and fake API ONLY. No real PostgreSQL/Android/SMS/Pix.
"""
import os
from pathlib import Path
import stat
import sys

import pytest

from backend.scripts import frfinance_m39078_special_credit_sandbox_private_config as m
from backend.scripts.frfinance_m39057_stored_verifier_readonly import GuardBlocked


@pytest.mark.parametrize("raw,expected",[
    ("DATABASE_URL='postgresql://private-value'\n", "UNSET"),
    ("FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO\n", "NO"),
    ("export FR_FINANCE_SPECIAL_CREDIT_SANDBOX='YES'\n", "YES"),
    ("# FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES\n", "UNSET"),
    ("FR_FINANCE_SPECIAL_CREDIT_SANDBOX=OFF\n", "NO"),
])
def test_read_flag_does_not_touch_other_secrets(raw,expected):
    assert m.existing_value(raw)[0] == expected
    updated=m.replace_flag(raw,"YES")
    assert m.existing_value(updated)[0]=="YES"
    active_lines = [line for line in updated.splitlines() if m.LINE.match(line)]
    assert active_lines == ["FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES"]


def test_absent_flag_only_appends_new_local_setting():
    before="AUTH_SECRET='never print this'\nDATABASE_URL='secret-url'\n"
    after=m.replace_flag(before,"YES")
    assert after.startswith(before)
    assert after.endswith("FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES\n")


def test_original_other_lines_and_order_preserved():
    before="# comment\nAUTH_SECRET=hidden\nFR_FINANCE_SPECIAL_CREDIT_SANDBOX='NO'\nOTHER=keep\n"
    after=m.replace_flag(before,"YES")
    assert "AUTH_SECRET=hidden" in after and "OTHER=keep" in after
    assert after.splitlines() == [
        "# comment", "AUTH_SECRET=hidden",
        "FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES", "OTHER=keep"
    ]


@pytest.mark.parametrize("bad",[
    "FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES\nFR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO",
    "FR_FINANCE_SPECIAL_CREDIT_SANDBOX=MAYBE",
    "FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES NO",
    "FR_FINANCE_SPECIAL_CREDIT_SANDBOX=\"not-closed",
])
def test_reject_duplicate_and_malformed_flags(bad):
    with pytest.raises(GuardBlocked):
        m.replace_flag(bad,"YES")


@pytest.mark.parametrize("bad",["", "ON", "TRUE", "enabled"])
def test_reject_unsupported_new_value(bad):
    with pytest.raises(GuardBlocked):
        m.replace_flag("OTHER=1",bad)


def test_atomic_backup_private_0600_without_secret_stdout(tmp_path,monkeypatch,capsys):
    config=tmp_path/"api.env"
    original="AUTH_SECRET='sensitive-keep-untouched'\n"
    config.write_text(original)
    os.chmod(config,0o600)
    monkeypatch.setattr(m,"ENV_PATH",config)
    replacement=m.replace_flag(original,"YES")
    m.write_private_config(original,replacement)
    assert config.read_text()==replacement
    assert stat.S_IMODE(config.stat().st_mode)==0o600
    archives=list(tmp_path.glob(".api.env.m39078.*.bak"))
    assert len(archives)==1
    assert archives[0].read_text()==original
    assert stat.S_IMODE(archives[0].stat().st_mode)==0o600
    out=capsys.readouterr().out
    assert "sensitive-keep-untouched" not in out
    assert str(config) not in out
    assert str(archives[0]) not in out


def test_no_backup_created_if_unmodified(tmp_path,monkeypatch):
    config=tmp_path/"api.env"
    config.write_text("FR_FINANCE_SPECIAL_CREDIT_SANDBOX=YES\n")
    monkeypatch.setattr(m,"ENV_PATH",config)
    m.write_private_config(config.read_text(),config.read_text())
    assert list(tmp_path.glob("*.bak"))==[]


def test_operator_inspect_never_writes(tmp_path,monkeypatch,capsys):
    config=tmp_path/"api.env"
    contents="FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO\n"
    config.write_text(contents)
    monkeypatch.setattr(m,"ENV_PATH",config)
    monkeypatch.setattr(m,"verify_original",lambda:None)
    monkeypatch.setattr(m,"private_config_read",lambda:(contents,"NO"))
    monkeypatch.setattr(m,"api_state",
        lambda:"AUTH_TEST_MODE_ALREADY_ACTIVE_CHECK_READINESS")
    monkeypatch.setattr(sys,"argv",["m39078","--inspect"])
    assert m.main()==0
    assert config.read_text()==contents
    assert "M39078_STATUS=PASS_READ_ONLY" in capsys.readouterr().out


def test_runtime_blocked_prevents_activation(tmp_path,monkeypatch,capsys):
    config=tmp_path/"api.env"
    contents="FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO\n"
    config.write_text(contents)
    monkeypatch.setattr(m,"ENV_PATH",config)
    monkeypatch.setattr(m,"verify_original",lambda:None)
    monkeypatch.setattr(m,"private_config_read",lambda:(contents,"NO"))
    monkeypatch.setattr(m,"api_state",lambda:"BLOCKED_API_RUNTIME_UNEXPECTED")
    monkeypatch.setattr(sys,"argv",["m39078","--enable"])
    assert m.main()==2
    assert config.read_text()==contents
    assert "BLOCKED_FASTAPI_AUTH_MODE_NOT_ATTESTED" in capsys.readouterr().out


def test_original_flags_are_fail_closed_without_new_dsn():
    source=Path(m.__file__).read_text()
    for required in (
        "verify_original()",
        "collect_urls()",
        "check_private_homologation(flags)",
        "AUTH_TEST_MODE_ALREADY_ACTIVE_CHECK_READINESS",
        "FR_FINANCE_SPECIAL_CREDIT_SANDBOX",
        "operator",
        "AI_STUDIO",
    ):
        if required not in source and required not in ("operator","AI_STUDIO"):
            raise AssertionError(required)
    assert "psycopg.connect" not in source
    assert "subprocess.Popen" not in source
    assert "os.kill(" not in source
    assert "FR_FINANCE_PIX_REAL=ON" not in source
