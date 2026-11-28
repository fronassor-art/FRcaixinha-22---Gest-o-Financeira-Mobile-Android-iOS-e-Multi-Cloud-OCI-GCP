#!/usr/bin/env python3
"""FR Finance M40530 — original Termux runtime preflight, no modifications.

No SQL, secrets, migrations, service controls, remote OCI or real payments.
Live mode reuses the original project's existing fixed-target read-only checks.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
import sys

# Invoked as `python -B backend/scripts/...py` from the original worktree.
# Python otherwise sets sys.path[0] to backend/scripts, not the repo root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_PROJECT = "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18"
EXPECTED_BINARIES = "TERMUX_POSTGRES_BINARIES_PRESENT_NOT_EXECUTED"
EXPECTED_CTL = "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING"
EXPECTED_READY = "PORT_5433_ACCEPTING_UNAUTHENTICATED"
EXPECTED_API = "PASS_API_GET_ONLY_NO_DATABASE_READINESS"


def api_no_database_probe() -> dict[str, str]:
    """Only four GET endpoints proven not to open database connections.

    In particular, NEVER call /api/health/ready, which directly opens
    asyncpg connections from the running FastAPI configuration. We must
    not risk reaching the independent FR Caixinha 2.2 PostgreSQL.
    """
    from backend.scripts.frfinance_m40190_operational_readonly_checkpoint import (
        HEALTH, CHECKPOINT, MARKER, ROUTES, guarded, safe_get,
    )
    from backend.scripts.frfinance_m40080_loaded_source_readonly import (
        local_hashes, classify_marker,
    )
    from backend.app.m39700_runtime_contract import (
        classify_health, classify_checkpoint, classify_routes,
    )
    result = {"M40530_API_STATUS": "BLOCKED_API_MARKERS"}
    try:
        local = local_hashes()
        if type(local) is not dict or len(local) != 3:
            return result
        health_code, health = guarded(safe_get, HEALTH)
        if health_code != 200 or classify_health(health) != "FR_FINANCE_ONLINE":
            return result
        checkpoint_code, checkpoint = guarded(safe_get, CHECKPOINT)
        if checkpoint_code != 200 or classify_checkpoint(checkpoint) != (
                "M39700_RUNNING_CODE_LOADED"):
            return result
        marker_code, marker = guarded(safe_get, MARKER)
        if classify_marker(marker_code, marker, local) != (
                "M40080_IMPORT_SNAPSHOT_MATCHES_LOCAL_FILES"):
            return result
        routes_code, routes = guarded(safe_get, ROUTES)
        if routes_code != 200:
            return result
        route_state, missing = classify_routes(routes)
        if route_state != "GET_ROUTES_PRESENT" or missing:
            return result
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return result
    return {"M40530_API_STATUS": "PASS_API_GET_ONLY_NO_DATABASE_READINESS"}


def assess(
    project: Callable[[], str],
    binaries: Callable[[], str],
    ctl_status: Callable[[], str],
    pg_ready: Callable[[], str],
    api_report: Callable[[], dict],
) -> dict[str, str]:
    """Fail closed; no probe if the original FR Finance identity fails."""
    out = {
        "M40530_PROJECT": "NOT_ATTESTED",
        "M40530_PG_CTL": "SKIPPED",
        "M40530_PG_5433": "SKIPPED",
        "M40530_API": "SKIPPED",
        "M40530_DB_AUTHENTICATED_IDENTITY": "NOT_ATTESTED",
        "M40530_RUNTIME_GIT_SHA": "NOT_ATTESTED",
        "M40530_REAL_FINANCE": "OFF",
        "M40530_PRODUCTION": "BLOCKED",
    }
    try:
        p = project()
    except Exception:
        p = "BLOCKED_PROJECT_EXCEPTION"
    out["M40530_PROJECT"] = p if p == EXPECTED_PROJECT else "BLOCKED_ORIGINAL_PROJECT_IDENTITY"
    if p != EXPECTED_PROJECT:
        out["M40530_STATUS"] = "BLOCKED_PROJECT_ISOLATION"
        return out
    try:
        b = binaries()
    except Exception:
        b = "BLOCKED_BINARY_EXCEPTION"
    if b != EXPECTED_BINARIES:
        out["M40530_STATUS"] = "BLOCKED_PG_BINARIES"
        return out
    try:
        ctl = ctl_status()
        ready = pg_ready()
    except Exception:
        out["M40530_STATUS"] = "BLOCKED_PG_STATUS_PROBE"
        return out
    out["M40530_PG_CTL"] = ctl if ctl == EXPECTED_CTL else "NOT_ATTESTED_RUNNING"
    out["M40530_PG_5433"] = ready if ready == EXPECTED_READY else "NOT_ATTESTED_READY"
    if ctl != EXPECTED_CTL or ready != EXPECTED_READY:
        out["M40530_STATUS"] = "BLOCKED_ORIGINAL_PG18_NOT_READY"
        return out
    try:
        api = api_report()
        outcome = api.get("M40530_API_STATUS") if type(api) is dict else None
    except Exception:
        outcome = None
    out["M40530_API"] = outcome if outcome == EXPECTED_API else "NOT_ATTESTED_LOCAL_API"
    out["M40530_STATUS"] = (
        "PASS_LOCAL_READONLY_NOT_PRODUCTION" if outcome == EXPECTED_API
        else "BLOCKED_API_OR_AUTH_READINESS"
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M40530 read-only original local preflight")
    parser.add_argument("--live-readonly", action="store_true",
                        help="explicitly inspect existing Termux services")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40530 — ORIGINAL LOCAL READ-ONLY PREFLIGHT ===")
    try:
        if not args.live_readonly:
            print("M40530_STATUS=PASS_SOURCE_ONLY_NOT_RUNTIME_ATTESTED")
            print("M40530_RUNTIME=NOT_ACCESSED")
            return 0
        from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
        if not native_termux():
            print("M40530_STATUS=BLOCKED_NOT_NATIVE_ORIGINAL_TERMUX")
            return 2
        from backend.scripts.frfinance_m40150_original_pg18_status_readonly import (
            identity, allowed_executables, pg_ctl_status, pg_isready_status,
        )
        result = assess(identity, allowed_executables, pg_ctl_status, pg_isready_status,
                        api_no_database_probe)
        for key, value in result.items():
            print(f"{key}={value}")
        return 0 if result["M40530_STATUS"] == "PASS_LOCAL_READONLY_NOT_PRODUCTION" else 2
    finally:
        print("M40530_PG_TARGET=FR_FINANCE_127_0_0_1_5433_ONLY")
        print("M40530_PG_5432_FR22=NOT_ACCESSED")
        print("M40530_DB_SQL=NONE")
        print("M40530_DB_WRITES=NONE")
        print("M40530_HTTP=FOUR_FIXED_GETS_ONLY_AFTER_ISOLATION")
        print("M40530_HTTP_READY_ROUTE=NEVER_CALLED")
        print("M40530_BACKEND_DB_READINESS=NOT_ACCESSED")
        print("M40530_HTTP_POST=NONE")
        print("M40530_MIGRATIONS=NONE")
        print("M40530_FASTAPI_RESTART=NONE")
        print("M40530_POSTGRESQL_RESTART=NONE")
        print("M40530_SECRETS=NOT_PRINTED")
        print("M40530_PIX_REAL=OFF")
        print("M40530_PAGAMENTOS_REAIS=OFF")
        print("M40530_ATIVACAO_REAL=OFF")
        print("M40530_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
