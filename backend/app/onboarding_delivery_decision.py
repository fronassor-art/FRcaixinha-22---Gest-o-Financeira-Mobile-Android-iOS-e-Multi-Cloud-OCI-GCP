"""M26500 — fail-closed policy for uncertain SMTP or provider responses.

Pure contract for future durable worker. Never retries after a possible send;
SMTP acceptance is NOT delivery, recipient verification or consent. No public
routes, network calls, database changes or activation toggles are included.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class DecisionBlocked(ValueError):
    pass


class SubmissionEvidence(str, Enum):
    PREFLIGHT_FAILED_BEFORE_NETWORK = "PREFLIGHT_FAILED_BEFORE_NETWORK"
    SMTP_ACCEPTED_UNVERIFIED = "SMTP_ACCEPTED_UNVERIFIED"
    SUBMISSION_TIMEOUT_UNKNOWN = "SUBMISSION_TIMEOUT_UNKNOWN"
    AUTHENTICATED_CI_BOUNCE = "AUTHENTICATED_CI_BOUNCE"


class DeliveryDisposition(str, Enum):
    REQUIRE_MANUAL_PREFLIGHT = "REQUIRE_MANUAL_PREFLIGHT"
    PRESUBMIT_RETRY_CANDIDATE = "PRESUBMIT_RETRY_CANDIDATE"
    SMTP_ACCEPTED_NO_DELIVERY_PROOF = "SMTP_ACCEPTED_NO_DELIVERY_PROOF"
    QUARANTINED_UNKNOWN_NO_RETRY = "QUARANTINED_UNKNOWN_NO_RETRY"
    BOUNCED_REVIEW_NO_RETRY = "BOUNCED_REVIEW_NO_RETRY"
    EXHAUSTED_NO_RETRY = "EXHAUSTED_NO_RETRY"


@dataclass(frozen=True)
class AttemptContext:
    event_id: UUID
    lease_id: UUID
    attempt_number: int
    submission_started: bool


@dataclass(frozen=True)
class DeliveryDecision:
    disposition: DeliveryDisposition
    can_auto_retry: bool = False
    may_request_new_lease_after_recheck: bool = False
    provider_delivery_confirmed: bool = False
    recipient_verified: bool = False
    consent_recorded: bool = False
    account_activated: bool = False
    public_delivery_enabled: bool = False


def decide_delivery(
    *, context: AttemptContext,
    evidence: SubmissionEvidence,
) -> DeliveryDecision:
    """Classify only audited local evidence; no token, email or secret needed.

    A claim that the submission never started must be independently proven by
    the transport worker, not accepted from an API request or end user.
    A pre-send retry is only a *candidate* for a new guarded DB lease.
    """
    if (not isinstance(context, AttemptContext)
            or not isinstance(context.event_id, UUID)
            or context.event_id.int == 0
            or not isinstance(context.lease_id, UUID)
            or context.lease_id.int == 0
            or type(context.attempt_number) is not int
            or not 1 <= context.attempt_number <= 3
            or type(context.submission_started) is not bool
            or not isinstance(evidence, SubmissionEvidence)):
        raise DecisionBlocked("M26500_INVALID_ATTEMPT")

    if evidence is SubmissionEvidence.PREFLIGHT_FAILED_BEFORE_NETWORK:
        if context.submission_started:
            return DeliveryDecision(DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY)
        if context.attempt_number == 3:
            return DeliveryDecision(DeliveryDisposition.EXHAUSTED_NO_RETRY)
        return DeliveryDecision(
            DeliveryDisposition.PRESUBMIT_RETRY_CANDIDATE,
            may_request_new_lease_after_recheck=True,
        )

    if evidence is SubmissionEvidence.SMTP_ACCEPTED_UNVERIFIED:
        if not context.submission_started:
            raise DecisionBlocked("M26500_INCONSISTENT_EVIDENCE")
        return DeliveryDecision(DeliveryDisposition.SMTP_ACCEPTED_NO_DELIVERY_PROOF)

    if evidence is SubmissionEvidence.SUBMISSION_TIMEOUT_UNKNOWN:
        # Even if transport claims it has not sent yet, an ambiguous failure
        # cannot be used to prove no bytes reached the provider.
        return DeliveryDecision(DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY)

    if evidence is SubmissionEvidence.AUTHENTICATED_CI_BOUNCE:
        if not context.submission_started:
            raise DecisionBlocked("M26500_INCONSISTENT_EVIDENCE")
        return DeliveryDecision(DeliveryDisposition.BOUNCED_REVIEW_NO_RETRY)
    raise DecisionBlocked("M26500_INVALID_EVIDENCE")
