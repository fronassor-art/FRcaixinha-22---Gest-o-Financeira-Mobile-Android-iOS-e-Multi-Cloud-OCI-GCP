"""M4200 OAuth tenant offline_access, rotation and revocation regression."""
from dataclasses import replace
from datetime import datetime,timezone
from uuid import UUID

import pytest

from app.mp_oauth_rotation import (
    CONTRACT,TenantAccountBinding,SecretRotation,OAuthSecurityBlocked,
    token_fingerprint,prepare_secret_rotation,persist_rotated_tokens,
    revoked_binding,
)
from app.mp_connect_http_runtime import OAuthTokens

T=UUID("00000000-0000-4000-8000-0000000000a1")
U=UUID("00000000-0000-4000-8000-0000000000a3")
OTHER=UUID("00000000-0000-4000-8000-0000000000a9")


def binding(**overrides):
    args=dict(tenant_id=T,provider_account_id="2002",oauth_actor_id=U,
              environment="HOMOLOGACAO",
              consent_version="accepted-2027-v1",
              scopes=frozenset(("read","write","offline_access")),
              approved_by_admin=True)
    args.update(overrides)
    return TenantAccountBinding(**args)


def tokens(**overrides):
    args=dict(seller_id="2002",scope="read write offline_access",
              expires_in=1209600,live_mode=False,
              access_token="APP_USR_SANDBOX_NEW_TOKEN_123456",
              refresh_token="TG_SANDBOX_NEW_REFRESH_TOKEN_987654321")
    args.update(overrides)
    return OAuthTokens(**args)


def rotation(b=None,t=None,**overrides):
    return prepare_secret_rotation(
        binding=b or binding(),tokens=t or tokens(),
        previous_secret_version=overrides.get("previous_secret_version","vault-secret-v1"),
        new_secret_version=overrides.get("new_secret_version","vault-secret-v2"),
        previous_refresh_fingerprint=overrides.get(
            "previous_refresh_fingerprint",token_fingerprint("TG_OLD_REFRESH_TOKEN_12345678")),
        rotated_at=datetime(2027,1,10,tzinfo=timezone.utc),
    )


def test_sandbox_rotation_is_metadata_only():
    r=rotation()
    assert r.tenant_id==T
    assert r.provider_account_id=="2002"
    assert r.access_valid_seconds==1209600
    assert r.refresh_token_hash==token_fingerprint(tokens().refresh_token)
    assert "APP_USR" not in repr(r)
    assert "TG_SANDBOX" not in repr(r)
    assert "TG_SANDBOX" not in str(r)
    assert CONTRACT=="AI_STUDIO_M4200_OAUTH_CONNECT_ROTATION_V1"


@pytest.mark.parametrize("change",[
    {"approved_by_admin":False},
    {"active":False},
    {"revoked":True},
    {"scopes":frozenset(("read","write"))},
    {"environment":"PRODUCAO"},
    {"provider_account_id":"3003"},
])
def test_unapproved_expired_or_other_tenant_refresh_denied(change):
    with pytest.raises(OAuthSecurityBlocked):
        rotation(b=binding(**change))


@pytest.mark.parametrize("change",[
    {"seller_id":"3003"},
    {"scope":"read write"},
    {"live_mode":True},
    {"expires_in":0},
    {"refresh_token":"TG_OLD_REFRESH_TOKEN_12345678"},
])
def test_provider_reply_must_preserve_account_offline_scope(change):
    with pytest.raises(OAuthSecurityBlocked):
        rotation(t=tokens(**change))


def test_revoke_active_merchant_connection_blocks_refresh():
    revoked=revoked_binding(binding(),"2002")
    assert revoked.revoked is True and revoked.active is False
    with pytest.raises(OAuthSecurityBlocked):
        rotation(b=revoked)
    with pytest.raises(OAuthSecurityBlocked):
        revoked_binding(binding(),"3003")


class Vault:
    def __init__(self):
        self.records={}
        self.calls=0
    async def store_and_compare_swap(self,*,binding,proposed,raw_tokens,
                                      expected_previous_refresh_fingerprint):
        self.calls+=1
        key=(binding.tenant_id,binding.provider_account_id)
        if key in self.records:
            return False
        self.records[key]=(proposed.refresh_token_hash,
                           expected_previous_refresh_fingerprint)
        return True


@pytest.mark.asyncio
async def test_vault_cas_metadata_no_token_return_and_one_update():
    store=Vault()
    r=rotation()
    await persist_rotated_tokens(repository=store,binding=binding(),
        proposed=r,tokens=tokens(),
        previous_refresh_fingerprint=token_fingerprint("TG_OLD_REFRESH_TOKEN_12345678"))
    assert store.calls==1
    assert store.records[(T,"2002")][0]==token_fingerprint(tokens().refresh_token)
    with pytest.raises(OAuthSecurityBlocked):
        await persist_rotated_tokens(repository=store,binding=binding(),
            proposed=r,tokens=tokens(),
            previous_refresh_fingerprint=token_fingerprint("TG_OLD_REFRESH_TOKEN_12345678"))


@pytest.mark.asyncio
async def test_worker_rejects_cross_tenant_rotation():
    store=Vault()
    with pytest.raises(OAuthSecurityBlocked):
        await persist_rotated_tokens(repository=store,
            binding=binding(tenant_id=OTHER),
            proposed=rotation(),tokens=tokens(),
            previous_refresh_fingerprint=token_fingerprint("TG_OLD_REFRESH_TOKEN_12345678"))
    assert store.calls==0
