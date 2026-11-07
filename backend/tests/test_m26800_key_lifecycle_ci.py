"""M26800 — tenant key rotation metadata cannot leak or reactivate keys."""
from dataclasses import replace
from uuid import uuid4

import pytest

from app.delivery_envelope import DeliveryScope,DeliverySecret
from app.delivery_key_lifecycle import (
    KeyAccessBlocked, KeyLifecycle, KeyMetadata, TenantKeyCatalog,
    seal_with_key_policy, open_with_key_policy,
)

NOW=1794000000
TOKEN="Q"*48
KEY="ci-vault-tenant-A-2026"


class FakeProvider:
    """Synthetic test key, NEVER a production Vault implementation."""
    def load_key(self,key_id):
        if key_id != KEY:
            raise KeyError("unknown test key")
        return b"K"*32


def fixture():
    tenant=uuid4()
    scope=DeliveryScope(
        tenant_id=tenant,event_id=uuid4(),document_id=uuid4(),
        target_role="TENANT_MEMBER",purpose="INVITATION",
        issued_at=NOW,expires_at=NOW+900,
    )
    details=KeyMetadata(
        key_id=KEY,tenant_id=tenant,lifecycle=KeyLifecycle.ACTIVE,
        active_from=NOW-100,encrypt_until=NOW+100,
        decrypt_until=NOW+500,
    )
    secret=DeliverySecret(recipient="member@example.com",token=TOKEN)
    return scope,details,secret


def seal(scope,details,secret):
    return seal_with_key_policy(
        scope=scope,secret=secret,key_id=KEY,
        catalog=TenantKeyCatalog({KEY:details}),
        provider=FakeProvider(),now=NOW,
    )


def test_active_key_round_trip_with_tenant_scope():
    scope,meta,secret=fixture()
    ciphertext=seal(scope,meta,secret)
    opened=open_with_key_policy(
        envelope=ciphertext,scope=scope,catalog=TenantKeyCatalog({KEY:meta}),
        provider=FakeProvider(),now=NOW+3,
    )
    assert opened==secret
    assert TOKEN not in repr(ciphertext)
    assert TOKEN not in repr(meta)


def test_decrypt_only_key_allows_old_payload_but_never_new_encryption():
    scope,meta,secret=fixture()
    ciphertext=seal(scope,meta,secret)
    retired=replace(meta,lifecycle=KeyLifecycle.DECRYPT_ONLY)
    with pytest.raises(KeyAccessBlocked):
        seal(scope,retired,secret)
    assert open_with_key_policy(
        envelope=ciphertext,scope=scope,
        catalog=TenantKeyCatalog({KEY:retired}),provider=FakeProvider(),
        now=NOW+105,
    )==secret


def test_revoked_key_cannot_encrypt_or_decrypt():
    scope,meta,secret=fixture()
    ciphertext=seal(scope,meta,secret)
    revoked=replace(meta,lifecycle=KeyLifecycle.REVOKED)
    with pytest.raises(KeyAccessBlocked):
        seal(scope,revoked,secret)
    with pytest.raises(KeyAccessBlocked):
        open_with_key_policy(
            envelope=ciphertext,scope=scope,
            catalog=TenantKeyCatalog({KEY:revoked}),
            provider=FakeProvider(),now=NOW+1,
        )


def test_wrong_tenant_cannot_use_another_tenants_key():
    scope,meta,secret=fixture()
    ciphertext=seal(scope,meta,secret)
    rogue=replace(meta,tenant_id=uuid4())
    with pytest.raises(KeyAccessBlocked):
        seal(scope,rogue,secret)
    with pytest.raises(KeyAccessBlocked):
        open_with_key_policy(
            envelope=ciphertext,scope=scope,
            catalog=TenantKeyCatalog({KEY:rogue}),
            provider=FakeProvider(),now=NOW+1,
        )


def test_decrypt_after_grace_is_blocked():
    scope,meta,secret=fixture()
    ciphertext=seal(scope,meta,secret)
    with pytest.raises(KeyAccessBlocked):
        open_with_key_policy(
            envelope=ciphertext,scope=scope,
            catalog=TenantKeyCatalog({KEY:replace(meta,lifecycle=KeyLifecycle.DECRYPT_ONLY)}),
            provider=FakeProvider(),now=NOW+501,
        )


@pytest.mark.parametrize("changed", [
    {"active_from":NOW+1},
    {"encrypt_until":NOW},
    {"decrypt_until":NOW-1},
    {"lifecycle":KeyLifecycle.REVOKED},
])
def test_invalid_key_lifecycle_or_policy_blocks_seal(changed):
    scope,meta,secret=fixture()
    config=replace(meta,**changed)
    try:
        catalog=TenantKeyCatalog({KEY:config})
    except KeyAccessBlocked:
        return
    with pytest.raises(KeyAccessBlocked):
        seal_with_key_policy(
            scope=scope,secret=secret,key_id=KEY,
            catalog=catalog,provider=FakeProvider(),now=NOW,
        )


@pytest.mark.parametrize("change", [
    {"tenant_id":uuid4()},
    {"key_id":"different-key-2026"},
    {"encrypt_until":NOW-1},
    {"decrypt_until":NOW-1},
])
def test_catalog_metadata_is_rejected_when_invalid(change):
    scope,meta,secret=fixture()
    config=replace(meta,**change)
    with pytest.raises(KeyAccessBlocked):
        TenantKeyCatalog({KEY:config}) if "key_id" in change or "encrypt_until" in change or "decrypt_until" in change else seal_with_key_policy(
            scope=scope,secret=secret,key_id=KEY,
            catalog=TenantKeyCatalog({KEY:config}),
            provider=FakeProvider(),now=NOW,
        )


def test_no_production_key_material_secrets_or_cloud_calls():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    code=(root/"backend/app/delivery_key_lifecycle.py").read_text()
    for forbidden in (
        "import oci", "os.environ", "os.getenv", "base64.b64decode",
        "DATABASE_URL", "execute(", "requests.", "httpx.", "SMTP(",
    ):
        assert forbidden not in code
    assert "KeyProvider" in code
    assert "KeyLifecycle.DECRYPT_ONLY" not in code or "KeyLifecycle" in code
