#!/usr/bin/env python3
"""M39059 — FastAPI existente e negação anônima no FR Finance (read-only).

NÃO inicia ou reinicia API/PG, não envia login, senha, token ou cookies.
Só GET e OPTIONS em caminhos fixos do loopback:8000; sem proxy/redirect.
O GET /api/health/ready consulta esquema/conexões, sem inserir sessões.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original

BASE = "http://127.0.0.1:8000"
CREDIT = "/api/v1/tenants/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/special-credit/capabilities"
PATHS = frozenset((
    "/api/health",
    "/api/health/ready",
    "/api/v1/auth/status",
    "/api/v1/auth/me",
    CREDIT,
))
MAX_BYTES = 4096


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def request_local(path: str, method: str = "GET") -> tuple[int, dict]:
    if path not in PATHS or method not in ("GET", "OPTIONS"):
        raise ValueError("UNAPPROVED_LOCAL_REQUEST")
    if method == "OPTIONS" and path != "/api/v1/auth/status":
        raise ValueError("UNAPPROVED_LOCAL_PREFLIGHT")
    headers = {"Accept": "application/json"}
    if method == "OPTIONS":
        headers.update({
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-requested-with",
        })
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirects(),
    )
    try:
        with opener.open(
            urllib.request.Request(
                BASE + path, headers=headers, method=method,
            ),
            timeout=4,
        ) as response:
            code = response.status
            if method == "OPTIONS":
                return code, {
                    "origin": response.headers.get("access-control-allow-origin"),
                    "credentials": response.headers.get("access-control-allow-credentials"),
                }
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Não ler corpo do erro, pois pode conter detalhes internos.
        return exc.code, {}
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return 0, {}
    if code != 200 or len(raw) > MAX_BYTES:
        return code, {}
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return code, {}
    return code, obj if isinstance(obj, dict) else {}


def probe() -> dict[str, str]:
    code, health = request_local("/api/health")
    if code != 200 or health.get("app") != "FR Finance" or health.get("status") != "ONLINE":
        return {"M39059_STATUS": "BLOCKED_FASTAPI_NOT_IDENTIFIED"}
    out = {"M39059_EXISTING_FASTAPI_8000": "FR_FINANCE_ONLINE"}
    code, auth = request_local("/api/v1/auth/status")
    if code != 200 or auth.get("requires_authentication") is not True:
        out["M39059_STATUS"] = "BLOCKED_AUTH_STATUS"
        return out
    mode = auth.get("status")
    if mode not in ("TEST_MODE", "BLOCKED_PENDING_IMPLEMENTATION", "BLOCKED_PENDING_CONFIG"):
        out["M39059_STATUS"] = "BLOCKED_AUTH_MODE_NOT_ATTESTED"
        return out
    out["M39059_AUTH_MODE"] = mode
    code, _ = request_local("/api/v1/auth/me")
    out["M39059_ANONYMOUS_ME"] = "DENIED_401" if code == 401 else "UNEXPECTED_HTTP_" + str(code)
    code, _ = request_local(CREDIT)
    out["M39059_ANONYMOUS_SPECIAL_CREDIT"] = (
        "DENIED_401" if code == 401 else "UNEXPECTED_HTTP_" + str(code)
    )
    code, cors = request_local("/api/v1/auth/status", "OPTIONS")
    out["M39059_ANDROID_CORS"] = (
        "PASS" if code == 200 and cors.get("origin") == "http://localhost"
        and cors.get("credentials") == "true" else "BLOCKED"
    )
    code, ready = request_local("/api/health/ready")
    if code == 200 and ready.get("status") == "READY_FOR_TEST_AUTH" and (
        ready.get("scope") == "LOCAL_HOMOLOGATION_ONLY"
    ):
        out["M39059_READINESS"] = "READY_FOR_TEST_AUTH"
    elif code == 503:
        out["M39059_READINESS"] = "HTTP_503_NOT_READY"
    else:
        out["M39059_READINESS"] = "NOT_ATTESTED_HTTP_" + str(code)
    guards_ok = (
        out["M39059_ANONYMOUS_ME"] == "DENIED_401"
        and out["M39059_ANONYMOUS_SPECIAL_CREDIT"] == "DENIED_401"
        and out["M39059_ANDROID_CORS"] == "PASS"
    )
    out["M39059_ACCESS_GUARDS"] = "PASS" if guards_ok else "BLOCKED"
    out["M39059_STATUS"] = (
        "PASS_LOCAL_TEST_READINESS"
        if guards_ok and out["M39059_READINESS"] == "READY_FOR_TEST_AUTH"
        and mode == "TEST_MODE"
        else "BLOCKED_API_CONFIGURATION_OR_GUARDS"
    )
    return out


def main() -> int:
    print("=== FR FINANCE M39059 — FASTAPI EXISTENTE + RBAC ANONIMO ===")
    try:
        verify_original()
    except Exception:
        print("M39059_STATUS=BLOCKED_ORIGINAL_REPO_OR_SHA")
        return 2
    result = probe()
    for key, value in result.items():
        print(f"{key}={value}")
    print("M39059_NEW_FASTAPI=NONE")
    print("M39059_REAL_LOGIN=NOT_ATTEMPTED")
    print("M39059_SESSIONS_CREATED=NONE")
    print("M39059_DATABASE_WRITES_BY_PROBE=NONE")
    print("M39059_PASSWORD_RESET=NONE")
    print("M39059_MIGRATIONS=NONE")
    print("M39059_PIX_REAL=OFF")
    print("M39059_PRODUCTION=BLOCKED")
    return 0 if result.get("M39059_STATUS") == "PASS_LOCAL_TEST_READINESS" else 2


if __name__ == "__main__":
    sys.exit(main())
