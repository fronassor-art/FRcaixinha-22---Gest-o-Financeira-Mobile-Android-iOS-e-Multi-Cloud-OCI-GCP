"""M4200 — MP Connect tenant OAuth lifecycle and secret rotation contracts.

Scoped multi-tenant, no inline secrets in logs/client, no in-memory store
used as production truth. Existing sandbox adapter handles HTTPS/token
exchange, but never persists. This module supplies durable port contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import re
from typing import Protocol
from uuid import UUID

from .mp_connect_http_runtime import OAuthTokens
from .mp_pix_execution import ProviderRequestBlocked

CONTRACT = "AI_STUDIO_M4200_OAUTH_CONNECT_ROTATION_V1"
_ACCOUNT = re.compile(r"[0-9]{1,40}\Z")
_REF = re.compile(r"[a-zA-Z0-9._:-]{8,180}\Z")


class OAuthSecurityBlocked(ProviderRequestBlocked):
    pass


@dataclass(frozen=True)
class TenantAccountBinding:
    tenant_id: UUID
    provider_account_id: str
    oauth_actor_id: UUID
    environment: str
    consent_version: str
    scopes: frozenset[str]
    approved_by_admin: bool
    active: bool = True
    revoked: bool = False

    def __post_init__(self):
        if (type(self.tenant_id) is not UUID
                or type(self.oauth_actor_id) is not UUID
                or type(self.provider_account_id) is not str
                or not _ACCOUNT.fullmatch(self.provider_account_id)
                or self.environment not in ("HOMOLOGACAO","PRODUCAO")
                or not _REF.fullmatch(self.consent_version)
                or type(self.scopes) is not frozenset
                or any(type(x) is not str or not re.fullmatch("[a-z_]{2,40}",x)
                       for x in self.scopes)):
            raise OAuthSecurityBlocked("Vínculo Connect sem escopo válido")

    def require_active_refresh(self):
        if (self.approved_by_admin is not True
                or self.active is not True or self.revoked is not False
                or "offline_access" not in self.scopes):
            raise OAuthSecurityBlocked("Sem autorização offline do administrador")


@dataclass(frozen=True,repr=False)
class SecretRotation:
    tenant_id: UUID
    provider_account_id: str
    previous_secret_version: str
    new_secret_version: str
    access_token_hash: str
    refresh_token_hash: str
    rotated_at: datetime
    access_valid_seconds: int
    secret_value_is_not_public: bool = field(default=True,init=False)

    def __repr__(self):
        return "SecretRotation(tenant_scoped=True,redacted=True)"


def token_fingerprint(secret:str)->str:
    if type(secret) is not str or len(secret)<16 or len(secret)>4096:
        raise OAuthSecurityBlocked("Credencial inválida")
    return sha256(secret.encode("utf-8")).hexdigest()


def prepare_secret_rotation(
    *, binding:TenantAccountBinding,tokens:OAuthTokens,
    previous_secret_version:str,new_secret_version:str,
    previous_refresh_fingerprint:str,rotated_at:datetime,
) -> SecretRotation:
    """Generate safe metadata; no mutation; never stores token text."""
    if type(binding) is not TenantAccountBinding or type(tokens) is not OAuthTokens:
        raise OAuthSecurityBlocked("Vínculo não comprovado")
    binding.require_active_refresh()
    if (binding.environment!="HOMOLOGACAO"
            or tokens.live_mode is not False
            or binding.provider_account_id!=tokens.seller_id
            or "offline_access" not in tokens.scope.split(" ")
            or not _REF.fullmatch(previous_secret_version)
            or not _REF.fullmatch(new_secret_version)
            or previous_secret_version==new_secret_version
            or type(rotated_at) is not datetime
            or rotated_at.tzinfo is None
            or not re.fullmatch("[a-f0-9]{64}",previous_refresh_fingerprint)
            or token_fingerprint(tokens.refresh_token)==previous_refresh_fingerprint
            or tokens.expires_in<=0):
        raise OAuthSecurityBlocked("Rotação sem prova de conta ou de token renovado")
    return SecretRotation(
        tenant_id=binding.tenant_id,
        provider_account_id=binding.provider_account_id,
        previous_secret_version=previous_secret_version,
        new_secret_version=new_secret_version,
        access_token_hash=token_fingerprint(tokens.access_token),
        refresh_token_hash=token_fingerprint(tokens.refresh_token),
        rotated_at=rotated_at,
        access_valid_seconds=tokens.expires_in,
    )


class OAuthSecretsRepository(Protocol):
    async def store_and_compare_swap(
        self,*,binding:TenantAccountBinding,
        proposed:SecretRotation,raw_tokens:OAuthTokens,
        expected_previous_refresh_fingerprint:str,
    )->bool: ...


async def persist_rotated_tokens(
    *, repository:OAuthSecretsRepository,binding:TenantAccountBinding,
    proposed:SecretRotation,tokens:OAuthTokens,
    previous_refresh_fingerprint:str,
) -> None:
    """Vault worker must commit both tokens atomically and CAS old version.

    Caller must bind tenant to authenticated administrator and verify revocation
    and consent from DB. Raw tokens never returned by this function.
    """
    if (type(proposed) is not SecretRotation or proposed.tenant_id!=binding.tenant_id
            or proposed.provider_account_id!=binding.provider_account_id
            or proposed.access_token_hash!=token_fingerprint(tokens.access_token)
            or proposed.refresh_token_hash!=token_fingerprint(tokens.refresh_token)):
        raise OAuthSecurityBlocked("Rotação divergente")
    binding.require_active_refresh()
    saved=await repository.store_and_compare_swap(
        binding=binding,proposed=proposed,
        raw_tokens=tokens,
        expected_previous_refresh_fingerprint=previous_refresh_fingerprint,
    )
    if saved is not True:
        raise OAuthSecurityBlocked("Conflito de renovação; reconectar via autorização")


def revoked_binding(binding:TenantAccountBinding,provider_account_id:str)->TenantAccountBinding:
    """Applies signed Connect deauthorization after durable verification."""
    if type(binding) is not TenantAccountBinding or provider_account_id!=binding.provider_account_id:
        raise OAuthSecurityBlocked("Revogação de outra conta")
    from dataclasses import replace
    return replace(binding,active=False,revoked=True)
