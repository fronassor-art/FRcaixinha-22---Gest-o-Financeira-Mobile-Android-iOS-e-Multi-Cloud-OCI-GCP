"""M40130 synthetic loopback TCP/HTTP safety regression tests."""
import errno
from pathlib import Path
import socket

import pytest

from backend.scripts import frfinance_m40130_loopback_tcp_health_readonly as m

HEALTH = {"app": "FR Finance", "status": "ONLINE"}


class FakeSocket:
    def __init__(self, code=0, error=None):
        self.code = code
        self.error = error
        self.timeout = None
        self.address = None
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect_ex(self, address):
        self.address = address
        if self.error is not None:
            raise self.error
        return self.code

    def close(self):
        self.closed = True


@pytest.mark.parametrize("code, label", [
    (0, "TCP_HANDSHAKE_ACCEPTED"),
    (errno.ECONNREFUSED, "TCP_CONNECTION_REFUSED"),
    (errno.ETIMEDOUT, "TCP_CONNECT_TIMEOUT"),
    (errno.EPERM, "TCP_UNREACHABLE_OR_RESTRICTED"),
    (errno.EACCES, "TCP_UNREACHABLE_OR_RESTRICTED"),
    (errno.EHOSTUNREACH, "TCP_UNREACHABLE_OR_RESTRICTED"),
    (errno.ENETUNREACH, "TCP_UNREACHABLE_OR_RESTRICTED"),
    (999, "TCP_CONNECT_UNVERIFIED"),
    (None, "TCP_NOT_ATTESTED"),
])
def test_classify_tcp(code, label):
    assert m.classify_tcp(code) == label


def test_only_ipv4_loopback_and_socket_closed():
    s = FakeSocket(errno.ECONNREFUSED)
    def factory(family, kind):
        assert (family, kind) == (socket.AF_INET, socket.SOCK_STREAM)
        return s
    assert m.tcp_probe(socket_factory=factory) == "TCP_CONNECTION_REFUSED"
    assert s.timeout == m.CONNECT_TIMEOUT_SECONDS
    assert s.address == ("127.0.0.1", 8000)
    assert s.closed


@pytest.mark.parametrize("error, label", [
    (TimeoutError(), "TCP_CONNECT_TIMEOUT"),
    (PermissionError(), "TCP_UNREACHABLE_OR_RESTRICTED"),
    (OSError(errno.ECONNREFUSED, "refused"), "TCP_CONNECTION_REFUSED"),
    (OSError(errno.EHOSTUNREACH, "unreachable"), "TCP_UNREACHABLE_OR_RESTRICTED"),
    (ValueError(), "TCP_NOT_ATTESTED"),
])
def test_fail_closed_and_always_close(error, label):
    s = FakeSocket(error=error)
    assert m.tcp_probe(socket_factory=lambda *_: s) == label
    assert s.closed


def tcp_pair(before, after):
    samples = iter((before, after))
    return lambda: next(samples)


def get_health(status=0, doc=None):
    def fetch(path):
        assert path == m.HEALTH
        return status, doc
    return fetch


@pytest.mark.parametrize("before, after, http, expected", [
    ("TCP_CONNECTION_REFUSED", "TCP_CONNECTION_REFUSED", 0,
     "BLOCKED_LOOPBACK_PORT_REFUSED_AT_TWO_SAMPLES"),
    ("TCP_CONNECT_TIMEOUT", "TCP_CONNECT_TIMEOUT", 0,
     "BLOCKED_LOOPBACK_TCP_TIMEOUT"),
    ("TCP_UNREACHABLE_OR_RESTRICTED", "TCP_UNREACHABLE_OR_RESTRICTED", 0,
     "BLOCKED_LOOPBACK_TCP_RESTRICTED_OR_UNREACHABLE"),
    ("TCP_NOT_ATTESTED", "TCP_NOT_ATTESTED", 0,
     "BLOCKED_LOOPBACK_TCP_NOT_ATTESTED"),
    ("TCP_HANDSHAKE_ACCEPTED", "TCP_HANDSHAKE_ACCEPTED", 0,
     "BLOCKED_TCP_ACCEPTS_BUT_HTTP_NO_RESPONSE"),
    ("TCP_HANDSHAKE_ACCEPTED", "TCP_HANDSHAKE_ACCEPTED", 404,
     "BLOCKED_TCP_ACCEPTS_BUT_HTTP_IDENTITY_NOT_ATTESTED"),
    ("TCP_CONNECTION_REFUSED", "TCP_HANDSHAKE_ACCEPTED", 0,
     "BLOCKED_TCP_STATE_CHANGED_BETWEEN_SAMPLES"),
])
def test_status_classifications(before, after, http, expected):
    r = m.report(tcp=tcp_pair(before, after), fetch=get_health(http))
    assert r["M40130_STATUS"] == expected
    assert r["M40130_POSTGRESQL"] == "NOT_CHECKED"
    assert r["M40130_RESTART_AUTHORIZED"] == "FALSE"
    assert r["M40130_PROCESS_OWNER"] == "NOT_ATTESTED"


def test_healthy_http_does_not_attest_owner_or_loaded_code():
    r = m.report(tcp=tcp_pair("TCP_HANDSHAKE_ACCEPTED",
                               "TCP_HANDSHAKE_ACCEPTED"),
                 fetch=get_health(200, HEALTH))
    assert r["M40130_HTTP_IDENTITY"] == "FR_FINANCE_ONLINE"
    assert r["M40130_STATUS"] == "BLOCKED_HEALTH_RESPONDS_OWNER_AND_VERSION_NOT_ATTESTED"
    assert r["M40130_LOADED_CODE"] == "NOT_ATTESTED"


def test_foreign_http_does_not_attest_identity():
    r = m.report(tcp=tcp_pair("TCP_HANDSHAKE_ACCEPTED",
                               "TCP_HANDSHAKE_ACCEPTED"),
                 fetch=get_health(200, {"app": "Other", "status": "ONLINE"}))
    assert r["M40130_HTTP_IDENTITY"] == "NOT_ATTESTED"


def test_exception_in_tcp_probe_fails_closed():
    def unavailable():
        raise OSError("private local info")
    r = m.report(tcp=unavailable, fetch=get_health(0))
    assert r["M40130_TCP_FIRST"] == "TCP_NOT_ATTESTED"
    assert r["M40130_TCP_SECOND"] == "TCP_NOT_ATTESTED"
    assert r["M40130_STATUS"] == "BLOCKED_LOOPBACK_TCP_NOT_ATTESTED"


def test_native_termux_gate(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40130_RUNTIME=NOT_ATTESTED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_source_has_no_process_control_sql_or_sensitive_output():
    src = (Path(__file__).resolve().parents[2] /
           "backend/scripts/frfinance_m40130_loopback_tcp_health_readonly.py"
          ).read_text(encoding="utf-8")
    for expected in ("M40130_FASTAPI_RESTART=NONE",
                     "M40130_DATABASE_CONNECTIONS=NONE",
                     "M40130_LOCAL_DB_WRITES=NONE",
                     "M40130_MIGRATIONS=NONE",
                     "M40130_PIX_REAL=OFF",
                     "M40130_PRODUCTION=BLOCKED"):
        assert expected in src
    for forbidden in ("os.kill(", "subprocess.run(", "subprocess.Popen(",
                      "psycopg.connect(", "asyncpg.connect(", "shell=True",
                      "pg_ctl", "uvicorn.run(", "print(http_body)",
                      "connect((\"0.0.0.0\"", "os.system("):
        assert forbidden not in src
