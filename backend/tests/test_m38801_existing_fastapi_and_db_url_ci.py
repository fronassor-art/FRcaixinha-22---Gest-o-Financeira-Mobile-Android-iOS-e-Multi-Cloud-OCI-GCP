"""M38801-38839: only original FR Finance FastAPI/PG18, prevent parallel resources."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/scripts/run_termux_fastapi.sh"
VALIDATOR = ROOT / "backend/scripts/validate_aistudio_database.py"
CLOSING = ROOT / "backend/app/routers/closings.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("m38801_url_guard", VALIDATOR)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


URLS = {
    "DATABASE_URL": "postgresql://frc_ai_app:test_only@127.0.0.1:5433/frcaixinha_aistudio_dev",
    "AUTH_DATABASE_URL": "postgresql://frc_ai_auth:test_only@127.0.0.1:5433/frcaixinha_aistudio_dev",
    "AUTH_VERIFIER_DATABASE_URL": "postgresql://frc_ai_verifier:test_only@127.0.0.1:5433/frcaixinha_aistudio_dev",
}


def set_urls(monkeypatch, urls):
    for key in URLS:
        monkeypatch.delenv(key, raising=False)
    for key, value in urls.items():
        monkeypatch.setenv(key, value)


def test_original_urls_are_allowed_without_connecting_database(monkeypatch, capsys):
    m = load_validator()
    set_urls(monkeypatch, URLS)
    assert m.check() == 0
    out = capsys.readouterr()
    assert "ISOLATED_URLS_VALIDATED" in out.out
    assert "test_only" not in out.out + out.err


def test_all_missing_urls_preserve_health_only_without_creating_db(monkeypatch, capsys):
    m = load_validator()
    set_urls(monkeypatch, {})
    assert m.check() == 0
    assert "NOT_CONFIGURED" in capsys.readouterr().out


@pytest.mark.parametrize("missing", list(URLS))
def test_partial_original_three_urls_fail_closed(monkeypatch, missing):
    m = load_validator()
    set_urls(monkeypatch, {k: v for k, v in URLS.items() if k != missing})
    assert m.check() == 2


@pytest.mark.parametrize("key", list(URLS))
@pytest.mark.parametrize("changed", [
    ("127.0.0.1:5433", "127.0.0.1:5432"),
    ("127.0.0.1:5433", "localhost:5433"),
    ("127.0.0.1:5433", "192.168.1.20:5433"),
    ("frcaixinha_aistudio_dev", "frcaixinha_2_2_dev"),
    ("postgresql://", "mysql://"),
    ("frcaixinha_aistudio_dev", "frcaixinha_aistudio_dev?options=-c%20search_path%3Dpublic"),
    ("frcaixinha_aistudio_dev", "frcaixinha_aistudio_dev?sslmode=disable"),
    ("frcaixinha_aistudio_dev", "frcaixinha_aistudio_dev#fragment"),
])
def test_wrong_port_db_remote_or_query_parameters_fail_closed(
        monkeypatch, key, changed, capsys):
    m = load_validator()
    target = URLS[key].replace(*changed)
    set_urls(monkeypatch, {**URLS, key: target})
    assert m.check() == 2
    logs = capsys.readouterr()
    assert "test_only" not in logs.out + logs.err


@pytest.mark.parametrize("key", list(URLS))
def test_role_change_to_2_2_is_rejected(monkeypatch, key):
    m = load_validator()
    value = URLS[key].replace("://frc_ai_", "://frc22_")
    set_urls(monkeypatch, {**URLS, key: value})
    assert m.check() == 2


def test_shell_syntax_valid():
    check = subprocess.run(["bash", "-n", str(RUNNER)],
                           capture_output=True, text=True, timeout=5)
    assert check.returncode == 0, check.stderr


def test_runner_uses_existing_api_only_and_blocks_duplicate():
    source = RUNNER.read_text()
    assert 'if [[ "$root" != "$HOME/fr-finance" ]]' in source
    assert "frfinance_m38794_project_isolation.py" in source
    assert 'pg_ctl -D "$PGDATA" status' in source
    assert 'pg_isready -q -h 127.0.0.1 -p 5433' in source
    assert '"127.0.0.1", 8000' in source
    assert "ALREADY_OCCUPIED_DO_NOT_START_DUPLICATE" in source
    assert "backend/scripts/validate_aistudio_database.py" in source
    assert '"$PYTHON_BIN" -m uvicorn app.main:app' in source
    assert 'exec "$PYTHON_BIN" -m uvicorn app.main:app' in source
    assert "frcaixinha_aistudio_pg18" in source
    assert "frcaixinha_2_2_pg18" not in source
    assert "createdb " not in source
    assert "initdb " not in source
    assert "git clone" not in source
    assert "mkdir " not in source
    assert "pg_ctl -D \"$PGDATA\" start" not in source


def test_legacy_closing_doc_no_cross_project_claim():
    source = CLOSING.read_text(encoding="utf-8")
    assert source.startswith('"""\nFR Finance — rota legada')
    assert "FR Caixinha 2.2 é projeto independente" in source
    assert "status_code=503" in source
    assert 'detail="Fechamento indisponível' in source


def test_one_existing_db_identity_in_validator():
    validator = VALIDATOR.read_text()
    assert 'PROJECT_DB = "frcaixinha_aistudio_dev"' in validator
    assert "PROJECT_PORT = 5433" in validator
    assert 'and parsed.query == ""' in validator
    assert 'and parsed.fragment == ""' in validator
    assert "frcaixinha_2_2_dev" not in validator
    assert "CREATE DATABASE" not in validator
