"""M37461: read-only disposable PostgreSQL SaaS server context reconstruction.

The session is a synthetic CI fixture, not the authentication token/session
returned by get_current_session. Even successful readback cannot establish a
real person's identity, legal consent, provider payment, or paid SaaS license.
No SQL writes, HTTP routes, payments, or external IO in this policy module.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
import re

from .routers.saas_authenticated_contract_ci import CITrustedServerContext
from .saas_acceptance_api_contract_ci import CIPublishedOffer

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MAX_SESSION = timedelta(hours=2)

# Every identifier is bound to a server-supplied CI fixture; no dynamic SQL.
# The only source for pricing, contract hash and session is PostgreSQL.
READBACK_SQL = """
SELECT
 s.session_id, s.tenant_id, s.admin_id, s.role AS session_role,
 s.session_active, s.email_verified, s.server_issued_at,
 s.server_expires_at, t.admin_user_id AS tenant_admin,
 t.status AS tenant_status, u.status AS admin_status,
 EXISTS(
   SELECT 1 FROM public.memberships m
   WHERE m.tenant_id=s.tenant_id AND m.user_id=s.admin_id
     AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 ) AS admin_membership_active,
 c.request_id, c.challenge_id, c.session_id AS challenge_session,
 c.tenant_id AS challenge_tenant, c.admin_id AS challenge_admin,
 c.document_id, c.document_sha, c.price_version_id, c.billing_period,
 c.server_issued_at AS challenge_issued_at,
 c.server_expires_at AS challenge_expires_at,
 d.document_kind, d.version_label, d.sha256 AS published_sha, d.published_at,
 v.id AS version_id, v.plan_tier, v.monthly_price, v.annual_price,
 p.status AS plan_status
FROM public.saas_preprep_sessions_m37458_ci s
JOIN public.tenants t ON t.id=s.tenant_id
JOIN public.users u ON u.id=s.admin_id
JOIN public.saas_preprep_challenges_m37458_ci c ON c.session_id=s.session_id
JOIN public.contract_documents d ON d.id=c.document_id
JOIN public.platform_license_price_versions v ON v.id=c.price_version_id
JOIN public.platform_license_plans p ON p.tier=v.plan_tier
WHERE s.session_id=%s AND s.tenant_id=%s
  AND s.admin_id=%s AND c.request_id=%s
LIMIT 2
"""


def _uuid(v: object) -> bool:
    return type(v) is UUID and v.int != 0


def _time(v: object) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _cents(v: object) -> int | None:
    if type(v) is not Decimal or not v.is_finite():
        return None
    amount=v*100
    if amount!=amount.to_integral_value() or not 0 < amount <= 999_999_999_999:
        return None
    return int(amount)


def build_ci_trusted_context(
    row: dict | None, *, session_id: UUID, tenant_id: UUID,
    admin_id: UUID, request_id: UUID, checked_at: datetime,
) -> tuple[str, CITrustedServerContext | None]:
    """Fail closed; only builds a synthetic context from an isolated DB row."""
    if (type(row) is not dict
        or not all(_uuid(x) for x in (session_id,tenant_id,admin_id,request_id))
        or not _time(checked_at)):
        return ("INVALID_CI_READBACK_INPUT",None)
    ids = (
        "session_id","tenant_id","admin_id","tenant_admin",
        "request_id","challenge_id","challenge_session",
        "challenge_tenant","challenge_admin","document_id",
        "price_version_id","version_id",
    )
    timestamps = (
        "server_issued_at","server_expires_at",
        "challenge_issued_at","challenge_expires_at","published_at",
    )
    try:
        if (not all(_uuid(row[k]) for k in ids)
            or not all(_time(row[k]) for k in timestamps)
            or not all(type(row[k]) is bool for k in (
                "session_active","email_verified","admin_membership_active"))
            or not all(type(row[k]) is str and _HEX.fullmatch(row[k]) is not None
                       for k in ("document_sha","published_sha"))):
            return ("MALFORMED_CI_DATABASE_CONTEXT",None)
        if (row["session_id"] != session_id
            or row["tenant_id"] != tenant_id
            or row["admin_id"] != admin_id
            or row["tenant_admin"] != admin_id
            or row["request_id"] != request_id
            or row["challenge_session"] != session_id
            or row["challenge_tenant"] != tenant_id
            or row["challenge_admin"] != admin_id
            or row["price_version_id"] != row["version_id"]
            or row["document_sha"] != row["published_sha"]):
            return ("CI_SCOPE_DOCUMENT_OR_PRICE_MISMATCH",None)
        if (row["session_role"] != "TENANT_ADMIN"
            or row["session_active"] is not True
            or row["email_verified"] is not True
            or row["admin_membership_active"] is not True
            or row["tenant_status"] != "ATIVO"
            or row["admin_status"] != "ACTIVE"):
            return ("CI_ADMIN_SESSION_NOT_ACTIVE",None)
        if (row["document_kind"] != "PLATFORM_LICENSE"
            or row["plan_status"] != "ACTIVE"
            or row["plan_tier"] not in ("ESSENCIAL","INTERMEDIARIO","AMPLIADO")
            or type(row["version_label"]) is not str
            or not 1 <= len(row["version_label"]) <= 96
            or row["version_label"].strip() != row["version_label"]
            or row["billing_period"] not in ("MONTHLY","ANNUAL")):
            return ("CI_OFFER_NOT_PUBLISHED_OR_ACTIVE",None)
        if (not row["published_at"] <= row["challenge_issued_at"]
            or not row["server_issued_at"] <= row["challenge_issued_at"]
            or not row["challenge_issued_at"] < row["challenge_expires_at"]
            or row["challenge_expires_at"]-row["challenge_issued_at"] > timedelta(minutes=6)
            or not row["server_issued_at"] <= checked_at < row["server_expires_at"]
            or row["server_expires_at"]-row["server_issued_at"] > _MAX_SESSION):
            return ("CI_SESSION_OR_CHALLENGE_TIME_INVALID",None)
        monthly=_cents(row["monthly_price"])
        annual=_cents(row["annual_price"])
        if monthly is None or annual is None or annual != 10 * monthly:
            return ("CI_FROZEN_PRICE_INVALID",None)
    except (KeyError,ValueError,TypeError,OverflowError):
        return ("MALFORMED_CI_DATABASE_CONTEXT",None)

    # A reconstructed CI offer is NOT a browser-supplied offer or legal contract.
    offer=CIPublishedOffer(
        tenant_id=tenant_id,document_id=row["document_id"],
        document_sha256=row["published_sha"],
        price_version_id=row["price_version_id"],
        billing_period=row["billing_period"],
        price_cents=monthly if row["billing_period"]=="MONTHLY" else annual,
        published_at=row["published_at"],state="ACTIVE",
    )
    context=CITrustedServerContext(
        tenant_id=tenant_id,administrator_id=admin_id,
        session_id=session_id,session_role="TENANT_ADMIN",
        session_active=True,email_verified=True,
        session_checked_at=checked_at,
        session_expires_at=row["server_expires_at"],
        request_id=request_id,challenge_id=row["challenge_id"],
        offer=offer,
    )
    return ("CI_DISPOSABLE_SERVER_CONTEXT_READBACK_ONLY",context)
