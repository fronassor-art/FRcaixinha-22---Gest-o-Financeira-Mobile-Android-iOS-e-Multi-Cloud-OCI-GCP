"""M37466: post-commit immutable SaaS evidence audit, disposable CI only.

A successful CI result proves a coherent *synthetic* historical record after
the server session has been revoked. It cannot authorize a fresh transition,
real-world consent, subscriptions, payments, licenses, members or Pix.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID
import json
import re

_HEX=re.compile(r"[0-9a-f]{64}\Z")
_CONFIRM="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
_AUDIT_SOURCE="CI_SYNTHETIC_NOT_LEGAL_CONSENT"

# Four original append-only tables + live session + published contract/price.
# Positional parameters are request, tenant, administrator, session. They
# must be known server-side fixture IDs, never reconstructed from an HTTP body.
# The currently revoked session is joined as historical evidence ONLY.
POST_COMMIT_AUDIT_SQL="""
SELECT
 c.challenge_id,c.request_id,c.session_id,c.tenant_id,c.admin_id,
 c.document_id,c.document_sha,c.price_version_id,c.billing_period,
 c.server_issued_at AS challenge_issued_at,
 c.server_expires_at AS challenge_expires_at,
 r.challenge_id AS receipt_challenge,r.request_id AS receipt_request,
 r.session_id AS receipt_session,r.tenant_id AS receipt_tenant,
 r.admin_id AS receipt_admin,r.document_id AS receipt_document,
 r.document_sha AS receipt_sha,
 r.price_version_id AS receipt_price_version,
 r.billing_period AS receipt_period,
 r.confirmation_text,r.server_recorded_at,r.evidence_source,
 d.request_id AS draft_request,d.challenge_id AS draft_challenge,
 d.tenant_id AS draft_tenant,d.admin_id AS draft_admin,
 d.document_id AS draft_document,d.price_version_id AS draft_price_version,
 d.billing_period AS draft_period,d.server_prepared_at,
 d.status AS draft_status,d.legal_consent_verified,
 d.payment_authorized,d.license_authorized,d.activation_authorized,
 f.session_id AS fixture_session,f.tenant_id AS fixture_tenant,
 f.admin_id AS fixture_admin,f.role AS fixture_role,
 f.session_active AS fixture_session_active,
 f.email_verified AS fixture_email_verified,
 f.server_issued_at AS fixture_issued_at,
 f.server_expires_at AS fixture_expires_at,
 s.id AS live_session,s.user_id AS live_user,
 s.active_tenant_id AS live_tenant,s.active_role AS live_role,
 s.revoked_at AS live_revoked_at,s.expires_at AS live_expires_at,
 contract.sha256 AS published_sha,contract.document_kind,
 contract.published_at,contract.version_label,
 v.id AS published_price_version,v.plan_tier,v.monthly_price,
 v.annual_price,p.status AS plan_status,
 t.admin_user_id AS tenant_admin,t.status AS tenant_status,
 u.status AS admin_status,u.is_master,
 EXISTS(
   SELECT 1 FROM public.memberships m
   WHERE m.user_id=c.admin_id AND m.tenant_id=c.tenant_id
     AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 ) AS admin_membership_active
FROM public.saas_preprep_challenges_m37458_ci c
JOIN public.saas_preprep_receipts_m37458_ci r
 ON r.challenge_id=c.challenge_id
JOIN public.saas_preprep_drafts_m37458_ci d
 ON d.challenge_id=r.challenge_id AND d.request_id=r.request_id
JOIN public.saas_preprep_sessions_m37458_ci f
 ON f.session_id=c.session_id
JOIN public.sessions s ON s.id=c.session_id
JOIN public.contract_documents contract ON contract.id=c.document_id
JOIN public.platform_license_price_versions v ON v.id=c.price_version_id
JOIN public.platform_license_plans p ON p.tier=v.plan_tier
JOIN public.tenants t ON t.id=c.tenant_id
JOIN public.users u ON u.id=c.admin_id
WHERE c.request_id=%s AND c.tenant_id=%s
 AND c.admin_id=%s AND c.session_id=%s
LIMIT 2
"""


@dataclass(frozen=True)
class PostCommitAudit:
    state:str
    historical_consistency:bool=False
    evidence_sha256:str|None=None
    issuer_session_revoked:bool=False
    synthetic_record_count:int=0
    legal_consent_verified:bool=False
    real_identity_verified:bool=False
    payment_authorized:bool=False
    license_authorized:bool=False
    pix_authorized:bool=False
    activation_authorized:bool=False
    production_authorized:bool=False
    financial_writes_performed:bool=False


def _id(value:object)->bool:
    return type(value) is UUID and value.int!=0


def _time(value:object)->bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _str(value:object)->bool:
    return type(value) is str


def _cents(value:object)->int|None:
    if type(value) is not Decimal or not value.is_finite():
        return None
    x=value*100
    if x!=x.to_integral_value() or not 0<x<=999_999_999_999:
        return None
    return int(x)


def audit_post_commit_ci(
    row:dict|None,*,request_id:UUID,tenant_id:UUID,
    administrator_id:UUID,session_id:UUID,observed_at:datetime,
)->PostCommitAudit:
    """Verify a *past* synthetic contract, never treat it as an active grant."""
    denied=lambda reason:PostCommitAudit(reason)
    if (type(row) is not dict or not all(_id(x) for x in (
        request_id,tenant_id,administrator_id,session_id))
        or not _time(observed_at)):
        return denied("CI_POST_COMMIT_INPUT_INVALID")

    uuid_fields=(
        "challenge_id","request_id","session_id","tenant_id","admin_id",
        "document_id","price_version_id","receipt_challenge",
        "receipt_request","receipt_session","receipt_tenant","receipt_admin",
        "receipt_document","receipt_price_version","draft_request",
        "draft_challenge","draft_tenant","draft_admin","draft_document",
        "draft_price_version","fixture_session","fixture_tenant",
        "fixture_admin","live_session","live_user","live_tenant",
        "published_price_version","tenant_admin",
    )
    times=(
        "challenge_issued_at","challenge_expires_at",
        "server_recorded_at","server_prepared_at",
        "fixture_issued_at","fixture_expires_at","live_expires_at",
        "published_at",
    )
    flags=(
        "legal_consent_verified","payment_authorized","license_authorized",
        "activation_authorized","fixture_session_active",
        "fixture_email_verified","admin_membership_active","is_master",
    )
    try:
        if (not all(_id(row[k]) for k in uuid_fields)
            or not all(_time(row[k]) for k in times)
            or not _time(row["live_revoked_at"])
            or not all(type(row[k]) is bool for k in flags)
            or not all(_str(row[k]) and _HEX.fullmatch(row[k]) is not None
                for k in ("document_sha","receipt_sha","published_sha"))
            or not all(_str(row[k]) for k in (
                "billing_period","receipt_period","draft_period",
                "confirmation_text","evidence_source","draft_status",
                "fixture_role","live_role","document_kind","plan_tier",
                "plan_status","tenant_status","admin_status","version_label"))
            or not _str(row["published_sha"])):
            return denied("CI_POST_COMMIT_MALFORMED_DB_EVIDENCE")
        if (row["request_id"]!=request_id
            or row["tenant_id"]!=tenant_id
            or row["admin_id"]!=administrator_id
            or row["session_id"]!=session_id
            or any(row[field]!=row["challenge_id"] for field in (
                "receipt_challenge","draft_challenge"))
            or any(row[field]!=request_id for field in (
                "receipt_request","draft_request"))
            or any(row[field]!=session_id for field in (
                "receipt_session","fixture_session","live_session"))
            or any(row[field]!=tenant_id for field in (
                "receipt_tenant","draft_tenant","fixture_tenant","live_tenant"))
            or any(row[field]!=administrator_id for field in (
                "receipt_admin","draft_admin","fixture_admin","live_user",
                "tenant_admin"))
            or any(row[field]!=row["document_id"] for field in (
                "receipt_document","draft_document"))
            or any(row[field]!=row["price_version_id"] for field in (
                "receipt_price_version","draft_price_version",
                "published_price_version"))
            or row["receipt_sha"]!=row["document_sha"]
            or row["published_sha"]!=row["document_sha"]
            or row["receipt_period"]!=row["billing_period"]
            or row["draft_period"]!=row["billing_period"]):
            return denied("CI_POST_COMMIT_CROSS_RECORD_SCOPE_MISMATCH")
        if (row["billing_period"] not in ("MONTHLY","ANNUAL")
            or row["fixture_role"]!="TENANT_ADMIN"
            or row["live_role"]!="TENANT_ADMIN"
            or row["fixture_session_active"] is not True
            or row["fixture_email_verified"] is not True
            or row["is_master"] is not False
            or row["admin_membership_active"] is not True
            or row["tenant_status"]!="ATIVO"
            or row["admin_status"]!="ACTIVE"
            or row["plan_status"]!="ACTIVE"
            or row["plan_tier"] not in (
                "ESSENCIAL","INTERMEDIARIO","AMPLIADO")
            or row["document_kind"]!="PLATFORM_LICENSE"
            or not row["version_label"] or len(row["version_label"])>96
            or row["version_label"].strip()!=row["version_label"]
            or row["confirmation_text"]!=_CONFIRM
            or row["evidence_source"]!=_AUDIT_SOURCE
            or row["draft_status"]!="CI_DRAFT_NO_PAYMENT"
            or any(row[key] for key in (
                "legal_consent_verified","payment_authorized",
                "license_authorized","activation_authorized"))):
            return denied("CI_POST_COMMIT_NONLEGAL_OR_PUBLISHED_SCOPE_INVALID")
        # The session must have been valid when the synthetic contract
        # was recorded, then revoked AFTER the last committed step.
        if not (
            row["fixture_issued_at"]<=row["challenge_issued_at"]
            <=row["server_recorded_at"]
            <=row["server_prepared_at"]
            <=row["live_revoked_at"]<=observed_at
            and row["published_at"]<=row["challenge_issued_at"]
            and row["server_recorded_at"]<row["challenge_expires_at"]
            and row["challenge_expires_at"]-row["challenge_issued_at"]
                <=timedelta(minutes=6)
            and row["challenge_issued_at"]<row["fixture_expires_at"]
            and row["server_prepared_at"]<row["fixture_expires_at"]
            and row["server_prepared_at"]<row["live_expires_at"]
            and row["fixture_expires_at"]>row["fixture_issued_at"]):
            return denied("CI_POST_COMMIT_CHRONOLOGY_INVALID")
        monthly=_cents(row["monthly_price"])
        annual=_cents(row["annual_price"])
        if monthly is None or annual is None or annual!=10*monthly:
            return denied("CI_POST_COMMIT_PUBLISHED_PRICE_INVALID")
        frozen_price=monthly if row["billing_period"]=="MONTHLY" else annual
        # This diagnostic digest is deterministic but NOT signed, not an
        # independent attestation and not a reusable authorization token.
        payload={
            "scope":"M37466_CI_SYNTHETIC_HISTORICAL_ONLY",
            "request_id":str(request_id),
            "challenge_id":str(row["challenge_id"]),
            "session_id":str(session_id),
            "tenant_id":str(tenant_id),
            "administrator_id":str(administrator_id),
            "document_id":str(row["document_id"]),
            "document_sha256":row["published_sha"],
            "version_label":row["version_label"],
            "price_version_id":str(row["price_version_id"]),
            "period":row["billing_period"],
            "price_cents":frozen_price,
            "issued_at":row["challenge_issued_at"].astimezone(timezone.utc).isoformat(),
            "recorded_at":row["server_recorded_at"].astimezone(timezone.utc).isoformat(),
            "prepared_at":row["server_prepared_at"].astimezone(timezone.utc).isoformat(),
        }
        digest=sha256(json.dumps(
            payload,sort_keys=True,separators=(",",":"),ensure_ascii=True,
        ).encode("ascii")).hexdigest()
        return PostCommitAudit(
            "CI_POST_COMMIT_SYNTHETIC_HISTORY_CONSISTENT_NOT_AUTHORITY",
            historical_consistency=True,evidence_sha256=digest,
            issuer_session_revoked=True,synthetic_record_count=3,
        )
    except (KeyError,ValueError,OverflowError,TypeError):
        return denied("CI_POST_COMMIT_MALFORMED_DB_EVIDENCE")
