"""M27000: no SMTP from encrypted outbox without rechecking scope/lease."""
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4

import pytest

from app.delivery_envelope import DeliveryScope, DeliverySecret, seal_delivery
from app.delivery_key_lifecycle import (
    KeyLifecycle, KeyMetadata, TenantKeyCatalog,
)
from app.outbound_worker_preflight import (
    AuthenticatedLeaseSnapshot, DispatchPreflightBlocked,
    RedactedDispatchPreflight, verify_sealed_outbox_before_dispatch,
)

NOW=1794000000
ALIAS="ci-tenant-mail-key-2026"
EMAIL="synthetic@example.com"
TOKEN="R"*48


class MockKeyProvider:
    def load_key(self,alias):
        assert alias==ALIAS
        return b"K"*32


def fixture():
    scope=DeliveryScope(
        tenant_id=uuid4(),event_id=uuid4(),document_id=uuid4(),
        target_role="TENANT_ADMIN",purpose="INVITATION",
        issued_at=NOW,expires_at=NOW+600,
    )
    metadata=KeyMetadata(
        key_id=ALIAS,tenant_id=scope.tenant_id,
        lifecycle=KeyLifecycle.ACTIVE,
        active_from=NOW-100,encrypt_until=NOW+100,decrypt_until=NOW+1000,
    )
    catalog=TenantKeyCatalog({ALIAS:metadata})
    encrypted=seal_delivery(
        scope=scope,secret=DeliverySecret(EMAIL,TOKEN),key_id=ALIAS,
        provider=MockKeyProvider(),now=NOW,
    )
    lease=AuthenticatedLeaseSnapshot(
        tenant_id=scope.tenant_id,event_id=scope.event_id,
        document_id=scope.document_id,target_role=scope.target_role,
        lease_id=uuid4(),lease_expires_at=NOW+60,
        invitation_expires_at=NOW+720,attempts=1,
        outbox_status="HELD_CI_NOT_SENT",terminal_quarantine=False,
    )
    return lease,scope,encrypted,catalog


def check(lease,scope,encrypted,catalog,*,now=NOW+1,digest=None):
    return verify_sealed_outbox_before_dispatch(
        lease=lease,scope=scope,envelope=encrypted,
        expected_recipient_digest=digest or sha256(EMAIL.encode()).hexdigest(),
        catalog=catalog,provider=MockKeyProvider(),now=now,
    )


def test_signed_aes_payload_cannot_become_delivery_or_activation_proof():
    lease,scope,encrypted,catalog=fixture()
    result=check(lease,scope,encrypted,catalog)
    assert result==RedactedDispatchPreflight()
    assert result.can_send_network is False
    assert result.provider_delivery_confirmed is False
    assert result.recipient_verified is False
    assert result.consent_recorded is False
    assert result.account_activated is False
    assert TOKEN not in repr(result)
    assert EMAIL not in repr(result)


@pytest.mark.parametrize("field,value",[
    ("tenant_id",uuid4()),
    ("event_id",uuid4()),
    ("document_id",uuid4()),
    ("target_role","TENANT_MEMBER"),
    ("lease_id",__import__("uuid").UUID(int=0)),
    ("outbox_status","DELIVERED"),
    ("terminal_quarantine",True),
    ("attempts",0),
    ("attempts",4),
    ("attempts",True),
    ("lease_expires_at",NOW),
    ("invitation_expires_at",NOW),
])
def test_bad_lease_metadata_blocks_dispatch(field,value):
    lease,scope,encrypted,catalog=fixture()
    with pytest.raises(DispatchPreflightBlocked):
        check(replace(lease,**{field:value}),scope,encrypted,catalog)


@pytest.mark.parametrize("field,value",[
    ("tenant_id",uuid4()),
    ("event_id",uuid4()),
    ("document_id",uuid4()),
    ("target_role","TENANT_MEMBER"),
    ("purpose","PASSWORD_RESET"),
])
def test_scope_or_tenant_switch_fails_closed(field,value):
    lease,scope,encrypted,catalog=fixture()
    with pytest.raises(DispatchPreflightBlocked):
        check(lease,replace(scope,**{field:value}),encrypted,catalog)


def test_wrong_or_invalid_recipient_digest_fails_closed():
    lease,scope,encrypted,catalog=fixture()
    for digest in ("0"*64,"bad",None,123):
        with pytest.raises(DispatchPreflightBlocked):
            verify_sealed_outbox_before_dispatch(
                lease=lease,scope=scope,envelope=encrypted,
                expected_recipient_digest=digest,catalog=catalog,
                provider=MockKeyProvider(),now=NOW+1,
            )


def test_expiration_and_decrypt_only_revocation_are_rechecked():
    lease,scope,encrypted,catalog=fixture()
    with pytest.raises(DispatchPreflightBlocked):
        check(lease,scope,encrypted,catalog,now=NOW+61)
    with pytest.raises(DispatchPreflightBlocked):
        check(lease,scope,encrypted,catalog,now=NOW-1)
    revoked=TenantKeyCatalog({ALIAS:KeyMetadata(
        ALIAS,scope.tenant_id,KeyLifecycle.REVOKED,
        NOW-100,NOW+100,NOW+1000,
    )})
    with pytest.raises(DispatchPreflightBlocked):
        check(lease,scope,encrypted,revoked)


def test_preflight_cannot_open_network_or_write_database_or_reveal_payload():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    source=(root/"backend/app/outbound_worker_preflight.py").read_text()
    for bad in (
        "smtplib", "submit_access_message(",
        "INSERT INTO", "UPDATE public.", "oci.config",
        "requests.", "httpx.", "SMTP(",
    ):
        assert bad not in source
    assert "hmac.compare_digest" in source
    for route in ("auth.py","invitations.py","master.py"):
        code=(root/"backend/app/routers"/route).read_text()
        assert "verify_sealed_outbox_before_dispatch" not in code
