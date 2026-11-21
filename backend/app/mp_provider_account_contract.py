"""AI Studio M3100: conta recebedora MP não é novo perfil funcional.

seller_id no protocolo do MP = identificador técnico da conta conectada.
Não introduzir papel SELLER/VENDEDOR; os únicos papéis de usuário são os
contratuais MASTER, TENANT_ADMIN e TENANT_MEMBER.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

CONTRACT = "AI_STUDIO_M3100_PROVIDER_ACCOUNT_ROLE_CONTRACT_V1"
_MP_ID = re.compile(r"[0-9]{1,40}\Z")
USER_ROLES = frozenset({"MASTER", "TENANT_ADMIN", "TENANT_MEMBER"})


class AccountPurpose(str, Enum):
    PLATFORM_LICENSE = "PLATFORM_LICENSE"
    TENANT_FINANCIAL = "TENANT_FINANCIAL"


class AccountScopeRejected(ValueError):
    """Does not return private tenant/account identifiers."""


@dataclass(frozen=True)
class MercadoPagoAccountBinding:
    """Trusted backend record, not a web client-supplied authorization claim."""
    provider_account_id: str
    purpose: AccountPurpose
    tenant_id: UUID | None
    connection_active: bool
    oauth_consent_valid: bool
    environment: str
    verified_owner: bool
    source: str = "SERVER_SIDE_BINDING_METADATA"

    @property
    def mercado_pago_user_id(self) -> str:
        """The same technical ID called user_id (or seller_id) in MP APIs."""
        return self.provider_account_id


@dataclass(frozen=True)
class AccountAccessReview:
    account_purpose: AccountPurpose
    provider_account_id: str
    allowed_to_query_provider: bool
    real_financial_operation_authorized: bool = False
    ledger_written: bool = False
    bank_reconciled: bool = False


def review_provider_account_access(
    *, binding: MercadoPagoAccountBinding,
    current_role: str,
    active_tenant_id: UUID | None,
    requested_purpose: AccountPurpose,
    requested_environment: str,
) -> AccountAccessReview:
    """Strong role/tenant/purpose separation before future authenticated GET.

    This is one read-only gate; production must separately verify the session,
    persistent record, secrets, regulated capability and provider consent.
    """
    if (type(binding) is not MercadoPagoAccountBinding
            or type(current_role) is not str or current_role not in USER_ROLES
            or type(requested_purpose) is not AccountPurpose
            or type(requested_environment) is not str
            or requested_environment not in ("DEMO", "HOMOLOGACAO", "PRODUCAO")
            or binding.environment != requested_environment
            or binding.purpose is not requested_purpose
            or type(binding.provider_account_id) is not str
            or not _MP_ID.fullmatch(binding.provider_account_id)
            or binding.source != "SERVER_SIDE_BINDING_METADATA"
            or binding.connection_active is not True
            or binding.oauth_consent_valid is not True
            or binding.verified_owner is not True):
        raise AccountScopeRejected("Conta externa nao autorizada")
    if requested_purpose is AccountPurpose.PLATFORM_LICENSE:
        if (current_role != "MASTER" or binding.tenant_id is not None
                or active_tenant_id is not None):
            raise AccountScopeRejected("Conta externa nao autorizada")
    else:
        if (current_role != "TENANT_ADMIN"
                or type(binding.tenant_id) is not UUID
                or active_tenant_id != binding.tenant_id):
            raise AccountScopeRejected("Conta externa nao autorizada")
    return AccountAccessReview(
        account_purpose=binding.purpose,
        provider_account_id=binding.provider_account_id,
        allowed_to_query_provider=True,
    )
