"""
FRcaixinha 2.2 — Rotas Exclusivas do Administrador Master
Contrato Técnico Mestre (Cláusulas 1.3, 2.8, 3.2, 5.4, 11.2 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal
import uuid
from ..dependencies import require_master, AuthenticatedSession
from ..database import get_rls_db_connection

router = APIRouter(prefix="/master", tags=["Governança Master da Plataforma"])

class SupportBreakGlassRequest(BaseModel):
    target_tenant_id: str
    justification: str = Field(..., min_length=15, description="Justificativa formal auditável para acesso emergencial de suporte")
    duration_minutes: int = Field(default=30, le=60, description="Duração máxima do acesso excepcional (máx 60 min)")

class LicensePriceChange(BaseModel):
    tier: Literal['ESSENCIAL', 'INTERMEDIARIO']
    monthly_price: Decimal = Field(..., gt=Decimal('0'), le=Decimal('999999.99'), decimal_places=2)
    reason: str = Field(..., min_length=15, max_length=500)


@router.get("/owner-access")
async def confirm_owner_access(session: AuthenticatedSession = Depends(require_master)):
    """Confirma papel MASTER no backend sem revelar dados de proprietario ou tenant."""
    return {
        "verified": True,
        "role": "MASTER",
        "scope": "PLATFORM_GOVERNANCE_ONLY",
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
