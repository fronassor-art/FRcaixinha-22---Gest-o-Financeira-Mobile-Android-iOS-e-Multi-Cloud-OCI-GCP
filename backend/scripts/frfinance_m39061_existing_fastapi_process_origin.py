#!/usr/bin/env python3
"""FR Finance M39061 — identificar origem do LISTENER FastAPI, somente leitura.

Nunca imprime cmdline completo, PID, ambiente ou argumentos de processos.
Só inspeciona o socket local 127.0.0.1:8000 e /proc do próprio UID.
Não interrompe/inicia servidores, não lê /proc/PID/environ, não grava banco.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39059_existing_fastapi_anonymous_readonly import request_local

TCP_PATH = Path("/proc/net/tcp")
PROC = Path("/proc")
LOCAL_IP_HEX = "0100007F"
LOCAL_PORT_HEX = "1F40"  # 8000
MAX_PID_COMMAND_BYTES = 8192
MAX_SOCKET_FDS = 4096


def listening_inodes(tcp_source: str) -> set[str]:
    """Inodes de sockets LISTEN em 127.0.0.1:8000, nunca porta 5432."""
    found: set[str] = set()
    for line in tcp_source.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 10 or parts[3] != "0A":
            continue
        try:
            ip, port = parts[1].split(":", 1)
        except (ValueError, IndexError):
            continue
        if ip == LOCAL_IP_HEX and port == LOCAL_PORT_HEX and parts[9].isdigit():
            found.add(parts[9])
    return found


def process_class(argv: list[str]) -> str:
    """Somente etiquetas aprovadas; argumentos jamais saem deste processo."""
    if any("frfinance_m39051_local_apk_api" in arg for arg in argv):
        return "M39051_VISUAL_APK" if "--serve" in argv else "M39051_OTHER_MODE"
    has_uvicorn = ("uvicorn" in argv or any(
        arg.endswith("/uvicorn") for arg in argv
    ))
    has_app = any(arg in ("app.main:app", "backend.app.main:app") for arg in argv)
    return "UVICORN_DIRECT_OR_LAUNCHER" if has_uvicorn and has_app else "OTHER_PROCESS"


def classify_listener(owner_class: list[str]) -> str:
    if len(owner_class) != 1:
        return "NOT_UNIQUELY_IDENTIFIED"
    return owner_class[0]


def matching_owners(inodes: set[str]) -> tuple[list[str], str]:
    if not inodes:
        return [], "SOCKET_NOT_ATTESTED"
    try:
        entries = list(PROC.iterdir())
    except OSError:
        return [], "PROC_INACCESSIBLE"
    uid = os.getuid()
    owners: list[str] = []
    for process in entries:
        if not process.name.isdecimal():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            fd_dir = process / "fd"
            n = 0
            matched = False
            for fd in fd_dir.iterdir():
                n += 1
                if n > MAX_SOCKET_FDS:
                    break
                try:
                    link = os.readlink(fd)
                except OSError:
                    continue
                if any(link == "socket:[" + inode + "]" for inode in inodes):
                    matched = True
                    break
            if not matched:
                continue
            # Read only this local same-UID process command, never environment.
            cmd = (process / "cmdline").open("rb")
            try:
                raw = cmd.read(MAX_PID_COMMAND_BYTES + 1)
            finally:
                cmd.close()
            if not raw or len(raw) > MAX_PID_COMMAND_BYTES:
                owners.append("UNCLASSIFIED_COMMAND")
                continue
            args = [a.decode("utf-8", errors="replace")
                    for a in raw.rstrip(b"\x00").split(b"\x00") if a]
            owners.append(process_class(args))
        except (OSError, PermissionError, ValueError):
            continue
    return owners, ("FOUND_SAME_UID_OWNERS" if owners
                    else "OWNER_NOT_VISIBLE_TO_TERMUX")


def probe_process_origin() -> dict[str, str]:
    health_code, health = request_local("/api/health")
    if health_code != 200 or health.get("app") != "FR Finance" or (
        health.get("status") != "ONLINE"
    ):
        return {"M39061_STATUS": "BLOCKED_EXISTING_FASTAPI_NOT_IDENTIFIED"}
    try:
        # /proc/net/tcp pode ser protegido pelo Android: bloquear conclusão.
        raw = TCP_PATH.read_text(encoding="ascii")
        inodes = listening_inodes(raw)
        owners, state = matching_owners(inodes)
    except (OSError, UnicodeError):
        owners, state = [], "ANDROID_PROC_TCP_RESTRICTED"
    result = {
        "M39061_FASTAPI_8000": "FR_FINANCE_ONLINE",
        "M39061_TCP_SOCKET_INSPECTION": state,
        "M39061_PROCESS_ORIGIN": classify_listener(owners),
    }
    result["M39061_NEXT_STEP"] = (
        "REVIEW_CONTROLLED_VISUAL_TO_AUTH_HANDOFF"
        if result["M39061_PROCESS_ORIGIN"] == "M39051_VISUAL_APK"
        else "IDENTIFY_LAUNCHER_BEFORE_ANY_RESTART"
    )
    result["M39061_STATUS"] = "PASS_READ_ONLY_PROCESS_CLASSIFICATION"
    return result


def main() -> int:
    print("=== FR FINANCE M39061 — ORIGEM FASTAPI EXISTENTE ===")
    try:
        verify_original()
    except Exception:
        print("M39061_STATUS=BLOCKED_ORIGINAL_REPOSITORY_OR_SHA")
        return 2
    result = probe_process_origin()
    for key, value in result.items():
        print(key + "=" + value)
    print("M39061_PROCESS_START_STOP=NONE")
    print("M39061_DATABASE_WRITES=NONE")
    print("M39061_DB_5432_ACCESS=NONE")
    print("M39061_PROC_ENV_READ=NONE")
    print("M39061_PID_AND_ARGUMENTS_DISPLAY=NONE")
    print("M39061_LOGIN_AND_SESSIONS=NONE")
    print("M39061_PIX_REAL=OFF")
    return 0 if result.get("M39061_STATUS") == (
        "PASS_READ_ONLY_PROCESS_CLASSIFICATION"
    ) else 2


if __name__ == "__main__":
    sys.exit(main())
