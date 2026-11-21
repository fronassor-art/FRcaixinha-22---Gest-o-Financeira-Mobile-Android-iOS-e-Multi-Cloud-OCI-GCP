"""M3100: no SELLER role, immutable business scope for MP connections."""
from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mp_provider_account_contract import (
    AccountPurpose, AccountScopeRejected, MercadoPagoAccountBinding,
    USER_ROLES, review_provider_account_access, CONTRACT,
)

T1=UUID("00000000-0000-4000-8000-0000000000a1")
T2=UUID("00000000-0000-4000-8000-0000000000b1")


def account(*,platform=False):
    return MercadoPagoAccountBinding(
        provider_account_id="2002" if not platform else "5005",
        purpose=(AccountPurpose.PLATFORM_LICENSE if platform
                 else AccountPurpose.TENANT_FINANCIAL),
        tenant_id=None if platform else T1,
        connection_active=True,oauth_consent_valid=True,
        environment="HOMOLOGACAO",verified_owner=True,
    )


def review(binding=None,**kwargs):
    opts=dict(binding=binding or account(),current_role="TENANT_ADMIN",
              active_tenant_id=T1,requested_purpose=AccountPurpose.TENANT_FINANCIAL,
              requested_environment="HOMOLOGACAO")
    opts.update(kwargs)
    return review_provider_account_access(**opts)


def test_contract_contains_only_three_roles():
    assert USER_ROLES=={"MASTER","TENANT_ADMIN","TENANT_MEMBER"}
    assert "SELLER" not in USER_ROLES
    assert "VENDEDOR" not in USER_ROLES


def test_tenant_admin_accesses_only_own_connected_account_metadata():
    result=review()
    assert result.provider_account_id=="2002"
    assert result.allowed_to_query_provider is True
    assert result.ledger_written is False
    assert result.bank_reconciled is False
    assert result.real_financial_operation_authorized is False
    assert account().mercado_pago_user_id=="2002"


@pytest.mark.parametrize("change",[
    {"current_role":"MASTER"},{"current_role":"TENANT_MEMBER"},
    {"current_role":"SELLER"},{"current_role":"VENDEDOR"},
    {"current_role":"tenant_admin"},{"active_tenant_id":T2},
    {"active_tenant_id":None},
    {"requested_purpose":AccountPurpose.PLATFORM_LICENSE},
    {"requested_environment":"PRODUCAO"},
    {"requested_environment":"unknown"},
])
def test_tenant_access_rejects_wrong_roles_tenant_purpose_environment(change):
    with pytest.raises(AccountScopeRejected):
        review(**change)


@pytest.mark.parametrize("change",[
    {"connection_active":False},{"oauth_consent_valid":False},
    {"verified_owner":False},{"provider_account_id":"20;02"},
    {"provider_account_id":""},{"provider_account_id":"abc"},
    {"source":"CLIENT_SUPPLIED"},{"environment":"PRODUCAO"},
    {"purpose":AccountPurpose.PLATFORM_LICENSE},
    {"tenant_id":T2},{"tenant_id":None},
])
def test_tenant_binding_fails_closed_on_fake_or_revoked_data(change):
    with pytest.raises(AccountScopeRejected):
        review(replace(account(),**change))


def test_platform_license_belongs_to_master_account_only():
    r=review(
        binding=account(platform=True),current_role="MASTER",
        active_tenant_id=None,requested_purpose=AccountPurpose.PLATFORM_LICENSE,
    )
    assert r.account_purpose is AccountPurpose.PLATFORM_LICENSE
    assert not r.real_financial_operation_authorized
    with pytest.raises(AccountScopeRejected):
        review(binding=account(platform=True),current_role="TENANT_ADMIN",
               active_tenant_id=None,
               requested_purpose=AccountPurpose.PLATFORM_LICENSE)
    with pytest.raises(AccountScopeRejected):
        review(binding=account(platform=True),current_role="MASTER",
               active_tenant_id=T1,
               requested_purpose=AccountPurpose.PLATFORM_LICENSE)


def test_master_cannot_query_tenant_financial_money():
    with pytest.raises(AccountScopeRejected):
        review(current_role="MASTER",active_tenant_id=None)


def test_no_role_added_to_fastapi_routes():
    with TestClient(app) as client:
        d=client.get("/api/health/features/m3100").json()
    assert d["contract"]==CONTRACT
    assert d["workstream"]=="AI_STUDIO"
    assert d["seller_is_application_role"] is False
    assert d["provider_account_is_technical_identifier"] is True
    assert d["mercado_pago_real_connected"] is False
    assert d["real_payments_enabled"] is False
