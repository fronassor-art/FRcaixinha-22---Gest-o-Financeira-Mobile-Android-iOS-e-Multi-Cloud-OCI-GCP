"""AI Studio M14100-M15000: notification policy; no messages are sent here.

The contract requires accurate information, regularization/security notices,
tenant and role separation and provider webhook authentication. It does NOT
approve a reminder cadence, WhatsApp blast, token collection or live delivery.
These are UNTRUSTED domain claims and cannot be used as delivery permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from re import fullmatch
from uuid import UUID

from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M15000_NOTIFICATION_CONTRACT_DRAFT_OFFLINE_V1"
MAX_BATCH = 100


class NoticeKind(str, Enum):
    LICENSE_REGULARIZATION = "LICENSE_REGULARIZATION"
    LICENSE_REVERSED_REVIEW = "LICENSE_REVERSED_REVIEW"
    SUPPORT_ACCESS_ALERT = "SUPPORT_ACCESS_ALERT"
    INVITATION_ACCEPTANCE_PENDING = "INVITATION_ACCEPTANCE_PENDING"
    CONTRIBUTION_DUE_INFO = "CONTRIBUTION_DUE_INFO"
    CONTRIBUTION_OVERDUE_INFO = "CONTRIBUTION_OVERDUE_INFO"
    LOAN_REVIEW_PENDING = "LOAN_REVIEW_PENDING"
    FINANCIAL_STATUS_UNVERIFIED = "FINANCIAL_STATUS_UNVERIFIED"
    CLOSING_REVIEW_PENDING = "CLOSING_REVIEW_PENDING"
    SECURITY_SESSION_ALERT = "SECURITY_SESSION_ALERT"
    SELF_TEST = "SELF_TEST"


class NoticeChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    PUSH = "PUSH"
    WHATSAPP = "WHATSAPP"


class NoticeRole(str, Enum):
    MASTER = "MASTER"
    TENANT_ADMIN = "TENANT_ADMIN"
    TENANT_MEMBER = "TENANT_MEMBER"


# Master receives platform/commercial alerts, NEVER member's financial status.
# Each tenant role receives only its own scoped operational messages.
_ROLES = {
    NoticeKind.LICENSE_REGULARIZATION: frozenset((NoticeRole.TENANT_ADMIN,)),
    NoticeKind.LICENSE_REVERSED_REVIEW: frozenset((NoticeRole.TENANT_ADMIN,)),
    NoticeKind.SUPPORT_ACCESS_ALERT: frozenset((NoticeRole.TENANT_ADMIN,)),
    NoticeKind.INVITATION_ACCEPTANCE_PENDING: frozenset((NoticeRole.TENANT_MEMBER,)),
    NoticeKind.CONTRIBUTION_DUE_INFO: frozenset((NoticeRole.TENANT_MEMBER,)),
    NoticeKind.CONTRIBUTION_OVERDUE_INFO: frozenset((NoticeRole.TENANT_MEMBER,)),
    NoticeKind.LOAN_REVIEW_PENDING: frozenset((NoticeRole.TENANT_ADMIN,NoticeRole.TENANT_MEMBER)),
    NoticeKind.FINANCIAL_STATUS_UNVERIFIED: frozenset((NoticeRole.TENANT_ADMIN,NoticeRole.TENANT_MEMBER)),
    NoticeKind.CLOSING_REVIEW_PENDING: frozenset((NoticeRole.TENANT_ADMIN,)),
    NoticeKind.SECURITY_SESSION_ALERT: frozenset(NoticeRole),
    NoticeKind.SELF_TEST: frozenset(NoticeRole),
}

_TEMPLATES = {
    NoticeKind.LICENSE_REGULARIZATION: (
        "Regularização da licença",
        "Há uma situação de licença a verificar. Consulte o painel da sua caixinha."
    ),
    NoticeKind.LICENSE_REVERSED_REVIEW: (
        "Revisão de licença",
        "Um evento financeiro exige conferência da licença. Nenhum pagamento foi confirmado por este aviso."
    ),
    NoticeKind.SUPPORT_ACCESS_ALERT: (
        "Acesso técnico excepcional",
        "Um evento de suporte exige conferência na área administrativa."
    ),
    NoticeKind.INVITATION_ACCEPTANCE_PENDING: (
        "Convite para caixinha",
        "Há um convite ou aceite pendente. A participação depende de confirmação."
    ),
    NoticeKind.CONTRIBUTION_DUE_INFO: (
        "Contribuição a conferir",
        "Consulte o vencimento registrado e o status da obrigação na sua caixinha."
    ),
    NoticeKind.CONTRIBUTION_OVERDUE_INFO: (
        "Pendência de contribuição",
        "Existe uma obrigação registrada que exige conferência. Este aviso não cria cobrança."
    ),
    NoticeKind.LOAN_REVIEW_PENDING: (
        "Análise de empréstimo",
        "Consulte a situação da solicitação. Este aviso não autoriza desembolso."
    ),
    NoticeKind.FINANCIAL_STATUS_UNVERIFIED: (
        "Pagamento em verificação",
        "A confirmação bancária ainda não foi comprovada. Não considere como pago."
    ),
    NoticeKind.CLOSING_REVIEW_PENDING: (
        "Fechamento em revisão",
        "Há uma etapa de conferência. Este aviso não autoriza fechamento ou Pix."
    ),
    NoticeKind.SELF_TEST: (
        "Aviso de teste interno",
        "Teste do recebimento interno realizado nesta conta. Nenhum pagamento ou envio externo foi executado."
    ),
    NoticeKind.SECURITY_SESSION_ALERT: (
        "Segurança de acesso",
        "Um evento de acesso exige verificação. Consulte as sessões da sua conta."
    ),
}


@dataclass(frozen=True)
class NoticeClaim:
    event_id: UUID
    event_kind: NoticeKind
    recipient_id: UUID
    role: NoticeRole
    tenant_id: UUID | None
    cycle_year: int | None
    occurred_at: datetime
    authenticated_event_source: bool
    authenticated_recipient: bool
    tenant_membership_verified: bool
    source_reference_digest: str


@dataclass(frozen=True)
class NoticePreferencesClaim:
    recipient_id: UUID
    channel: NoticeChannel
    opt_in: bool
    address_verified: bool
    purpose_documented: bool


@dataclass(frozen=True)
class NoticePreview:
    recipient_id: UUID
    role: NoticeRole
    tenant_id: UUID | None
    event_kind: NoticeKind
    title: str
    message: str
    fingerprint: str
    policy_only: bool = True
    in_app_write_authorized: bool = False
    external_send_authorized: bool = False
    payment_confirmed: bool = False
    bank_reconciled: bool = False
    ledger_written: bool = False
    payout_authorized: bool = False


@dataclass(frozen=True)
class NoticeBatchPreview:
    candidate_count: int
    exact_replays_suppressed: int
    fingerprints: tuple[str, ...]
    tenant_scoped: bool = True
    delivered: bool = False
    persisted: bool = False
    external_send_authorized: bool = False
    payment_confirmed: bool = False


def _aware_utc(t: datetime) -> bool:
    return (type(t) is datetime and t.tzinfo is not None
            and t.utcoffset() is not None)


def _validate_notice(c: NoticeClaim) -> None:
    if (
        type(c) is not NoticeClaim
        or type(c.event_id) is not UUID or c.event_id.int == 0
        or type(c.recipient_id) is not UUID or c.recipient_id.int == 0
        or type(c.event_kind) is not NoticeKind
        or type(c.role) is not NoticeRole
        or not _aware_utc(c.occurred_at)
        or type(c.authenticated_event_source) is not bool
        or type(c.authenticated_recipient) is not bool
        or type(c.tenant_membership_verified) is not bool
        or type(c.source_reference_digest) is not str
        or fullmatch(r"[a-f0-9]{64}", c.source_reference_digest) is None
        or (c.tenant_id is not None
            and (type(c.tenant_id) is not UUID or not c.tenant_id.int))
        or (c.cycle_year is not None
            and (type(c.cycle_year) is not int or not 2020 <= c.cycle_year <= 2100))
        or c.role not in _ROLES[c.event_kind]
        or (c.role is NoticeRole.MASTER) != (c.tenant_id is None)
        or (c.role is NoticeRole.MASTER) != (c.cycle_year is None)
        or (c.role is not NoticeRole.MASTER and c.cycle_year is None)
    ):
        raise FinancialOperationBlocked("Notificação sem identidade, contexto ou origem válida")


def inspect_notification_claim(
    c: NoticeClaim, *,
    preference: NoticePreferencesClaim | None = None
) -> NoticePreview:
    """No delivery or storage, even for claims all marked true."""
    _validate_notice(c)
    if preference is not None:
        if (
            type(preference) is not NoticePreferencesClaim
            or preference.recipient_id != c.recipient_id
            or type(preference.channel) is not NoticeChannel
            or type(preference.opt_in) is not bool
            or type(preference.address_verified) is not bool
            or type(preference.purpose_documented) is not bool
        ):
            raise FinancialOperationBlocked("Preferência de canal pertence a outro destinatário")
        if preference.channel is not NoticeChannel.IN_APP and not all((
            preference.opt_in, preference.address_verified,
            preference.purpose_documented,
        )):
            raise FinancialOperationBlocked("Canal externo não tem autorização/contato verificado")

    title, message = _TEMPLATES[c.event_kind]
    payload = json.dumps({
        "domain": "AI_STUDIO_NOTIFICATION_M15000_DRAFT_NO_SEND_V1",
        "event_id": str(c.event_id),
        "recipient_id": str(c.recipient_id),
        "role": c.role.value,
        "tenant_id": str(c.tenant_id) if c.tenant_id else None,
        "cycle_year": c.cycle_year,
        "event_kind": c.event_kind.value,
        "occurred_utc": c.occurred_at.astimezone(timezone.utc).isoformat(),
        "source_digest": c.source_reference_digest,
        "event_source_authenticated_claim": c.authenticated_event_source,
        "recipient_authenticated_claim": c.authenticated_recipient,
        "membership_verified_claim": c.tenant_membership_verified,
        "requested_channel": preference.channel.value if preference else "IN_APP",
        "opt_in_claim": preference.opt_in if preference else None,
    }, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return NoticePreview(
        recipient_id=c.recipient_id,role=c.role,tenant_id=c.tenant_id,
        event_kind=c.event_kind,title=title,message=message,
        fingerprint=sha256(payload.encode("ascii")).hexdigest(),
    )


def inspect_notification_batch(
    claims: tuple[NoticeClaim, ...],
    *,
    tenant_id: UUID | None = None,
) -> NoticeBatchPreview:
    if (
        type(claims) is not tuple or len(claims)>MAX_BATCH
        or (tenant_id is not None and (
            type(tenant_id) is not UUID or tenant_id.int == 0))
    ):
        raise FinancialOperationBlocked("Lote de notificação inválido")
    seen: dict[tuple[UUID, UUID], NoticeClaim] = {}
    fingerprints = []
    dup = 0
    for c in claims:
        d = inspect_notification_claim(c)
        if tenant_id != c.tenant_id:
            raise FinancialOperationBlocked("Notificações de contextos diferentes no lote")
        key = (c.event_id, c.recipient_id)
        if key in seen:
            if seen[key] != c:
                raise FinancialOperationBlocked("Replay contraditório de aviso")
            dup+=1
            continue
        seen[key]=c
        fingerprints.append(d.fingerprint)
    return NoticeBatchPreview(
        candidate_count=len(fingerprints),
        exact_replays_suppressed=dup,
        fingerprints=tuple(fingerprints),
    )
