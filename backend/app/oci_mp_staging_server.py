"""AI Studio M3000: standalone OCI staging webhook server (receive ONLY).

This ASGI process is separate from app.main and disabled by default.
It has no payments, ledger, closing, payout or bank reconciliation endpoints.
A deployed server can activate it ONLY after signed configuration, OCI
Instance Principal, Vault secrets and a dedicated staging PostgreSQL exist.
"""
from __future__ import annotations

import asyncio
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Callable, Mapping
from urllib.parse import parse_qs, urlsplit

import asyncpg
from fastapi import FastAPI

from .oci_secret_bridge import (
    VaultUnavailable, build_instance_principal_secrets_client, get_current_secret,
)
from .mp_staging_postgres import StagingPostgresInbox
from .mp_webhook_staging_runtime import create_webhook_staging_router

CONTRACT = "AI_STUDIO_M3000_OCI_STANDALONE_STAGING_SERVER_V1"
_SECRET_OCID = re.compile(r"ocid1\.vaultsecret\.[A-Za-z0-9._-]{8,512}\Z")
_REGION = re.compile(r"[a-z][a-z0-9-]{3,50}\Z")


class StagingServerBlocked(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class StagingServerConfig:
    enabled: bool = False
    environment: str = "development"
    region: str = ""
    db_dsn_secret_ocid: str = ""
    server_mode: str = "DISABLED"
    accept_live_notifications: bool = False

    def __repr__(self):
        return "StagingServerConfig(redacted=True)"

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None):
        env = os.environ if env is None else env
        return cls(
            enabled=env.get("FRC_MP_OCI_STAGING_ENABLED") == "1",
            environment=env.get("ENVIRONMENT","development"),
            region=env.get("OCI_REGION",""),
            db_dsn_secret_ocid=env.get("FRC_MP_STAGING_DB_SECRET_OCID",""),
            server_mode=env.get("FRC_MP_STAGING_SERVER_MODE","DISABLED"),
            accept_live_notifications=(
                env.get("FRC_MP_ACCEPT_LIVE_NOTIFICATIONS")=="1"
            ),
        )

    def require_safe_receive_only(self):
    # Dedicated staging refuses live notifications even if a deployment
    # operator accidentally enables the old flag. Only signed TEST inbox.
        if self.enabled is not True:
            raise StagingServerBlocked("Staging server disabled")
        if (self.environment != "homologation"
                or self.server_mode != "RECEIVE_ONLY"
                or not _REGION.fullmatch(self.region)
                or not _SECRET_OCID.fullmatch(self.db_dsn_secret_ocid)
                or self.accept_live_notifications is not False):
            raise StagingServerBlocked("Staging configuration unsafe")


def validate_staging_database_dsn(dsn: str) -> str:
    """DB hostname/cert checks; never echo credentials in error."""
    if type(dsn) is not str or not 0 < len(dsn) <= 4096:
        raise StagingServerBlocked("Staging database connection invalid")
    try:
        url=urlsplit(dsn)
        params=parse_qs(url.query,keep_blank_values=True)
        valid=(
            url.scheme in ("postgresql","postgres")
            and url.hostname is not None
            and url.hostname not in ("localhost","127.0.0.1","::1")
            and url.username=="frcaixinha_mp_webhook_ingest"
            and url.path=="/frcaixinha_staging"
            and url.password is not None
            and len(url.password)>12
            and not url.fragment
            and params.get("sslmode")==["verify-full"]
            and set(params)=={"sslmode"}
        )
    except (ValueError,TypeError):
        valid=False
    if not valid:
        raise StagingServerBlocked("Staging DB must use dedicated login and verified TLS")
    return dsn


def create_staging_app(
    config: StagingServerConfig | None = None,
    *,
    sdk_client_factory: Callable | None = None,
    pool_factory: Callable | None = None,
    clock_ms: Callable[[],int] | None = None,
) -> FastAPI:
    config=config or StagingServerConfig.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ready=False
        if not config.enabled:
            yield
            return
        config.require_safe_receive_only()
        client=None
        pool=None
        try:
            # SDK initialization uses instance principal only; secret references
            # are identifiers (never credentials) in environment variables.
            if sdk_client_factory is None:
                client=await asyncio.to_thread(
                    build_instance_principal_secrets_client,
                    region=config.region,enabled=True,
                )
            else:
                client=await asyncio.to_thread(sdk_client_factory,config.region)
            db_secret=await asyncio.to_thread(
                get_current_secret,
                secret_ocid=config.db_dsn_secret_ocid,client=client,
            )
            dsn=validate_staging_database_dsn(db_secret.secret)
            factory=pool_factory if pool_factory is not None else asyncpg.create_pool
            pool=await factory(dsn=dsn,min_size=1,max_size=4,timeout=5)
            repo=StagingPostgresInbox(pool)
            async with pool.acquire() as conn:
                await repo._ensure_staging(conn)

            async def fetch_secret(seller):
                value=await asyncio.to_thread(
                    get_current_secret,
                    secret_ocid=seller.webhook_secret_ocid,client=client,
                )
                return value.secret.encode("utf-8")

            import time
            app.include_router(create_webhook_staging_router(
                resolve_seller=repo.resolve_seller,
                load_signing_secret=fetch_secret,
                persist_verified=repo.append,
                now_ms=clock_ms or (lambda: int(time.time()*1000)),
                allow_live_ingest=config.accept_live_notifications,
            ))
            app.state.ready=True
            yield
        except Exception:
            raise StagingServerBlocked(
                "Staging webhook server cannot start safely"
            ) from None
        finally:
            app.state.ready=False
            if pool is not None:
                await pool.close()

    app=FastAPI(
        title="FR Caixinha AI Studio — OCI webhook staging",
        lifespan=lifespan,
        docs_url=None,redoc_url=None,openapi_url=None,
    )

    @app.get("/api/health/oci-staging",include_in_schema=False)
    async def staging_health():
        return {
            "workstream":"AI_STUDIO",
            "contract":CONTRACT,
            "webhook_receiver_ready":bool(app.state.ready),
            "only_durable_inbox_enabled":True,
            "bank_reconciled":False,
            "ledger_written":False,
            "real_payments_enabled":False,
            "financial_closing_authorized":False,
        }

    return app


app=create_staging_app()
