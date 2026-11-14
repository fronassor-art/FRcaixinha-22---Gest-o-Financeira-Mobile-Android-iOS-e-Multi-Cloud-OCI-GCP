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


# M38070-M38089: supplemental *read-only* durable receipt snapshot check.
# The caller must fetch this from independently authenticated, tenant-scoped
# PostgreSQL (not an HTTP/client-supplied object). This module cannot attest
# its provenance, grant a lease, access a database or send an email.
@dataclass(frozen=True)
class PersistedOutboxEvidence:
    event_id: UUID
    lease_id: UUID
    recorded_receipt_kinds: tuple[str, ...]
    terminal_state: str | None


_RECEIPT_STATES = frozenset(("CI_SMTP_ACCEPTED", "CI_BOUNCE"))
_TERMINAL_STATES = frozenset((
    "CI_UNKNOWN_TIMEOUT_QUARANTINE",
    "CI_SMTP_ACCEPTED_UNVERIFIED",
    "CI_BOUNCED_REQUIRES_REVIEW",
))


def decide_delivery_with_outbox_evidence(
    *, context: AttemptContext,
    evidence: SubmissionEvidence,
    persisted: PersistedOutboxEvidence,
) -> DeliveryDecision:
    """Never request another lease when any prior receipt or terminal exists.

    The snapshot must cover the complete outbox history, including previous
    leases, and be loaded under a trusted transaction lock. Receipt presence
    is never treated as inbox-delivery, consent, or account-activation proof.
    """
    # Preserve all original malformed attempt / inconsistent SMTP evidence
    # errors before considering any external persisted snapshot.
    baseline = decide_delivery(context=context, evidence=evidence)
    if (
        type(persisted) is not PersistedOutboxEvidence
        or type(persisted.event_id) is not UUID or persisted.event_id.int == 0
        or type(persisted.lease_id) is not UUID or persisted.lease_id.int == 0
        or persisted.event_id != context.event_id
        or persisted.lease_id != context.lease_id
        or type(persisted.recorded_receipt_kinds) is not tuple
        or len(persisted.recorded_receipt_kinds) > 16
        or any(type(kind) is not str or kind not in _RECEIPT_STATES
               for kind in persisted.recorded_receipt_kinds)
        or (persisted.terminal_state is not None and (
            type(persisted.terminal_state) is not str
            or persisted.terminal_state not in _TERMINAL_STATES
        ))
    ):
        raise DecisionBlocked("M38070_INVALID_PERSISTED_OUTBOX_EVIDENCE")
    kinds = frozenset(persisted.recorded_receipt_kinds)
    terminal = persisted.terminal_state
    if len(kinds) > 1:
        return DeliveryDecision(DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY)
    if terminal == "CI_UNKNOWN_TIMEOUT_QUARANTINE":
        return DeliveryDecision(DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY)
    if terminal == "CI_SMTP_ACCEPTED_UNVERIFIED":
        if kinds != {"CI_SMTP_ACCEPTED"}:
            return DeliveryDecision(DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY)
        return DeliveryDecision(DeliveryDisposition.SMTP_ACCEPTED_NO_DELIVERY_PROOF)
    if terminal == "CI_BOUNCED_REQUIRES_REVIEW":
        if kinds != {"CI_BOUNCE"}:
            return DeliveryDecision(DeliveryDisposition.QUARANTINED_UNKNOWN_NO_RETRY)
        return DeliveryDecision(DeliveryDisposition.BOUNCED_REVIEW_NO_RETRY)
    if "CI_SMTP_ACCEPTED" in kinds:
        return DeliveryDecision(DeliveryDisposition.SMTP_ACCEPTED_NO_DELIVERY_PROOF)
    if "CI_BOUNCE" in kinds:
        return DeliveryDecision(DeliveryDisposition.BOUNCED_REVIEW_NO_RETRY)
    # No receipt or terminal was found in a trusted ledger snapshot.
    # Baseline still only grants *consideration* for another guarded lease.
    return baseline
