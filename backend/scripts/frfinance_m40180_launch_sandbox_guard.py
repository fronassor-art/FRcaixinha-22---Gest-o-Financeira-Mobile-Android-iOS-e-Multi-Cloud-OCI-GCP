#!/usr/bin/env python3
"""M40180: only homologation-safe flags may reach the original FastAPI.

Executed after the legacy private api.env is sourced. Reads only a fixed
allowlist of flags, never passwords, DSNs, tokens or unrelated environment.
Never starts a service or connects to any database.
"""
from __future__ import annotations

import os
import sys

OFF_VALUES = frozenset(("", "OFF", "0", "FALSE", "NO", "DISABLED"))
LOCKED_OFF = (
    "PIX_REAL",
    "PAGAMENTOS_REAIS",
    "ATIVACAO_REAL",
    "FR_FINANCE_ACCESS_MAIL_ENABLE",
    "FR_FINANCE_ACCESS_MAIL_WORKER",
    "FRCAIXINHA_CI_ISOLATED",
    "AI_STUDIO_M2040_CI_EVIDENCE_READS",
)


def check_flags(flags):
    """Return only an allowlisted *key* when unsafe; never secret data."""
    if str(flags.get("ENVIRONMENT", "")).strip().lower() == "production":
        return "ENVIRONMENT"
    for key in LOCKED_OFF:
        val = flags.get(key, "")
        if not isinstance(val, str) or val.strip().upper() not in OFF_VALUES:
            return key
    return None


def main():
    blocked = check_flags(os.environ)
    if blocked:
        print("M40180_LAUNCH_GATE=BLOCKED_" + blocked)
        return 2
    print("M40180_LAUNCH_GATE=PASS_SANDBOX_ONLY")
    print("M40180_FINANCIAL_REAL=OFF")
    print("M40180_DELIVERY_WORKER=OFF")
    print("M40180_DB_CONNECTIONS=NONE")
    print("M40180_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
