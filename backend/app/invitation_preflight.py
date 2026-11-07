"""M24900 — pré-diagnóstico de convite AI Studio, somente leitura.

Este módulo não emite, entrega, aceita ou revoga convites. Não verifica
identidade real, publicação de documento ou direitos de um tenant no banco.
As verificações de autorização reais devem ocorrer no momento da escrita,
por uma role restrita e transação auditada, após revisão de segurança.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException


def authorize_invitation_intent(*, session, payload) -> None:
    """Impedir que papéis sem escopo preparem até mesmo uma intenção."""
    if session.role not in ("MASTER", "TENANT_ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Somente Master ou administrador de caixinha podem solicitar convites.",
        )
    if session.role == "MASTER":
        if not session.is_master or payload.target_role != "TENANT_ADMIN":
            raise HTTPException(
                status_code=403,
                detail="O Master somente pode convidar administradores de caixinha.",
            )
        return
    if payload.target_role != "TENANT_MEMBER" or not session.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="O administrador somente pode convidar membros de sua caixinha.",
        )
    if payload.tenant_id is not None and payload.tenant_id != session.tenant_id:
        # Identificadores idênticos preservam clientes/fixtures legados;
        # para UUID reais, comparar também formas textuais equivalentes.
        try:
            incoming = UUID(payload.tenant_id)
            active = UUID(session.tenant_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(status_code=403, detail="Caixinha não autorizada.") from None
        if incoming != active:
            raise HTTPException(status_code=403, detail="Caixinha não autorizada.")


def invitation_readiness(*, session, payload, database_configured: bool) -> dict:
    """Diagnóstico de prontidão sem consultar usuários, banco, documentos ou e-mail.

    Uma referência UUID recebida nunca equivale a documento publicado.
    A sessão de preflight também NÃO cria autorização para operação futura.
    """
    authorize_invitation_intent(session=session, payload=payload)
    gates = [
        "PUBLISHED_MEMBERSHIP_CONTRACT_NOT_VERIFIED",
        "RECIPIENT_EMAIL_OWNERSHIP_NOT_VERIFIED",
        "EMAIL_DELIVERY_PROVIDER_NOT_VERIFIED",
        "TRANSACTIONAL_AUDIT_AND_SINGLE_USE_NOT_VERIFIED",
        "DATABASE_ROLE_AND_TENANT_RECHECK_NOT_VERIFIED",
    ]
    if payload.required_document_id is None:
        gates.insert(0, "REQUIRED_DOCUMENT_ID_MISSING")
    if session.role == "MASTER":
        try:
            target = UUID(payload.tenant_id) if payload.tenant_id else None
        except (ValueError, TypeError, AttributeError):
            target = None
        if target is None:
            gates.insert(0, "TARGET_TENANT_ID_REQUIRED")
        gates += ["MASTER_MFA_NOT_ATTESTED", "INDEPENDENT_APPROVAL_NOT_ATTESTED"]
    if not database_configured:
        gates.insert(0, "DATABASE_CONFIG_NOT_ATTESTED")
    return {
        "scope": "AI_STUDIO_INVITATION_PREFLIGHT",
        "mode": "READ_ONLY_NO_DELIVERY",
        "status": "BLOCKED",
        "actor_role": session.role,
        "target_role": payload.target_role,
        "required_document_reference_present": payload.required_document_id is not None,
        "document_published_verified": False,
        "recipient_verified": False,
        "provider_delivery_verified": False,
        "activation_authorized": False,
        "invitation_created": False,
        "email_sent": False,
        "user_created": False,
        "membership_changed": False,
        "writes_performed": False,
        "blocking_gates": gates,
    }
