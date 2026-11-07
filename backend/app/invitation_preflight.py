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
    if payload.tenant_id is not None and str(payload.tenant_id) != str(session.tenant_id):
        # Identificadores idênticos preservam clientes/fixtures legados;
        # para UUID reais, comparar também formas textuais equivalentes.
        try:
            incoming = UUID(str(payload.tenant_id))
            active = UUID(str(session.tenant_id))
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


async def invitation_contract_readiness(*, session, payload, conn) -> dict:
    """Consulta RLS real de caixinha e documento, sem emissão ou concessão.

    O conector fornecido por get_rls_db_connection usa role sem INSERT/UPDATE
    em documentos, contexto do usuário autenticado e transação isolada.
    Nenhum CPF, e-mail, nome de usuário ou token é consultado ou retornado.
    """
    authorize_invitation_intent(session=session, payload=payload)
    # A API de prontidão requer referência exata do tenant e da publicação.
    if not isinstance(payload.tenant_id, UUID) or not isinstance(
        payload.required_document_id, UUID
    ):
        raise HTTPException(status_code=422, detail="Referências inválidas.")
    # SELECT sob RLS: invisibilidade e estado inativo ficam indistinguíveis.
    active = bool(await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM public.tenants "
        "WHERE id=$1::uuid AND status='ATIVO')",
        payload.tenant_id,
    ))
    published = bool(await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM public.contract_documents "
        "WHERE id=$1::uuid AND document_kind='TENANT_MEMBERSHIP' "
        "AND published_at IS NOT NULL)",
        payload.required_document_id,
    ))
    gates: list[str] = []
    if not active:
        gates.append("ACTIVE_TENANT_NOT_ATTESTED")
    if not published:
        gates.append("PUBLISHED_MEMBERSHIP_CONTRACT_NOT_ATTESTED")
    gates += [
        "RECIPIENT_EMAIL_OWNERSHIP_NOT_VERIFIED",
        "EMAIL_DELIVERY_PROVIDER_NOT_VERIFIED",
        "TRANSACTIONAL_AUDIT_AND_SINGLE_USE_NOT_VERIFIED",
        "RUNTIME_INVITATION_ISSUANCE_DISABLED",
    ]
    if session.role == "MASTER":
        gates += [
            "MASTER_MFA_NOT_ATTESTED",
            "INDEPENDENT_APPROVAL_NOT_ATTESTED",
            "PLATFORM_LICENSE_ACCEPTANCE_NOT_VERIFIED",
        ]
    return {
        "scope": "AI_STUDIO_INVITATION_CONTRACT_READINESS",
        "source": "POSTGRESQL_RLS",
        "status": "BLOCKED",
        "tenant_active_verified": active,
        "document_published_verified": published,
        "document_kind": "TENANT_MEMBERSHIP",
        "target_role": payload.target_role,
        "recipient_email_verified": False,
        "provider_delivery_verified": False,
        "activation_authorized": False,
        "invitation_created": False,
        "email_sent": False,
        "user_created": False,
        "membership_changed": False,
        "writes_performed": False,
        "blocking_gates": gates,
    }
