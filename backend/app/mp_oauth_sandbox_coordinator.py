"""M23100: server-only OAuth orchestration. NOT a mounted public endpoint.

A deployed store must use a unique state digest and atomic one-time consume.
A deployed sink must persist tokens to OCI Vault and bind seller in PostgreSQL.
This coordinator intentionally has no production network mode.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID
import httpx
from .dependencies import AuthenticatedSession,require_tenant_access
from .mp_oauth_connect_preflight import OAuthDraft,prepare_oauth_draft,precheck_oauth_callback
from .mp_connect_http_runtime import OAuthTokens,exchange_sandbox_authorization_code

class SandboxConnectBlocked(RuntimeError):
    """Never include secrets, OAuth state, codes or vendor errors."""

class DurableOAuthAttempts(Protocol):
    async def reserve_once(self,*,draft:OAuthDraft)->bool: ...
    async def consume_once(self,*,tenant_id:UUID,actor_id:UUID,
                           state_sha256:str,redirect_sha256:str,
                           provided_state:str,now_epoch:int)->OAuthDraft|None: ...
    async def expected_seller(self,*,tenant_id:UUID,actor_id:UUID)->str|None: ...

class VaultBoundTokenSink(Protocol):
    async def persist_sandbox_connection(
        self,*,draft:OAuthDraft,tokens:OAuthTokens
    )->bool: ...

@dataclass(frozen=True,repr=False)
class SandboxConnectedMetadata:
    tenant_id:UUID
    initiated_by:UUID
    seller_id:str
    status:str="SANDBOX_VAULT_PERSISTENCE_REPORTED"
    provider_connected_for_real_money:bool=False
    real_payments_enabled:bool=False
    bank_reconciled:bool=False
    ledger_written:bool=False
    def __repr__(self):
        return "SandboxConnectedMetadata(redacted=True, real_money=False)"

def _identity(session:AuthenticatedSession,tenant_id:UUID)->UUID:
    if type(session) is not AuthenticatedSession or type(tenant_id) is not UUID:
        raise SandboxConnectBlocked("OAuth actor invalid")
    try:
        require_tenant_access(str(tenant_id),session)
        if session.role!="TENANT_ADMIN" or session.is_master is True:
            raise SandboxConnectBlocked("OAuth requires tenant administrator")
        return UUID(session.user_id)
    except (ValueError,TypeError):
        raise SandboxConnectBlocked("OAuth actor invalid") from None

def _digest(value:str)->str:
    if type(value) is not str or not value or len(value)>512:
        raise SandboxConnectBlocked("OAuth callback invalid")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

class OAuthSandboxCoordinator:
    def __init__(self,*,attempts:DurableOAuthAttempts,vault:VaultBoundTokenSink,
                 client_secret:str,transport:httpx.AsyncBaseTransport|None=None):
        self._attempts=attempts
        self._vault=vault
        self._client_secret=client_secret
        self._transport=transport

    async def begin(self,*,session:AuthenticatedSession,tenant_id:UUID,
                    client_id:str,registered_redirect_uri:str,now_epoch:int)->str:
        actor=_identity(session,tenant_id)
        try:
            draft=prepare_oauth_draft(tenant_id=tenant_id,initiated_by=actor,
                client_id=client_id,registered_redirect_uri=registered_redirect_uri,
                now_epoch=now_epoch)
            stored=await self._attempts.reserve_once(draft=draft)
            if stored is not True:
                raise SandboxConnectBlocked("OAuth state not reserved")
            return draft.authorization_url
        except SandboxConnectBlocked:
            raise
        except Exception:
            raise SandboxConnectBlocked("OAuth cannot start") from None

    async def complete(self,*,session:AuthenticatedSession,tenant_id:UUID,
                       state:str,authorization_code:str,redirect_uri:str,
                       now_epoch:int)->SandboxConnectedMetadata:
        actor=_identity(session,tenant_id)
        try:
            draft=await self._attempts.consume_once(
                tenant_id=tenant_id,actor_id=actor,state_sha256=_digest(state),
                redirect_sha256=_digest(redirect_uri),provided_state=state,
                now_epoch=now_epoch)
        except Exception:
            raise SandboxConnectBlocked("OAuth state unavailable") from None
        if (type(draft) is not OAuthDraft or
            not precheck_oauth_callback(
                draft=draft,tenant_id=tenant_id,initiated_by=actor,
                provided_state=state,code=authorization_code,
                redirect_uri=redirect_uri,now_epoch=now_epoch,
                already_consumed=False)):
            raise SandboxConnectBlocked("OAuth state expired or mismatched")
        try:
            seller=await self._attempts.expected_seller(
                tenant_id=tenant_id,actor_id=actor)
            if type(seller) is not str:
                raise SandboxConnectBlocked("OAuth seller not prebound")
            tokens=await exchange_sandbox_authorization_code(
                draft=draft,returned_state=state,code=authorization_code,
                client_secret=self._client_secret,expected_seller_id=seller,
                consumed_by_durable_store=True,transport=self._transport,
                real_https_authorized=False)
            saved=await self._vault.persist_sandbox_connection(
                draft=draft,tokens=tokens)
            if saved is not True:
                raise SandboxConnectBlocked("OAuth Vault persistence missing")
            return SandboxConnectedMetadata(tenant_id,actor,tokens.seller_id)
        except SandboxConnectBlocked:
            raise
        except Exception:
            raise SandboxConnectBlocked("OAuth exchange or persistence blocked") from None
