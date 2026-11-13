"""M39064: only synthetic signer fingerprints and temporary private files."""
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from backend.scripts import frfinance_m39064_installed_apk_signer_readonly as m


def test_keytool_colon_hex_fingerprint_matches_reference():
    digest = ":".join(m.EXPECTED_MAIN_CERT[i:i+2]
                      for i in range(0, len(m.EXPECTED_MAIN_CERT), 2)).upper()
    assert m.parse_certificate("Alias name: frcaixinha_aistudio\n SHA256: " + digest + "\n") == (
        m.EXPECTED_MAIN_CERT
    )


@pytest.mark.parametrize("text", [
    "", "not-a-digest", "SHA256: AB:CD",
    "SHA256: " + "aa:" * 31 + "aa\nSHA256: " + "bb:" * 31 + "bb",
])
def test_invalid_certificate_fails_closed(text):
    with pytest.raises(m.SignerBlocked):
        m.parse_certificate(text)


def test_private_signer_paths_require_owner_perms(tmp_path, monkeypatch):
    d = tmp_path / "signer"
    d.mkdir(mode=0o700)
    keystore = d / "frcaixinha-aistudio-stable.p12"
    password = d / "frcaixinha-aistudio-password.txt"
    keystore.write_bytes(b"sample PKCS12 no real key")
    password.write_text("synthetic_password_no_real_secret")
    keystore.chmod(0o600)
    password.chmod(0o600)
    monkeypatch.setattr(m, "SIGNING_DIR", d)
    monkeypatch.setattr(m, "KEYSTORE", keystore)
    monkeypatch.setattr(m, "PASSWORD_FILE", password)
    m.validate_paths()
    password.chmod(0o644)
    with pytest.raises(m.SignerBlocked, match="UNSAFE_KEY_MATERIAL_PERMISSIONS"):
        m.validate_paths()


def test_check_signer_only_uses_password_in_child_env(monkeypatch, tmp_path, capsys):
    d = tmp_path / "signer"
    d.mkdir(mode=0o700)
    keystore = d / "frcaixinha-aistudio-stable.p12"
    password = d / "frcaixinha-aistudio-password.txt"
    keystore.write_bytes(b"sample PKCS12 no real key")
    password.write_text("synthetic_password_no_real_secret")
    keystore.chmod(0o600)
    password.chmod(0o600)
    monkeypatch.setattr(m, "SIGNING_DIR", d)
    monkeypatch.setattr(m, "KEYSTORE", keystore)
    monkeypatch.setattr(m, "PASSWORD_FILE", password)
    calls = []
    def run(args, **kw):
        calls.append((args, kw))
        digest = ":".join(
            m.EXPECTED_MAIN_CERT[i:i+2]
            for i in range(0, len(m.EXPECTED_MAIN_CERT), 2)
        )
        return SimpleNamespace(returncode=0, stdout="SHA256: " + digest, stderr="")
    monkeypatch.setattr(m.subprocess, "run", run)
    assert m.check_existing_signer() == m.EXPECTED_MAIN_CERT
    args, options = calls[0]
    assert "synthetic_password_no_real_secret" not in " ".join(args)
    assert "-storepass:env" in args
    assert options["env"]["FR_FINANCE_READONLY_STOREPASS"] == "synthetic_password_no_real_secret"
    assert "synthetic_password_no_real_secret" not in capsys.readouterr().out


@pytest.mark.parametrize("local_hash,expected,ret", [
    (m.EXPECTED_MAIN_CERT, "PASS_SIGNER_MATCH_READ_ONLY", 0),
    ("f" * 64, "BLOCKED_CERTIFICATE_MISMATCH", 2),
])
def test_main_fail_closed(monkeypatch, capsys, local_hash, expected, ret):
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "check_existing_signer", lambda: local_hash)
    assert m.main() == ret
    out = capsys.readouterr().out
    assert "M39064_STATUS=" + expected in out
    assert "M39064_NEW_KEY_GENERATED=NO" in out
    assert "M39064_KEYSTORE_MODIFIED=NO" in out
    assert "M39064_PASSWORD_DISPLAYED=NO" in out


def test_source_never_generates_or_exports_private_signing_material():
    source = (Path(__file__).resolve().parents[1] /
              "scripts/frfinance_m39064_installed_apk_signer_readonly.py").read_text()
    assert "verify_original()" in source
    assert '"-storepass:env"' in source
    assert "capture_output=True" in source
    for prohibited in (
        "keytool -genkeypair", "github secret set", "gh secret set",
        "base64.b64encode(", "os.system(", "os.kill(", "print(password)",
        "print(environment)", "print(result.stdout)", "shutil.copy",
        '"assembleDebug"', "ALTER ROLE", "CREATE DATABASE",
    ):
        assert prohibited not in source
