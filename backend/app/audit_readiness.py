"""FRcaixinha AI Studio: diagnóstico sintático de trilha, nunca comprovação de autenticidade."""
import uuid
from datetime import datetime
from fastapi import HTTPException
from .models import AuditReadinessResponse

def summarize_audit_rows(rows, tenant_id: str) -> AuditReadinessResponse:
    if len(rows)>500:
        raise HTTPException(status_code=503,detail="Auditoria indisponível: limite de consulta.")
    seen=set()
    review=0
    for row in rows:
        try:
            event_id=str(uuid.UUID(str(row["id"])))
            if event_id in seen:
                raise ValueError("Evento duplicado")
            seen.add(event_id)
            created=row["created_at"]
            fields=(row["actor_role"],row["action"],row["object_type"],
                    row["object_id"],row["reason"],row["evidence_ref"])
            if not isinstance(created,datetime) or any(
                not isinstance(v,str) or not v.strip() for v in fields
            ):
                review+=1
            actor=row["actor_id"]
            if actor is not None:
                uuid.UUID(str(actor))
        except (KeyError,ValueError,TypeError,OverflowError) as exc:
            raise HTTPException(status_code=503,
                detail="Auditoria indisponível: identificadores inválidos.") from exc
    total=len(rows)
    return AuditReadinessResponse(
        source="POSTGRESQL_RLS",scope="TENANT_ADMIN_READ_ONLY",tenant_id=tenant_id,
        checked_events=total,fields_present_events=total-review,
        review_required_events=review,
        status="NO_EVENTS" if total==0 else
               ("REVIEW_REQUIRED" if review else "FIELDS_PRESENT_ONLY"),
        provenance_verified=False,append_only_verified=False,
        financial_audit_approved=False
    )
