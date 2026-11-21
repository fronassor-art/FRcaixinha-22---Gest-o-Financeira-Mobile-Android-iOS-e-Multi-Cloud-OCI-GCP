#!/usr/bin/env python3
"""FR Finance M39051 — API local para inspeção do APK debug, SOMENTE Termux.

Modo padrão --check: FastAPI in-memory, nenhuma porta / PostgreSQL / sessão.
Modo --serve: MESMO app FastAPI original em 127.0.0.1:8000; login,
crédito e mensagens DESATIVADOS. NÃO habilita usuários reais nem Pix.

Execute: AI_STUDIO_APPROVED_SHA=<commit-40hex> python -B -m \
    backend.scripts.frfinance_m39051_local_apk_api --check
Ou substitua --check por --serve para abrir a API no mesmo aparelho.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess

ROOT = Path("/data/data/com.termux/files/home/fr-finance")
BRANCH = "atualizacao-ai-studio-9b46a63187"
TENANT_DUMMY = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCAL_URL = "http://127.0.0.1:8000"

SAFE_ENV = {
    "ENVIRONMENT": "development",
    "FRCAIXINHA_TERMUX_LOCAL_API": "1",
    "FRCAIXINHA_TEST_AUTH": "0",
    "FRCAIXINHA_CI_ISOLATED": "0",
    "FR_FINANCE_SPECIAL_CREDIT_SANDBOX": "NO",
    "FR_FINANCE_PIX_REAL": "OFF",
    "FR_FINANCE_ACCESS_MAIL_ENABLE": "OFF",
    "FR_FINANCE_ACCESS_MAIL_WORKER": "OFF",
    # Explicitly erase active DSNs in THIS Python process. Never clear or
    # change credentials persisted elsewhere or touch the original PG18.
    "DATABASE_URL": "",
    "AUTH_DATABASE_URL": "",
    "AUTH_VERIFIER_DATABASE_URL": "",
}
EXPECTED_CHECKS = (
    ("M39051_MAIN_FASTAPI", "/api/health", 200),
    ("M39051_AUTH_STATUS", "/api/v1/auth/status", 200),
    ("M39051_ANONYMOUS_ME", "/api/v1/auth/me", 401),
    (
        "M39051_ANONYMOUS_CREDIT",
        f"/api/v1/tenants/{TENANT_DUMMY}/special-credit/capabilities",
        401,
    ),
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ("git", "-C", str(ROOT), *args),
        stderr=subprocess.DEVNULL,
        text=True,
    ).strip()


def check_original_termux() -> None:
    if (os.getenv("HOME") != "/data/data/com.termux/files/home"
            or Path.cwd().resolve() != ROOT
            or not (ROOT / ".git").is_dir()):
        raise RuntimeError("ONLY_CANONICAL_TERMUX_NATIVE_REPOSITORY")
    if _git("branch", "--show-current") != BRANCH:
        raise RuntimeError("ORIGINAL_BRANCH_MISMATCH")
    approved = os.getenv("AI_STUDIO_APPROVED_SHA", "")
    if len(approved) != 40 or any(c not in "0123456789abcdef" for c in approved):
        raise RuntimeError("EXPECTED_SHA_REQUIRED")
    if _git("rev-parse", "HEAD") != approved:
        raise RuntimeError("HEAD_MISMATCH")
    if _git("rev-parse", "refs/remotes/origin/" + BRANCH) != approved:
        raise RuntimeError("ORIGIN_MISMATCH")
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("LOCAL_WORKTREE_NOT_CLEAN")


def configure_readonly_visual_mode() -> None:
    for key, value in SAFE_ENV.items():
        os.environ[key] = value
    assert os.environ["DATABASE_URL"] == ""
    assert os.environ["AUTH_DATABASE_URL"] == ""
    assert os.environ["AUTH_VERIFIER_DATABASE_URL"] == ""


def probe_original_fastapi() -> None:
    """Only ASGI in memory; no TCP listener, tokens, passwords or SQL calls."""
    from fastapi.testclient import TestClient
    from backend.app.config import settings
    from backend.app.main import app

    if not (
        settings.DATABASE_URL == ""
        and "http://localhost" in settings.BACKEND_CORS_ORIGINS
        and os.getenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX") == "NO"
        and os.getenv("FRCAIXINHA_TEST_AUTH") == "0"
    ):
        raise RuntimeError("M39051_ORIGINAL_FASTAPI_FLAGS_NOT_SAFE")

    client = TestClient(app, raise_server_exceptions=True)
    for name, path, expected in EXPECTED_CHECKS:
        response = client.get(path)
        if response.status_code != expected:
            raise RuntimeError(name + "_UNEXPECTED_HTTP_" + str(response.status_code))
        if path == "/api/v1/auth/status":
            body = response.json()
            if body.get("configured") is not False or body.get("requires_authentication") is not True:
                raise RuntimeError("M39051_AUTH_STATUS_NOT_BLOCKED")
        print(name + "=PASS")

    # Capacitor with androidScheme=http initiates WebView requests at
    # Origin=http://localhost. Without this exact CORS origin the APK cannot
    # call its loopback FastAPI even when health works in curl.
    cors = client.options(
        "/api/v1/auth/status",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-requested-with",
        },
    )
    if (cors.status_code != 200
            or cors.headers.get("access-control-allow-origin") != "http://localhost"
            or cors.headers.get("access-control-allow-credentials") != "true"):
        raise RuntimeError("M39051_CAPACITOR_CORS_ORIGIN_BLOCKED")
    print("M39051_CAPACITOR_CORS=PASS")
    print("M39051_DATABASE_URLS=EMPTY_THIS_PROCESS")
    print("M39051_DATABASE_WRITES=NONE")
    print("M39051_EXTERNAL_DELIVERY=OFF")
    print("M39051_PIX_REAL=OFF")
    print("M39051_LOGIN_REAL=BLOCKED")


def _check_local_socket_available() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", 8000))
        except OSError:
            raise RuntimeError("M39051_PORT_8000_ALREADY_IN_USE_DO_NOT_KILL_SERVER") from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspecionar o APK local com API sem dados reais")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="Sonda interna sem rede nem banco")
    modes.add_argument("--serve", action="store_true", help="API original SOMENTE no loopback:8000")
    args = parser.parse_args()

    print("=== FR FINANCE M39051 — APK + FASTAPI TERMUX NATIVE ===", flush=True)
    try:
        check_original_termux()
        configure_readonly_visual_mode()
        probe_original_fastapi()
        if args.check:
            print("M39051_STATUS=PASS_CHECK_ONLY")
            return 0
        _check_local_socket_available()
        print("M39051_BIND=127.0.0.1:8000_ONLY", flush=True)
        print("M39051_SERVER=FOREGROUND_USE_CTRL_C_TO_STOP", flush=True)
        import uvicorn
        uvicorn.run(
            "backend.app.main:app", host="127.0.0.1", port=8000,
            reload=False, workers=1, log_level="warning", access_log=False,
        )
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        # No credentials or member data in errors; only expected guard markers.
        label = str(exc)
        if label.startswith("M39051_") or label.startswith("ONLY_") or label.startswith(
            ("EXPECTED_", "ORIGINAL_", "HEAD_", "ORIGIN_", "LOCAL_")
        ):
            print("M39051_REASON=" + label)
        else:
            print("M39051_REASON=PRECHECK_FAILED")
        print("M39051_STATUS=BLOCKED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
