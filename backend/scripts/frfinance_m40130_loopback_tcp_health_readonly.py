#!/usr/bin/env python3
"""M40130: classify native Termux loopback TCP and HTTP without process or DB access.

TCP connect_ex is a bounded handshake to 127.0.0.1:8000, NOT evidence of
which process owns the port or permission to start/restart any service.
"""
from __future__ import annotations

import argparse
import errno
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import classify_health
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40090_old_fastapi_diagnosis import HEALTH, fetch_json
from backend.scripts.frfinance_m40100_safe_runtime_triage import status_class
from backend.scripts.frfinance_m40120_http_health_disambiguation_readonly import guarded_get

HOST = "127.0.0.1"
PORT = 8000
CONNECT_TIMEOUT_SECONDS = 1.5
SUCCESS = frozenset((0,))
REFUSED = frozenset((errno.ECONNREFUSED,))
TIMEOUT = frozenset((errno.ETIMEDOUT,))
RESTRICTED = frozenset((errno.EACCES, errno.EPERM, errno.ENETUNREACH,
                        errno.EHOSTUNREACH))


def classify_tcp(code):
    if type(code) is not int:
        return "TCP_NOT_ATTESTED"
    if code in SUCCESS:
        return "TCP_HANDSHAKE_ACCEPTED"
    if code in REFUSED:
        return "TCP_CONNECTION_REFUSED"
    if code in TIMEOUT:
        return "TCP_CONNECT_TIMEOUT"
    if code in RESTRICTED:
        return "TCP_UNREACHABLE_OR_RESTRICTED"
    return "TCP_CONNECT_UNVERIFIED"


def tcp_probe(socket_factory=socket.socket):
    """One short IPv4 TCP handshake with exact constant loopback destination.

    No HTTP payload, binding, listening, process discovery or long-lived socket.
    """
    connection = None
    try:
        connection = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
        connection.settimeout(CONNECT_TIMEOUT_SECONDS)
        code = connection.connect_ex((HOST, PORT))
        return classify_tcp(code)
    except (socket.timeout, TimeoutError):
        return "TCP_CONNECT_TIMEOUT"
    except PermissionError:
        return "TCP_UNREACHABLE_OR_RESTRICTED"
    except OSError as exc:
        return classify_tcp(exc.errno)
    except (ValueError, TypeError):
        return "TCP_NOT_ATTESTED"
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def report(tcp=tcp_probe, fetch=fetch_json):
    """Triangulate two TCP handshakes with one HTTP health GET between them.

    All samples are point-in-time observations; a matching pair still does not
    prove process ownership, application code version or PostgreSQL identity.
    """
    try:
        before = tcp()
    except (OSError, ValueError, PermissionError, TypeError):
        before = "TCP_NOT_ATTESTED"
    http_status, http_body = guarded_get(fetch, HEALTH)
    try:
        after = tcp()
    except (OSError, ValueError, PermissionError, TypeError):
        after = "TCP_NOT_ATTESTED"

    allowed = frozenset(("TCP_HANDSHAKE_ACCEPTED", "TCP_CONNECTION_REFUSED",
                         "TCP_CONNECT_TIMEOUT", "TCP_UNREACHABLE_OR_RESTRICTED",
                         "TCP_CONNECT_UNVERIFIED", "TCP_NOT_ATTESTED"))
    if before not in allowed:
        before = "TCP_NOT_ATTESTED"
    if after not in allowed:
        after = "TCP_NOT_ATTESTED"

    health_identity = (
        "FR_FINANCE_ONLINE"
        if http_status == 200 and classify_health(http_body) == "FR_FINANCE_ONLINE"
        else "NOT_ATTESTED"
    )

    if before != after:
        state = "BLOCKED_TCP_STATE_CHANGED_BETWEEN_SAMPLES"
    elif before == "TCP_CONNECTION_REFUSED":
        state = "BLOCKED_LOOPBACK_PORT_REFUSED_AT_TWO_SAMPLES"
    elif before == "TCP_CONNECT_TIMEOUT":
        state = "BLOCKED_LOOPBACK_TCP_TIMEOUT"
    elif before == "TCP_UNREACHABLE_OR_RESTRICTED":
        state = "BLOCKED_LOOPBACK_TCP_RESTRICTED_OR_UNREACHABLE"
    elif before != "TCP_HANDSHAKE_ACCEPTED":
        state = "BLOCKED_LOOPBACK_TCP_NOT_ATTESTED"
    elif http_status == 0:
        state = "BLOCKED_TCP_ACCEPTS_BUT_HTTP_NO_RESPONSE"
    elif http_status == 200 and health_identity == "FR_FINANCE_ONLINE":
        state = "BLOCKED_HEALTH_RESPONDS_OWNER_AND_VERSION_NOT_ATTESTED"
    else:
        state = "BLOCKED_TCP_ACCEPTS_BUT_HTTP_IDENTITY_NOT_ATTESTED"

    return {
        "M40130_TCP_FIRST": before,
        "M40130_HTTP_HEALTH": status_class(http_status),
        "M40130_HTTP_IDENTITY": health_identity,
        "M40130_TCP_SECOND": after,
        "M40130_PROCESS_OWNER": "NOT_ATTESTED",
        "M40130_LOADED_CODE": "NOT_ATTESTED",
        "M40130_POSTGRESQL": "NOT_CHECKED",
        "M40130_RESTART_AUTHORIZED": "FALSE",
        "M40130_STATUS": state,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="M40130 native Termux loopback-only")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40130 — TCP / HTTP LOOPBACK READ ONLY ===")
    if args.source_only:
        print("M40130_SOURCE_ONLY=PASS")
        print("M40130_RUNTIME=NOT_ATTESTED")
        return 0
    if not native_termux():
        print("M40130_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        for key, value in report().items():
            print(key + "=" + value)
        return 2  # No result is service-control or production authorization.
    finally:
        print("M40130_SCOPE=127_0_0_1_PORT_8000_ONLY")
        print("M40130_TCP=BOUNDED_CONNECT_ONLY")
        print("M40130_HTTP=GET_ALLOWLIST_ONLY")
        print("M40130_RAW_HTTP_PROCESS_DATA=NONE_DISCLOSED")
        print("M40130_PS_LSOF_PROC=NONE")
        print("M40130_PROCESS_START_STOP_SIGNAL=NONE")
        print("M40130_FASTAPI_RESTART=NONE")
        print("M40130_DATABASE_CONNECTIONS=NONE")
        print("M40130_LOCAL_DB_WRITES=NONE")
        print("M40130_MIGRATIONS=NONE")
        print("M40130_PIX_REAL=OFF")
        print("M40130_PAGAMENTOS_REAIS=OFF")
        print("M40130_ATIVACAO_REAL=OFF")
        print("M40130_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
