"""Executa somente no PostgreSQL efêmero do GitHub Actions."""
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

import psycopg
import pytest
from app.security import verify_password_secure


@pytest.mark.skipif(os.getenv("FRCAIXINHA_CI_ISOLATED") != "1", reason="Somente banco isolado de CI")
def test_bootstrap_creates_one_master_and_rejects_second():
    dsn = os.environ["CI_ADMIN_DATABASE_URL"]
    parsed = urlparse(dsn)
    assert parsed.hostname in ("127.0.0.1", "localhost") and parsed.path == "/frcaixinha_ci"
    password = "senha-sintetica-ci-1234"
    secret = "segredo-sintetico-exclusivo-de-ci-123456"
    environment = os.environ.copy()
    environment.update({
        "DATABASE_URL": dsn, "CONFIRM_MASTER_PROVISIONING": "YES",
        "MASTER_BOOTSTRAP_SECRET": secret, "MASTER_EMAIL": "bootstrap-ci@example.invalid",
        "MASTER_PASSWORD": password, "MASTER_CPF": "11111111111", "MASTER_PHONE": "00000000000",
    })
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_master.py"
    first = subprocess.run([sys.executable, str(script)], env=environment, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    assert password not in first.stdout + first.stderr and secret not in first.stdout + first.stderr
    with psycopg.connect(dsn) as conn:
        row = conn.execute("SELECT c.password_hash FROM credentials c JOIN users u ON u.id=c.user_id WHERE u.email=%s", ("bootstrap-ci@example.invalid",)).fetchone()
        assert row and verify_password_secure(password, row[0])
    second = subprocess.run([sys.executable, str(script)], env=environment, capture_output=True, text=True)
    assert second.returncode == 3
    assert password not in second.stdout + second.stderr and secret not in second.stdout + second.stderr
