"""M37459 CI-only contract for a future authenticated SaaS acceptance API.

Not mounted in FastAPI, not a live session verifier, not a legal consent
collector, and not a billing/entitlement API. Every identity/offer is
provided by the TEST HARNESS as a server-readback fixture. No network or DB.
Never trust a browser-constructed CIPrincipal or CIPublishedOffer in prod.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping, Protocol
from uuid import UUID
import re

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CONFIRM = "ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
_ALLOWED_ACTIONS = frozenset(("ISSUE","ACCEPT","PREPARE"))
_ALLOWED_FIELDS = frozenset(("action","request_id","challenge_id","confirmation"))
_MAX_CHECK_AGE = timedelta(minutes=5)


@dataclass(frozen=True, kw_only=True)
class CIPrincipal:
    user_id: UUID
    tenant_id: UUID
    session_id: UUID
    active_role: str
    active: bool
    email_verified: bool
    server_checked_at: datetime
    expires_at: datetime
    source: str = "CI_SYNTHETIC_SERVER_AUTH_READBACK"


@dataclass(frozen=True, kw_only=True)
class CIPublishedOffer:
    tenant_id: UUID
    document_id: UUID
    document_sha256: str
    price_version_id: UUID
    billing_period: str
    price_cents: int
    published_at: datetime
    state: str
    source: str = "CI_SYNTHETIC_SERVER_OFFER_READBACK"


@dataclass(frozen=True)
class CITransition:
    state: str


class CIDisposableExecutor(Protocol):
    """Only implemented by disposable/isolated regression test adapters."""
    def transition(
        self, *, action: str, request_id: UUID, challenge_id: UUID,
        principal: CIPrincipal, offer: CIPublishedOffer, confirmation: str | None,
    ) -> CITransition: ...


@dataclass(frozen=True)
class APIContractDecision:
    status_code: int
    state: str
    hypothetical_consistency_only: bool = False
    real_identity_verified: bool = False
    legal_consent_verified: bool = False
    payment_authorized: bool = False
    license_authorized: bool = False
    pix_authorized: bool = False
    real_activation_authorized: bool = False
    production_authorized: bool = False
    real_writes_performed: bool = False


def environment_allowed(env: Mapping[str, str]) -> bool:
    return (
        env.get("GITHUB_ACTIONS") == "true"
        and env.get("FRCAIXINHA_CI_ISOLATED") == "1"
        and env.get("ENVIRONMENT") == "ci"
        and env.get("FR_FINANCE_SAAS_REAL") == "OFF"
        and env.get("FR_FINANCE_PIX_REAL") == "OFF"
    )


def _uuid(value: object) -> UUID | None:
    # Canonical lower-case representation; reject nil and wrong UUID types.
    if type(value) is not str or len(value) != 36:
        return None
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return None
    return parsed if parsed.int and str(parsed) == value else None


def _trusted_uuid(value: object) -> bool:
    return type(value) is UUID and value.int != 0


def _time(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def evaluate_api_contract_ci(
    *, body: Mapping[str, object], principal: CIPrincipal,
    offer: CIPublishedOffer, challenge_id_server: UUID,
    request_id_server: UUID, executor: CIDisposableExecutor | None,
    env: Mapping[str, str], now: datetime,
) -> APIContractDecision:
    denied = APIContractDecision
    # The feature cannot be enabled by adding a bearer token, HTTP header,
    # user controlled role, or environment variable in a client request.
    if not environment_allowed(env):
        return denied(503,"CI_CONTRACT_NOT_AVAILABLE")
    if (type(body) is not dict or not _time(now)
        or type(principal) is not CIPrincipal
        or type(offer) is not CIPublishedOffer
        or not _trusted_uuid(challenge_id_server)
        or not _trusted_uuid(request_id_server)):
        return denied(400,"INVALID_TYPED_REQUEST")
    if not body.keys() <= _ALLOWED_FIELDS or type(body.get("action")) is not str:
        return denied(400,"UNEXPECTED_OR_MISSING_CLIENT_FIELD")
    action = body["action"]
    if action not in _ALLOWED_ACTIONS:
        return denied(400,"INVALID_ACTION")
    # ISSUE never accepts a client-generated challenge or identity; that ID
    # is derived by the server and included in later ACCEPT/PREPARE calls.
    expected_fields = {
        "ISSUE": frozenset(("action","request_id")),
        "ACCEPT": frozenset(("action","request_id","challenge_id","confirmation")),
        "PREPARE": frozenset(("action","request_id","challenge_id")),
    }[action]
    if set(body) != expected_fields:
        return denied(400,"UNEXPECTED_OR_MISSING_CLIENT_FIELD")
    request_id = _uuid(body["request_id"])
    challenge_id = (_uuid(body["challenge_id"]) if action != "ISSUE"
                    else challenge_id_server)
    if request_id is None or challenge_id is None:
        return denied(400,"INVALID_CLIENT_IDENTIFIERS")
    # CI-only application callback compares IDs to server generated values.
    if request_id != request_id_server or challenge_id != challenge_id_server:
        return denied(403,"SERVER_CHALLENGE_OR_REQUEST_MISMATCH")
    confirmation = body.get("confirmation")
    if action == "ACCEPT" and (
            type(confirmation) is not str or confirmation != _CONFIRM):
        return denied(422,"EXPLICIT_CONTRACT_CONFIRMATION_REQUIRED")

    if (principal.source != "CI_SYNTHETIC_SERVER_AUTH_READBACK"
        or offer.source != "CI_SYNTHETIC_SERVER_OFFER_READBACK"):
        return denied(403,"UNTRUSTED_SERVER_READBACK")
    if (not all(_trusted_uuid(x) for x in (
            principal.user_id,principal.tenant_id,principal.session_id,
            offer.tenant_id,offer.document_id,offer.price_version_id))
        or not all(_time(t) for t in (
            principal.server_checked_at,principal.expires_at,offer.published_at))
        or any(type(v) is not bool for v in (
            principal.active,principal.email_verified))
        or type(offer.price_cents) is not int
        or not 0 < offer.price_cents <= 999999999999
        or type(offer.document_sha256) is not str
        or _HASH.fullmatch(offer.document_sha256) is None):
        return denied(403,"MALFORMED_SERVER_CLAIMS")
    if (principal.tenant_id != offer.tenant_id
        or not principal.active or not principal.email_verified
        or principal.active_role != "TENANT_ADMIN"):
        return denied(403,"UNAUTHORIZED_TENANT_ADMIN")
    if (not principal.server_checked_at <= now < principal.expires_at
        or now-principal.server_checked_at > _MAX_CHECK_AGE):
        return denied(401,"SESSION_MUST_BE_REVERIFIED")
    if (offer.state != "ACTIVE"
        or offer.billing_period not in ("MONTHLY","ANNUAL")
        or offer.published_at > principal.server_checked_at):
        return denied(409,"PUBLISHED_OFFER_NOT_CURRENT")
    if executor is None:
        return denied(503,"CI_DISPOSABLE_EXECUTOR_REQUIRED")
    # Do not catch, reclassify or suppress unknown executor errors as success.
    try:
        outcome = executor.transition(
            action=action,request_id=request_id,challenge_id=challenge_id,
            principal=principal,offer=offer,
            confirmation=confirmation if action=="ACCEPT" else None,
        )
    except Exception:
        return denied(503,"CI_EXECUTOR_FAILED_CLOSED")
    if type(outcome) is not CITransition:
        return denied(503,"CI_EXECUTOR_INVALID_RESPONSE")
    accepted = {
        "ISSUE": frozenset(("CHALLENGE_ISSUED_CI","REPLAY_ISSUE_CI_NO_WRITE")),
        "ACCEPT": frozenset(("CONSENT_RECORDED_CI_NO_LEGAL_PROOF","REPLAY_ACCEPT_CI_NO_WRITE")),
        "PREPARE": frozenset(("DRAFT_PREPARED_CI_NO_PAYMENT","REPLAY_PREPARE_CI_NO_WRITE")),
    }[action]
    if outcome.state in accepted:
        return denied(202,"CI_"+outcome.state,True)
    if outcome.state in (
        "DENIED_CI","CONSENT_BEFORE_PREPARATION_REQUIRED",
        "CHALLENGE_COLLISION_CI_DENIED","CONSENT_COLLISION_CI_DENIED",
        "DRAFT_COLLISION_CI_DENIED",
    ):
        return denied(409,"CI_TRANSACTION_DENIED")
    return denied(503,"CI_UNEXPECTED_EXECUTOR_STATE")
