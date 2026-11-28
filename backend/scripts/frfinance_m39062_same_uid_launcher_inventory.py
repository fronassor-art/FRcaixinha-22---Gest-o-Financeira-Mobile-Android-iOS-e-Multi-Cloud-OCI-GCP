#!/usr/bin/env python3
"""FR Finance M39062 — inventario de candidatos FastAPI sem /proc/net/tcp.

Inspeciona apenas processos do mesmo UID Termux para detectar comandos
reconhecidos de inicializacao; sem PID, argumentos ou segredos em saidas.
NAO associa o processo ao socket 8000, NAO mata/inicia/reinicia servicos.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39059_existing_fastapi_anonymous_readonly import request_local
from backend.scripts.frfinance_m39061_existing_fastapi_process_origin import process_class

PROC_DIR = Path("/proc")
MAX_ENTRIES = 16384
MAX_CMDLINE_BYTES = 8192
CANDIDATES = frozenset(("M39051_VISUAL_APK", "UVICORN_DIRECT_OR_LAUNCHER"))


def classify_raw_command(raw: bytes) -> str | None:
    if not raw or len(raw) > MAX_CMDLINE_BYTES:
        return None
    argv = [
        value.decode("utf-8", errors="replace")
        for value in raw.split(bytes((0,))) if value
    ]
    label = process_class(argv)
    return label if label in CANDIDATES else None


def scan_same_uid_candidates(root: Path = PROC_DIR) -> tuple[list[str], str]:
    """READ ONLY. Nunca retorna PID, linha de comando, caminho ou ambiente."""
    candidates: list[str] = []
    permitted = 0
    same_uid_count = 0
    try:
        with os.scandir(root) as it:
            entries = []
            for i, entry in enumerate(it):
                if i >= MAX_ENTRIES:
                    return [], "PROC_LIST_LIMIT_REACHED"
                if entry.name.isdecimal():
                    entries.append(entry.name)
    except OSError:
        return [], "ANDROID_PROC_LIST_RESTRICTED"

    uid = os.getuid()
    for name in entries:
        directory = root / name
        try:
            if directory.stat().st_uid != uid:
                continue
            same_uid_count += 1
            with (directory / "cmdline").open("rb") as stream:
                raw = stream.read(MAX_CMDLINE_BYTES + 1)
            permitted += 1
            # The scanner itself is not a possible API launcher.
            if int(name) == os.getpid():
                continue
            label = classify_raw_command(raw)
            if label:
                candidates.append(label)
        except (OSError, ValueError):
            continue
    if not same_uid_count or permitted == 0:
        return [], "ANDROID_PROC_COMMANDS_RESTRICTED"
    return candidates, "SAME_UID_COMMANDS_SCANNED"


def summarize_candidates(candidates: list[str]) -> tuple[str, str]:
    if len(candidates) == 1:
        return candidates[0], "UNIQUE_MATCHED_PROCESS_NOT_SOCKET_ATTESTED"
    if len(candidates) > 1:
        return "MULTIPLE_LAUNCHER_CANDIDATES", "REQUIRES_MANUAL_SUPERVISOR_REVIEW"
    return "NONE_IDENTIFIED", "REQUIRES_MANUAL_SUPERVISOR_REVIEW"


def probe() -> dict[str, str]:
    code, health = request_local("/api/health")
    if code != 200 or health.get("app") != "FR Finance" or (
        health.get("status") != "ONLINE"
    ):
        return {"M39062_STATUS": "BLOCKED_ACTIVE_API_NOT_FR_FINANCE"}
    candidates, scan = scan_same_uid_candidates()
    origin, confidence = summarize_candidates(candidates)
    return {
        "M39062_ACTIVE_FASTAPI": "FR_FINANCE_ONLINE_8000",
        "M39062_PROCESS_INVENTORY": scan,
        "M39062_CANDIDATE_CLASS": origin,
        "M39062_CLASSIFICATION": confidence,
        "M39062_SOCKET_OWNER_ATTESTED": "NO_ANDROID_PROC_RESTRICTION",
        "M39062_HANDOFF": "NO_AUTOMATIC_STOP_OR_RESTART",
        "M39062_STATUS": "PASS_READ_ONLY_INVENTORY",
    }


def main() -> int:
    print("=== FR FINANCE M39062 — ALTERNATIVA A PROC TCP RESTRITO ===")
    try:
        verify_original()
    except Exception:
        print("M39062_STATUS=BLOCKED_ORIGINAL_WORKTREE_OR_SHA")
        return 2
    result = probe()
    for key, value in result.items():
        print(key + "=" + value)
    print("M39062_PROCESS_ARGUMENTS_OR_PID=NOT_DISPLAYED")
    print("M39062_PROC_ENV=NOT_READ")
    print("M39062_PROCESS_START_STOP=NONE")
    print("M39062_PG18_WRITES=NONE")
    print("M39062_REAL_LOGIN_OR_SESSIONS=NONE")
    print("M39062_PIX_REAL=OFF")
    print("M39062_PRODUCTION=BLOCKED")
    return 0 if result.get("M39062_STATUS") == "PASS_READ_ONLY_INVENTORY" else 2


if __name__ == "__main__":
    sys.exit(main())
