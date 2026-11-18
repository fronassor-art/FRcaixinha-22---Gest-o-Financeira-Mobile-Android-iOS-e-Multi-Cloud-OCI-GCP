#!/usr/bin/env python3
"""FR Finance M40530 — original Termux runtime preflight, no modifications.

No SQL, secrets, migrations, service controls, remote OCI or real payments.
Live mode reuses the original project's existing fixed-target read-only checks.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable

EXPECTED_PROJECT = "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18"
EXPECTED_BINARIES = "TERMUX_POSTGRES_BINARIES_PRESENT_NOT_EXECUTED"
EXPECTED_CTL = "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING"
EXPECTED_READY = "PORT_5433_ACCEPTING_UNAUTHENTICATED"
EXPECTED_API = "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"


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
        outcome = api.get("M40190_STATUS") if type(api) is dict else None
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
        from backend.scripts.frfinance_m40190_operational_readonly_checkpoint import report
        result = assess(identity, allowed_executables, pg_ctl_status, pg_isready_status, report)
        for key, value in result.items():
            print(f"{key}={value}")
        return 0 if result["M40530_STATUS"] == "PASS_LOCAL_READONLY_NOT_PRODUCTION" else 2
    finally:
        print("M40530_PG_TARGET=FR_FINANCE_127_0_0_1_5433_ONLY")
        print("M40530_PG_5432_FR22=NOT_ACCESSED")
        print("M40530_DB_SQL=NONE")
        print("M40530_DB_WRITES=NONE")
        print("M40530_HTTP=GET_FIXED_LOOPBACK_ONLY_IF_ISOLATION_PASSED")
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
