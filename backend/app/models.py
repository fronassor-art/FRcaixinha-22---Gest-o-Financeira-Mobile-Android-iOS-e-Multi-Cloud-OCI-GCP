"""
FRcaixinha 2.2 — Modelos de Dados e Schemas
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 4.2, 4.5, 5.4, 6.3, 6.4, 8.2, 8.6, 8.8, 10.3, 10.4, 12.2, 16.2 e 16.4)
Precisão Monetária: Uso de Decimal e centavos auditáveis com ROUND_HALF_UP.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, AliasChoices

# --- Schemas de Entrada / Saída para Autenticação ---

class LoginRequest(BaseModel):
    username_or_email: str = Field(..., validation_alias=AliasChoices('username_or_email', 'usernameOrEmail'), max_length=255, description="E-mail")
    password: str = Field(..., min_length=1, description="Senha de acesso")
    requested_role: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices('requested_role', 'requestedRole'),
        pattern="^(MASTER|TENANT_ADMIN|TENANT_MEMBER)$",
        description="Papel escolhido na tela de login. O servidor valida o vinculo.",
    )
    requested_tenant_id: Optional[UUID] = Field(
        default=None,
        validation_alias=AliasChoices('requested_tenant_id', 'requestedTenantId'),
        description="Caixinha escolhida, confirmada por vinculo ativo no PostgreSQL.",
    )

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    cpf: str
    role: str
    tenant_id: Optional[str] = None
    is_master: bool = False

class SessionResponse(BaseModel):
    success: bool
    user: UserResponse
    expires_at: datetime
    message: str
    token: str

class AuthStatusResponse(BaseModel):
    status: str
    configured: bool
    provider: str
    architecture_contract: str
    scaffold_note: str
    requires_authentication: bool
    message: str
    server_time: datetime

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class InvitationCreateRequest(BaseModel):
    target_email: EmailStr
    target_role: str = Field(..., pattern="^(TENANT_ADMIN|TENANT_MEMBER)$")
    tenant_id: Optional[str] = None
    required_document_id: Optional[UUID] = Field(
        default=None,
        validation_alias=AliasChoices("required_document_id", "requiredDocumentId"),
        description="Referência de adesão versionada; não autoriza emissão de convites.",
    )

class InvitationContractReadinessRequest(BaseModel):
    """Consulta somente leitura: não recebe nem armazena e-mail de destinatário."""
    target_role: str = Field(..., pattern="^(TENANT_ADMIN|TENANT_MEMBER)$")
    tenant_id: UUID
    required_document_id: UUID


class ContextSwitchRequest(BaseModel):
    target_role: str = Field(..., pattern="^(MASTER|TENANT_ADMIN|TENANT_MEMBER)$")
    target_tenant_id: Optional[str] = None

# --- Schemas de Contribuições e Cotas ---


class FinancialIntegrityPreviewResponse(BaseModel):
    """Prévia contábil e cadastral; não é saldo bancário nem fechamento."""
    source: str
    scope: str
    tenant_id: UUID
    cycle_id: UUID
    year: int
    status: str
    findings: tuple[str, ...]
    members_links: int
    members_distinct: int
    member_role_links: int
    admin_role_links: int
    quota_value_cents: Optional[int] = None
    admin_percent: Optional[str] = None
    member_percent: Optional[str] = None
    registered_contributions: int
    registered_due_cents: int
    registered_paid_cents: int
    registered_open_cents: int
    complete_count: int
    partial_count: int
    pending_count: int
    ledger_transactions: int
    balanced_transactions: int
    ledger_dr_cents: int
    ledger_cr_cents: int
    linked_contributions: int
    linked_payment_cents: int
    missing_ledger_count: int
    incorrect_link_count: int
    no_bank_evidence: bool = True
    bank_reconciled: bool = False
    cash_available_cents: None = None
    member_profit_share_cents: None = None
    master_saas_revenue_cents: None = None
    closing_authorized: bool = False
    transfer_authorized: bool = False


class MemberCycleRiskPreviewResponse(BaseModel):
    """Histórico registrado sem conclusão bancária, punitiva ou distributiva."""
    tenant_id: str
    cycle_year: int
    membership_id: str
    as_of: date
    source: str
    scope: str
    owner_box: bool
    registered_contributions_count: int
    registered_due_cents: int
    registered_paid_cents: int
    registered_open_cents: int
    longest_registered_overdue_days: int
    currently_unpaid_consecutive_months: int
    potential_three_unpaid_trigger_date: Optional[date] = None
    membership_profit_eligible: Optional[bool] = None
    reconciled_principal_cents: Optional[int] = None
    capital_days_weight: Optional[Decimal] = None
    contractual_effect_applied: bool = False
    real_financial_operations_enabled: bool = False
    financial_closing_authorized: bool = False
    bank_reconciled: bool = False
    result_status: str = "HISTORY_AND_PROOF_NOT_ATTESTED"

class QuotaResponse(BaseModel):
    id: str
    tenant_id: str
    membership_id: str
    quota_number: int
    value_brl: Decimal
    status: str
    created_at: datetime

class ContributionResponse(BaseModel):
    id: str
    tenant_id: str
    cycle_id: str
    membership_id: str
    member_name: Optional[str] = None
    competence: str
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    payment_status: str
    due_status: str
    paid_at: Optional[datetime] = None

class MemberAnnualPreviewResponse(BaseModel):
    """Prévia somente de registros próprios; não é fechamento ou pagamento."""
    source: str = 'POSTGRESQL_RLS'
    tenant_id: str
    year: int
    contribution_count: int
    pending_count: int
    total_due: Decimal
    amount_paid_recorded: Decimal
    remaining_due: Decimal
    result_status: str = 'PREVIA_NAO_E_LIQUIDACAO'
    profit_amount: Optional[Decimal] = None


class ContributionPayRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Valor para intenção de pagamento em BRL")

class ContributionPayResponse(BaseModel):
    status: str = Field(default="AGUARDANDO_CONCILIACAO", description="Status da transação de pagamento")
    contribution_id: str
    amount_requested: Decimal
    intent_id: Optional[str] = None
    pix_copy_paste: Optional[str] = None
    message: str
    is_reconciled: bool = False

# --- Schemas de Empréstimos e Tabela Price ---

class LoanSimulateRequest(BaseModel):
    principal: Decimal = Field(..., gt=0, le=50000.00, description="Valor principal do empréstimo")
    term_months: int = Field(..., ge=1, le=6, description="Prazo em meses (máx 6 meses)")
    monthly_rate: Optional[Decimal] = Field(
        default=None,
        description="Legado: se informado, será recusado; taxa vem exclusivamente da política ACTIVE do tenant.",
    )
    disbursement_date: Optional[date] = Field(default=None, description="Data de desembolso para apuração de período irregular")
    first_due_date: Optional[date] = Field(default=None, description="Data do 1º vencimento")

class InstallmentScheduleItem(BaseModel):
    installment_number: int
    due_date: str
    opening_balance: Decimal
    monthly_payment: Decimal
    interest_portion: Decimal
    amortization_portion: Decimal
    closing_balance: Decimal
    is_cents_adjusted: bool = False

class LoanSimulateResponse(BaseModel):
    principal: Decimal
    monthly_rate: Decimal
    term_months: int
    uniform_payment: Decimal
    last_payment: Decimal
    total_interest: Decimal
    total_payable: Decimal
    is_irregular_first_period: bool
    first_period_days: Optional[int] = None
    effective_first_rate: Optional[Decimal] = None
    schedule: List[InstallmentScheduleItem]

class LoanRequestPayload(BaseModel):
    principal: Decimal = Field(..., gt=0, le=50000.00)
    term_months: int = Field(..., ge=1, le=6)
    is_admin_loan: bool = False
    justification: Optional[str] = None

class LoanInstallmentResponse(BaseModel):
    id: str
    installment_number: int
    due_date: date
    principal_due: Decimal
    interest_due: Decimal
    total_due: Decimal
    paid_principal: Decimal
    paid_interest: Decimal
    paid_mora: Decimal
    paid_fine: Decimal
    status: str
    days_overdue: int = 0
    calculated_mora: Decimal = Decimal("0.00")
    calculated_fine: Decimal = Decimal("0.00")
    total_due_updated: Decimal = Decimal("0.00")

class LoanResponse(BaseModel):
    id: str
    tenant_id: str
    cycle_id: str
    borrower_membership_id: str
    borrower_name: Optional[str] = None
    is_admin_loan: bool
    principal: Decimal
    monthly_rate: Decimal
    term_months: int
    monthly_payment: Decimal
    last_payment: Decimal
    total_interest: Decimal
    status: str
    created_at: datetime
    disbursed_at: Optional[datetime] = None
    installments: List[LoanInstallmentResponse] = []

class LoanRepayPayload(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Valor pago para amortização/imputação")
    payment_date: Optional[datetime] = None

class LoanRepayResponse(BaseModel):
    loan_id: str
    amount_received: Decimal
    allocated_interest: Decimal
    allocated_mora: Decimal
    allocated_fine: Decimal
    allocated_principal: Decimal
    remaining_balance: Decimal
    is_fully_settled: bool = False

class LoanEarlySettlementResponse(BaseModel):
    loan_id: str
    open_principal: Decimal
    overdue_interest: Decimal
    overdue_mora: Decimal
    overdue_fine: Decimal
    total_overdue_charges: Decimal
    unaccrued_future_interest_waived: Decimal
    total_settlement_amount: Decimal
    is_fully_settled: bool
    message: str

# --- Schemas do Livro-Razão Contábil (Partidas Dobradas) ---

class LedgerIntegrityPreviewResponse(BaseModel):
    """Only counts, never banking confirmation or authorization to close cycles."""
    source: str = "POSTGRESQL_RLS"
    scope: str = "TENANT_ADMIN_READ_ONLY"
    tenant_id: str
    checked_transactions: int
    balanced_transactions: int
    review_required_transactions: int
    status: str
    bank_reconciled: bool = False
    financial_closing_authorized: bool = False


class LedgerAccountDirectoryItemResponse(BaseModel):
    id: str
    account_code: str
    account_name: str
    account_type: str


class LedgerAccountDirectoryResponse(BaseModel):
    source: str = "POSTGRESQL_RLS"
    scope: str = "TENANT_ADMIN_READ_ONLY"
    tenant_id: str
    accounts: List[LedgerAccountDirectoryItemResponse]
    balance_values_hidden: bool = True
    complete_ledger_verified: bool = False
    bank_reconciled: bool = False
    financial_closing_authorized: bool = False


class LedgerAccountResponse(BaseModel):
    id: str
    tenant_id: str
    account_code: str
    account_name: str
    account_type: str
    balance_cents: int
    balance_brl: Decimal

class LedgerAccountJournalEntryResponse(BaseModel):
    id: str
    transaction_id: str
    transaction_date: datetime
    description: str
    reference_id: str
    entry_type: str
    amount_cents: int
    amount_brl: Decimal


class LedgerAccountJournalPageResponse(BaseModel):
    source: str = "POSTGRESQL_RLS"
    tenant_id: str
    account_id: str
    page: int
    page_size: int
    has_more: bool
    complete_ledger_verified: bool = False
    bank_reconciled: bool = False
    financial_closing_authorized: bool = False
    entries: List[LedgerAccountJournalEntryResponse]


class LedgerAccountJournalKeysetResponse(BaseModel):
    """Extrato parcial por cursor: nunca autoriza conciliacao ou fechamento."""
    source: str = "POSTGRESQL_RLS"
    tenant_id: str
    account_id: str
    page_size: int
    has_more: bool
    next_cursor: Optional[str] = None
    complete_ledger_verified: bool = False
    bank_reconciled: bool = False
    financial_closing_authorized: bool = False
    entries: List[LedgerAccountJournalEntryResponse]


class LedgerEntryResponse(BaseModel):
    id: str
    account_id: str
    account_name: str
    entry_type: str
    amount_cents: int
    amount_brl: Decimal

class LedgerTransactionResponse(BaseModel):
    id: str
    tenant_id: str
    transaction_date: datetime
    description: str
    reference_id: str
    entries: List[LedgerEntryResponse]

# --- Schemas de Consentimento para Autoempréstimo de Admin ---

class AdminConsentVotePayload(BaseModel):
    decision: str = Field(..., pattern="^(FAVORAVEL|CONTRARIO|ABSTENCAO)$")
    justification: Optional[str] = None

class AdminConsentResponse(BaseModel):
    tenant_id: str
    loan_id: Optional[str] = None
    total_members_required: int
    favorable_votes: int
    contrary_votes: int
    is_unanimous: bool
    status: str

# --- Schemas de Fechamento de Ciclo (Capital-Dias V2) ---

class MemberDistributionResponse(BaseModel):
    membership_id: str
    member_name: str
    is_eligible: bool
    capital_dias_weight: Decimal
    weight_percentage: Decimal
    exact_share: Decimal
    truncated_share: Decimal
    bonus_centavos: Decimal
    final_profit_share: Decimal

class CycleClosePayload(BaseModel):
    cycle_id: str

class CycleClosingResponse(BaseModel):
    closing_id: str
    tenant_id: str
    cycle_id: str
    total_net_profit: Decimal
    admin_share_amount: Decimal
    member_pool_amount: Decimal
    total_capital_dias_weights: Decimal
    residual_cents_distributed: int
    status: str
    closed_at: datetime
    distributions: List[MemberDistributionResponse]

# --- Schemas de Auditoria ---

class AuditReadinessResponse(BaseModel):
    source: str
    scope: str
    tenant_id: str
    checked_events: int
    fields_present_events: int
    review_required_events: int
    status: str
    provenance_verified: bool = False
    append_only_verified: bool = False
    financial_audit_approved: bool = False


class AuditEventResponse(BaseModel):
    id: str
    actor_id: Optional[str] = None
    actor_role: str
    tenant_id: Optional[str] = None
    action: str
    object_type: str
    object_id: str
    reason: str
    evidence_ref: str
    created_at: datetime

class AuditEventCreatePayload(BaseModel):
    action: str
    object_type: str
    object_id: str
    reason: str
    evidence_ref: str
