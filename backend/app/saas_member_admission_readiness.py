"""M33400-M33800: RLS-backed member admission capacity review, read-only.

Never grants membership, issues an invitation or claims a reserved seat.
The final atomic admission path and independent MP readback remain missing.
"""
from __future__ import annotations

from uuid import UUID
from fastapi import HTTPException

from .invitation_preflight import authorize_invitation_intent

async def member_admission_readiness(*, session, payload, conn) -> dict:
    """Read committed tenant/license/plan occupancy through authenticated RLS."""
    authorize_invitation_intent(session=session, payload=payload)
    if (session.role != "TENANT_ADMIN" or payload.target_role != "TENANT_MEMBER"
            or not isinstance(payload.tenant_id, UUID)
            or not isinstance(payload.required_document_id, UUID)):
        raise HTTPException(status_code=403, detail="Cadastro de membro reservado ao administrador.")
    try:
        signed_tenant = UUID(str(session.tenant_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="Caixinha nao autorizada.") from None
    if payload.tenant_id != signed_tenant:
        raise HTTPException(status_code=403, detail="Caixinha nao autorizada.")

    gates = [
        "PROVIDER_INDEPENDENT_READBACK_NOT_ATTESTED",
        "ATOMIC_MEMBER_ADMISSION_AND_CAPACITY_CLAIM_NOT_IMPLEMENTED",
        "RUNTIME_INVITATION_ISSUANCE_DISABLED",
    ]
    active = bool(await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM public.tenants "
        "WHERE id=$1::uuid AND status='ATIVO')", signed_tenant,
    ))
    published = bool(await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM public.contract_documents "
        "WHERE id=$1::uuid AND document_kind='TENANT_MEMBERSHIP' "
        "AND published_at IS NOT NULL)", payload.required_document_id,
    ))
    if not active:
        gates.append("ACTIVE_TENANT_NOT_ATTESTED")
    if not published:
        gates.append("PUBLISHED_MEMBERSHIP_CONTRACT_NOT_ATTESTED")

    license_record_visible = False
    candidate_capacity = False
    occupied_members = None
    member_limit = None
    occupied_quotas = None
    quota_limit = None
    if active and published:
        # RLS on all four joins, including plan visibility narrowed by 045.
        # No SELECT on users, credentials, e-mail, CPF, or provider secrets.
        license_row = await conn.fetchrow(
            "SELECT e.plan_tier,e.status AS entitlement_status,"
            " (e.valid_from<=clock_timestamp() AND e.valid_until>clock_timestamp()) AS within_term,"
            " p.status AS plan_status,p.members_limit,p.quotas_limit,"
            " i.status AS payment_status,i.reconciled_at IS NOT NULL AS locally_reconciled,"
            " i.live_mode AS payment_live_mode "
            "FROM public.saas_license_entitlements e "
            "JOIN public.platform_license_plans p ON p.tier=e.plan_tier "
            "JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id "
            " AND s.tenant_id=e.tenant_id AND s.plan_tier=e.plan_tier "
            "JOIN public.saas_payment_intents i ON i.id=e.payment_intent_id "
            " AND i.tenant_id=e.tenant_id AND i.preparation_id=e.preparation_id "
            " AND i.admin_user_id=s.admin_user_id "
            "WHERE e.tenant_id=$1::uuid AND s.admin_user_id=$2::uuid "
            "ORDER BY e.valid_until DESC,e.id DESC LIMIT 1",
            signed_tenant, UUID(str(session.user_id)),
        )
        if license_row is None:
            gates.append("LICENSE_PLAN_OR_PAYMENT_NOT_VISIBLE")
        else:
            license_record_visible = True
            member_limit = license_row["members_limit"]
            quota_limit = license_row["quotas_limit"]
            occupied_members = await conn.fetchval(
                "SELECT count(*) FROM public.memberships "
                "WHERE tenant_id=$1::uuid AND role='TENANT_MEMBER' "
                "AND status='ATIVA'", signed_tenant,
            )
            occupied_quotas = await conn.fetchval(
                "SELECT count(*) FROM public.quotas "
                "WHERE tenant_id=$1::uuid AND status='ATIVA'", signed_tenant,
            )
            if (license_row["entitlement_status"] != "ACTIVE"
                    or license_row["within_term"] is not True):
                gates.append("LICENSE_EXPIRED_OR_INACTIVE")
            if (license_row["plan_status"] != "ACTIVE"
                    or type(member_limit) is not int or member_limit <= 0
                    or type(quota_limit) is not int or quota_limit <= 0):
                gates.append("PLAN_LIMITS_NOT_APPROVED")
            if (license_row["payment_status"] != "APPROVED"
                    or license_row["locally_reconciled"] is not True):
                gates.append("PAYMENT_RECORD_NOT_RECONCILED")
            if (type(occupied_members) is not int
                    or type(occupied_quotas) is not int
                    or occupied_members < 0 or occupied_quotas < 0):
                gates.append("RLS_OCCUPANCY_NOT_ATTESTED")
            elif (type(member_limit) is int and type(quota_limit) is int
                    and (occupied_members + 1 > member_limit
                         or occupied_quotas > quota_limit)):
                gates.append("PLAN_CAPACITY_EXCEEDED")
            candidate_capacity = not any(gate in gates for gate in (
                "LICENSE_EXPIRED_OR_INACTIVE", "PLAN_LIMITS_NOT_APPROVED",
                "PAYMENT_RECORD_NOT_RECONCILED", "RLS_OCCUPANCY_NOT_ATTESTED",
                "PLAN_CAPACITY_EXCEEDED",
            ))
    # A snapshot can be stale after this response: do not return an admission token.
    return {
        "scope": "AI_STUDIO_MEMBER_ADMISSION_PREFLIGHT",
        "source": "POSTGRESQL_RLS_READ_ONLY",
        "status": "BLOCKED",
        "tenant_active_verified": active,
        "document_published_verified": published,
        "license_record_visible": license_record_visible,
        "capacity_candidate_only": candidate_capacity,
        "active_member_count_snapshot": occupied_members,
        "member_limit_snapshot": member_limit,
        "active_quota_count_snapshot": occupied_quotas,
        "quota_limit_snapshot": quota_limit,
        "provider_verified_live": False,
        "final_capacity_reserved": False,
        "invitation_created": False,
        "user_created": False,
        "membership_created": False,
        "quota_created": False,
        "billing_created": False,
        "pix_authorized": False,
        "activation_authorized": False,
        "writes_performed": False,
        "blocking_gates": gates,
    }
