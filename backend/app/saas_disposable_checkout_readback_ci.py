"""M37453: PostgreSQL disposable SaaS preparation readback, CI-only.

Reads committed staging fixtures, without a public route, billing, entitlement
or network provider call. CI labels on acceptance records are NOT independently
validated legal consent; a consistent preparation remains NOT operational.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID
import re

_SHA = re.compile(r"[a-f0-9]{64}\Z")

# This query is deliberately tied to the M30900 disposable staging schema.
# SQL bind parameters must be supplied by the guarded CI entrypoint.
READBACK_SQL = """
SELECT
 e.request_id, e.tenant_id, e.admin_user_id, e.price_version_id,
 e.contract_acceptance_id, e.billing_period, e.preparation_id,
 e.payment_created, e.entitlement_created,
 s.tenant_id AS prepared_tenant, s.admin_user_id AS prepared_admin,
 s.price_version_id AS prepared_price, s.contract_acceptance_id AS prepared_acceptance,
 s.billing_period AS prepared_period, s.plan_tier AS prepared_tier,
 s.status AS preparation_status, s.created_at AS prepared_at,
 a.document_id AS accepted_document_id, a.user_id AS accepted_by,
 a.tenant_id AS accepted_tenant, a.document_kind AS accepted_kind,
 a.accepted_at, a.evidence_method, a.evidence_hash,
 d.id AS published_document_id, d.document_kind AS published_kind,
 d.published_at, d.sha256 AS published_sha,
 v.id AS version_id, v.plan_tier AS version_tier,
 v.monthly_price, v.annual_price,
 p.tier AS plan_tier, p.status AS plan_status,
 t.admin_user_id AS tenant_admin, t.status AS tenant_status,
 u.status AS admin_status,
 EXISTS (
   SELECT 1 FROM public.memberships m
   WHERE m.tenant_id=e.tenant_id AND m.user_id=e.admin_user_id
     AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 ) AS admin_membership_active,
 (SELECT count(*) FROM public.saas_payment_intents i
   WHERE i.preparation_id=e.preparation_id) AS payment_count,
 (SELECT count(*) FROM public.saas_license_entitlements l
   WHERE l.preparation_id=e.preparation_id) AS license_count,
 (SELECT count(*) FROM public.ledger_entries le
   WHERE le.tenant_id=e.tenant_id) AS tenant_ledger_entries
FROM public.saas_enrollment_requests_staging e
JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id
JOIN public.contract_acceptances a ON a.id=e.contract_acceptance_id
JOIN public.contract_documents d ON d.id=a.document_id
JOIN public.platform_license_price_versions v ON v.id=e.price_version_id
JOIN public.platform_license_plans p ON p.tier=v.plan_tier
JOIN public.tenants t ON t.id=e.tenant_id
JOIN public.users u ON u.id=e.admin_user_id
WHERE e.request_id=%s AND e.tenant_id=%s AND e.admin_user_id=%s
LIMIT 2
"""


@dataclass(frozen=True)
class DisposableReadback:
    state: str
    structure_consistent_in_ci: bool = False
    published_contract_operationally_verified: bool = False
    explicit_consent_operationally_verified: bool = False
    payment_verified: bool = False
    license_activated: bool = False
    member_activated: bool = False
    pix_authorized: bool = False
    production_authorized: bool = False
    writes_performed: bool = False


def _uuid(x: object) -> bool:
    return type(x) is UUID and x.int != 0


def _instant(x: object) -> bool:
    return type(x) is datetime and x.tzinfo is not None and x.utcoffset() is not None


def _amount(x: object) -> int | None:
    if type(x) is not Decimal or not x.is_finite():
        return None
    cents = x * 100
    if cents != cents.to_integral_value() or not 0 < cents <= 999_999_999_999:
        return None
    return int(cents)


def evaluate_disposable_readback(
    row: dict | None, *, request_id: UUID, tenant_id: UUID,
    admin_id: UUID, now: datetime,
) -> DisposableReadback:
    """Never promotes a synthetic DB record to billing/contract authority."""
    blocked = DisposableReadback
    if not all(_uuid(x) for x in (request_id, tenant_id, admin_id)) or not _instant(now):
        return blocked("INVALID_REQUEST_SCOPE")
    if type(row) is not dict:
        return blocked("NO_SINGLE_DATABASE_RECORD")
    ids = (
        "request_id", "tenant_id", "admin_user_id", "price_version_id",
        "contract_acceptance_id", "preparation_id", "prepared_tenant",
        "prepared_admin", "prepared_price", "prepared_acceptance",
        "accepted_document_id", "accepted_by", "published_document_id",
        "version_id", "tenant_admin",
    )
    try:
        if not all(_uuid(row[k]) for k in ids):
            return blocked("MALFORMED_DATABASE_IDENTIFIERS")
        if (row["request_id"] != request_id or row["tenant_id"] != tenant_id
                or row["admin_user_id"] != admin_id
                or row["prepared_tenant"] != tenant_id
                or row["prepared_admin"] != admin_id
                or row["tenant_admin"] != admin_id
                or row["accepted_by"] != admin_id
                or row["price_version_id"] != row["prepared_price"]
                or row["price_version_id"] != row["version_id"]
                or row["contract_acceptance_id"] != row["prepared_acceptance"]
                or row["accepted_document_id"] != row["published_document_id"]):
            return blocked("CROSS_SCOPE_OR_VERSION_MISMATCH")
        if (row["accepted_tenant"] is not None
                or row["accepted_kind"] != "PLATFORM_LICENSE"
                or row["published_kind"] != "PLATFORM_LICENSE"
                or row["published_at"] is None
                or row["evidence_method"] != "CI_VERIFIED_IDENTITY"
                or type(row["published_sha"]) is not str
                or _SHA.fullmatch(row["published_sha"]) is None
                or type(row["evidence_hash"]) is not str
                or _SHA.fullmatch(row["evidence_hash"]) is None
                or not all(_instant(row[k]) for k in (
                    "published_at", "accepted_at", "prepared_at"))
                or not row["published_at"] <= row["accepted_at"] <= row["prepared_at"] <= now):
            return blocked("CONTRACT_RECORD_NOT_CONSISTENT_IN_CI")
        if (row["tenant_status"] != "ATIVO"
                or row["admin_status"] != "ACTIVE"
                or row["admin_membership_active"] is not True):
            return blocked("TENANT_ADMIN_INACTIVE")
        if (row["billing_period"] not in ("MONTHLY", "ANNUAL")
                or row["prepared_period"] != row["billing_period"]
                or row["prepared_tier"] != row["version_tier"]
                or row["prepared_tier"] != row["plan_tier"]
                or row["plan_tier"] not in ("ESSENCIAL", "INTERMEDIARIO", "AMPLIADO")
                or row["plan_status"] != "ACTIVE"
                or row["preparation_status"] != "PENDING_PAYMENT"):
            return blocked("INVALID_PLAN_OR_PREPARATION")
        monthly = _amount(row["monthly_price"])
        annual = _amount(row["annual_price"])
        if monthly is None or annual is None or annual != 10 * monthly:
            return blocked("INVALID_FROZEN_PRICE_VERSION")
        if (row["payment_created"] is not False
                or row["entitlement_created"] is not False
                or any(type(row[k]) is not int or row[k] != 0
                    for k in ("payment_count", "license_count", "tenant_ledger_entries"))):
            return blocked("FINANCIAL_OR_ENTITLEMENT_RECORD_PRESENT")
    except (KeyError, TypeError, ValueError):
        return blocked("MALFORMED_DATABASE_RECORD")
    return blocked("CI_PERSISTED_PREPARATION_REVIEW_ONLY", True)
