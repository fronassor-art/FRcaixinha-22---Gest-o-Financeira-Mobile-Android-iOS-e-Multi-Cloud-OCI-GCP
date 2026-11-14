"""FR Finance M38070-M38089: read-only persisted outbox evidence vetoes resend."""
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.onboarding_delivery_decision import (
    AttemptContext, DecisionBlocked, DeliveryDisposition,
    PersistedOutboxEvidence, SubmissionEvidence,
    decide_delivery_with_outbox_evidence,
)

def fixture(*, attempt=1, started=False, kinds=(), terminal=None):
    context=AttemptContext(uuid4(),uuid4(),attempt,started)
    persisted=PersistedOutboxEvidence(
        event_id=context.event_id,lease_id=context.lease_id,
        recorded_receipt_kinds=kinds,terminal_state=terminal,
    )
    return context,persisted

def decide(context,persisted,evidence=SubmissionEvidence.PREFLIGHT_FAILED_BEFORE_NETWORK):
    return decide_delivery_with_outbox_evidence(
        context=context,evidence=evidence,persisted=persisted)

@pytest.mark.parametrize("attempt",[1,2])
def test_only_empty_history_may_request_separate_guarded_lease(attempt):
    ctx,snapshot=fixture(attempt=attempt)
    outcome=decide(ctx,snapshot)
    assert outcome.disposition is DeliveryDisposition.PRESUBMIT_RETRY_CANDIDATE
    assert outcome.may_request_new_lease_after_recheck
    assert not outcome.can_auto_retry
    assert not outcome.provider_delivery_confirmed
    assert not outcome.recipient_verified
    assert not outcome.consent_recorded
    assert not outcome.account_activated
    assert not outcome.public_delivery_enabled

def test_exhaustion_without_receipts_still_blocks():
    ctx,snapshot=fixture(attempt=3)
    outcome=decide(ctx,snapshot)
    assert outcome.disposition is DeliveryDisposition.EXHAUSTED_NO_RETRY
    assert not outcome.may_request_new_lease_after_recheck

@pytest.mark.parametrize("receipts,expected",[
    (("CI_SMTP_ACCEPTED",),DeliveryDisposition.SMTP_ACCEPTED_NO_DELIVERY_PROOF),
    (("CI_BOUNCE",),DeliveryDisposition.BOUNCED_REVIEW_NO_RETRY),
    (("CI_SMTP_ACCEPTED","CI_BOUNCE"),DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY),
    (("CI_SMTP_ACCEPTED","CI_SMTP_ACCEPTED"),DeliveryDisposition.SMTP_ACCEPTED_NO_DELIVERY_PROOF),
    (("CI_BOUNCE","CI_BOUNCE"),DeliveryDisposition.BOUNCED_REVIEW_NO_RETRY),
])
@pytest.mark.parametrize("attempt",[1,2,3])
def test_historic_receipt_always_vetoes_another_send(receipts,expected,attempt):
    ctx,snapshot=fixture(attempt=attempt,kinds=receipts)
    outcome=decide(ctx,snapshot)
    assert outcome.disposition is expected
    assert not outcome.may_request_new_lease_after_recheck
    assert not outcome.can_auto_retry
    assert not outcome.provider_delivery_confirmed
    assert not outcome.recipient_verified
    assert not outcome.consent_recorded
    assert not outcome.account_activated

@pytest.mark.parametrize("terminal,receipt,expected",[
    ("CI_UNKNOWN_TIMEOUT_QUARANTINE",(),DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY),
    ("CI_UNKNOWN_TIMEOUT_QUARANTINE",("CI_SMTP_ACCEPTED",),DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY),
    ("CI_SMTP_ACCEPTED_UNVERIFIED",("CI_SMTP_ACCEPTED",),DeliveryDisposition.SMTP_ACCEPTED_NO_DELIVERY_PROOF),
    ("CI_BOUNCED_REQUIRES_REVIEW",("CI_BOUNCE",),DeliveryDisposition.BOUNCED_REVIEW_NO_RETRY),
    ("CI_SMTP_ACCEPTED_UNVERIFIED",(),DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY),
    ("CI_BOUNCED_REQUIRES_REVIEW",(),DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY),
    ("CI_SMTP_ACCEPTED_UNVERIFIED",("CI_BOUNCE",),DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY),
    ("CI_BOUNCED_REQUIRES_REVIEW",("CI_SMTP_ACCEPTED",),DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY),
])
def test_terminal_states_reject_retries_even_when_current_evidence_is_preflight(terminal,receipt,expected):
    ctx,snapshot=fixture(kinds=receipt,terminal=terminal)
    outcome=decide(ctx,snapshot)
    assert outcome.disposition is expected
    assert not outcome.may_request_new_lease_after_recheck
    assert not outcome.can_auto_retry

@pytest.mark.parametrize("field,value",[
    ("event_id",uuid4()),
    ("lease_id",uuid4()),
    ("event_id",UUID(int=0)),
    ("lease_id",UUID(int=0)),
    ("event_id","uuid"),
    ("lease_id",False),
    ("recorded_receipt_kinds",["CI_SMTP_ACCEPTED"]),
    ("recorded_receipt_kinds",None),
    ("recorded_receipt_kinds",("CI_DELIVERED",)),
    ("recorded_receipt_kinds",("CI_SMTP_ACCEPTED",None)),
    ("recorded_receipt_kinds",("CI_SMTP_ACCEPTED",)*17),
    ("terminal_state","DELIVERED"),
    ("terminal_state",False),
])
def test_malformed_or_wrong_lease_snapshot_is_rejected(field,value):
    ctx,snapshot=fixture()
    with pytest.raises(DecisionBlocked,match="M38070_INVALID_PERSISTED_OUTBOX_EVIDENCE"):
        decide(ctx,replace(snapshot,**{field:value}))

@pytest.mark.parametrize("evidence,started",[
    (SubmissionEvidence.SMTP_ACCEPTED_UNVERIFIED,False),
    (SubmissionEvidence.AUTHENTICATED_CI_BOUNCE,False),
])
def test_inconsistent_current_evidence_cannot_be_made_valid_by_receipt(evidence,started):
    ctx,snapshot=fixture(kinds=("CI_SMTP_ACCEPTED",),started=started)
    with pytest.raises(DecisionBlocked):
        decide(ctx,snapshot,evidence)

@pytest.mark.parametrize("evidence",[
    SubmissionEvidence.SUBMISSION_TIMEOUT_UNKNOWN,
    SubmissionEvidence.SMTP_ACCEPTED_UNVERIFIED,
    SubmissionEvidence.AUTHENTICATED_CI_BOUNCE,
])
def test_current_network_evidence_does_not_allow_auto_retry(evidence):
    ctx,snapshot=fixture(started=True)
    outcome=decide(ctx,snapshot,evidence)
    assert not outcome.can_auto_retry
    assert not outcome.may_request_new_lease_after_recheck

def test_requires_persisted_snapshot_from_trusted_worker_and_never_dispatches():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/app/onboarding_delivery_decision.py").read_text()
    assert "def decide_delivery_with_outbox_evidence(" in src
    assert "persisted: PersistedOutboxEvidence" in src
    assert "persisted.event_id != context.event_id" in src
    assert "persisted.lease_id != context.lease_id" in src
    assert "recorded_receipt_kinds" in src and "terminal_state" in src
    assert "return baseline" in src
    for forbidden in ("smtplib","submit_access_message(","INSERT INTO","UPDATE public.",
                      "requests.post(","httpx.post(","os.environ["):
        assert forbidden not in src
    for name in ("invitations.py","auth.py"):
        api=(root/"backend/app/routers"/name).read_text()
        assert "decide_delivery_with_outbox_evidence" not in api

def test_sql_terminal_gate_and_receipt_proofs_are_staging_only():
    root=Path(__file__).resolve().parents[2]
    terminal=(root/"backend/staging_migrations/054_invite_delivery_terminal_gate_staging_only.sql").read_text()
    receipt=(root/"backend/staging_migrations/053_mail_receipt_audit_staging_only.sql").read_text()
    assert "frcaixinha_staging" in terminal and "frcaixinha_staging" in receipt
    assert "CI_UNKNOWN_TIMEOUT_QUARANTINE" in terminal
    assert "CI_SMTP_ACCEPTED_UNVERIFIED" in terminal
    assert "CI_BOUNCED_REQUIRES_REVIEW" in terminal
    assert "CI_SMTP_ACCEPTED" in receipt and "CI_BOUNCE" in receipt
    assert "provider_delivery_confirmed=false" in terminal
    assert "recipient_verified=false" in receipt
