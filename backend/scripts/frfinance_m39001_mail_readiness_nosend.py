#!/usr/bin/env python3
"""FR Finance M39001 — readiness of EXISTING PG18 / access / Brevo, NO SEND.

Only reads the existing original Termux private api.env, local FastAPI OpenAPI,
and original PG18 catalog using frc_ai_auth. Optionally HTTP GET public APP_URL
(no tokens/query). Never logs credentials, never applies SQL or enables worker.
"""
from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from frfinance_m38996_stage_existing_mail_config import (
    _guard_original, _load_env, _load_public, _verify_original_dsn,
    StageBlocked,
)
from app.access_delivery_pg18 import (
    AccessQueueBlocked, require_reviewed_config,
    verify_existing_schema, verify_existing_redemption_schema,
)
from app.config import safe_public_https_origin

ROUTES = (
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/invitations",
    "/api/v1/invitations/verify-email",
)
_OFF = ("", "OFF", "0", "NO")


def original_runtime_readonly(env: dict[str, str], public: dict[str, str]):
    if any(env.get(key) != value for key, value in public.items()):
        raise StageBlocked("EXISTING_PUBLIC_INTAKE_MISMATCH")
    if env.get("FR_FINANCE_ACCESS_MAIL_ENABLE", "OFF") not in _OFF:
        raise StageBlocked("ACCESS_DELIVERY_ALREADY_ENABLED")
    if env.get("FR_FINANCE_ACCESS_MAIL_WORKER", "OFF") not in _OFF:
        raise StageBlocked("WORKER_ALREADY_ENABLED")
    if env.get("FR_FINANCE_REAL_PIX", "OFF") not in _OFF:
        raise StageBlocked("REAL_PIX_NOT_DISABLED")

    # Flags are set IN MEMORY to exercise the configuration parser only.
    # No changes to file, running API, worker, system environment or DB.
    proof = dict(env)
    proof.update({
        "ENVIRONMENT": "homologation",
        "FRCAIXINHA_TERMUX_LOCAL_API": "1",
        "FR_FINANCE_ACCESS_MAIL_ENABLE": "REVIEWED_SINGLE_DB",
        "FR_FINANCE_OUTBOX_047_VERIFIED": "YES",
        "FR_FINANCE_SMTP_OPERATOR_APPROVED": "YES",
    })
    return require_reviewed_config(proof)


async def original_db_readonly(config) -> None:
    await verify_existing_schema(config)
    await verify_existing_redemption_schema(config)


def check_original_api_routes() -> str:
    try:
        with urlopen("http://127.0.0.1:8000/openapi.json", timeout=4) as res:
            if res.status != 200:
                return "API_NOT_ATTESTED"
            data = json.load(res)
        paths = data.get("paths", {}) if type(data) is dict else {}
        if type(paths) is not dict:
            return "API_NOT_ATTESTED"
        for route in ROUTES:
            methods = paths.get(route, {})
            if type(methods) is not dict or "post" not in methods:
                return "ACCESS_ROUTES_NOT_ALL_LOADED"
        return "ACCESS_ROUTES_LOADED_NOT_ENABLED"
    except (OSError, ValueError, TimeoutError):
        return "API_NOT_ATTESTED"


def check_public_html(origin: str) -> str:
    """A generic 200 does not prove HTTPS site is the FR Finance frontend."""
    if safe_public_https_origin(origin) != origin:
        return "APP_URL_NOT_PUBLIC_ORIGIN"
    try:
        req = Request(origin, headers={"User-Agent": "FRFinance-M39001-Readiness/1"})
        with urlopen(req, timeout=8) as res:
            final = urlsplit(res.geturl())
            original = urlsplit(origin)
            if (res.status != 200 or final.scheme != "https"
                    or final.hostname != original.hostname
                    or final.port not in (None, 443)
                    or final.username or final.password):
                return "HTTPS_NOT_ATTESTED"
            sample = res.read(32768).decode("utf-8", "ignore")
            return ("FR_FINANCE_HTML_OBSERVED_NOT_DEPLOYMENT_ATTESTED"
                    if "FR Finance" in sample
                    else "HTTPS_RESPONDED_APP_UNVERIFIED")
    except (OSError, ValueError, TimeoutError):
        return "HTTPS_UNREACHABLE_OR_UNVERIFIED"


def main() -> int:
    print("=== FR FINANCE M39001 — NO-SEND READINESS ===")
    try:
        _guard_original()
        _, env = _load_env()
        _verify_original_dsn(env)
        public = _load_public()
        config = original_runtime_readonly(env, public)
        print("M39001_ORIGINAL_CONFIG=PASS")
        asyncio.run(original_db_readonly(config))
        print("M39001_ORIGINAL_PG18_047_048=PASS")
        print("M39001_ORIGINAL_FASTAPI="+check_original_api_routes())
        print("M39001_PUBLIC_HTTPS="+check_public_html(config.smtp.app_origin))
        print("M39001_SMTP_SYNTAX=PASS_NOT_PROVIDER_DELIVERY_PROOF")
    except (StageBlocked, AccessQueueBlocked) as exc:
        print("M39001_BLOCKED="+str(exc))
        return 2
    except (OSError, ValueError, RuntimeError, TypeError):
        # No exception repr: a malformed DSN can contain credentials.
        print("M39001_BLOCKED=LOCAL_READONLY_ATTESTATION_FAILED")
        return 2
    finally:
        print("M39001_SQL_MIGRATIONS=NONE")
        print("M39001_DATABASE_MUTATIONS=NONE")
        print("M39001_SMTP_CONNECTIONS=NONE")
        print("M39001_SMTP_MESSAGES=NONE")
        print("M39001_WORKER_ACTIVATIONS=NONE")
        print("M39001_USER_ACTIVATIONS=NONE")
        print("M39001_PIX_REAL=OFF_UNCHANGED")
        print("M39001_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
