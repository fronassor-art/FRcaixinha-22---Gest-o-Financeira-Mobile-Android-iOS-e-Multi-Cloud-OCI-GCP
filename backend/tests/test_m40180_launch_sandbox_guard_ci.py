"""Synthetic-only tests for the fixed native Termux FastAPI launcher M40180."""
from pathlib import Path

import pytest

from backend.scripts.frfinance_m40180_launch_sandbox_guard import (
    LOCKED_OFF, check_flags, main,
)

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "backend/scripts/run_termux_fastapi.sh"


def test_empty_flags_are_sandbox_only():
    assert check_flags({}) is None
    assert check_flags({"ENVIRONMENT": "homologation"}) is None


@pytest.mark.parametrize("key", LOCKED_OFF)
@pytest.mark.parametrize("active", ("ON", "YES", "TRUE", "1", "reviewed_single_db"))
def test_real_or_worker_flags_block(key, active):
    assert check_flags({key: active}) == key


@pytest.mark.parametrize("val", ("OFF", "off", "FALSE", "0", "disabled", "NO"))
def test_explicit_off_flags_allowed(val):
    assert check_flags({key: val for key in LOCKED_OFF}) is None


def test_no_production():
    assert check_flags({"ENVIRONMENT": "production"}) == "ENVIRONMENT"
    assert check_flags({"ENVIRONMENT": " PRODUCTION "}) == "ENVIRONMENT"


def test_hides_credentials_and_urls(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://some-secret-value")
    monkeypatch.setenv("AUTH_DATABASE_URL", "secret-auth-credential")
    monkeypatch.setenv("PIX_REAL", "NO")
    for key in LOCKED_OFF:
        if key != "PIX_REAL":
            monkeypatch.delenv(key, raising=False)
    assert main() == 0
    captured = capsys.readouterr().out
    assert "some-secret-value" not in captured
    assert "secret-auth-credential" not in captured
    monkeypatch.setenv("PIX_REAL", "YES_SECRET_MUST_NOT_PRINT")
    assert main() == 2
    captured = capsys.readouterr().out
    assert "YES_SECRET_MUST_NOT_PRINT" not in captured


def test_guards_after_source_before_uvicorn():
    src = LAUNCHER.read_text(encoding="utf-8")
    assert src.index('source "$config_file"') < src.index(
        'frfinance_m40180_launch_sandbox_guard.py') < src.index(
        'exec "$PYTHON_BIN" -m uvicorn')
    assert 'env -i' not in src  # preserve original private identity environment
    assert 'export PIX_REAL=OFF' in src
    assert 'export PAGAMENTOS_REAIS=OFF' in src
    assert 'export ATIVACAO_REAL=OFF' in src
    assert 'export FR_FINANCE_ACCESS_MAIL_ENABLE=OFF' in src
    assert 'export FR_FINANCE_ACCESS_MAIL_WORKER=OFF' in src
    assert 'result == errno.ECONNREFUSED' in src
    assert 'BLOCKED_PORT_8000_OCCUPIED_OR_UNVERIFIED' in src
    assert 'pg_ctl -D "$PGDATA" status' in src
    assert 'pg_isready -q -h 127.0.0.1 -p 5433' in src
    assert 'validate_aistudio_database.py' in src


def test_no_restart_or_bank_mutation_in_guard():
    src = (ROOT / "backend/scripts/frfinance_m40180_launch_sandbox_guard.py"
           ).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system(", "os.kill(", "psycopg",
                      "asyncpg", "pg_ctl", "pg_resetwal", "migrate"):
        assert forbidden not in src
