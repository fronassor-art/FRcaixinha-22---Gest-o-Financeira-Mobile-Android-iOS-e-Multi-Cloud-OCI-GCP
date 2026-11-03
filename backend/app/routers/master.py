"""
FRcaixinha 2.2 — Rotas Exclusivas do Administrador Master
Contrato Técnico Mestre (Cláusulas 1.3, 2.8, 3.2, 5.4, 11.2 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal
import uuid
from ..dependencies import require_master, AuthenticatedSession
from ..database import get_rls_db_connection
from ..admin_onboarding_policy import readiness_manifest, preflight_assessment
from ..admin_onboarding_workflow import (
    STATES, workflow_contract, preview_transition,
)
from ..onboarding_permission_matrix import permission_matrix_contract

router = APIRouter(prefix="/master", tags=["Governança Master da Plataforma"])

class SupportBreakGlassRequest(BaseModel):
    target_tenant_id: str
    justification: str = Field(..., min_length=15, description="Justificativa formal auditável para acesso emergencial de suporte")
    duration_minutes: int = Field(default=30, le=60, description="Duração máxima do acesso excepcional (máx 60 min)")

class AdminOnboardingPreflightRequest(BaseModel):
    tenant_id: uuid.UUID
    target_role: Literal["TENANT_ADMIN"]
    candidate_user_id: uuid.UUID | None = None
    purpose: str = Field(..., min_length=15, max_length=240)


class AdminTransitionPreviewRequest(BaseModel):
    current_state: Literal[
        "REQUESTED", "EMAIL_VERIFIED", "MASTER_REVIEW", "APPROVED",
        "INVITE_PREPARED", "DELIVERED", "ACCEPTED", "ACTIVE",
        "REJECTED", "REVOKED", "EXPIRED",
    ]
    proposed_state: Literal[
        "REQUESTED", "EMAIL_VERIFIED", "MASTER_REVIEW", "APPROVED",
        "INVITE_PREPARED", "DELIVERED", "ACCEPTED", "ACTIVE",
        "REJECTED", "REVOKED", "EXPIRED",
    ]
    simulated_actor_role: Literal["MASTER", "TENANT_ADMIN", "TENANT_MEMBER"]
    candidate_is_actor: bool = False
    email_verified: bool = False
    tenant_active: bool = False
    independent_approval: bool = False
    token_valid: bool = False
    expected_revision: int = Field(default=0, ge=0, le=1000000)
    observed_revision: int = Field(default=0, ge=0, le=1000000)
    idempotency_key: uuid.UUID
    previously_used_keys: list[uuid.UUID] = Field(default_factory=list, max_length=32)


class LicensePriceChange(BaseModel):
    tier: Literal['ESSENCIAL', 'INTERMEDIARIO']
    monthly_price: Decimal = Field(..., gt=Decimal('0'), le=Decimal('999999.99'), decimal_places=2)
    reason: str = Field(..., min_length=15, max_length=500)


@router.get("/admin-onboarding/permission-matrix")
async def admin_onboarding_permission_matrix(
    session: AuthenticatedSession = Depends(require_master),
):
    """Matriz descritiva. A autorização verdadeira permanece em RBAC e PostgreSQL."""
    return permission_matrix_contract()


@router.get("/admin-onboarding/workflow-contract")
async def admin_workflow_contract(
    session: AuthenticatedSession = Depends(require_master),
):
    """Desenho imutável do ciclo de convites; nenhuma consulta ou escrita SQL."""
    return workflow_contract()


@router.post("/admin-onboarding/transition-preview")
async def admin_transition_preview(
    payload: AdminTransitionPreviewRequest,
    session: AuthenticatedSession = Depends(require_master),
):
    """Simulador em memória. Nunca cria convite, evento auditável ou conta."""
    return preview_transition(
        current=payload.current_state,
        proposed=payload.proposed_state,
        actor_role=payload.simulated_actor_role,
        candidate_is_actor=payload.candidate_is_actor,
        email_verified=payload.email_verified,
        tenant_active=payload.tenant_active,
        independent_approval=payload.independent_approval,
        token_valid=payload.token_valid,
        expected_revision=payload.expected_revision,
        observed_revision=payload.observed_revision,
        idempotency_key=payload.idempotency_key,
        previously_used_keys=payload.previously_used_keys,
    )


@router.get("/admin-onboarding/capabilities")
async def admin_onboarding_capabilities(
    session: AuthenticatedSession = Depends(require_master),
):
    """Relatorio server-side de bloqueios de criacao de administradores."""
    return readiness_manifest()


@router.post("/admin-onboarding/preflight")
async def admin_onboarding_preflight(
    payload: AdminOnboardingPreflightRequest,
    session: AuthenticatedSession = Depends(require_master),
    conn = Depends(get_rls_db_connection),
):
    """PRE-ANALISE SOMENTE LEITURA. Nunca cria conta, convite ou permissao.

    O UUID do candidato e apenas hipotetico: nao consulta users.
    A justificativa e validada, mas jamais armazenada, ecoada ou enviada.
    """
    if len(payload.purpose.strip()) < 15:
        raise HTTPException(status_code=422, detail="Justificativa insuficiente.")
    tenant = await conn.fetchrow(
        "SELECT id,display_name,status,is_owner_box "
        "FROM public.tenants WHERE id=$1",
        payload.tenant_id,
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Caixinha não encontrada.")
    return preflight_assessment(
        tenant_id=str(tenant["id"]),
        tenant_name=tenant["display_name"],
        tenant_status=tenant["status"],
        is_owner_box=tenant["is_owner_box"],
        candidate_id=str(payload.candidate_user_id) if payload.candidate_user_id else None,
        actor_id=session.user_id,
    )


@router.get("/owner-access")
async def confirm_owner_access(session: AuthenticatedSession = Depends(require_master)):
    """Confirma papel MASTER no backend sem revelar dados de proprietario ou tenant."""
    return {
        "verified": True,
        "role": "MASTER",
        "scope": "PLATFORM_GOVERNANCE_ONLY",
    }


@router.get("/admin-registry")
async def get_master_admin_registry(
    search: str = Query(default="", max_length=36),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=5, le=50),
    session: AuthenticatedSession = Depends(require_master),
    conn = Depends(get_rls_db_connection),
):
    """Responsáveis cadastrais principais de caixinhas, sem dados pessoais.

    O campo admin_user_id nao prova conta ativa nem membership autorizado.
    Usa exclusivamente public.tenants, sob RLS e papel MASTER validado.
    """
    term = search.strip().lower()
    filter_sql = (
        " FROM public.tenants "
        "WHERE strpos(lower(admin_user_id::text), $1::text) > 0"
    )
    total = await conn.fetchval(
        "SELECT count(DISTINCT admin_user_id)" + filter_sql, term
    )
    rows = await conn.fetch(
        "SELECT admin_user_id,count(*)::int AS tenant_count,"
        "count(*) FILTER (WHERE status='ATIVO')::int AS active_count,"
        "count(*) FILTER (WHERE status='SUSPENSO')::int AS suspended_count,"
        "count(*) FILTER (WHERE status='RASCUNHO_INATIVO')::int AS draft_count,"
        "count(*) FILTER (WHERE status='ENCERRADO')::int AS closed_count"
        + filter_sql +
        " GROUP BY admin_user_id"
        " ORDER BY count(*) DESC, admin_user_id"
        " LIMIT $2 OFFSET $3",
        term, page_size, (page - 1) * page_size,
    )
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "MASTER_PRIMARY_ADMIN_REGISTRY",
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
        "identity_status": "UNVERIFIED_REFERENCE_ONLY",
        "invitation_status": "NOT_IMPLEMENTED",
        "access_changes": "BLOCKED_PENDING_APPROVAL",
        "administrators": [
            {
                "admin_user_id": str(row["admin_user_id"]),
                "tenant_count": row["tenant_count"],
                "active_count": row["active_count"],
                "suspended_count": row["suspended_count"],
                "draft_count": row["draft_count"],
                "closed_count": row["closed_count"],
            }
            for row in rows
        ],
    }


@router.get("/tenant-registry")
async def get_master_tenant_registry(
    search: str = Query(default="", max_length=80),
    tenant_status: Literal[
        "TODOS", "RASCUNHO_INATIVO", "ATIVO", "SUSPENSO", "ENCERRADO"
    ] = "TODOS",
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=5, le=50),
    session: AuthenticatedSession = Depends(require_master),
    conn = Depends(get_rls_db_connection),
):
    """Governanca cadastral: somente tenants e UUID do responsavel principal.

    Sem join com users/memberships, sem telefone, e-mail, saldos ou ledger.
    Identidade e status sao verificados por require_master e RLS PostgreSQL.
    """
    term = search.strip()
    state = "" if tenant_status == "TODOS" else tenant_status
    filter_sql = (
        " FROM public.tenants "
        "WHERE strpos(lower(display_name), lower($1::text)) > 0 "
        "AND ($2::text = '' OR status = $2::text)"
    )
    total = await conn.fetchval("SELECT count(*)" + filter_sql, term, state)
    rows = await conn.fetch(
        "SELECT id,display_name,status,is_owner_box,admin_user_id,created_at"
        + filter_sql +
        " ORDER BY created_at DESC,id DESC LIMIT $3 OFFSET $4",
        term, state, page_size, (page - 1) * page_size,
    )
    # Estes totais independem dos filtros e nao consultam financas dos tenants.
    groups = await conn.fetch(
        "SELECT status,count(*)::int AS count FROM public.tenants "
        "GROUP BY status ORDER BY status"
    )
    counts = {key: 0 for key in
              ("RASCUNHO_INATIVO", "ATIVO", "SUSPENSO", "ENCERRADO")}
    for group in groups:
        if group["status"] in counts:
            counts[group["status"]] = group["count"]
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "MASTER_TENANT_REGISTRY",
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
        "status_counts": counts,
        "tenants": [
            {
                "id": str(row["id"]),
                "display_name": row["display_name"],
                "status": row["status"],
                "is_owner_box": row["is_owner_box"],
                "admin_user_id": str(row["admin_user_id"]),
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ],
        "admin_invitation_status": "NOT_IMPLEMENTED",
        "admin_access_changes": "BLOCKED_PENDING_APPROVAL",
    }



@router.get("/saas-portfolio")
async def get_master_saas_portfolio(
    search: str = Query(default="", max_length=80),
    tenant_status: Literal["TODOS","RASCUNHO_INATIVO","ATIVO","SUSPENSO","ENCERRADO"] = "TODOS",
    page: int = Query(default=1, ge=1, le=1000),
    session: AuthenticatedSession = Depends(require_master),
    conn = Depends(get_rls_db_connection),
):
    """Inventario comercial por caixinha: apenas metadados SaaS, sem finanças dos membros.

    Nao existe capacidade de numero de caixinhas por administrador no contrato
    persistido. Por isso nunca inferir vagas a partir de limite de membros/cotas.
    """
    term = search.strip()
    predicate = (
        " FROM public.tenants t WHERE ("
        "strpos(lower(t.display_name),lower($1::text))>0 OR "
        "strpos(lower(t.admin_user_id::text),lower($1::text))>0) "
        "AND ($2::text='TODOS' OR t.status=$2::text)"
    )
    total = await conn.fetchval("SELECT count(*)" + predicate, term, tenant_status)
    rows = await conn.fetch("""
        SELECT t.id,t.display_name,t.status AS tenant_status,t.created_at,
               t.admin_user_id,
               (SELECT count(*)::int FROM public.tenants tx
                WHERE tx.admin_user_id=t.admin_user_id) AS admin_total,
               (SELECT count(*)::int FROM public.tenants tx
                WHERE tx.admin_user_id=t.admin_user_id AND tx.status='ATIVO') AS admin_active,
               (SELECT count(*)::int FROM public.tenants tx
                WHERE tx.admin_user_id=t.admin_user_id AND tx.status='SUSPENSO') AS admin_suspended,
               (SELECT count(*)::int FROM public.tenants tx
                WHERE tx.admin_user_id=t.admin_user_id AND tx.status='RASCUNHO_INATIVO') AS admin_draft,
               (SELECT count(*)::int FROM public.tenants tx
                WHERE tx.admin_user_id=t.admin_user_id AND tx.status='ENCERRADO') AS admin_closed,
               e.plan_tier AS licensed_plan,e.status AS license_status,
               e.valid_from,e.valid_until,
               CASE WHEN e.status='ACTIVE' AND e.valid_until<=now() THEN 'EXPIRED'
                    WHEN e.status='ACTIVE' AND e.valid_from>now() THEN 'NOT_STARTED'
                    ELSE e.status END AS effective_status,
               p.plan_tier AS prepared_plan,p.billing_period AS prepared_period,
               p.status AS preparation_status,p.created_at AS prepared_at,
               lp.members_limit,lp.quotas_limit
        FROM public.tenants t
        LEFT JOIN LATERAL (
            SELECT plan_tier,status,valid_from,valid_until
            FROM public.saas_license_entitlements
            WHERE tenant_id=t.id
            ORDER BY (status='ACTIVE' AND valid_from<=now() AND valid_until>now()) DESC,
                     valid_until DESC,id DESC LIMIT 1
        ) e ON true
        LEFT JOIN LATERAL (
            SELECT plan_tier,billing_period,status,created_at
            FROM public.saas_subscription_preparations
            WHERE tenant_id=t.id
            ORDER BY created_at DESC,id DESC LIMIT 1
        ) p ON true
        LEFT JOIN public.platform_license_plans lp ON lp.tier=e.plan_tier
        WHERE (strpos(lower(t.display_name),lower($1::text))>0 OR
               strpos(lower(t.admin_user_id::text),lower($1::text))>0)
          AND ($2::text='TODOS' OR t.status=$2::text)
        ORDER BY t.created_at DESC,t.id DESC
        LIMIT $3 OFFSET $4
    """, term, tenant_status, 20, (page-1)*20)
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "MASTER_SAAS_PORTFOLIO",
        "boxes_limit_policy": "NOT_DEFINED",
        "total": total, "page": page, "page_size": 20,
        "tenant_status_filter": tenant_status,
        "has_more": page*20 < total,
        "tenants": [
            {
                "id": str(row["id"]), "display_name": row["display_name"],
                "admin_user_id": str(row["admin_user_id"]),
                "tenant_status": row["tenant_status"],
                "registered_at": row["created_at"].isoformat(),
                "admin_total": row["admin_total"], "admin_active": row["admin_active"],
                "admin_suspended": row["admin_suspended"],
                "admin_draft": row["admin_draft"],
                "admin_closed": row["admin_closed"],
                "licensed_plan": row["licensed_plan"],
                "license_status": row["license_status"],
                "effective_status": row["effective_status"],
                "valid_from": row["valid_from"].isoformat() if row["valid_from"] else None,
                "valid_until": row["valid_until"].isoformat() if row["valid_until"] else None,
                "prepared_plan": row["prepared_plan"],
                "prepared_period": row["prepared_period"],
                "preparation_status": row["preparation_status"],
                "prepared_at": row["prepared_at"].isoformat() if row["prepared_at"] else None,
                "members_limit": row["members_limit"],
                "quotas_limit": row["quotas_limit"],
            }
            for row in rows
        ],
    }


@router.get("/licenses")
async def get_platform_licenses(
    session: AuthenticatedSession = Depends(require_master),
    conn = Depends(get_rls_db_connection),
):
    """Catalogo e versoes reais, nao cobrancas ou assinaturas ficticias."""
    rows = await conn.fetch(
        "SELECT p.tier,p.display_name,p.members_limit,p.quotas_limit,p.status,"
        "v.id AS version_id,v.monthly_price,v.annual_price,v.created_at "
        "FROM public.platform_license_plans p "
        "LEFT JOIN LATERAL (SELECT id,monthly_price,annual_price,created_at "
        "FROM public.platform_license_price_versions "
        "WHERE plan_tier=p.tier ORDER BY created_at DESC,id DESC LIMIT 1) v ON true "
        "ORDER BY p.tier"
    )
    return {
        "source": "POSTGRESQL_RLS",
        "billing_status": "NOT_CONNECTED_TO_RECONCILED_PROVIDER",
        "plans": [
            {
                "tier": r["tier"], "name": r["display_name"],
                "members_limit": r["members_limit"], "quotas_limit": r["quotas_limit"],
                "status": r["status"], "version_id": str(r["version_id"]) if r["version_id"] else None,
                "monthly_price": str(r["monthly_price"]) if r["monthly_price"] is not None else None,
                "annual_price_computed": str(r["annual_price"]) if r["annual_price"] is not None else None,
                "updated_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.post("/license-prices")
async def change_platform_license_price(
    payload: LicensePriceChange,
    session: AuthenticatedSession = Depends(require_master),
    conn = Depends(get_rls_db_connection),
):
    """Apenas o Master registra uma NOVA versao; sem alterar assinaturas ja pagas."""
    plan = await conn.fetchrow(
        "SELECT tier,status FROM public.platform_license_plans WHERE tier=$1", payload.tier
    )
    if not plan or plan["status"] != "ACTIVE":
        raise HTTPException(status_code=422, detail="Plano indisponivel para precificacao.")
    actor = uuid.UUID(session.user_id)
    row = await conn.fetchrow(
        "INSERT INTO public.platform_license_price_versions"
        "(plan_tier,monthly_price,changed_by,reason) VALUES($1,$2,$3,$4) "
        "RETURNING id,monthly_price,annual_price,created_at",
        payload.tier, payload.monthly_price, actor, payload.reason.strip()
    )
    await conn.execute(
        "INSERT INTO public.audit_events(actor_id,actor_role,action,object_type,object_id,"
        "reason,evidence_ref) VALUES($1,'MASTER','SAAS_PRICE_VERSION_CREATED',"
        "'LICENSE_PRICE',$2,$3,$4)",
        actor, str(row["id"]), payload.reason.strip(), "SAAS_PRICE_VERSION"
    )
    return {
        "status": "VERSION_PERSISTED_NO_BILLING",
        "tier": payload.tier,
        "version_id": str(row["id"]),
        "monthly_price": str(row["monthly_price"]),
        "annual_price_computed": str(row["annual_price"]),
        "created_at": row["created_at"].isoformat(),
    }


@router.post("/support-session")
def request_support_break_glass(payload: SupportBreakGlassRequest, session: AuthenticatedSession = Depends(require_master)):
    """
    RECURSO BREAK-GLASS: DESABILITADO POR PADRÃO.
    Conformidade Contratual Estrita (Cláusulas 1.3, 2.8, 5.4 e 16.4):
    O Contrato Técnico Mestre estabelece VEDAÇÃO ABSOLUTA DE INGERÊNCIA DO MASTER
    sobre saldos, dados financeiros e operações de membros das caixinhas.
    Como não há autorização explícita nem especificação completa de requisitos de
    consentimento mútuo prévio no Contrato, este endpoint é mantido BLOQUEADO e registrado
    como pendência negocial/jurídica. Não é permitido habilitá-lo por inferência.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "Recurso Desabilitado",
            "code": "BREAK_GLASS_UNAUTHORIZED_BY_CONTRACT",
            "message": (
                "Acesso excepcional de suporte (Break-Glass) está desabilitado. "
                "O Contrato Técnico Mestre (Cláusulas 1.3, 2.8 e 5.4) impõe vedação absoluta de "
                "ingerência do Master sobre caixinhas. Operação mantida como pendência contratual."
            )
        }
    )



@router.get("/overview")
async def get_master_overview(
    session: AuthenticatedSession = Depends(require_master),
    conn = Depends(get_rls_db_connection),
):
    """Inventario cadastral visivel ao MASTER, sem saldos de caixinhas."""
    total = await conn.fetchval("SELECT count(*) FROM public.tenants")
    rows = await conn.fetch(
        "SELECT id,display_name,status,is_owner_box "
        "FROM public.tenants ORDER BY created_at DESC,id LIMIT 200"
    )
    return {
        "source": "POSTGRESQL_RLS",
        "total_tenants": total,
        "tenants": [
            {
                "id": str(r["id"]),
                "display_name": r["display_name"],
                "status": r["status"],
                "is_owner_box": r["is_owner_box"],
            }
            for r in rows
        ],
        "has_more": total > len(rows),
        "saas_revenue_status": "NOT_CONNECTED_TO_RECONCILED_BILLING",
        "subscriptions_status": "NOT_IMPLEMENTED_IN_PERSISTENT_SCHEMA",
    }



@router.get("/subscription-preparations")
async def list_saas_subscription_preparations(
    session: AuthenticatedSession = Depends(require_master),
    conn=Depends(get_rls_db_connection),
):
    """Inventário documental SaaS da plataforma, sem dados de saldo dos tenants.

    Nenhuma assinatura nesta tabela representa pagamento confirmado.
    """
    rows = await conn.fetch(
        "SELECT id,tenant_id,plan_tier,price_version_id,billing_period,status,created_at "
        "FROM public.saas_subscription_preparations "
        "ORDER BY created_at DESC,id DESC LIMIT 200"
    )
    return {
        "source":"POSTGRESQL_RLS",
        "billing_status":"NO_PROVIDER_NO_FINANCIAL_ACTIVATION",
        "total_returned":len(rows),
        "preparations":[
            {"id":str(r["id"]),"tenant_id":str(r["tenant_id"]),
             "plan_tier":r["plan_tier"],"price_version_id":str(r["price_version_id"]),
             "billing_period":r["billing_period"],"status":r["status"],
             "created_at":r["created_at"].isoformat()}
            for r in rows
        ],
    }



@router.get("/saas-payment-status")
async def master_saas_payment_status(
    session: AuthenticatedSession = Depends(require_master),
    conn=Depends(get_rls_db_connection),
):
    """Visibilidade SaaS da plataforma: sem saldo das caixinhas, sem ativar."""
    payments=await conn.fetch(
        "SELECT id,tenant_id,status,expected_amount_cents,currency,created_at "
        "FROM public.saas_payment_intents "
        "ORDER BY created_at DESC,id DESC LIMIT 200"
    )
    entitlements=await conn.fetch(
        "SELECT id,tenant_id,plan_tier,status,valid_from,valid_until,"
        "CASE WHEN status='ACTIVE' AND valid_until<=NOW() THEN 'EXPIRED' "
        "ELSE status END AS effective_status "
        "FROM public.saas_license_entitlements "
        "ORDER BY valid_until DESC,id DESC LIMIT 200"
    )
    return {
        "source":"POSTGRESQL_RLS","provider":"MERCADO_PAGO",
        "payments":[
            {"id":str(p["id"]),"tenant_id":str(p["tenant_id"]),"status":p["status"],
             "expected_amount_cents":p["expected_amount_cents"],
             "currency":p["currency"],"created_at":p["created_at"].isoformat()}
            for p in payments
        ],
        "licenses":[
            {"id":str(e["id"]),"tenant_id":str(e["tenant_id"]),
             "plan_tier":e["plan_tier"],"status":e["status"],
             "effective_status":e["effective_status"],
             "valid_from":e["valid_from"].isoformat(),
             "valid_until":e["valid_until"].isoformat()}
            for e in entitlements
        ],
    }


@router.get("/integration-readiness")
async def master_integration_readiness(
    session: AuthenticatedSession = Depends(require_master),
):
    """Não consulta credenciais e não permite habilitar provedor pela interface."""
    from ..platform_provider_adapters import read_configuration_status
    return read_configuration_status()
