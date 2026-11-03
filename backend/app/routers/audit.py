"""
FRcaixinha 2.2 — Rotas de Trilha de Auditoria Imutável (Append-Only)
Contrato Técnico Mestre (Cláusulas 2.8, 14.1 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid
from ..models import AuditEventResponse, AuditEventCreatePayload
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection

router = APIRouter(prefix="/tenants/{tenant_id}/audit-events", tags=["Trilha de Auditoria Imutável"])

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

    event_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO audit_events (
            id, actor_id, actor_role, tenant_id, action, object_type, object_id, reason, evidence_ref, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW());
    """, event_id, uuid.UUID(session.user_id), session.role, uuid.UUID(tenant_id),
       payload.action, payload.object_type, payload.object_id, payload.reason, payload.evidence_ref)

    return AuditEventResponse(
        id=str(event_id),
        actor_id=str(session.user_id),
        actor_role=session.role,
        tenant_id=tenant_id,
        action=payload.action,
        object_type=payload.object_type,
        object_id=payload.object_id,
        reason=payload.reason,
        evidence_ref=payload.evidence_ref,
        created_at=datetime.utcnow()
    )
