#!/usr/bin/env python3
"""M40929 offline Linux demonstration: SO_PEERCRED UID is not process identity.

No database, web service, provider, financial action or production credential.
This proves a *socket access boundary*, NOT a bypass of Ed25519 or SQL seals.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile


def _parent_allowed() -> bool:
    return (
        sys.platform.startswith("linux")
        and hasattr(socket, "SO_PEERCRED")
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("CI_M40929_OFFLINE") == "1"
        and all(os.environ.get(k) == "OFF" for k in (
            "PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"
        ))
    )


def _child(path: str) -> int:
    if os.environ.get("CI_M40929_CHILD") != "1":
        return 2
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(path)
        client.sendall(b"UNTRUSTED_PROCESS_SAME_UID")
        client.shutdown(socket.SHUT_WR)
        return 0 if client.recv(64) == b"SOCKET_TEST_ONLY" else 2


def _proof() -> int:
    if not _parent_allowed():
        print("M40929_CI_OFFLINE_ONLY=BLOCKED")
        return 2
    # Exclusive temporary directory is not protection against the SAME UID.
    with tempfile.TemporaryDirectory(prefix="frfinance_m40929_") as root:
        os.chmod(root, 0o700)
        path = str(Path(root) / "guardian-test.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(path)
            os.chmod(path, 0o600)
            server.listen(1)
            server.settimeout(8)
            env = {
                "PATH": os.environ.get("PATH", ""),
                "CI_M40929_CHILD": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            child = subprocess.Popen(
                [sys.executable, "-B", __file__, "--child", path, "--internal"],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                with server.accept()[0] as peer:
                    credential = peer.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
                    )
                    pid, uid, _gid = struct.unpack("3i", credential)
                    request = peer.recv(64)
                    peer.sendall(b"SOCKET_TEST_ONLY")
                    assert pid == child.pid and pid != os.getpid()
                    assert uid == os.geteuid()
                    assert request == b"UNTRUSTED_PROCESS_SAME_UID"
                assert child.wait(timeout=5) == 0
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
    print("M40929_DISTINCT_PROCESS_SAME_GATEWAY_UID=SO_PEERCRED_ACCEPTS_UID")
    print("M40929_SOCKET_MODE_0600_AND_DIR_0700=SAME_UID_CAN_CONNECT")
    print("M40929_ED25519_OR_SQL_BYPASS=NOT_TESTED")
    print("M40929_PROCESS_IDENTITY_AND_SIGNED_REQUEST_ENFORCEMENT=NOT_ATTESTED")
    print("M40929_ORIGINAL_PG18=NOT_ACCESSED")
    print("M40929_MIGRATIONS=NONE")
    print("M40929_PIX_REAL=OFF")
    print("M40929_PAGAMENTOS_REAIS=OFF")
    print("M40929_ATIVACAO_REAL=OFF")
    print("M40929_PRODUCTION=BLOCKED")
    return 0


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        return _child(sys.argv[2]) if sys.argv[3] == "--internal" else 2
    if sys.argv[1:] == ["--proof"]:
        try:
            return _proof()
        except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired):
            print("M40929_PROOF=BLOCKED_FAIL_CLOSED")
            return 2
    print("M40929_USAGE=BLOCKED_CI_PROOF_ONLY")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
