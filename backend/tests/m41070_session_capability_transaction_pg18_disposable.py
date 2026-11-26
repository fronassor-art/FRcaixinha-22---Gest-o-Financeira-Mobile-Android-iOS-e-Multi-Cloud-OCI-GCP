#!/usr/bin/env python3
"""M41070: prove SET LOCAL capability restoration in disposable PostgreSQL 18."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
sys.path.insert(0, str(APP))
from m41050_session_context_seal_prototype import (
    InvalidSessionCapability,
    install_session_capability,
)

DATABASE = "fr_m41070_disposable_ci"
PORT = 55440
DATABASE_PASSWORD = "only_m41070_disposable_ci"
BASELINE = "m41070-baseline-context"
CAPABILITY = "a" * 64


def require_disposable() -> str:
    expected = {
        "GITHUB_ACTIONS": "true",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "CI_M41070_DISPOSABLE": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("M41070_DISPOSABLE_ONLY")
    if any(os.environ.get(key) for key in (
        "DATABASE_URL", "AUTH_DATABASE_URL", "AUTH_VERIFIER_DATABASE_URL",
    )):
        raise RuntimeError("M41070_UNEXPECTED_DATABASE_DSN_PRESENT")
    dsn = os.environ.get("CI_M41070_DATABASE_URL", "")
    try:
        parsed = urlsplit(dsn)
        valid = (
            parsed.scheme == "postgresql"
            and parsed.hostname == "127.0.0.1"
            and parsed.port == PORT
            and parsed.path == "/" + DATABASE
            and parsed.username == "postgres"
            and parsed.password == DATABASE_PASSWORD
            and not parsed.query
            and not parsed.fragment
        )
    except (ValueError, AttributeError, TypeError):
        valid = False
    if not valid:
        raise RuntimeError("M41070_DISPOSABLE_DATABASE_IDENTITY_DENIED")
    return dsn


async def exercise(dsn: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn, timeout=5, command_timeout=5)
    try:
        await conn.execute(
            "SELECT pg_catalog.set_config('app.session_capability', $1, false)",
            BASELINE,
        )
        if conn.is_in_transaction():
            raise AssertionError("M41070_PRETEST_TRANSACTION_UNEXPECTED")

        try:
            await install_session_capability(conn, CAPABILITY)
        except InvalidSessionCapability:
            pass
        else:
            raise AssertionError("M41070_OUTSIDE_TRANSACTION_WAS_ACCEPTED")
        if await conn.fetchval(
            "SELECT pg_catalog.current_setting('app.session_capability', true)"
        ) != BASELINE:
            raise AssertionError("M41070_OUTSIDE_TRANSACTION_CHANGED_CONTEXT")
        print("M41070_OUTSIDE_TRANSACTION_REJECTED=PASS")

        async with conn.transaction():
            await install_session_capability(conn, CAPABILITY)
            observed = await conn.fetchval(
                "SELECT pg_catalog.current_setting('app.session_capability', true)"
            )
            if observed != CAPABILITY:
                raise AssertionError("M41070_TRANSACTION_LOCAL_VALUE_MISMATCH")
        print("M41070_TRANSACTION_LOCAL_VALUE=PASS")
        if await conn.fetchval(
            "SELECT pg_catalog.current_setting('app.session_capability', true)"
        ) != BASELINE:
            raise AssertionError("M41070_COMMIT_DID_NOT_RESTORE_BASELINE")
        print("M41070_COMMIT_RESTORES_PRIOR_CONTEXT=PASS")

        class RollbackProbe(Exception):
            pass

        try:
            async with conn.transaction():
                await install_session_capability(conn, "b" * 64)
                observed = await conn.fetchval(
                    "SELECT pg_catalog.current_setting('app.session_capability', true)"
                )
                if observed != "b" * 64:
                    raise AssertionError("M41070_ROLLBACK_LOCAL_VALUE_MISMATCH")
                raise RollbackProbe
        except RollbackProbe:
            pass
        if await conn.fetchval(
            "SELECT pg_catalog.current_setting('app.session_capability', true)"
        ) != BASELINE:
            raise AssertionError("M41070_ROLLBACK_DID_NOT_RESTORE_BASELINE")
        print("M41070_ROLLBACK_RESTORES_PRIOR_CONTEXT=PASS")
    finally:
        await conn.close()


def main() -> int:
    try:
        dsn = require_disposable()
    except RuntimeError as exc:
        print("M41070_STATUS=BLOCKED_" + type(exc).__name__)
        print("M41070_DATABASE_CONNECTIONS=NONE")
        return 2

    print("M41070_TARGET=POSTGRES18_DISPOSABLE_ONLY")
    asyncio.run(exercise(dsn))
    print("M41070_STATUS=PASS_DISPOSABLE_TRANSACTION_SCOPE_ONLY")
    print("M41070_ORIGINAL_DATABASE=NOT_ACCESSED")
    print("M41070_MIGRATIONS=NONE")
    print("M41070_DATABASE_WRITES=NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
