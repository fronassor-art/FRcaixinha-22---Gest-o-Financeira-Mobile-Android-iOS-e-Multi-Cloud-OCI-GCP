"""M23700: SQL CAS registry for OCI staging OAuth, disabled unless injected.

Wraps the isolated PostgreSQL-18 worker's SECURITY DEFINER functions from
staging migration 046. Does not create connections or deploy infrastructure.
It never receives or stores raw OAuth/Pix credentials.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from .mp_oauth_staging_token_sink import PendingTokenRevision

_SELLER = re.compile(r"[0-9]{1,40}\Z")
_REVISION = re.compile(r"[A-Za-z0-9._:-]{16,128}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")

_CREDENTIAL_REF = re.compile(r"[A-Za-z0-9._:/-]{16,512}\Z")


class StagingSellerCASRegistry:
    """Implements SellerRegistry port for an injected asyncpg-style worker."""

    def __init__(self, *, db: Any, enabled: bool = False):
        self._db = db
        self._enabled = enabled is True

    @staticmethod
    def _ids(tenant: UUID, actor: UUID, seller: str) -> bool:
        return (type(tenant) is UUID and type(actor) is UUID
                and type(seller) is str and _SELLER.fullmatch(seller) is not None)

    async def _identity_ok(self) -> bool:
        if not self._enabled:
            return False
        try:
            row = await self._db.fetchrow(
                "SELECT current_database() AS db_name,"
                "session_user AS login_role,"
                "current_setting('server_version_num')::int AS pg_version,"
                "inet_server_port() AS pg_port"
            )
            return (row is not None
                    and row["db_name"] == "frcaixinha_staging"
                    and row["login_role"] == "frcaixinha_mp_oauth_worker"
                    and type(row["pg_version"]) is int
                    and 180000 <= row["pg_version"] < 190000
                    and type(row["pg_port"]) is int
                    and row["pg_port"] != 5433
                    and 1 <= row["pg_port"] <= 65535)
        except Exception:
            return False

    async def eligible(self, *, tenant: UUID, actor: UUID, seller: str) -> bool:
        if not self._ids(tenant, actor, seller) or not await self._identity_ok():
            return False
        try:
            result = await self._db.fetchval(
                "SELECT public.mp_staging_oauth_eligible($1::uuid,$2::uuid,$3::varchar)",
                tenant, actor, seller,
            )
            return result is True
        except Exception:
            return False

    async def stage_pending(self, *, pending: PendingTokenRevision) -> bool:
        """Register opaque PENDING revision using SQL's consent generation guard."""
        if (type(pending) is not PendingTokenRevision
                or not self._ids(pending.tenant_id, pending.actor_id, pending.seller_id)
                or type(pending.revision) is not str
                or _REVISION.fullmatch(pending.revision) is None
                or type(pending.credential_ref) is not str
                or _CREDENTIAL_REF.fullmatch(pending.credential_ref) is None
                or type(pending.expected_generation) is not int
                or not 0 <= pending.expected_generation <= 9_223_372_036_854_775_807
                or not await self._identity_ok()):
            return False
        try:
            result = await self._db.fetchval(
                "SELECT public.mp_staging_oauth_stage("
                "$1::uuid,$2::uuid,$3::varchar,$4::varchar,$5::varchar,$6::bigint)",
                pending.tenant_id, pending.actor_id, pending.seller_id,
                pending.revision, pending.credential_ref, pending.expected_generation,
            )
            return result is True
        except Exception:
            return False

    async def activate_cas(
        self, *, pending: PendingTokenRevision,
        access_hash: str, refresh_hash: str,
    ) -> bool:
        if (type(pending) is not PendingTokenRevision
                or not self._ids(pending.tenant_id, pending.actor_id, pending.seller_id)
                or type(pending.revision) is not str
                or _REVISION.fullmatch(pending.revision) is None
                or type(access_hash) is not str or _SHA256.fullmatch(access_hash) is None
                or type(refresh_hash) is not str or _SHA256.fullmatch(refresh_hash) is None
                or not await self._identity_ok()):
            return False
        try:
            result = await self._db.fetchval(
                "SELECT public.mp_staging_oauth_activate("
                "$1::uuid,$2::uuid,$3::varchar,$4::varchar,$5::text,$6::text)",
                pending.tenant_id, pending.actor_id, pending.seller_id,
                pending.revision, access_hash, refresh_hash,
            )
            return result is True
        except Exception:
            return False

    async def mark_failed(self, *, pending: PendingTokenRevision) -> bool:
        if (type(pending) is not PendingTokenRevision
                or not self._ids(pending.tenant_id, pending.actor_id, pending.seller_id)
                or type(pending.revision) is not str
                or _REVISION.fullmatch(pending.revision) is None
                or not await self._identity_ok()):
            return False
        try:
            result = await self._db.fetchval(
                "SELECT public.mp_staging_oauth_fail_pending("
                "$1::uuid,$2::uuid,$3::varchar,$4::varchar)",
                pending.tenant_id, pending.actor_id,
                pending.seller_id, pending.revision,
            )
            return result is True
        except Exception:
            return False

    async def active_credential_ref(
        self, *, tenant: UUID, actor: UUID, seller: str
    ) -> str | None:
        """Opaque reference only. This must not be exposed in an API response."""
        if not self._ids(tenant, actor, seller) or not await self._identity_ok():
            return None
        try:
            result = await self._db.fetchval(
                "SELECT public.mp_staging_oauth_active_ref("
                "$1::uuid,$2::uuid,$3::varchar)",
                tenant, actor, seller,
            )
            if (type(result) is not str
                    or not 16 <= len(result) <= 512
                    or re.fullmatch(r"[A-Za-z0-9._:/-]+", result) is None):
                return None
            return result
        except Exception:
            return None
