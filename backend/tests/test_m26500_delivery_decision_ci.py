"""M26500 — timeout/unknown SMTP ACK never authorizes a duplicate send."""
from dataclasses import replace
from uuid import uuid4

import pytest

from app.onboarding_delivery_decision import (
    AttemptContext, DecisionBlocked, DeliveryDisposition, SubmissionEvidence,
    decide_delivery,
)


def context(attempt=1, started=True):
    return AttemptContext(uuid4(), uuid4(), attempt, started)


@pytest.mark.parametrize("attempt",[1,2,3])
def test_ambiguous_submission_quarantined_for_all_attempt_counts(attempt):
    for started in (True,False):
        result=decide_delivery(
            context=context(attempt,started),evidence=SubmissionEvidence.SUBMISSION_TIMEOUT_UNKNOWN,
        )
        assert result.disposition == DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY
        assert result.can_auto_retry is False
        assert result.may_request_new_lease_after_recheck is False


def test_smtp_accepted_is_not_delivery_or_verification():
    result=decide_delivery(
        context=context(1,True),evidence=SubmissionEvidence.SMTP_ACCEPTED_UNVERIFIED,
    )
    assert result.disposition==DeliveryDisposition.SMTP_ACCEPTED_NO_DELIVERY_PROOF
    assert result.can_auto_retry is False
    assert result.provider_delivery_confirmed is False
    assert result.recipient_verified is False
    assert result.consent_recorded is False
    assert result.account_activated is False
    assert result.public_delivery_enabled is False


def test_authentic_ci_bounce_requires_manual_review():
    result=decide_delivery(
        context=context(1,True),evidence=SubmissionEvidence.AUTHENTICATED_CI_BOUNCE,
    )
    assert result.disposition==DeliveryDisposition.BOUNCED_REVIEW_NO_RETRY
    assert not result.can_auto_retry
    assert not result.recipient_verified


@pytest.mark.parametrize("attempt",[1,2])
def test_verified_presubmit_failure_is_only_candidate_for_new_lease(attempt):
    result=decide_delivery(
        context=context(attempt,False),
        evidence=SubmissionEvidence.PREFLIGHT_FAILED_BEFORE_NETWORK,
    )
    assert result.disposition==DeliveryDisposition.PRESUBMIT_RETRY_CANDIDATE
    assert not result.can_auto_retry
    assert result.may_request_new_lease_after_recheck
    assert not result.provider_delivery_confirmed


def test_three_presubmit_failures_are_exhausted():
    result=decide_delivery(
        context=context(3,False),
        evidence=SubmissionEvidence.PREFLIGHT_FAILED_BEFORE_NETWORK,
    )
    assert result.disposition==DeliveryDisposition.EXHAUSTED_NO_RETRY
    assert not result.may_request_new_lease_after_recheck


def test_preflight_failure_after_network_must_be_quarantined():
    result=decide_delivery(
        context=context(1,True),
        evidence=SubmissionEvidence.PREFLIGHT_FAILED_BEFORE_NETWORK,
    )
    assert result.disposition==DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY


@pytest.mark.parametrize("evidence",[
    SubmissionEvidence.SMTP_ACCEPTED_UNVERIFIED,
    SubmissionEvidence.AUTHENTICATED_CI_BOUNCE,
])
def test_provider_ack_without_started_submission_is_inconsistent(evidence):
    with pytest.raises(DecisionBlocked):
        decide_delivery(context=context(1,False),evidence=evidence)


@pytest.mark.parametrize("bad_attempt",[0,-1,4,True,"1",None])
def test_bad_attempt_number_not_accepted(bad_attempt):
    with pytest.raises(DecisionBlocked):
        decide_delivery(
            context=replace(context(1,True),attempt_number=bad_attempt),
            evidence=SubmissionEvidence.SMTP_ACCEPTED_UNVERIFIED,
        )


@pytest.mark.parametrize("bad_evidence",["SMTP_ACCEPTED_UNVERIFIED",None,True,123,[]])
def test_evidence_must_be_typed_and_never_client_controlled(bad_evidence):
    with pytest.raises(DecisionBlocked):
        decide_delivery(context=context(1,True),evidence=bad_evidence)


def test_invalid_uuid_context_is_blocked():
    from uuid import UUID
    for attr in ("event_id","lease_id"):
        with pytest.raises(DecisionBlocked):
            decide_delivery(context=replace(context(),**{attr:UUID(int=0)}),
                            evidence=SubmissionEvidence.SUBMISSION_TIMEOUT_UNKNOWN)


def test_module_has_no_direct_smtp_or_database_write():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    source=(root/"backend/app/onboarding_delivery_decision.py").read_text()
    for unsafe in ("smtplib", "asyncpg", "INSERT INTO", "UPDATE public.",
                   "submit_access_message(", "request.post(", "localStorage"):
        assert unsafe not in source
    for name in ("invitations.py","auth.py"):
        route=(root/"backend/app/routers"/name).read_text()
        assert "decide_delivery" not in route
