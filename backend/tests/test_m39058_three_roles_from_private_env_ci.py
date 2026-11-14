"""M39058: testes offline, sem PostgreSQL real ou segredos do Termux."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from backend.scripts import frfinance_m39058_three_roles_from_private_env as m


def dsn(role, *, port=5433, db="frcaixinha_aistudio_dev"):
    return f"postgresql://{role}:synthetic-test-only@127.0.0.1:{port}/{db}"


def patch_urls(monkeypatch, *, app=None, auth=None, verifier=None):
    monkeypatch.setattr(
        m, "read_configured_urls",
        lambda: {
            "AUTH_DATABASE_URL": auth or dsn("frc_ai_auth"),
            "AUTH_VERIFIER_DATABASE_URL": verifier or dsn("frc_ai_verifier"),
        },
    )
    monkeypatch.setattr(m, "read_app_url", lambda: app or dsn("frc_ai_app"))


def test_three_distinct_roles_on_original_target(monkeypatch):
    patch_urls(monkeypatch)
    urls = m.collect_urls()
    assert tuple(urls) == ("DATABASE_URL", "AUTH_DATABASE_URL", "AUTH_VERIFIER_DATABASE_URL")
    assert all("5433/frcaixinha_aistudio_dev" in u for u in urls.values())


@pytest.mark.parametrize("key,bad_url", [
    ("app", dsn("frc22_owner", port=5432, db="frcaixinha_2_2_dev")),
    ("auth", dsn("frc_ai_auth", port=5432)),
    ("verifier", dsn("frc_ai_verifier", db="frcaixinha_2_2_dev")),
    ("app", dsn("frc_ai_owner")),
    ("verifier", dsn("frc_ai_auth")),
])
def test_cross_role_or_cross_project_blocked(monkeypatch, key, bad_url):
    patch_urls(monkeypatch, **{key: bad_url})
    with pytest.raises(m.GuardBlocked):
        m.collect_urls()


def test_app_url_parser_one_value_only(monkeypatch, tmp_path):
    f = tmp_path / "api.env"
    f.write_text("# comment\nDATABASE_URL='postgresql://frc_ai_app:x@127.0.0.1:5433/frcaixinha_aistudio_dev'\n")
    monkeypatch.setattr(m, "ENV_PATH", f)
    assert m.read_app_url() == dsn("frc_ai_app").replace("synthetic-test-only", "x")


@pytest.mark.parametrize("line", [
    "",
    "DATABASE_URL='unterminated",
    "DATABASE_URL=one two",
    "DATABASE_URL=a\nDATABASE_URL=b",
])
def test_app_url_rejects_missing_or_invalid(monkeypatch, tmp_path, line):
    f = tmp_path / "api.env"
    f.write_text(line)
    monkeypatch.setattr(m, "ENV_PATH", f)
    with pytest.raises(m.GuardBlocked):
        m.read_app_url()


def test_main_uses_all_three_private_connections_readonly(monkeypatch, capsys):
    urls = {
        "DATABASE_URL": dsn("frc_ai_app"),
        "AUTH_DATABASE_URL": dsn("frc_ai_auth"),
        "AUTH_VERIFIER_DATABASE_URL": dsn("frc_ai_verifier"),
    }
    calls = []
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
    def connect(url, *, connect_timeout, options):
        assert "default_transaction_read_only=on" in options
        assert connect_timeout == 5
        calls.append(url)
        return Connection()
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=connect))
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "collect_urls", lambda: urls)
    monkeypatch.setattr(m, "role_connection_audit", lambda conn, role: {"role": role})
    assert m.main() == 0
    output = capsys.readouterr().out
    assert "M39058_STATUS=PASS_READ_ONLY" in output
    assert len(calls) == 3
    assert all("synthetic-test-only" not in line for line in output.splitlines())


def test_main_fails_closed_on_pg_login_rejection(monkeypatch, capsys):
    class BadPassword(Exception):
        sqlstate = "28P01"
    def connect(*args, **kwargs):
        raise BadPassword("password authentication failed; raw secret must never appear")
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=connect))
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "collect_urls", lambda: {"DATABASE_URL": dsn("frc_ai_app")})
    assert m.main() == 2
    output = capsys.readouterr().out
    assert "INVALID_PASSWORD" in output
    assert "raw secret" not in output


def test_source_does_not_write_or_print_secrets():
    source = (Path(__file__).resolve().parents[1] / "scripts" /
              "frfinance_m39058_three_roles_from_private_env.py").read_text()
    assert "read_configured_urls()" in source
    assert "role_connection_audit(conn, role)" in source
    assert "default_transaction_read_only=on" in source
    for forbidden in ("ALTER ROLE", "CREATE ROLE", "INSERT INTO", "UPDATE public.",
                      "print(urls)", "print(password)", "print(exc)", "subprocess.Popen("):
        assert forbidden not in source
