"""M37468 — CI-only historical receipt proof bound to M37467 frozen offer.

No public API and no production authorization. Reconciles the same synthetic
challenge/receipt/draft and a frozen price/document snapshot *after revocation*.
The SHA-256 fingerprint is diagnostic only, neither signed nor legal consent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Mapping
from uuid import UUID
import json

from .saas_post_commit_audit_ci import (
    POST_COMMIT_AUDIT_SQL, audit_post_commit_ci,
)

# All identifiers are supplied from the trusted CI server test harness,
# never a browser body. M37466 already checks contract/receipt/plan/session.
# An INNER JOIN fails closed if the frozen offer row is absent.
FROZEN_RECEIPT_AUDIT_SQL = """
SELECT h.*,
 q.request_id AS frozen_request_id,
 q.challenge_id AS frozen_challenge_id,
 q.session_id AS frozen_session_id,
 q.tenant_id AS frozen_tenant_id,
 q.admin_id AS frozen_admin_id,
 q.document_id AS frozen_document_id,
 q.document_sha AS frozen_document_sha,
 q.price_version_id AS frozen_price_version_id,
 q.billing_period AS frozen_billing_period,
 q.frozen_price_cents,
 q.recorded_at AS frozen_recorded_at,
 q.evidence_source AS frozen_evidence_source
FROM (
""" + POST_COMMIT_AUDIT_SQL + """
) h
JOIN public.saas_frozen_offer_m37467_ci q
 ON q.request_id=h.request_id
 AND q.challenge_id=h.challenge_id
 AND q.session_id=h.session_id
 AND q.tenant_id=h.tenant_id
 AND q.admin_id=h.admin_id
 AND q.document_id=h.document_id
 AND q.document_sha=h.document_sha
 AND q.price_version_id=h.price_version_id
 AND q.billing_period=h.billing_period
LIMIT 2
"""


@dataclass(frozen=True)
class HistoricalReceiptEvidenceCI:
    state: str
    historical_consistency: bool = False
    frozen_offer_consistent: bool = False
    issuer_session_revoked: bool = False
    diagnostic_sha256: str | None = None
    historical_price_cents: int | None = None
    synthetic_record_count: int = 0
    real_identity_verified: bool = False
    legal_consent_verified: bool = False
    payment_authorized: bool = False
    license_authorized: bool = False
    pix_authorized: bool = False
    activation_authorized: bool = False
    production_authorized: bool = False
    real_writes_performed: bool = False


def _time(x: object) -> bool:
    return (type(x) is datetime and x.tzinfo is not None
            and x.utcoffset() is not None)


def _uuid(x: object) -> bool:
    return type(x) is UUID and x.int != 0


def _cents(x: object) -> int | None:
    if type(x) is not Decimal or not x.is_finite():
        return None
    value = x * 100
    if (value != value.to_integral_value()
            or value <= 0 or value > 999_999_999_999):
        return None
    return int(value)


def verify_frozen_receipt_ci(
    row: dict | None, *,
    request_id: UUID, tenant_id: UUID, administrator_id: UUID,
    session_id: UUID, observed_at: datetime,
) -> HistoricalReceiptEvidenceCI:
    """Fail-closed historical readback; cannot authorize any future operation."""
    fail = lambda reason: HistoricalReceiptEvidenceCI(reason)
    if (type(row) is not dict or not all(
            _uuid(x) for x in (request_id, tenant_id, administrator_id, session_id))
            or not _time(observed_at)):
        return fail("CI_FROZEN_AUDIT_INVALID_INPUT")

    prior = audit_post_commit_ci(
        row, request_id=request_id, tenant_id=tenant_id,
        administrator_id=administrator_id, session_id=session_id,
        observed_at=observed_at,
    )
    if (not prior.historical_consistency
            or prior.state != "CI_POST_COMMIT_SYNTHETIC_HISTORY_CONSISTENT_NOT_AUTHORITY"
            or prior.synthetic_record_count != 3
            or not prior.issuer_session_revoked
            or type(prior.evidence_sha256) is not str):
        return fail("CI_FROZEN_AUDIT_PREVIOUS_HISTORY_INVALID")

    links = {
        "frozen_request_id": request_id,
        "frozen_challenge_id": row["challenge_id"],
        "frozen_session_id": session_id,
        "frozen_tenant_id": tenant_id,
        "frozen_admin_id": administrator_id,
        "frozen_document_id": row["document_id"],
        "frozen_price_version_id": row["price_version_id"],
    }
    try:
        if any(
            not _uuid(row[k]) or row[k] != expected
            for k, expected in links.items()
        ):
            return fail("CI_FROZEN_AUDIT_SCOPE_MISMATCH")
        if (type(row["frozen_document_sha"]) is not str
                or row["frozen_document_sha"] != row["document_sha"]
                or row["frozen_document_sha"] != row["receipt_sha"]
                or row["frozen_document_sha"] != row["published_sha"]
                or row["frozen_billing_period"] != row["billing_period"]
                or row["frozen_billing_period"] != row["receipt_period"]
                or row["frozen_billing_period"] != row["draft_period"]
                or row["frozen_evidence_source"]
                    != "CI_FROZEN_SYNTHETIC_NOT_LEGAL"):
            return fail("CI_FROZEN_AUDIT_DOCUMENT_OR_PERIOD_MISMATCH")
        if (not _time(row["frozen_recorded_at"])
                or not (row["challenge_issued_at"]
                        <= row["frozen_recorded_at"]
                        <= row["server_recorded_at"]
                        <= row["server_prepared_at"]
                        <= row["live_revoked_at"]
                        <= observed_at)):
            return fail("CI_FROZEN_AUDIT_CHRONOLOGY_INVALID")
        frozen_amount = row["frozen_price_cents"]
        if (type(frozen_amount) is not int
                or not 0 < frozen_amount <= 999_999_999_999):
            return fail("CI_FROZEN_AUDIT_PRICE_INVALID")
        monthly = _cents(row["monthly_price"])
        annual = _cents(row["annual_price"])
        if monthly is None or annual is None or annual != monthly * 10:
            return fail("CI_FROZEN_AUDIT_CURRENT_PRICE_MALFORMED")
        expected_amount = (
            monthly if row["billing_period"] == "MONTHLY" else annual
        )
        if frozen_amount != expected_amount:
            return fail("CI_FROZEN_AUDIT_PRICE_CHANGED")
        payload = {
            "scope": "M37468_SYNTHETIC_HISTORICAL_NOT_AUTHORITY",
            "baseline": prior.evidence_sha256,
            "request_id": str(request_id),
            "challenge_id": str(row["frozen_challenge_id"]),
            "session_id": str(session_id),
            "tenant_id": str(tenant_id),
            "administrator_id": str(administrator_id),
            "document_id": str(row["frozen_document_id"]),
            "document_sha256": row["frozen_document_sha"],
            "price_version_id": str(row["frozen_price_version_id"]),
            "billing_period": row["frozen_billing_period"],
            "frozen_price_cents": frozen_amount,
            "frozen_recorded_at":
                row["frozen_recorded_at"].astimezone(timezone.utc).isoformat(),
        }
        digest = sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii")).hexdigest()
        return HistoricalReceiptEvidenceCI(
            state="CI_FROZEN_RECEIPT_HISTORY_CONSISTENT_NOT_AUTHORITY",
            historical_consistency=True,
            frozen_offer_consistent=True,
            issuer_session_revoked=True,
            diagnostic_sha256=digest,
            historical_price_cents=frozen_amount,
            synthetic_record_count=4,
        )
    except (KeyError, ValueError, TypeError, OverflowError):
        return fail("CI_FROZEN_AUDIT_MALFORMED_DATABASE_ROW")


def historical_receipt_view_ci(
    evidence: HistoricalReceiptEvidenceCI,
    *, env: Mapping[str, str],
) -> dict[str, object]:
    """Non-HTTP, server-only CI summary. No bearer / claim / grant is emitted."""
    if (type(evidence) is not HistoricalReceiptEvidenceCI
            or env.get("GITHUB_ACTIONS") != "true"
            or env.get("FRCAIXINHA_CI_ISOLATED") != "1"
            or env.get("ENVIRONMENT") != "ci"
            or env.get("FR_FINANCE_SAAS_REAL") != "OFF"
            or env.get("FR_FINANCE_PIX_REAL") != "OFF"
            or env.get("FR_FINANCE_LICENSE_REAL", "OFF") != "OFF"
            or not evidence.historical_consistency
            or not evidence.frozen_offer_consistent
            or not evidence.issuer_session_revoked
            or evidence.state
                != "CI_FROZEN_RECEIPT_HISTORY_CONSISTENT_NOT_AUTHORITY"
            or any((
                evidence.real_identity_verified,
                evidence.legal_consent_verified,
                evidence.payment_authorized,
                evidence.license_authorized,
                evidence.pix_authorized,
                evidence.activation_authorized,
                evidence.production_authorized,
                evidence.real_writes_performed,
            ))):
        return {"state": "CI_HISTORICAL_READBACK_UNAVAILABLE"}
    return {
        "state": evidence.state,
        "kind": "CI_SYNTHETIC_HISTORICAL_ONLY",
        "synthetic_record_count": evidence.synthetic_record_count,
        "diagnostic_sha256": evidence.diagnostic_sha256,
        "historical_price_cents": evidence.historical_price_cents,
        "real_authorization": False,
    }
