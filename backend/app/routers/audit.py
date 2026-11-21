"""
FRcaixinha AI Studio — Rotas de auditoria de tenant (consulta administrativa)
Contrato Técnico Mestre (Cláusulas 2.8, 14.1 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid
from ..models import AuditEventResponse, AuditEventCreatePayload, AuditReadinessResponse
from ..audit_readiness import summarize_audit_rows
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection

router = APIRouter(prefix="/tenants/{tenant_id}/audit-events", tags=["Trilha de Auditoria Imutável"])

@router.get("/readiness-preview", response_model=AuditReadinessResponse)
async def get_audit_readiness_preview(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection),
):
    """Sintaxe dos eventos, sem afirmar autoria ou origem verificadas."""
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Diagnóstico exclusivo do administrador.")
    try:
        tenant = uuid.UUID(tenant_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Caixinha inválida.") from exc
    rows = await conn.fetch("""
        SELECT id, actor_id, actor_role, action, object_type, object_id,
               reason, evidence_ref, created_at
        FROM public.audit_events
        WHERE tenant_id=$1
        ORDER BY created_at DESC, id ASC
        LIMIT 501
    """, tenant)
    return summarize_audit_rows(rows, tenant_id)


@router.get("", response_model=List[AuditEventResponse])
async def list_tenant_audit_events(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Consulta os eventos de auditoria registrados na caixinha:
    - Master: RECUSADO com 403 (Cláusula 2.8);
    - Membros comuns: RECUSADO com 403;
    - Administrador do Tenant: Acesso à trilha de conformidade do seu tenant.
    """
    require_tenant_access(tenant_id, session)

    if session.role in ("MASTER", "TENANT_MEMBER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido à trilha analítica de auditoria do tenant."
        )

    rows = await conn.fetch("""
        SELECT id, actor_id, actor_role, tenant_id, action, object_type, object_id, reason, evidence_ref, created_at
        FROM audit_events
        WHERE tenant_id = $1
        ORDER BY created_at DESC;
    """, uuid.UUID(tenant_id))

    return [
        AuditEventResponse(
            id=str(r["id"]),
            actor_id=str(r["actor_id"]) if r["actor_id"] else None,
            actor_role=r["actor_role"],
            tenant_id=str(r["tenant_id"]) if r["tenant_id"] else None,
            action=r["action"],
            object_type=r["object_type"],
            object_id=r["object_id"],
            reason=r["reason"],
            evidence_ref=r["evidence_ref"],
            created_at=r["created_at"]
        )
        for r in rows
    ]


@router.post("", response_model=AuditEventResponse)
async def create_tenant_audit_event(
    tenant_id: str,
    payload: AuditEventCreatePayload,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Registra um novo evento na trilha imutável (Append-Only):
    - Impede alteração ou exclusão de eventos existentes.
    """
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Evento de auditoria exclusivo do administrador.")
    # O payload legado era autodeclarado pelo cliente, sem procedência
    # verificada ou vínculo com ação de domínio confirmada pelo servidor.
    # Sem esse controle, criar uma trilha oficial seria evidência falsa.
    raise HTTPException(status_code=503, detail=(
        "Registro manual de auditoria indisponível até comprovar origem e integridade."
    ))

