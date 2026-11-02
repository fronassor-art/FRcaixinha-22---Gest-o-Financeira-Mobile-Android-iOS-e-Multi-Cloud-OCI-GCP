"""Consultas autoritativas das caixinhas para o aplicativo AI Studio.

Nunca retorna dados seed nem permite acesso MASTER a finanças.
Todas as consultas usam transacao com contexto da sessao e RLS PostgreSQL.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_rls_db_connection
from ..dependencies import (
    AuthenticatedSession,
    get_current_session,
    require_tenant_access,
)

router = APIRouter(prefix="/tenants", tags=["Caixinhas e Isolamento Multi-Tenant"])


def _tenant_uuid(tenant_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(tenant_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="Identificador de caixinha inválido.")


@router.get("/{tenant_id}/dashboard")
async def get_tenant_dashboard(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Resumo somente leitura para o papel ativo, sem extrapolar RLS."""
    require_tenant_access(tenant_id, session)
    tenant = _tenant_uuid(tenant_id)
    # SELECT por RLS: para o membro, somente suas próprias linhas.
    quotas = await conn.fetchval(
        "SELECT count(*) FROM public.quotas WHERE tenant_id=$1", tenant
    )
    contributions = await conn.fetchval(
        "SELECT count(*) FROM public.contributions WHERE tenant_id=$1", tenant
    )
    loans = await conn.fetchval(
        "SELECT count(*) FROM public.loans WHERE tenant_id=$1", tenant
    )
    response = {
        "source": "POSTGRESQL_RLS",
        "tenant_id": str(tenant),
        "role": session.role,
        "quota_count_visible": quotas,
        "contribution_count_visible": contributions,
        "loan_count_visible": loans,
        "financial_operations": "PENDING_BANK_RECONCILIATION",
    }
    if session.role == "TENANT_ADMIN":
        response["member_count_visible"] = await conn.fetchval(
            "SELECT count(*) FROM public.memberships "
            "WHERE tenant_id=$1 AND status='ATIVA'", tenant
        )
    return response


@router.get("/{tenant_id}/members")
async def get_tenant_members(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Lista minimizada, visível apenas ao administrador do próprio tenant.

    Não divulga CPF, telefone, credenciais ou histórico financeiro.
    """
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Lista de membros exclusiva do administrador.")
    tenant = _tenant_uuid(tenant_id)
    rows = await conn.fetch(
        "SELECT m.id,m.role,m.status,m.joined_at,u.full_name "
        "FROM public.memberships m JOIN public.users u ON u.id=m.user_id "
        "WHERE m.tenant_id=$1 "
        "ORDER BY m.joined_at DESC,m.id LIMIT 200",
        tenant,
    )
    return {
        "source": "POSTGRESQL_RLS",
        "tenant_id": str(tenant),
        "members": [
            {
                "id": str(r["id"]),
                "name": r["full_name"],
                "role": r["role"],
                "status": r["status"],
                "joined_at": r["joined_at"].isoformat(),
            }
            for r in rows
        ],
    }



@router.get("/{tenant_id}/license-preparation")
async def tenant_license_preparation(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Admin vê somente preparações da própria licença, nunca receita ou Pix."""
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403,detail="Licenciamento exclusivo do administrador da caixinha.")
    tenant = _tenant_uuid(tenant_id)
    rows = await conn.fetch(
        "SELECT id,plan_tier,price_version_id,billing_period,status,created_at "
        "FROM public.saas_subscription_preparations "
        "WHERE tenant_id=$1 ORDER BY created_at DESC,id DESC LIMIT 50",tenant
    )
    return {
        "source":"POSTGRESQL_RLS","tenant_id":str(tenant),
        "billing_status":"NO_PROVIDER_NO_FINANCIAL_ACTIVATION",
        "preparations":[
            {"id":str(r["id"]),"plan_tier":r["plan_tier"],
             "price_version_id":str(r["price_version_id"]),
             "billing_period":r["billing_period"],"status":r["status"],
             "created_at":r["created_at"].isoformat()}
            for r in rows
        ],
    }


@router.get("/{tenant_id}/my-contracts")
async def own_contracts_in_tenant(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Aceites documentais próprios no tenant ativo; não revela outros membros."""
    require_tenant_access(tenant_id,session)
    tenant=_tenant_uuid(tenant_id)
    rows=await conn.fetch(
        "SELECT a.id,a.document_id,a.document_kind,a.accepted_at,"
        "d.version_label,d.sha256,d.source_reference "
        "FROM public.contract_acceptances a "
        "JOIN public.contract_documents d ON d.id=a.document_id "
        "WHERE a.user_id=$1 AND (a.tenant_id=$2 OR "
        "(a.tenant_id IS NULL AND a.document_kind='PLATFORM_LICENSE')) "
        "ORDER BY a.accepted_at DESC,a.id DESC LIMIT 100",
        uuid.UUID(session.user_id),tenant,
    )
    return {
        "source":"POSTGRESQL_RLS","tenant_id":str(tenant),
        "contracts":[
            {"id":str(r["id"]),"document_id":str(r["document_id"]),
             "kind":r["document_kind"],"version":r["version_label"],
             "sha256":r["sha256"],"source_reference":r["source_reference"],
             "accepted_at":r["accepted_at"].isoformat()}
            for r in rows
        ],
    }



@router.get("/{tenant_id}/saas-payment-status")
async def tenant_saas_payment_status(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Somente o administrador da caixinha consulta sua cobrança de licença."""
    require_tenant_access(tenant_id,session)
    if session.role!="TENANT_ADMIN":
        raise HTTPException(status_code=403,detail="Cobrança SaaS exclusiva do administrador.")
    tenant=_tenant_uuid(tenant_id)
    payments=await conn.fetch(
        "SELECT id,status,expected_amount_cents,currency,created_at "
        "FROM public.saas_payment_intents WHERE tenant_id=$1 "
        "ORDER BY created_at DESC,id DESC LIMIT 50",tenant,
    )
    entitlements=await conn.fetch(
        "SELECT id,plan_tier,status,valid_from,valid_until,"
        "CASE WHEN status='ACTIVE' AND valid_until<=NOW() THEN 'EXPIRED' "
        "ELSE status END AS effective_status "
        "FROM public.saas_license_entitlements WHERE tenant_id=$1 "
        "ORDER BY valid_until DESC,id DESC LIMIT 50",tenant,
    )
    return {
        "source":"POSTGRESQL_RLS","tenant_id":str(tenant),
        "payments":[
            {"id":str(p["id"]),"status":p["status"],
             "expected_amount_cents":p["expected_amount_cents"],"currency":p["currency"],
             "created_at":p["created_at"].isoformat()}
            for p in payments
        ],
        "licenses":[
            {"id":str(e["id"]),"plan_tier":e["plan_tier"],"status":e["status"],
             "effective_status":e["effective_status"],
             "valid_from":e["valid_from"].isoformat(),
             "valid_until":e["valid_until"].isoformat()}
            for e in entitlements
        ],
    }
