"""M39060 offline tests: no real HTTP, process changes, PostgreSQL, credentials."""
from pathlib import Path
import pytest

from backend.scripts import frfinance_m39060_live_vs_private_api_config as m


def test_disk_valid_but_active_api_without_database():
    assert m.diagnosis({}, {"database_configured": False},
                       {"status": "BLOCKED_PENDING_CONFIG"}) == (
        "DISK_HAS_VALID_DSNS_BUT_ACTIVE_API_DATABASE_URL_EMPTY"
    )


def test_auth_disabled_with_finance_database_active():
    assert m.diagnosis({}, {"database_configured": True},
                       {"status": "BLOCKED_PENDING_IMPLEMENTATION"}) == (
        "ACTIVE_API_AUTH_FLAGS_OR_CREDENTIALS_NOT_LOADED"
    )


def test_test_mode_not_production_evidence():
    assert m.diagnosis({}, {"database_configured": True},
                       {"status": "TEST_MODE"}) == (
        "ACTIVE_API_TEST_MODE_READY_REQUIRES_SEPARATE_READINESS"
    )


def test_flags_safe_redacted(monkeypatch, tmp_path):
    f = tmp_path / "api.env"
    f.write_text(
        "ENVIRONMENT='homologation'\n"
        "FRCAIXINHA_TEST_AUTH=1\n"
        "FRCAIXINHA_TERMUX_LOCAL_API=1\n"
        "AUTH_RATE_LIMIT_HMAC_KEY='synthetic_test_key_long_enough_123456'\n"
        "FR_FINANCE_PIX_REAL=OFF\n"
        "FR_FINANCE_ACCESS_MAIL_WORKER=OFF\n"
        "AUTH_VERIFIER_DATABASE_URL='fake_very_sensitive_password'\n"
    )
    monkeypatch.setattr(m, "ENV_PATH", f)
    statuses = m.read_flag_status()
    assert statuses["M39060_SAVED_TEST_AUTH"] == "ENABLED"
    assert statuses["M39060_SAVED_RATE_LIMIT_KEY"] == "SUFFICIENT_LENGTH"
    assert statuses["M39060_SAVED_PIX_FLAG"] == "NOT_EXPLICITLY_ENABLED"
    assert "synthetic_test" not in str(statuses)
    assert "fake_very_sensitive_password" not in str(statuses)


@pytest.mark.parametrize("content", [
    "AUTH_RATE_LIMIT_HMAC_KEY=one\nAUTH_RATE_LIMIT_HMAC_KEY=two\n",
    "ENVIRONMENT='unterminated\n",
    "FRCAIXINHA_TEST_AUTH=one two\n",
])
def test_private_flag_parser_fail_closed(monkeypatch, tmp_path, content):
    f = tmp_path / "api.env"
    f.write_text(content)
    monkeypatch.setattr(m, "ENV_PATH", f)
    with pytest.raises(m.GuardBlocked):
        m.read_flag_status()


@pytest.mark.parametrize("flags", [
    {"M39060_SAVED_TEST_AUTH": "ENABLED"},
    {"M39060_SAVED_TEST_AUTH": "NOT_ENABLED"},
])
def test_main_reports_diagnosis_without_secrets(monkeypatch, capsys, flags):
    calls = []
    def local(path):
        calls.append(path)
        if path == "/api/health":
            return 200, {
                "app": "FR Finance", "status": "ONLINE", "database_configured": False
            }
        if path == "/api/v1/auth/status":
            return 200, {
                "status": "BLOCKED_PENDING_CONFIG", "requires_authentication": True
            }
        pytest.fail("unexpected URL")
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "collect_urls", lambda: {"secret": "do-not-print"})
    monkeypatch.setattr(m, "read_flag_status", lambda: flags)
    monkeypatch.setattr(m, "request_local", local)
    assert m.main() == 0
    output = capsys.readouterr().out
    assert "M39060_ACTIVE_DATABASE_CONFIGURED=FALSE" in output
    assert "M39060_STATUS=PASS_READ_ONLY_DIAGNOSIS" in output
    assert "do-not-print" not in output
    assert calls == ["/api/health", "/api/v1/auth/status"]


def test_api_not_fr_finance_blocked(monkeypatch, capsys):
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "collect_urls", lambda: {})
    monkeypatch.setattr(m, "read_flag_status", lambda: {})
    monkeypatch.setattr(m, "request_local", lambda path: (
        (200, {"app": "FR Caixinha 2.2", "status": "ONLINE",
               "database_configured": True})
        if path == "/api/health"
        else (200, {"status": "TEST_MODE", "requires_authentication": True})
    ))
    assert m.main() == 2
    assert "BLOCKED_EXISTING_API_NOT_ATTESTED" in capsys.readouterr().out


def test_source_only_read():
    source = (Path(__file__).resolve().parents[1] /
              "scripts/frfinance_m39060_live_vs_private_api_config.py").read_text()
    assert "verify_original()" in source
    assert "collect_urls()" in source
    assert 'request_local("/api/health")' in source
    assert 'request_local("/api/v1/auth/status")' in source
    for value in ('"POST"', "ALTER ROLE ", "INSERT INTO ", "CREATE ROLE ",
                  "uvicorn.run(", "subprocess.Popen(", "print(flags)",
                  "print(health)", "Path(\"/proc", "os.system("):
        assert value not in source
