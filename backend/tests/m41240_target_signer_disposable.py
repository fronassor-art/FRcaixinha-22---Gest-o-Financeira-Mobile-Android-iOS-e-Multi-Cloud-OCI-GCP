"""M41240 isolated target signer: disposable CI only, no database connection."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
import re
import secrets
import socket
import struct
import subprocess
import sys
from threading import Lock
from uuid import UUID

CREDENTIAL = struct.Struct("3i")
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
    return (sys.platform == "linux" and hasattr(socket, "SO_PASSCRED")
            and hasattr(socket, "SCM_CREDENTIALS")
            and all(os.environ.get(k) == v for k, v in GATE.items()))


def payload(packet: dict) -> bytes:
    if type(packet) is not dict or set(packet) != {"digest", "tenant", "pid", "vxid", "micros", "challenge"}:
        raise ValueError("M41240_INVALID_PACKET")
    digest, tenant, pid, vxid, micros = (packet[k] for k in ("digest", "tenant", "pid", "vxid", "micros"))
    challenge = packet["challenge"]
    if (type(challenge) is not str or not HEX.fullmatch(challenge)
            or type(digest) is not str or not HEX.fullmatch(digest)
            or type(tenant) is not str or str(UUID(tenant)) != tenant or UUID(tenant).int == 0
            or type(pid) is not int or not 0 < pid <= 2147483647
            or type(vxid) is not str or len(vxid) > 32 or not VXID.fullmatch(vxid)
            or type(micros) is not int or not 0 < micros < 2**63):
        raise ValueError("M41240_INVALID_PACKET")
    return f"FRF-M41270|v1|{digest}|{tenant}|{pid}|{vxid}|{micros}|{challenge}".encode("ascii")


def process_credentials(pid: int) -> tuple[int, int, int]:
    return pid, os.getuid(), os.getgid()


def receive_frame(channel: socket.socket, limit: int) -> tuple[bytes, tuple | None]:
    """Read one bounded packet and kernel credentials, never claimed JSON identity."""
    data, controls, flags, _ = channel.recvmsg(
        limit + 1, socket.CMSG_SPACE(CREDENTIAL.size),
        getattr(socket, "MSG_CMSG_CLOEXEC", 0),
    )
    credential = None
    invalid = False
    for level, kind, value in controls:
        if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS:
            if credential is not None or len(value) != CREDENTIAL.size:
                invalid = True
            else:
                credential = CREDENTIAL.unpack(value)
        else:
            invalid = True
            # Reject and close any received descriptors, including partial rights.
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                size = struct.calcsize("i")
                for (fd,) in struct.iter_unpack("i", value[:len(value) // size * size]):
                    os.close(fd)
    if invalid or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(data) > limit:
        return b"INVALID", None
    return data, credential


def worker(parent_pid: int, fd: int) -> int:
    if (not allowed() or os.getppid() != parent_pid or parent_pid <= 1
            or set(os.environ) - (set(GATE) | {"PYTHONDONTWRITEBYTECODE", "LC_CTYPE"})):
        return 2
    expected = process_credentials(parent_pid)
    with socket.socket(fileno=fd) as channel:
        if channel.family != socket.AF_UNIX or channel.getsockopt(
            socket.SOL_SOCKET, socket.SO_TYPE
        ) != socket.SOCK_SEQPACKET:
            return 2
        channel.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        key = secrets.token_bytes(32)
        channel.sendall(key.hex().encode("ascii"))
        while os.getppid() == parent_pid:
            data, credentials = receive_frame(channel, MAX_FRAME)
            if not data:
                return 0
            if credentials != expected or os.getppid() != parent_pid:
                channel.sendall(b"DENIED")
                continue
            try:
                message = payload(json.loads(data))
                response = hmac.new(key, message, sha256).hexdigest().encode("ascii")
            except (ValueError, TypeError, OverflowError):
                response = b"DENIED"
            channel.sendall(response)
    return 2


class TargetSigner:
    """Private inherited seqpacket channel; per-packet Linux process credentials."""

    def __init__(self):
        if not allowed():
            raise RuntimeError("M41240_CI_ONLY")
        self._lock = Lock()
        self._key = None
        self._channel, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            # Enable on BOTH receivers before either process sends a packet.
            self._channel.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            child.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            self._channel.settimeout(TIMEOUT)
            self._proc = subprocess.Popen(
                [sys.executable, "-B", __file__, "--worker", str(os.getpid()),
                 str(child.fileno())],
                env={**GATE, "PYTHONDONTWRITEBYTECODE": "1"},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                pass_fds=(child.fileno(),), close_fds=True,
            )
        except BaseException:
            self._channel.close()
            raise
        finally:
            child.close()
        try:
            self._key = bytes.fromhex(self._read_hex())
        except BaseException:
            self.close()
            raise

    def _read_hex(self) -> str:
        try:
            data, credentials = receive_frame(self._channel, 64)
            value = data.decode("ascii")
            if credentials != process_credentials(self._proc.pid) or not HEX.fullmatch(value):
                raise ValueError("M41250_INVALID_SIGNER_RESPONSE")
            return value
        except (OSError, ValueError):
            raise RuntimeError("M41240_SIGNER_UNAVAILABLE") from None

    def take_bootstrap_key(self) -> bytes:
        with self._lock:
            if self._key is None:
                raise RuntimeError("M41240_BOOTSTRAP_ALREADY_CONSUMED")
            value, self._key = self._key, None
            return value

    def sign(self, ticket, tenant, pid, vxid, started, *, challenge) -> str:
        if not isinstance(started, datetime) or started.utcoffset() is None:
            raise ValueError("M41240_INVALID_TIMESTAMP")
        if type(ticket) is not str or not HEX.fullmatch(ticket):
            raise ValueError("M41240_INVALID_TICKET")
        delta = started - datetime(1970, 1, 1, tzinfo=timezone.utc)
        packet = {
            "digest": sha256(ticket.encode("ascii")).hexdigest(), "tenant": str(tenant),
            "pid": pid, "vxid": vxid, "challenge": challenge,
            "micros": (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds,
        }
        payload(packet)
        frame = json.dumps(packet, separators=(",", ":")).encode("ascii")
        with self._lock:
            try:
                if self._proc.poll() is not None or self._key is not None:
                    raise RuntimeError("M41240_SIGNER_UNAVAILABLE")
                if len(frame) > MAX_FRAME or self._channel.send(frame) != len(frame):
                    raise RuntimeError("M41240_SIGNER_UNAVAILABLE")
                return self._read_hex()
            except (OSError, ValueError, RuntimeError):
                self._close()
                raise RuntimeError("M41240_SIGNER_UNAVAILABLE") from None

    def _close(self):
        self._key = None
        self._channel.close()
        try:
            self._proc.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=TIMEOUT)

    def close(self):
        with self._lock:
            self._close()


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--worker" or not all(x.isdigit() for x in sys.argv[2:]):
        raise SystemExit(2)
    raise SystemExit(worker(int(sys.argv[2]), int(sys.argv[3])))
