"""M37463: CI-only token-scoped *read-only* contract offer readback.

This is NOT a production repository adapter. It requires an authenticated
token-bound principal (M37462) plus a SELECT joined to the disposable
PostgreSQL M37458 session/offer fixture. No license, payment or consent writes.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timedelta
from uuid import UUID

from .dependencies import AuthenticatedSession
from .routers.saas_authenticated_contract_ci import (
    CITrustedServerContext,check_server_identity_binding,
)
from .saas_server_context_readback_ci import build_ci_trusted_context

# Five parameters: verified session_id, user_id, tenant_id, request_id,
# server-computed SHA-256 of the raw bearer. The digest is used ONLY in the
# WHERE clause and is not returned by this SQL.
TOKEN_SCOPE_SQL = """
SELECT
 f.session_id, f.tenant_id, f.admin_id, f.role AS session_role,
 f.session_active, f.email_verified, f.server_issued_at,
 f.server_expires_at, t.admin_user_id AS tenant_admin,
 t.status AS tenant_status, u.status AS admin_status,
 EXISTS(
  SELECT 1 FROM public.memberships m
  WHERE m.tenant_id=f.tenant_id AND m.user_id=f.admin_id
    AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 ) AS admin_membership_active,
 c.request_id,c.challenge_id,c.session_id AS challenge_session,
 c.tenant_id AS challenge_tenant,c.admin_id AS challenge_admin,
 c.document_id,c.document_sha,c.price_version_id,c.billing_period,
 c.server_issued_at AS challenge_issued_at,
 c.server_expires_at AS challenge_expires_at,
 d.document_kind,d.version_label,d.sha256 AS published_sha,d.published_at,
 v.id AS version_id,v.plan_tier,v.monthly_price,v.annual_price,
 p.status AS plan_status,
 s.id AS live_session_id,s.user_id AS live_user_id,
 s.active_tenant_id AS live_tenant_id,s.active_role AS live_role,
 s.expires_at AS live_expires_at,s.created_at AS live_created_at,
 s.revoked_at AS live_revoked_at,u.is_master AS live_is_master
FROM public.sessions s
JOIN public.saas_preprep_sessions_m37458_ci f
 ON f.session_id=s.id AND f.tenant_id=s.active_tenant_id
 AND f.admin_id=s.user_id AND f.role=s.active_role
JOIN public.tenants t ON t.id=f.tenant_id
JOIN public.users u ON u.id=f.admin_id
JOIN public.saas_preprep_challenges_m37458_ci c
 ON c.session_id=f.session_id AND c.tenant_id=f.tenant_id
 AND c.admin_id=f.admin_id
JOIN public.contract_documents d ON d.id=c.document_id
JOIN public.platform_license_price_versions v ON v.id=c.price_version_id
JOIN public.platform_license_plans p ON p.tier=v.plan_tier
WHERE s.id=%s AND s.user_id=%s AND s.active_tenant_id=%s
 AND c.request_id=%s AND s.token_hash=%s
 AND s.active_role='TENANT_ADMIN'
 AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp()
 AND u.status='ACTIVE' AND u.is_master=false
 AND t.status='ATIVO' AND t.admin_user_id=s.user_id
 AND p.status='ACTIVE' AND d.document_kind='PLATFORM_LICENSE'
 AND d.published_at<=clock_timestamp()
 AND c.document_sha=d.sha256
LIMIT 2
"""


def _utc_time(value:object)->bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _uuid(value:object)->bool:
    return type(value) is UUID and value.int!=0


def token_scope_params(
    session:AuthenticatedSession,request_id:UUID,token_digest:str,
    *,now:datetime,
)->tuple|None:
    """Produce bounded SQL params from VERIFIED server session, not client IDs."""
    if (type(session) is not AuthenticatedSession
        or session.verification_source!="POSTGRES_TOKEN_HASH_REFRESH"
        or session.role!="TENANT_ADMIN" or session.is_master is not False
        or not _utc_time(now)
        or not _utc_time(session.verified_session_at)
        or not _utc_time(session.verified_session_expires_at)
        or session.verified_session_at>now
        or now-session.verified_session_at>timedelta(minutes=5)
        or session.verified_session_expires_at<=now
        or not _uuid(request_id)
        or type(token_digest) is not str
        or len(token_digest)!=64
        or any(c not in "0123456789abcdef" for c in token_digest)):
        return None
    try:
        sid=UUID(session.verified_session_id or "")
        admin=UUID(session.user_id)
        tenant=UUID(session.tenant_id or "")
    except (ValueError,TypeError,AttributeError):
        return None
    if (not all(_uuid(v) for v in (sid,admin,tenant))
        or str(sid)!=session.verified_session_id
        or str(admin)!=session.user_id
        or str(tenant)!=session.tenant_id):
        return None
    return sid,admin,tenant,request_id,token_digest


def build_token_scoped_ci_context(
    row:dict|None,session:AuthenticatedSession,request_id:UUID,
    token_digest:str,*,now:datetime
)->tuple[str,CITrustedServerContext|None]:
    params=token_scope_params(session,request_id,token_digest,now=now)
    if params is None:
        return "CI_AUTHENTICATED_SESSION_REQUIRED",None
    if type(row) is not dict:
        return "CI_TOKEN_SCOPED_DATABASE_ROW_REQUIRED",None
    sid,admin,tenant,request,_=params
    required=("live_session_id","live_user_id","live_tenant_id",
              "live_role","live_expires_at","live_created_at",
              "live_revoked_at","live_is_master")
    try:
        if (not all(key in row for key in required)
            or not all(type(row[k]) is UUID and row[k].int!=0
                       for k in ("live_session_id","live_user_id","live_tenant_id"))
            or not all(_utc_time(row[k]) for k in (
                "live_expires_at","live_created_at"))):
            return "CI_MALFORMED_TOKEN_SCOPED_ROW",None
        if (row["live_session_id"]!=sid
            or row["live_user_id"]!=admin
            or row["live_tenant_id"]!=tenant
            or row["live_role"]!="TENANT_ADMIN"
            or row["live_is_master"] is not False
            or row["live_revoked_at"] is not None
            or row["live_expires_at"]<=now
            or row["live_created_at"]>now
            or row["live_created_at"]>row["live_expires_at"]
            or session.verified_session_expires_at>row["live_expires_at"]+timedelta(seconds=2)):
            return "CI_TOKEN_SCOPE_SESSION_CHANGED_OR_REVOKED",None
        state,context=build_ci_trusted_context(
            row,session_id=sid,tenant_id=tenant,
            admin_id=admin,request_id=request,checked_at=now,
        )
        if state!="CI_DISPOSABLE_SERVER_CONTEXT_READBACK_ONLY" or context is None:
            return state,None
        context=replace(
            context,session_expires_at=min(
                context.session_expires_at,
                row["live_expires_at"],
                session.verified_session_expires_at,
            ),
        )
        if check_server_identity_binding(session,context,now=now) is None:
            return "CI_TOKEN_SCOPE_INCONSISTENT_WITH_SERVER_CONTEXT",None
    except (KeyError,ValueError,TypeError,OverflowError):
        return "CI_MALFORMED_TOKEN_SCOPED_ROW",None
    return "CI_TOKEN_HASH_SESSION_CONTRACT_READBACK_ONLY",context
