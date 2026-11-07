"""M25200 — verificação de bytes contratuais sem aceite, gravação nem entrega.

Apenas SHA-256 do texto exato UTF-8 contra uma versão publicada, sob o RLS
da conexão injetada pela API. Nunca converte CRLF, normaliza Unicode, usa
HTML, assina ou expõe o texto recebido em resposta. Não suporta arquivos PDF;
o hash publicado precisa ter sido calculado sobre os mesmos bytes UTF-8.
"""
from __future__ import annotations

from hashlib import sha256
import hmac

from fastapi import HTTPException

from .invitation_preflight import authorize_invitation_intent

MAX_CONTRACT_TEXT_BYTES = 65536


def exact_utf8_sha256(text: str) -> str:
    """Retorna digest somente de texto não vazio, codificável em UTF-8."""
    if type(text) is not str or not text:
        raise HTTPException(status_code=422, detail="Texto contratual inválido.")
    try:
        raw = text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise HTTPException(status_code=422, detail="Texto contratual não é UTF-8 válido.") from None
    if not 1 <= len(raw) <= MAX_CONTRACT_TEXT_BYTES:
        raise HTTPException(status_code=422, detail="Tamanho de texto contratual não permitido.")
    return sha256(raw).hexdigest()


async def verify_contract_body_digest(*, session, payload, conn) -> dict:
    """Compara texto proposto ao digest publicado, usando SELECT sob RLS.

    Mesmo se coincidir, não produz documento canônico hospedado, aceite,
    convite, ativação ou autorização para outra operação. Nunca ecoa body,
    hash fornecido pelo cliente, usuário, nomes ou detalhes de origem.
    """
    authorize_invitation_intent(session=session, payload=payload)
    candidate_digest = exact_utf8_sha256(payload.contract_text)

    active = bool(await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM public.tenants "
        "WHERE id=$1::uuid AND status='ATIVO')",
        payload.tenant_id,
    ))
    published_digest = None
    if active:
        published_digest = await conn.fetchval(
            "SELECT sha256 FROM public.contract_documents "
            "WHERE id=$1::uuid AND document_kind='TENANT_MEMBERSHIP' "
            "AND published_at IS NOT NULL",
            payload.required_document_id,
        )
    published = published_digest is not None
    expected = published_digest.strip() if type(published_digest) is str else ""
    matches = bool(
        published and len(expected) == 64
        and hmac.compare_digest(candidate_digest, expected)
    )
    gates = [
        "RUNTIME_INVITATION_ISSUANCE_DISABLED",
        "CANONICAL_CONTRACT_HOSTING_NOT_ATTESTED",
        "RECIPIENT_EMAIL_OWNERSHIP_NOT_VERIFIED",
        "EMAIL_DELIVERY_PROVIDER_NOT_VERIFIED",
        "TRANSACTIONAL_ACCEPTANCE_NOT_IMPLEMENTED",
    ]
    if not active:
        gates.insert(0, "ACTIVE_TENANT_NOT_ATTESTED")
    if not published:
        gates.insert(0, "PUBLISHED_MEMBERSHIP_CONTRACT_NOT_ATTESTED")
    if not matches:
        gates.insert(0, "EXACT_UTF8_DOCUMENT_DIGEST_NOT_MATCHED")
    if session.role == "MASTER":
        gates.extend(["MASTER_MFA_NOT_ATTESTED", "INDEPENDENT_APPROVAL_NOT_ATTESTED",
                      "PLATFORM_LICENSE_ACCEPTANCE_NOT_VERIFIED"])

    return {
        "source": "POSTGRESQL_RLS",
        "scope": "AI_STUDIO_CONTRACT_BODY_DIGEST_PREFLIGHT",
        "status": "BLOCKED",
        "target_role": payload.target_role,
        "tenant_active_verified": active,
        "document_published_verified": published,
        "exact_utf8_document_digest_matched": matches,
        "canonical_document_hosted": False,
        "body_rendered_for_invitee": False,
        "consent_verified": False,
        "acceptance_recorded": False,
        "invitation_created": False,
        "email_sent": False,
        "user_created": False,
        "membership_changed": False,
        "writes_performed": False,
        "activation_authorized": False,
        "blocking_gates": gates,
    }
