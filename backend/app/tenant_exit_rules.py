"""AI Studio: encerramento voluntário de tenant ≠ saída de membro ≠ licença SaaS.

Contrato Mestre 3.10 e 10.6. Toda mudança permanece PENDENTE de liquidação,
documento, prova e autoridade. Nenhum código aqui executa cancelamento.
"""
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantWindDown:
    tenant_id: UUID
    requesting_admin_user_id: UUID
    request_id: UUID
    members_principal_cents: int
    members_profit_cents: int
    admin_remuneration_cents: int
    open_loans_cents: int
    disputed_amount_cents: int
    reserved_cycle_cents: int
    unreconciled_receipts_cents: int
    pending_pix_cents: int
    accepted_document_version: str | None
    audit_evidence_ref: str | None

    def __post_init__(self):
        if any(type(i) is not UUID for i in (
            self.tenant_id,self.requesting_admin_user_id,self.request_id)):
            raise ValueError("Identidades formais obrigatórias")
        for attr in (
            "members_principal_cents","members_profit_cents",
            "admin_remuneration_cents","open_loans_cents",
            "disputed_amount_cents","reserved_cycle_cents",
            "unreconciled_receipts_cents","pending_pix_cents"
        ):
            v=getattr(self,attr)
            if type(v) is not int or v<0:
                raise ValueError("Obrigação não comprovada em centavos")
        if self.accepted_document_version is not None and (
            not isinstance(self.accepted_document_version,str)
            or len(self.accepted_document_version)<8
        ):
            raise ValueError("Versão contratual inválida")
        if self.audit_evidence_ref is not None and (
            not isinstance(self.audit_evidence_ref,str)
            or len(self.audit_evidence_ref)<8
        ):
            raise ValueError("Auditoria inválida")


@dataclass(frozen=True)
class TenantWindDownPreview:
    tenant_id: UUID
    request_id: UUID
    outstanding_cents: int
    status: str
    obligations_preserved: bool = True
    tenant_closed: bool = False
    member_data_deleted: bool = False
    pix_enabled: bool = False
    financial_closing_authorized: bool = False


def review_tenant_wind_down(ask: TenantWindDown,
                            *, legal_clearance: bool,
                            independent_authorization: bool) -> TenantWindDownPreview:
    if not isinstance(ask,TenantWindDown):
        raise ValueError("Pedido inválido")
    if type(legal_clearance) is not bool or type(independent_authorization) is not bool:
        raise ValueError("Gates formais obrigatórios")
    amounts=(
        ask.members_principal_cents,ask.members_profit_cents,
        ask.admin_remuneration_cents,ask.open_loans_cents,
        ask.disputed_amount_cents,ask.reserved_cycle_cents,
        ask.unreconciled_receipts_cents,ask.pending_pix_cents,
    )
    total=sum(amounts)
    if not ask.accepted_document_version or not ask.audit_evidence_ref:
        status="PENDING_DOCUMENTS"
    elif total:
        status="PENDING_FINANCIAL_SETTLEMENT"
    elif not legal_clearance or not independent_authorization:
        status="PENDING_LEGAL_AND_INDEPENDENT_APPROVAL"
    else:
        status="REVIEW_COMPLETE_NO_AUTOMATIC_CLOSE"
    return TenantWindDownPreview(
        tenant_id=ask.tenant_id,request_id=ask.request_id,
        outstanding_cents=total,status=status,
    )
