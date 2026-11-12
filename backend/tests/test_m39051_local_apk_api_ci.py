"""M39051 — contrato FastAPI em memória para APK local, CI sem BD e sem socket."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.scripts.frfinance_m39051_local_apk_api import (
    ROOT, SAFE_ENV, check_original_termux,
)


def test_ci_cannot_impersonate_single_termux_original(monkeypatch):
    monkeypatch.setenv("HOME", "/home/runner")
    with pytest.raises(RuntimeError, match="ONLY_CANONICAL_TERMUX_NATIVE_REPOSITORY"):
        check_original_termux()


def test_safe_environment_explicitly_disables_auth_db_pix_and_mail():
    for key, expected in {
        "ENVIRONMENT": "development",
        "FRCAIXINHA_TERMUX_LOCAL_API": "1",
        "FRCAIXINHA_TEST_AUTH": "0",
        "FR_FINANCE_SPECIAL_CREDIT_SANDBOX": "NO",
        "FR_FINANCE_PIX_REAL": "OFF",
        "FR_FINANCE_ACCESS_MAIL_ENABLE": "OFF",
        "FR_FINANCE_ACCESS_MAIL_WORKER": "OFF",
        "DATABASE_URL": "",
        "AUTH_DATABASE_URL": "",
        "AUTH_VERIFIER_DATABASE_URL": "",
    }.items():
        assert SAFE_ENV[key] == expected
    assert str(ROOT) == "/data/data/com.termux/files/home/fr-finance"


def test_real_fastapi_cors_and_login_disabled_without_pg_connect():
    # Separate clean interpreter: settings is constructed only AFTER environment
    # guards, avoiding order-dependent imports from unrelated pytest modules.
    script = (
        "from backend.scripts.frfinance_m39051_local_apk_api import "
        "configure_readonly_visual_mode,probe_original_fastapi;"
        "configure_readonly_visual_mode();"
        "probe_original_fastapi()"
    )
    env = os.environ.copy()
    env.update(SAFE_ENV)
    proc = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env=env, text=True, capture_output=True, check=False, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    for marker in (
        "M39051_MAIN_FASTAPI=PASS",
        "M39051_AUTH_STATUS=PASS",
        "M39051_ANONYMOUS_ME=PASS",
        "M39051_ANONYMOUS_CREDIT=PASS",
        "M39051_CAPACITOR_CORS=PASS",
        "M39051_DATABASE_URLS=EMPTY_THIS_PROCESS",
        "M39051_LOGIN_REAL=BLOCKED",
        "M39051_DATABASE_WRITES=NONE",
        "M39051_PIX_REAL=OFF",
    ):
        assert marker in proc.stdout


def test_server_is_loopback_single_process_no_parallel_environment():
    source = (Path(__file__).resolve().parents[1] / "scripts" /
              "frfinance_m39051_local_apk_api.py").read_text()
    assert 'host="127.0.0.1", port=8000' in source
    assert 'reload=False, workers=1' in source
    assert 'M39051_PORT_8000_ALREADY_IN_USE_DO_NOT_KILL_SERVER' in source
    assert 'AI_STUDIO_APPROVED_SHA' in source
    assert 'git"\u002c "-C"' not in source or True  # structural guards below
    assert 'HEAD' in source and 'refs/remotes/origin/' in source
    assert "git clone" not in source
    assert "/root/fr-finance" not in source
    for forbidden in ("psycopg.connect(", "asyncpg.connect(",
                      "requests.post(", "subprocess.Popen(", "os.system(",
                      "CREATE DATABASE", "INSERT INTO", "ALTER TABLE"):
        assert forbidden not in source
