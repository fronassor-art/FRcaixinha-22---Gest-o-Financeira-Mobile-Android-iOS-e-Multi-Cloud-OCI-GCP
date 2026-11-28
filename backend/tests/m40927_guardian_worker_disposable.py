#!/usr/bin/env python3
"""M40927 independent guardian worker (CI-only UNIX socket; no real services).

The child receives ONLY its own SQL guardian DSN and public Ed25519 keys,
never the original PG URL, issuer/app DSNs, or signing private keys.
The orchestrating test parent remains privileged: NOT production isolation.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import socket
import sys
from uuid import UUID

MAX_REQUEST=16384
GUARD_COLUMNS=(
    "approval_digest,session_digest,actor_id,tenant_id,operation,"
    "campaign_id,expected_revision,body_digest,expires_at"
)

def gate() -> None:
    expected={
        "GITHUB_ACTIONS":"true",
        "FRCAIXINHA_CI_ISOLATED":"1",
        "CI_M40927_GUARDIAN_ONLY":"1",
        "PIX_REAL":"OFF",
        "PAGAMENTOS_REAIS":"OFF",
        "ATIVACAO_REAL":"OFF",
    }
    if any(os.environ.get(k)!=v for k,v in expected.items()):
        raise RuntimeError("M40927_NOT_DISPOSABLE_GITHUB_GUARDIAN")
    for forbidden in (
        "CI_PROMOTIONS_DATABASE_URL","CI_M40927_ISSUER_DSN",
        "CI_M40927_APP_DSN","DATABASE_URL","PGPASSWORD",
        "POSTGRES_PASSWORD","CI_M40927_PRIVATE_KEY",
    ):
        if forbidden in os.environ:
            raise RuntimeError("M40927_GUARDIAN_MUST_NOT_HAVE_"+forbidden)
    from psycopg.conninfo import conninfo_to_dict
    dsn=os.environ.get("CI_M40927_GUARDIAN_DSN","")
    parsed=conninfo_to_dict(dsn)
    if any((
        parsed.get("host")!="127.0.0.1",
        parsed.get("port")!="55433",
        parsed.get("dbname")!="fr_m39067_disposable_ci",
        parsed.get("user")!="m40926_guardian_login",
        not parsed.get("password"),
    )):
        raise RuntimeError("M40927_GUARDIAN_DATABASE_IDENTITY_DENIED")
    if not os.environ.get("CI_M40927_PUBLIC_REGISTRY"):
        raise RuntimeError("M40927_GUARDIAN_PUBLIC_REGISTRY_MISSING")

def registry() -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
    raw=json.loads(os.environ["CI_M40927_PUBLIC_REGISTRY"])
    if not isinstance(raw,dict) or not raw:
        raise ValueError("M40927_INVALID_REGISTRY")
    keys={}
    for compound,key_b64 in raw.items():
        parts=compound.split("|")
        if len(parts)!=3 or len(parts[2])!=64:
            raise ValueError("M40927_INVALID_KEY_SCOPE")
        encoded=base64.urlsafe_b64decode(key_b64+"==")
        if len(encoded)!=32:
            raise ValueError("M40927_ONLY_PUBLIC_ED25519_KEYS")
        keys[tuple(parts)]=Ed25519PublicKey.from_public_bytes(encoded)
    return keys

def serve(socket_path: str) -> None:
    import psycopg
    from m40923_offdb_master_action_gate import (
        EphemeralApprovalGate,body_digest,
    )
    from m40925_signed_master_sql_bridge_disposable import parse_arguments

    verification=EphemeralApprovalGate(registry())
    path=os.path.abspath(socket_path)
    if not path.startswith("/tmp/") or len(path.encode())>100:
        raise RuntimeError("M40927_SOCKET_MUST_BE_EPHEMERAL")
    # The CI harness allocates a private temporary directory; no TCP listen.
    if os.path.lexists(path):
        raise RuntimeError("M40927_SOCKET_ALREADY_EXISTS")
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(path)
        os.chmod(path,0o600)
        server.listen(12)
        server.settimeout(20)
        print("M40927_GUARDIAN_WORKER_UNIX_SOCKET=READY",flush=True)
        print("M40927_GUARDIAN_HAS_NO_ROOT_ISSUER_APP_DSN=PASS",flush=True)
        print("M40927_GUARDIAN_PUBLIC_KEYS_ONLY=PASS",flush=True)
        try:
            while True:
                peer,_=server.accept()
                with peer:
                    peer.settimeout(3)
                    buff=bytearray()
                    while len(buff)<=MAX_REQUEST:
                        part=peer.recv(4096)
                        if not part:
                            break
                        buff.extend(part)
                    if len(buff)>MAX_REQUEST:
                        peer.sendall(b'{"ok":false}\n')
                        continue
                    try:
                        packet=json.loads(buff.decode("utf-8"))
                        if not isinstance(packet,dict) or set(packet)!={
                            "command","payload","signature",
                        }:
                            raise ValueError("M40927_BAD_ENVELOPE")
                        command=packet["command"]
                        body=packet["payload"]
                        signature=packet["signature"]
                        if (not isinstance(command,dict)
                            or not isinstance(body,dict)
                            or command["body_digest"]!=body_digest(body)):
                            raise ValueError("M40927_BODY_MISMATCH")
                        action=command["action"]
                        params=parse_arguments(action,body,command)
                        if not verification.authorize(
                            command,signature,
                            now=int(datetime.now(timezone.utc).timestamp())
                        ):
                            raise ValueError("M40927_ED25519_REJECTED")
                        capability=os.urandom(48)
                        raw=base64.urlsafe_b64encode(capability).decode().rstrip("=")
                        digest=sha256(raw.encode("ascii")).hexdigest()
                        with psycopg.connect(
                            os.environ["CI_M40927_GUARDIAN_DSN"],
                            autocommit=True,
                        ) as guardian:
                            guardian.execute("SET ROLE m40926_guardian_writer")
                            if action=="DRAFT":
                                fingerprint=guardian.execute(
                                    "SELECT m40924.draft_digest("
                                    "%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                    params,
                                ).fetchone()[0]
                            else:
                                fingerprint=guardian.execute(
                                    "SELECT m40924.transition_digest("
                                    "%s,%s,%s,%s)",params,
                                ).fetchone()[0]
                            guardian.execute(
                                "INSERT INTO m40926.seals ("+GUARD_COLUMNS+") "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (
                                    digest,command["session_digest"],
                                    UUID(command["actor_id"]),
                                    UUID(command["tenant_id"]),action,
                                    UUID(command["campaign_id"])
                                    if command["campaign_id"] else None,
                                    command["expected_revision"],fingerprint,
                                    datetime.fromtimestamp(
                                        command["expires_at"],timezone.utc
                                    ),
                                ),
                            )
                        peer.sendall(
                            json.dumps({"ok":True,"capability":raw},
                                       separators=(",",":")).encode()+b"\n"
                        )
                    except (ValueError,KeyError,TypeError,OverflowError,
                            UnicodeDecodeError,psycopg.Error):
                        peer.sendall(b'{"ok":false}\n')
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

def main() -> int:
    try:
        gate()
        if len(sys.argv)!=2:
            raise RuntimeError("M40927_GUARDIAN_SOCKET_REQUIRED")
        serve(sys.argv[1])
    except Exception as exc:
        print("M40927_GUARDIAN_STATUS=BLOCKED_"+type(exc).__name__,flush=True)
        return 2
    finally:
        print("M40927_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED",flush=True)
        print("M40927_GUARDIAN_REAL_PAYMENTS=OFF",flush=True)
    return 0

if __name__=="__main__":
    sys.exit(main())
