#!/usr/bin/env python3
"""M40140 — preflight the ORIGINAL FR Finance launcher; NO service control.

Inspects versioned launcher source, original PGDATA identity metadata, and the
private env FILE METADATA only (never its contents). No PG connection, SQL,
password request, uvicorn invocation, process signals, or automatic recovery.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.scripts.frfinance_m38794_project_isolation import (
    inspect_local, IsolationBlocked,
)
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40130_loopback_tcp_health_readonly import tcp_probe

LAUNCHER = ROOT / "backend/scripts/run_termux_fastapi.sh"
LEGACY_CONTROL = ROOT / "backend/scripts/aistudio_termux_api_control.py"
ENV_FILE = Path.home() / ".config/frcaixinha-aistudio-mobile/api.env"

# Exact source facts verified in repository at M40130; not authority to run it.
LAUNCHER_REQUIRED = (
    'if [[ "$root" != "$HOME/fr-finance" ]]; then',
    'PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"',
    'pg_isready -q -h 127.0.0.1 -p 5433',
    'validate_aistudio_database.py',
    'export ENVIRONMENT=homologation',
    'exec "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log',
)


def launcher_snapshot(path=LAUNCHER):
    """No shell execution; fail closed if launcher changes or is a symlink."""
    try:
        if path.is_symlink() or not path.is_file():
            return "BLOCKED_LAUNCHER_ABSENT_OR_LINK"
        if path.stat().st_size > 32768:
            return "BLOCKED_LAUNCHER_SIZE"
        source = path.read_text(encoding="utf-8")
        if all(mark in source for mark in LAUNCHER_REQUIRED):
            return "PASS_M38801_ORIGINAL_STATIC_CONTRACT"
        return "BLOCKED_LAUNCHER_CONTRACT_DRIFT"
    except (OSError, UnicodeError, ValueError):
        return "BLOCKED_LAUNCHER_NOT_READABLE"


def legacy_snapshot(path=LEGACY_CONTROL):
    """Historic control points to the former directory; never execute it."""
    try:
        if path.is_symlink() or not path.is_file():
            return "LEGACY_CONTROL_UNVERIFIED"
        if path.stat().st_size > 65536:
            return "LEGACY_CONTROL_UNVERIFIED"
        code = path.read_text(encoding="utf-8")
        if 'ROOT=Path.home()/"frcaixinha-aistudio-mobile"' in code:
            return "HISTORIC_WORKTREE_CONTROL_DO_NOT_EXECUTE"
        return "LEGACY_CONTROL_CHANGED_REVIEW_ONLY"
    except (OSError, UnicodeError, ValueError):
        return "LEGACY_CONTROL_UNVERIFIED"


def env_file_snapshot(path=ENV_FILE, uid=None):
    """Only file metadata. Never open api.env, read passwords or print a path."""
    if uid is None:
        uid = os.getuid()
    try:
        if path.parent.is_symlink() or path.is_symlink():
            return "BLOCKED_ENV_SYMLINK"
        if not path.exists():
            return "ABSENT_NO_AUTH_CONFIG_ATTESTATION"
        st = path.stat()
        if not stat.S_ISREG(st.st_mode):
            return "BLOCKED_ENV_NOT_REGULAR_FILE"
        if st.st_uid != uid or (stat.S_IMODE(st.st_mode) & 0o077):
            return "BLOCKED_ENV_OWNER_OR_PERMISSIONS"
        return "PRIVATE_FILE_PRESENT_CONTENT_NOT_READ"
    except (OSError, ValueError):
        return "BLOCKED_ENV_METADATA_UNAVAILABLE"


def local_identity(probe=inspect_local):
    """M38794 checks the original manifest, PG_VERSION and PGDATA path only."""
    try:
        report = probe(Path.home())
        if (report.get("M38794_GIT_IDENTITY") == "FR_FINANCE_AI_STUDIO"
                and report.get("M38794_PGDATA_IDENTITY") ==
                "FR_FINANCE_AI_STUDIO_PG18"
                and report.get("M38794_PGDATA_VERSION") == "18"):
            return "PASS_STATIC_FR_FINANCE_ONLY"
        return "BLOCKED_ORIGINAL_IDENTITY"
    except (IsolationBlocked, OSError, ValueError, PermissionError, TypeError):
        return "BLOCKED_ORIGINAL_IDENTITY"


def binaries(which=shutil.which):
    """Check only executable discovery, never run pg_ctl or pg_isready."""
    try:
        available = all(which(name) for name in ("pg_ctl", "pg_isready"))
    except (OSError, ValueError, TypeError):
        available = False
    return "PG_TOOLS_LOCATED_NOT_EXECUTED" if available else "PG_TOOLS_NOT_ATTESTED"


def report(identity=local_identity, launcher=launcher_snapshot,
           legacy=legacy_snapshot, env=env_file_snapshot,
           port=tcp_probe, pgtools=binaries):
    project = identity()
    versioned_launcher = launcher()
    historic = legacy()
    env_metadata = env()
    tools = pgtools()
    try:
        listener = port()
    except (OSError, ValueError, PermissionError):
        listener = "TCP_NOT_ATTESTED"
    if listener not in frozenset((
        "TCP_HANDSHAKE_ACCEPTED", "TCP_CONNECTION_REFUSED",
        "TCP_CONNECT_TIMEOUT", "TCP_UNREACHABLE_OR_RESTRICTED",
        "TCP_CONNECT_UNVERIFIED", "TCP_NOT_ATTESTED",
    )):
        listener = "TCP_NOT_ATTESTED"

    if project != "PASS_STATIC_FR_FINANCE_ONLY":
        status = "BLOCKED_PROJECT_IDENTITY"
    elif versioned_launcher != "PASS_M38801_ORIGINAL_STATIC_CONTRACT":
        status = "BLOCKED_LAUNCHER_SOURCE"
    elif env_metadata.startswith("BLOCKED_"):
        status = "BLOCKED_ENV_METADATA"
    elif listener == "TCP_HANDSHAKE_ACCEPTED":
        status = "BLOCKED_PORT_ALREADY_OCCUPIED"
    elif listener != "TCP_CONNECTION_REFUSED":
        status = "BLOCKED_PORT_NOT_STABLY_AVAILABLE"
    elif tools != "PG_TOOLS_LOCATED_NOT_EXECUTED":
        status = "BLOCKED_DEPENDENCY_DISCOVERY"
    else:
        status = "BLOCKED_LIVE_PG_AND_RUNTIME_NOT_ATTESTED_NO_START_APPROVAL"
    return {
        "M40140_FR_FINANCE_IDENTITY": project,
        "M40140_LAUNCHER": versioned_launcher,
        "M40140_HISTORIC_CONTROL": historic,
        "M40140_API_ENV_METADATA": env_metadata,
        "M40140_PG_TOOLS": tools,
        "M40140_PORT_8000": listener,
        "M40140_PG_LIVE_IDENTITY": "NOT_ATTESTED",
        "M40140_FASTAPI_OWNER": "NOT_ATTESTED",
        "M40140_LAUNCH_AUTHORIZED": "FALSE",
        "M40140_RESTART_AUTHORIZED": "FALSE",
        "M40140_STATUS": status,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="FR Finance original launcher preflight")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40140 — ORIGINAL LAUNCHER PREFLIGHT READ ONLY ===")
    if args.source_only:
        print("M40140_SOURCE_ONLY=" + launcher_snapshot())
        print("M40140_RUNTIME=NOT_ATTESTED")
        return 0 if launcher_snapshot() == "PASS_M38801_ORIGINAL_STATIC_CONTRACT" else 2
    if not native_termux():
        print("M40140_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        for key, value in report().items():
            print(key + "=" + value)
        return 2
    finally:
        print("M40140_ENV_FILE_CONTENT=NOT_READ")
        print("M40140_PID_OR_COMMAND_LINES=NOT_DISCLOSED")
        print("M40140_DB_5432=NOT_ACCESSED")
        print("M40140_DATABASE_CONNECTIONS=NONE")
        print("M40140_LOCAL_DB_WRITES=NONE")
        print("M40140_MIGRATIONS=NONE")
        print("M40140_SERVICE_START_STOP=NONE")
        print("M40140_FASTAPI_RESTART=NONE")
        print("M40140_PIX_REAL=OFF")
        print("M40140_PAGAMENTOS_REAIS=OFF")
        print("M40140_ATIVACAO_REAL=OFF")
        print("M40140_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
