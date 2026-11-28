"""M27200–M27210: synthetic token preparation and receipt correlation."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid4

import pytest

from app.delivery_envelope import DeliveryScope, DeliverySecret, seal_delivery
from app.delivery_key_lifecycle import KeyLifecycle, KeyMetadata, TenantKeyCatalog
from app.email_challenge_material import (
    EmailChallengeBlocked, prepare_ci_email_challenge,
)
from app.email_receipt_correlation import (
    ReceiptCorrelationBlocked, correlate_ci_receipt_to_sealed_outbox,
)
from app.outbound_worker_preflight import AuthenticatedLeaseSnapshot
from app.synthetic_mail_receipt import VerifiedSyntheticReceipt

NOW = 1794000000
EMAIL = "synthetic@example.com"
ALIAS = "ci-tenant-mail-key-2026"


class MockKeyProvider:
    def load_key(self, alias):
        assert alias == ALIAS
        return b"K" * 32


def fixture():
    scope = DeliveryScope(
        tenant_id=uuid4(), event_id=uuid4(), document_id=uuid4(),
        target_role="TENANT_ADMIN", purpose="INVITATION",
        issued_at=NOW, expires_at=NOW + 1500,
    )
    catalog = TenantKeyCatalog({ALIAS: KeyMetadata(
        key_id=ALIAS, tenant_id=scope.tenant_id,
        lifecycle=KeyLifecycle.ACTIVE, active_from=NOW - 100,
        encrypt_until=NOW + 100, decrypt_until=NOW + 2000,
    )})
    sealed = seal_delivery(
        scope=scope, secret=DeliverySecret(EMAIL, "R" * 48),
        key_id=ALIAS, provider=MockKeyProvider(), now=NOW,
    )
    lease = AuthenticatedLeaseSnapshot(
        tenant_id=scope.tenant_id, event_id=scope.event_id,
        document_id=scope.document_id, target_role=scope.target_role,
        lease_id=uuid4(), lease_expires_at=NOW + 60,
        invitation_expires_at=NOW + 1600, attempts=1,
        outbox_status="HELD_CI_NOT_SENT", terminal_quarantine=False,
    )
    return lease, scope, sealed, catalog


def prepare(lease, scope, sealed, catalog, **changes):
    kwargs=dict(
        lease=lease, scope=scope, envelope=sealed,
        expected_recipient_digest=sha256(EMAIL.encode()).hexdigest(),
        catalog=catalog, provider=MockKeyProvider(), now=NOW+1,
        ttl_seconds=600,
    )
    kwargs.update(changes)
    return prepare_ci_email_challenge(**kwargs)


def receipt(scope, **changes):
    kwargs=dict(
        event_id=uuid4(), invitation_event_id=scope.event_id,
        kind="CI_SMTP_ACCEPTED", occurred_at=NOW+1,
        body_sha256="a"*64,
    )
    kwargs.update(changes)
    return VerifiedSyntheticReceipt(**kwargs)


def correlate(item, lease, scope, sealed, catalog, **changes):
    kwargs=dict(
        receipt=item, lease=lease, scope=scope, envelope=sealed,
        expected_recipient_digest=sha256(EMAIL.encode()).hexdigest(),
        catalog=catalog, provider=MockKeyProvider(), now=NOW+1,
    )
    kwargs.update(changes)
    return correlate_ci_receipt_to_sealed_outbox(**kwargs)


def test_challenge_token_has_384_bits_and_never_enters_sql_parameters_or_repr():
    lease, scope, sealed, catalog=fixture()
    first=prepare(lease, scope, sealed, catalog)
    second=prepare(lease, scope, sealed, catalog)
    assert first.raw_token_for_trusted_worker != second.raw_token_for_trusted_worker
    assert re.fullmatch(r"[A-Za-z0-9_-]{64}", first.raw_token_for_trusted_worker)
    assert first.challenge_digest == sha256(first.raw_token_for_trusted_worker.encode()).hexdigest()
    assert first.issue_sql_parameters() == (scope.event_id, first.challenge_digest, 600)
    assert first.expires_at == NOW+601
    assert first.raw_token_for_trusted_worker not in repr(first)
    assert "redacted=True" in repr(first)
    assert first.can_send_network is False
    assert first.recipient_verified is False
    assert first.account_activated is False
    assert first.contract_accepted is False


@pytest.mark.parametrize("ttl", [0, 59, 901, True, "600", None])
def test_untrusted_or_invalid_ttl_is_rejected(ttl):
    lease, scope, sealed, catalog=fixture()
    with pytest.raises(EmailChallengeBlocked, match="M27200_CHALLENGE_PREPARATION_BLOCKED"):
        prepare(lease, scope, sealed, catalog, ttl_seconds=ttl)


def test_challenge_ttl_must_fit_envelope_and_invitation():
    lease, scope, sealed, catalog=fixture()
    with pytest.raises(EmailChallengeBlocked):
        prepare(lease, replace(scope, expires_at=NOW+601), sealed, catalog)
    with pytest.raises(EmailChallengeBlocked):
        prepare(replace(lease, invitation_expires_at=NOW+601),
                scope, sealed, catalog)


def test_challenge_does_not_bypass_scope_key_or_tenant_checks():
    lease, scope, sealed, catalog=fixture()
    with pytest.raises(EmailChallengeBlocked):
        prepare(replace(lease, tenant_id=uuid4()), scope, sealed, catalog)
    with pytest.raises(EmailChallengeBlocked):
        prepare(replace(lease, terminal_quarantine=True), scope, sealed, catalog)
    with pytest.raises(EmailChallengeBlocked):
        prepare(lease, scope, sealed, catalog, expected_recipient_digest="0"*64)


@pytest.mark.parametrize("kind,expected", [
    ("CI_SMTP_ACCEPTED", "CI_SMTP_ACCEPTED_NOT_DELIVERED"),
    ("CI_BOUNCE", "CI_BOUNCE_QUARANTINE_REQUIRED"),
])
def test_mock_receipt_correlation_never_grants_delivery_or_activation(kind,expected):
    lease, scope, sealed, catalog=fixture()
    result=correlate(receipt(scope,kind=kind), lease, scope, sealed, catalog)
    assert result.status == expected
    assert result.durable_receipt_recorded is False
    assert result.provider_delivery_confirmed is False
    assert result.recipient_verified is False
    assert result.contract_accepted is False
    assert result.account_activated is False
    assert result.can_send_network is False


@pytest.mark.parametrize("change", [
    {"invitation_event_id":uuid4()},
    {"signature_authenticated_in_ci":False},
    {"provider_delivery_confirmed":True},
    {"recipient_verified":True},
    {"consent_recorded":True},
    {"user_activated":True},
    {"kind":"DELIVERED"},
    {"occurred_at":NOW-400},
    {"occurred_at":NOW+2},
    {"body_sha256":"invalid"},
])
def test_fake_unbound_or_privilege_escalating_receipt_is_rejected(change):
    lease, scope, sealed, catalog=fixture()
    with pytest.raises(ReceiptCorrelationBlocked, match="M27210_RECEIPT_CORRELATION_BLOCKED"):
        correlate(receipt(scope,**change), lease, scope, sealed, catalog)


def test_wrong_outbox_scope_or_digest_blocks_receipt():
    lease, scope, sealed, catalog=fixture()
    r=receipt(scope)
    with pytest.raises(ReceiptCorrelationBlocked):
        correlate(r, replace(lease,event_id=uuid4()), scope, sealed, catalog)
    with pytest.raises(ReceiptCorrelationBlocked):
        correlate(r, lease, scope, sealed, catalog, expected_recipient_digest="0"*64)


def test_bridge_is_offline_not_exposed_to_public_routes():
    root=Path(__file__).resolve().parents[2]
    for name in ("email_challenge_material.py","email_receipt_correlation.py"):
        source=(root/"backend/app"/name).read_text()
        for forbidden in ("smtplib", "requests.", "httpx.", "INSERT INTO",
                          "UPDATE public.", "CREATE USER", "send_message("):
            assert forbidden not in source
    for route in ("auth.py","invitations.py","master.py"):
        source=(root/"backend/app/routers"/route).read_text()
        assert "prepare_ci_email_challenge" not in source
        assert "correlate_ci_receipt_to_sealed_outbox" not in source
    workflow=(root/".github/workflows/validacao-atualizacao.yml").read_text()
    assert "test_m27200_email_bridge_ci.py" in workflow
