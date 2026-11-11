"""M38996: reuse existing Brevo intake in ONE private api.env without activation."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "backend/scripts/frfinance_m38996_stage_existing_mail_config.py"
spec = importlib.util.spec_from_file_location("frfinance_m38996", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

PUBLIC = {
    "APP_URL": "https://frfinance.com.br",
    "SMTP_HOST": "smtp-relay.brevo.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "ci-auth@example.invalid",
    "FR_FINANCE_EMAIL_FROM": "notificacoes@frfinance.com.br",
}
AUTH_URL = (
    "postgresql://frc_ai_auth:synthetic-ci-only-secret@"
    "127.0.0.1:5433/frcaixinha_aistudio_dev"
)
EXISTING = {"AUTH_DATABASE_URL": AUTH_URL, "FRCAIXINHA_TERMUX_LOCAL_API": "1"}


def test_original_db_url_and_inactive_worker_required():
    module._verify_original_dsn(EXISTING)
    for bad in (
        "postgresql://frc_ai_owner:secret@127.0.0.1:5433/frcaixinha_aistudio_dev",
        "postgresql://frc_ai_auth:secret@127.0.0.1:5432/frcaixinha_aistudio_dev",
        "postgresql://frc_ai_auth:secret@127.0.0.1:5433/frcaixinha_2_2_dev",
        "postgresql://frc_ai_auth:secret@localhost:5433/frcaixinha_aistudio_dev",
    ):
        with pytest.raises(module.StageBlocked):
            module._verify_original_dsn({"AUTH_DATABASE_URL": bad})
    for active in ("REVIEWED_SINGLE_DB", "EXPLICITLY_APPROVED"):
        with pytest.raises(module.StageBlocked):
            module._verify_original_dsn({**EXISTING, "FR_FINANCE_ACCESS_MAIL_ENABLE": active})


def test_public_fields_only_from_preexisting_intake_no_email():
    changes = module._changes(PUBLIC, EXISTING, include_private=False, smtp_key=None)
    assert set(changes) == set(PUBLIC)
    assert "SMTP_PASSWORD" not in changes
    assert "FR_FINANCE_ACCESS_MAIL_ENABLE" not in changes
    assert "FR_FINANCE_ACCESS_MAIL_WORKER" not in changes
    assert "AUTH_DATABASE_URL" not in changes


def test_conflicting_public_inputs_never_override_existing_config():
    with pytest.raises(module.StageBlocked) as exc:
        module._changes(PUBLIC, {**EXISTING, "SMTP_HOST": "another.example.com"},
                        include_private=False, smtp_key=None)
    assert str(exc.value) == "PUBLIC_CONFIGURATION_CONFLICT_SMTP_HOST"


def test_existing_provider_smtp_password_not_regenerated():
    existing = {
        **EXISTING, **PUBLIC,
        "SMTP_PASSWORD": "previous-provider-password",
        "FR_FINANCE_ACCESS_HMAC_KEY": "existing-strong-key-not-a-real-secret",
        "FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64": "already-preserved-not-real-key",
    }
    changes = module._changes(PUBLIC, existing, include_private=True, smtp_key=None)
    assert changes == {}


def test_private_staging_generates_one_time_secrets_only_when_absent():
    existing = {**EXISTING, **PUBLIC}
    secret = "CI-EXISTING-BREVO-KEY-ONLY-DO-NOT-LOG"
    changes = module._changes(PUBLIC, existing,
                              include_private=True, smtp_key=secret)
    assert set(changes) == set(module.SECRET_FIELDS)
    assert changes["SMTP_PASSWORD"] == secret
    assert re.fullmatch(r"[A-Za-z0-9+/=]+",
                        changes["FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64"])
    import base64
    assert len(base64.b64decode(changes["FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64"])) == 32
    assert len(changes["FR_FINANCE_ACCESS_HMAC_KEY"]) >= 48
    assert all(k not in changes for k in module.DANGEROUS_FLAGS)


@pytest.mark.parametrize("secret", [None, "", "short", "bad space key with length", "x\n"*15])
def test_invalid_smtp_secret_never_changes_env(secret):
    with pytest.raises(module.StageBlocked):
        module._changes(PUBLIC, EXISTING, include_private=True, smtp_key=secret)


def test_preview_read_only_and_stage_no_active_mail(monkeypatch):
    modified = []
    monkeypatch.setattr(module, "_guard_original", lambda: None)
    monkeypatch.setattr(module, "_load_public", lambda: dict(PUBLIC))
    monkeypatch.setattr(module, "_load_env", lambda: (["AUTH_DATABASE_URL='redacted'"], dict(EXISTING)))
    monkeypatch.setattr(module, "_save_original",
                        lambda lines, changes: modified.append(dict(changes)))
    result = module.stage(mode="public", approved=False)
    assert result["mode"] == "PREVIEW_ONLY"
    assert modified == []
    committed = module.stage(mode="public", approved=True)
    assert committed["mail_enabled"] is False
    assert committed["database_mutations"] is False
    assert committed["sql_migrations"] is False
    assert committed["real_pix"] is False
    assert len(modified) == 1
    assert set(modified[0]) == set(PUBLIC)


def test_existing_env_real_atomic_write_preserves_old_auth_url(tmp_path, monkeypatch):
    parent = tmp_path
    parent.chmod(0o700)
    original = parent / "api.env"
    original.write_text(f"AUTH_DATABASE_URL='{AUTH_URL}'\nFR_FINANCE_REAL_PIX=OFF\n")
    original.chmod(0o600)
    monkeypatch.setattr(module, "ENV", original)
    lines = original.read_text().splitlines()
    module._save_original(lines, {"APP_URL": "https://frfinance.com.br"})
    output = original.read_text()
    assert AUTH_URL in output
    assert "FR_FINANCE_REAL_PIX=OFF" in output
    assert "APP_URL=https://frfinance.com.br" in output
    assert original.stat().st_mode & 0o777 == 0o600
    assert len(list(tmp_path.iterdir())) == 1


def test_env_duplicate_and_unsafe_line_fail_closed(tmp_path, monkeypatch):
    parent = tmp_path
    parent.chmod(0o700)
    original = parent / "api.env"
    original.write_text("SMTP_USER='x@y.z'\nSMTP_USER='b@y.z'\n")
    original.chmod(0o600)
    monkeypatch.setattr(module, "ENV", original)
    with pytest.raises(module.StageBlocked):
        module._load_env()
    original.write_text("source /tmp/untrusted-env\n")
    with pytest.raises(module.StageBlocked):
        module._load_env()


def test_legacy_empty_optional_value_preserved_without_recreation(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    env = tmp_path / "api.env"
    env.write_text("AUTH_DATABASE_URL='postgresql://frc_ai_auth:x@127.0.0.1:5433/frcaixinha_aistudio_dev'\nOPTIONAL_FEATURE=\n")
    env.chmod(0o600)
    monkeypatch.setattr(module, "ENV", env)
    _lines, values = module._load_env()
    assert values["OPTIONAL_FEATURE"] == ""


def test_only_original_infrastructure_and_protected_file_may_be_used():
    source = SCRIPT.read_text()
    assert '"fr-finance"' in source
    assert "frcaixinha_aistudio_dev" in source
    assert "127.0.0.1" in source
    assert "5433" in source
    assert "frfinance-aistudio/provider-public-inputs.json" in source
    assert ".config/frcaixinha-aistudio-mobile/api.env" in source
    assert "FR_FINANCE_ACCESS_MAIL_ENABLE" in source
    for forbidden in (
        "createdb", "initdb", "CREATE DATABASE", "CREATE ROLE",
        "pg_ctl start", "smtplib", "send_message(", "uvicorn.run",
        "os.makedirs", ".mkdir(", "FR_FINANCE_ACCESS_MAIL_ENABLE=REVIEWED_SINGLE_DB",
    ):
        assert forbidden not in source
