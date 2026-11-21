"""FR Finance M38995: read-only public intake and private env presence, no secrets."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/frfinance_m38995_access_runtime_readonly.py"
spec = importlib.util.spec_from_file_location("frfinance_m38995", SCRIPT)
assert spec is not None and spec.loader is not None
from importlib.util import module_from_spec
m = module_from_spec(spec)
spec.loader.exec_module(m)


def test_api_env_parser_never_displays_values(monkeypatch):
    secret = "M38995_SYNTHETIC_NEVER_LOG_THIS_PASSWORD"
    content = (
        "AUTH_DATABASE_URL='postgresql://frc_ai_auth:" + secret +
        "@127.0.0.1:5433/frcaixinha_aistudio_dev'\n"
        "SMTP_PASSWORD='" + secret + "'\n"
        "export APP_URL=https://frfinance.com.br\n"
    )
    monkeypatch.setattr(m, "_protected_file", lambda _: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: content)
    result, names = m._declared(Path("/synthetic/no-real-file"))
    assert result == "READABLE_REDACTED"
    assert names == {"AUTH_DATABASE_URL", "SMTP_PASSWORD", "APP_URL"}
    assert secret not in repr(names)
    assert "frc_ai_auth" not in repr(names)


def test_original_public_intake_is_recognized_without_output(monkeypatch):
    fake = json.dumps({
        "public_inputs": {
            "APP_URL": "https://frfinance.com.br",
            "SMTP_HOST": "smtp-relay.brevo.com",
            "FR_FINANCE_EMAIL_FROM": "notificacoes@frfinance.com.br",
        }
    })
    monkeypatch.setattr(m, "_protected_file", lambda _: True)
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: fake)
    result, keys = m._public_intake(Path("/synthetic/only"))
    assert result == "READABLE_REDACTED"
    assert keys == {"APP_URL", "SMTP_HOST", "FR_FINANCE_EMAIL_FROM"}
    assert "notificacoes@" not in repr(keys)


def test_report_is_safe_and_never_sends_or_changes_services(monkeypatch, capsys):
    monkeypatch.setattr(Path, "is_dir", lambda p: True)
    monkeypatch.setattr(Path, "is_symlink", lambda p: False)
    monkeypatch.setattr(m.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        stdout=m.EXPECTED_BRANCH,
    ))
    monkeypatch.setattr(m, "_declared", lambda _:
        ("READABLE_REDACTED", {"AUTH_DATABASE_URL", "SMTP_PASSWORD"}))
    monkeypatch.setattr(m, "_public_intake", lambda _:
        ("READABLE_REDACTED", {"APP_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER",
                              "FR_FINANCE_EMAIL_FROM"}))
    monkeypatch.setattr(m, "_local_paths", lambda _unused=None:
        ("ONLINE", {"/api/v1/auth/reset-password",
                    "/api/v1/invitations/verify-email"}))
    assert m.main() == 0
    output = capsys.readouterr().out
    assert "M38995_PROJECT=ORIGINAL_FR_FINANCE_BRANCH" in output
    assert "M38995_INTAKE_APP_URL=ALREADY_REGISTERED" in output
    assert "M38995_ENV_APP_URL=ABSENT" in output
    assert "M38995_ROUTE_RESET_PASSWORD=LOADED" in output
    assert "M38995_ROUTE_VERIFY_INVITATION=LOADED" in output
    assert "M38995_SQL_MIGRATIONS=NONE" in output
    assert "M38995_SECRET_VALUES_PRINTED=NONE" in output


def test_old_api_causes_read_only_restart_hint(monkeypatch):
    monkeypatch.setattr(Path, "is_dir", lambda p: True)
    monkeypatch.setattr(Path, "is_symlink", lambda p: False)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw:
        SimpleNamespace(stdout=m.EXPECTED_BRANCH))
    monkeypatch.setattr(m, "_declared", lambda _: ("READABLE_REDACTED", set()))
    monkeypatch.setattr(m, "_public_intake", lambda _: ("READABLE_REDACTED", set()))
    monkeypatch.setattr(m, "_local_paths", lambda: ("ONLINE", set()))
    result = m.report()
    assert result["M38995_ROUTE_RESET_PASSWORD"] == "NOT_LOADED_OR_NOT_EXPOSED"
    assert result["M38995_ROUTE_VERIFY_INVITATION"] == "NOT_LOADED_OR_NOT_EXPOSED"


def test_project_identity_fails_closed(monkeypatch):
    monkeypatch.setattr(Path, "is_dir", lambda p: True)
    monkeypatch.setattr(Path, "is_symlink", lambda p: False)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw:
        SimpleNamespace(stdout="frcaixinha-2.2"))
    assert m.report() == {"M38995_PROJECT": "BLOCKED_WRONG_BRANCH_OR_WORKTREE"}


def test_no_mutation_or_external_smtp_code_in_probe():
    s = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("smtplib", "SMTP(", "CREATE DATABASE", "createdb", "initdb",
                      "pg_ctl", "os.makedirs", ".mkdir(", "Path.write_text(",
                      ".write_bytes(", "os.environ[", "curl ", "secret ="):
        assert forbidden not in s, forbidden
    assert "http://127.0.0.1:8000/openapi.json" in s
