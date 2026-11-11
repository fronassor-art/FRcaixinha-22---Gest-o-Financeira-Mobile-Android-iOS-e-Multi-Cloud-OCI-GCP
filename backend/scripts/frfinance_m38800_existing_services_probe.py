#!/usr/bin/env python3
"""M38800 FR Finance: check existing PostgreSQL 18 and existing FastAPI FIRST.

Never create/start/stop PG, FastAPI, directory, database, repository or migrate.
Unauthenticated 5433 pg_isready and GET /api/health, /api/health/ready 8000.
A health response is not permission for real payments/production activation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

import frfinance_m38794_project_isolation as identity

AUTH = "AUTHORIZE_FRFINANCE_EXISTING_SERVICES_READONLY"
API_HEALTH_URL = "http://127.0.0.1:8000/api/health"
API_READY_URL = "http://127.0.0.1:8000/api/health/ready"
MAX_RESPONSE_BYTES = 4096


class ExistingServiceBlocked(Exception):
    """Safe error category only; no raw exception or credentials printed."""


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _pg_ready() -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    try:
        cp = subprocess.run(
            ["pg_isready", "-q", "-t", "3",
             "-h", "127.0.0.1", "-p", "5433",
             "-U", identity.FINANCE_OWNER, "-d", identity.FINANCE_DB],
            capture_output=True, text=True, env=env, timeout=8, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"
    return {0: "ACCEPTING", 1: "REJECTING", 2: "NO_RESPONSE"}.get(
        cp.returncode, "UNKNOWN")


def _get_local_json(url: str) -> tuple[str, dict | None]:
    if url not in (API_HEALTH_URL, API_READY_URL):
        raise ExistingServiceBlocked("UNAPPROVED_LOCAL_URL")
    # No proxy, no redirects, no credentials, no client-supplied paths.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirects())
    try:
        with opener.open(
            urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET"),
            timeout=4,
        ) as response:
            if response.status != 200:
                return "HTTP_OTHER", None
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return ("HTTP_503" if exc.code == 503 else "HTTP_OTHER"), None
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return "UNREACHABLE", None
    if len(raw) > MAX_RESPONSE_BYTES:
        return "INVALID_BODY", None
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return "INVALID_BODY", None
    if not isinstance(obj, dict):
        return "INVALID_BODY", None
    return "HTTP_200_JSON", obj


def probe() -> dict[str, str]:
    # First ensure the filesystem/worktree is this original project.
    inspected = identity.inspect_local(Path.home())
    if inspected.get("M38794_PROJECT_SEPARATION") == "BLOCKED":
        raise ExistingServiceBlocked("WRONG_PROJECT")
    pg = _pg_ready()
    api_status, api_payload = _get_local_json(API_HEALTH_URL)
    if api_status == "HTTP_200_JSON":
        if (api_payload.get("app") != "FR Finance"
                or api_payload.get("status") != "ONLINE"):
            api = "WRONG_APPLICATION_ON_8000"
        else:
            api = "ONLINE_FR_FINANCE"
    elif api_status == "UNREACHABLE":
        api = "NOT_RESPONDING"
    else:
        api = "NOT_IDENTIFIED_" + api_status
    ready = "NOT_CHECKED"
    if api == "ONLINE_FR_FINANCE" and pg == "ACCEPTING":
        ready_status, ready_payload = _get_local_json(API_READY_URL)
        if (ready_status == "HTTP_200_JSON"
                and ready_payload.get("status") == "READY_FOR_TEST_AUTH"
                and ready_payload.get("scope") == "LOCAL_HOMOLOGATION_ONLY"):
            ready = "READY_FOR_TEST_AUTH"
        elif ready_status == "HTTP_503":
            ready = "HTTP_503_NOT_READY"
        elif ready_status == "UNREACHABLE":
            ready = "NO_RESPONSE"
        else:
            ready = "NOT_ATTESTED"
    elif pg != "ACCEPTING":
        ready = "NOT_CHECKED_POSTGRES_UNAVAILABLE"
    if api == "WRONG_APPLICATION_ON_8000" or api.startswith("NOT_IDENTIFIED_"):
        next_step = "BLOCKED_VERIFY_EXISTING_API_8000"
    elif pg != "ACCEPTING":
        next_step = "CHECK_EXISTING_POSTGRES_5433_FIRST"
    elif api != "ONLINE_FR_FINANCE":
        next_step = "CHECK_EXISTING_FASTAPI_8000"
    elif ready == "READY_FOR_TEST_AUTH":
        next_step = "CONTINUE_EXISTING_FR_FINANCE_HOMOLOGATION"
    else:
        next_step = "CHECK_EXISTING_API_CONFIGURATION"
    return {
        "M38800_GIT_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38800_PG_5433": pg,
        "M38800_PG_SERVER_IDENTITY": "NOT_ATTESTED_BY_PG_ISREADY",
        "M38800_FASTAPI_8000": api,
        "M38800_FASTAPI_READY": ready,
        "M38800_NEXT_STEP": next_step,
        "M38800_PRODUCTION": "BLOCKED",
    }


def _safety() -> None:
    print("M38800_TARGET=EXISTING_FR_FINANCE_ONLY")
    print("M38800_NEW_PG_CLUSTER=NONE")
    print("M38800_NEW_DATABASE=NONE")
    print("M38800_NEW_WORKTREE=NONE")
    print("M38800_NEW_REPOSITORY=NONE")
    print("M38800_NEW_FASTAPI=NONE")
    print("M38800_PG_START_STOP=NONE")
    print("M38800_API_START_STOP=NONE")
    print("M38800_SQL_QUERIES=NONE")
    print("M38800_SQL_MIGRATIONS=NONE")
    print("M38800_FR22_ACCESS=NONE")
    print("M38800_REAL_PIX=OFF")
    print("M38800_REAL_ACTIVATION=OFF")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FR Finance existing PG/API first")
    parser.add_argument("mode", choices=("offline", "local"), nargs="?", default="offline")
    parser.add_argument("authorization", nargs="?")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M38800 EXISTING SERVICES FIRST ===")
    if args.mode == "offline":
        if args.authorization is not None:
            print("M38800_AUDIT=BLOCKED_AUTH")
            _safety()
            return 2
        try:
            identity.manifest()
        except identity.IsolationBlocked:
            print("M38800_AUDIT=BLOCKED_MANIFEST")
            _safety()
            return 2
        print("M38800_AUDIT=OFFLINE_ONLY")
        print("M38800_PG_5433=NOT_QUERIED")
        print("M38800_FASTAPI_8000=NOT_QUERIED")
        _safety()
        return 0
    if args.authorization != AUTH:
        print("M38800_AUDIT=BLOCKED_AUTH")
        _safety()
        return 2
    try:
        result = probe()
    except (identity.IsolationBlocked, ExistingServiceBlocked):
        print("M38800_AUDIT=BLOCKED_ISOLATION")
        _safety()
        return 2
    except Exception:
        print("M38800_AUDIT=BLOCKED_UNCLASSIFIED")
        _safety()
        return 2
    print("M38800_AUDIT=LOCAL_READONLY")
    for key, value in result.items():
        print(key + "=" + value)
    _safety()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
