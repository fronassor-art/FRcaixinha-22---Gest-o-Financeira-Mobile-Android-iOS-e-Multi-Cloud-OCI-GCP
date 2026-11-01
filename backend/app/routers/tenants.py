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
