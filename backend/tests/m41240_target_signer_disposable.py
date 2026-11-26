"""M41240 isolated target signer: disposable CI only, no database connection."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
import re
import secrets
import select
import subprocess
import sys
from threading import Lock
from time import monotonic
from uuid import UUID

MAX_FRAME = 2048
TIMEOUT = 4
HEX = re.compile(r"[0-9a-f]{64}\Z")
VXID = re.compile(r"[0-9]+/[0-9]+\Z")
GATE = {
    "GITHUB_ACTIONS": "true",
    "FRCAIXINHA_CI_ISOLATED": "1",
    "CI_M41150_DISPOSABLE": "1",
    "PIX_REAL": "OFF",
    "PAGAMENTOS_REAIS": "OFF",
    "ATIVACAO_REAL": "OFF",
}


def allowed() -> bool:
    return sys.platform == "linux" and all(os.environ.get(k) == v for k, v in GATE.items())


def payload(packet: dict) -> bytes:
    if type(packet) is not dict or set(packet) != {"digest", "tenant", "pid", "vxid", "micros"}:
        raise ValueError("M41240_INVALID_PACKET")
    digest, tenant, pid, vxid, micros = (packet[k] for k in ("digest", "tenant", "pid", "vxid", "micros"))
    if (type(digest) is not str or not HEX.fullmatch(digest)
            or type(tenant) is not str or str(UUID(tenant)) != tenant or UUID(tenant).int == 0
            or type(pid) is not int or not 0 < pid <= 2147483647
            or type(vxid) is not str or len(vxid) > 32 or not VXID.fullmatch(vxid)
            or type(micros) is not int or not 0 < micros < 2**63):
        raise ValueError("M41240_INVALID_PACKET")
    return f"FRF-M41230|v1|{digest}|{tenant}|{pid}|{vxid}|{micros}".encode("ascii")


def worker(parent_pid: int) -> int:
    if (not allowed() or os.getppid() != parent_pid or parent_pid <= 1
            or set(os.environ) - (set(GATE) | {"PYTHONDONTWRITEBYTECODE", "LC_CTYPE"})):
        return 2
    key = secrets.token_bytes(32)
    # One-time bootstrap to privileged disposable SQL fixture owner.
    sys.stdout.buffer.write(key.hex().encode("ascii") + b"\n")
    sys.stdout.buffer.flush()
    while os.getppid() == parent_pid:
        line = sys.stdin.buffer.readline(MAX_FRAME + 1)
        if not line:
            return 0
        if len(line) > MAX_FRAME or not line.endswith(b"\n"):
            return 2
        try:
            message = payload(json.loads(line))
            response = hmac.new(key, message, sha256).hexdigest().encode("ascii")
        except (ValueError, TypeError, OverflowError):
            response = b"DENIED"
        sys.stdout.buffer.write(response + b"\n")
        sys.stdout.buffer.flush()
    return 2


class TargetSigner:
    """Private inherited pipes; no named socket, listener, DB DSN or bearer."""

    def __init__(self):
        if not allowed():
            raise RuntimeError("M41240_CI_ONLY")
        self._lock = Lock()
        self._key = None
        self._proc = subprocess.Popen(
            [sys.executable, "-B", __file__, "--worker", str(os.getpid())],
            env={**GATE, "PYTHONDONTWRITEBYTECODE": "1"},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=0, close_fds=True,
        )
        try:
            self._key = bytes.fromhex(self._read_hex())
        except BaseException:
            self.close()
            raise

    def _read_hex(self) -> str:
        fd = self._proc.stdout.fileno()
        deadline = monotonic() + TIMEOUT
        result = bytearray()
        while len(result) <= 64:
            left = deadline - monotonic()
            if left <= 0 or not select.select([fd], [], [], left)[0]:
                raise RuntimeError("M41240_SIGNER_UNAVAILABLE")
            part = os.read(fd, 65 - len(result))
            if not part:
                break
            result.extend(part)
            if result.endswith(b"\n"):
                break
        try:
            value = bytes(result).decode("ascii").removesuffix("\n")
        except UnicodeError:
            raise RuntimeError("M41240_SIGNER_UNAVAILABLE") from None
        if len(result) != 65 or not result.endswith(b"\n") or not HEX.fullmatch(value):
            raise RuntimeError("M41240_SIGNER_UNAVAILABLE")
        return value

    def take_bootstrap_key(self) -> bytes:
        with self._lock:
            if self._key is None:
                raise RuntimeError("M41240_BOOTSTRAP_ALREADY_CONSUMED")
            value, self._key = self._key, None
            return value

    def sign(self, ticket, tenant, pid, vxid, started) -> str:
        if not isinstance(started, datetime) or started.utcoffset() is None:
            raise ValueError("M41240_INVALID_TIMESTAMP")
        if type(ticket) is not str or not HEX.fullmatch(ticket):
            raise ValueError("M41240_INVALID_TICKET")
        delta = started - datetime(1970, 1, 1, tzinfo=timezone.utc)
        packet = {
            "digest": sha256(ticket.encode("ascii")).hexdigest(), "tenant": str(tenant),
            "pid": pid, "vxid": vxid,
            "micros": (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds,
        }
        payload(packet)
        frame = json.dumps(packet, separators=(",", ":")).encode("ascii") + b"\n"
        with self._lock:
            try:
                if self._proc.poll() is not None or self._key is not None:
                    raise RuntimeError("M41240_SIGNER_UNAVAILABLE")
                if len(frame) > MAX_FRAME or self._proc.stdin.write(frame) != len(frame):
                    raise RuntimeError("M41240_SIGNER_UNAVAILABLE")
                return self._read_hex()
            except (OSError, ValueError, RuntimeError):
                self._close()
                raise RuntimeError("M41240_SIGNER_UNAVAILABLE") from None

    def _close(self):
        self._key = None
        if self._proc.stdin and not self._proc.stdin.closed:
            self._proc.stdin.close()
        try:
            self._proc.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=TIMEOUT)
        if self._proc.stdout and not self._proc.stdout.closed:
            self._proc.stdout.close()

    def close(self):
        with self._lock:
            self._close()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--worker" or not sys.argv[2].isdigit():
        raise SystemExit(2)
    raise SystemExit(worker(int(sys.argv[2])))
