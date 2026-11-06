"""M23300: OCI-staging OAuth state adapter (disabled by default).

Only accepts an injected, dedicated PostgreSQL worker connection and an
injected ephemeral Vault verifier service. No OCI or DB creation here.
A real deployment still needs a server-authenticated seller registry, durable
Vault implementation, HTTPS callback and complete end-to-end review.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import hmac
import re
from typing import Any,Protocol
from uuid import UUID

from .mp_oauth_connect_preflight import OAuthDraft
from .mp_oauth_sandbox_coordinator import SandboxConnectBlocked

_OCID=re.compile(r"ocid1[.]secret[.][A-Za-z0-9._-]{8,512}\Z")
_VERIFIER=re.compile(r"[A-Za-z0-9_-]{43,128}\Z")
_SELLER=re.compile(r"[0-9]{1,40}\Z")
_TTL=600

class EphemeralPKCEVault(Protocol):
    async def store_verifier(self,*,tenant_id:UUID,actor_id:UUID,
                             verifier:str,ttl_seconds:int)->str: ...
    async def read_verifier(self,*,secret_ocid:str)->str: ...
    async def revoke_verifier(self,*,secret_ocid:str)->bool: ...

class ApprovedSellerRegistry(Protocol):
    async def expected_seller(self,*,tenant_id:UUID,actor_id:UUID)->str|None: ...

class StagingOAuthAttemptRepository:
    """A single dedicated asyncpg-style connection; no public HTTP surface.

    On real OCI this connection must have session_user
    frcaixinha_mp_oauth_worker, never owner/postgres/auth/app.
    """
    def __init__(self,*,db:Any,vault:EphemeralPKCEVault,
                 sellers:ApprovedSellerRegistry,enabled:bool=False):
        self._db=db
        self._vault=vault
        self._sellers=sellers
        self._enabled=enabled is True

    async def _ready(self)->None:
        if not self._enabled:
            raise SandboxConnectBlocked("OCI staging OAuth disabled")
        try:
            row=await self._db.fetchrow(
                "SELECT current_database() AS db_name,"
                "session_user AS login_role,"
                "current_setting('server_version_num')::int AS pg_version"
            )
            if (row is None or row["db_name"]!="frcaixinha_staging"
                or row["login_role"]!="frcaixinha_mp_oauth_worker"
                or type(row["pg_version"]) is not int
                or not 180000<=row["pg_version"]<190000):
                raise SandboxConnectBlocked("Wrong staging database or OAuth role")
        except SandboxConnectBlocked:
            raise
        except Exception:
            raise SandboxConnectBlocked("OCI staging database unavailable") from None

    async def reserve_once(self,*,draft:OAuthDraft)->bool:
        await self._ready()
        if type(draft) is not OAuthDraft or draft.live_mode is not False:
            return False
        ref=None
        try:
            ref=await self._vault.store_verifier(
                tenant_id=draft.tenant_id,actor_id=draft.initiated_by,
                verifier=draft.code_verifier,ttl_seconds=_TTL)
            if type(ref) is not str or not _OCID.fullmatch(ref):
                raise SandboxConnectBlocked("Vault reference unavailable")
            recorded=await self._db.fetchval(
                "SELECT public.mp_staging_oauth_begin("
                "$1::uuid,$2::uuid,$3::text,$4::text,$5::text,"
                "$6::text,$7::text,$8::text,$9::integer)",
                draft.tenant_id,draft.initiated_by,
                sha256(draft.state.encode("ascii")).hexdigest(),
                sha256(draft.redirect_uri.encode("utf-8")).hexdigest(),
                draft.pkce_challenge,ref,draft.client_id,draft.redirect_uri,_TTL)
            if type(recorded) is not UUID:
                raise SandboxConnectBlocked("State not reserved")
            return True
        except Exception:
            if type(ref) is str and _OCID.fullmatch(ref):
                try:
                    await self._vault.revoke_verifier(secret_ocid=ref)
                except Exception:
                    pass   # no false-positive success; operator must audit orphan
            return False

    async def consume_once(self,*,tenant_id:UUID,actor_id:UUID,
                           state_sha256:str,redirect_sha256:str,
                           provided_state:str,now_epoch:int)->OAuthDraft|None:
        await self._ready()
        if (type(tenant_id) is not UUID or type(actor_id) is not UUID
            or type(provided_state) is not str
            or type(state_sha256) is not str or type(redirect_sha256) is not str
            or type(now_epoch) is not int or now_epoch<=0
            or not hmac.compare_digest(sha256(provided_state.encode()).hexdigest(),
                                      state_sha256)):
            return None
        # UPDATE/RETURNING is single-use and scoped by tenant, actor, redirect.
        try:
            row=await self._db.fetchrow(
                "SELECT client_id,redirect_uri,pkce_verifier_secret_ocid,"
                "pkce_challenge,created_at FROM public.mp_staging_oauth_consume("
                "$1::uuid,$2::uuid,$3::text,$4::text)",
                tenant_id,actor_id,state_sha256,redirect_sha256)
        except Exception:
            return None
        if row is None:
            return None
        reference=None
        try:
            reference=row["pkce_verifier_secret_ocid"]
            created=row["created_at"]
            if (type(reference) is not str or not _OCID.fullmatch(reference)
                or type(created) is not datetime or created.tzinfo is None
                or created.utcoffset() is None or type(row["client_id"]) is not str
                or type(row["redirect_uri"]) is not str
                or not hmac.compare_digest(
                    sha256(row["redirect_uri"].encode()).hexdigest(),
                    redirect_sha256)):
                return None
            verifier=await self._vault.read_verifier(secret_ocid=reference)
            if type(verifier) is not str or not _VERIFIER.fullmatch(verifier):
                return None
            reconstructed=OAuthDraft(
                tenant_id=tenant_id,initiated_by=actor_id,
                client_id=row["client_id"],redirect_uri=row["redirect_uri"],
                state=provided_state,code_verifier=verifier,
                created_at_epoch=int(created.timestamp()),live_mode=False)
            challenge=row["pkce_challenge"]
            if (type(challenge) is not str
                or not hmac.compare_digest(challenge,reconstructed.pkce_challenge)
                or now_epoch<reconstructed.created_at_epoch
                or now_epoch-reconstructed.created_at_epoch>_TTL):
                return None
            # Revoke ephemeral reference before token exchange. Retry requires
            # new OAuth consent, since state has already been consumed.
            if await self._vault.revoke_verifier(secret_ocid=reference) is not True:
                return None
            return reconstructed
        except Exception:
            return None

    async def expected_seller(self,*,tenant_id:UUID,actor_id:UUID)->str|None:
        await self._ready()
        try:
            seller=await self._sellers.expected_seller(
                tenant_id=tenant_id,actor_id=actor_id)
        except Exception:
            return None
        return seller if type(seller) is str and _SELLER.fullmatch(seller) else None
