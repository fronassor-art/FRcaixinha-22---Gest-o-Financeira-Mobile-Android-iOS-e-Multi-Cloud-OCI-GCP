"""M40923: offline-only, ephemeral Ed25519 authorization for synthetic SaaS commands.

This module is NOT wired into real FastAPI, NOT a persistent nonce service,
NOT a production device enrollment and NOT a SQL-layer cryptographic check.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import re
from uuid import UUID

from cryptography.exceptions import InvalidSignature

FIELDS = frozenset((
    "version","method","path","actor_id","tenant_id","session_digest",
    "action","campaign_id","expected_revision","body_digest",
    "nonce","expires_at",
))
DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
PATHS = {
    "DRAFT": "/master/saas-promotions/draft",
    "PUBLISH": "/master/saas-promotions/transition",
    "CANCEL": "/master/saas-promotions/transition",
}
DOMAIN = b"FRF-M40923-MASTER-ACTION-V1\n"

def _canonical_uuid(value: object) -> bool:
    try:
        return isinstance(value,str) and str(UUID(value))==value and UUID(value).int!=0
    except (ValueError, TypeError, AttributeError):
        return False

def canonical(command: dict) -> bytes:
    if not isinstance(command,dict) or set(command)!=FIELDS:
        raise ValueError("INVALID_COMMAND_FIELDS")
    return DOMAIN+json.dumps(command,sort_keys=True,separators=(",",":"),
                             ensure_ascii=True,allow_nan=False).encode("ascii")

def sign(private_key,command: dict) -> str:
    return base64.urlsafe_b64encode(
        private_key.sign(canonical(command))
    ).decode("ascii").rstrip("=")

class EphemeralApprovalGate:
    """Server-side public-key registry and nonce set, both CI memory only."""
    def __init__(self,keys):
        self._keys=dict(keys)
        self._seen=set()

    def authorize(self, command: dict, signature: str, *, now: int) -> bool:
        try:
            data=canonical(command)
            if (command["version"]!=1 or command["method"]!="POST"
                or command["action"] not in PATHS
                or command["path"]!=PATHS[command["action"]]
                or not _canonical_uuid(command["actor_id"])
                or not _canonical_uuid(command["tenant_id"])
                or not _canonical_uuid(command["nonce"])
                or (command["campaign_id"] is not None
                    and not _canonical_uuid(command["campaign_id"]))
                or not isinstance(command["expected_revision"],int)
                or isinstance(command["expected_revision"],bool)
                or not DIGEST_PATTERN.fullmatch(command["session_digest"])
                or not DIGEST_PATTERN.fullmatch(command["body_digest"])
                or not isinstance(command["expires_at"],int)
                or isinstance(command["expires_at"],bool)
                or command["expires_at"]<=now
                or command["expires_at"]>now+20
                or (command["action"]=="DRAFT"
                    and (command["campaign_id"] is not None
                         or command["expected_revision"]!=0))
                or (command["action"]!="DRAFT"
                    and (command["campaign_id"] is None
                         or command["expected_revision"]<1))
                or not isinstance(signature,str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{86}",signature)):
                return False
            raw=base64.urlsafe_b64decode(signature+"==")
            if (len(raw)!=64
                or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")!=signature):
                return False
            scope=(command["actor_id"],command["tenant_id"],
                   command["session_digest"])
            public=self._keys.get(scope)
            if public is None or command["nonce"] in self._seen:
                return False
            public.verify(raw,data)
            self._seen.add(command["nonce"])
            return True
        except (KeyError,ValueError,TypeError,InvalidSignature,OverflowError):
            return False

def body_digest(payload: dict) -> str:
    return sha256(
        json.dumps(payload,sort_keys=True,separators=(",",":"),
                   ensure_ascii=True,allow_nan=False).encode("ascii")
    ).hexdigest()
