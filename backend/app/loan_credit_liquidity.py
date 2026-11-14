"""M6200: tenant-scoped credit liquidity PREVIEW, not reservation/transfer.

FR Caixinha does not hold client money. Free cash only comes from a fresh
external authenticated account statement for the respective tenant's
provider account, minus already committed financial obligations. This
contract has no database or payout side effects, and never authorizes
Money Out or customer loan approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from uuid import UUID
import re

from .pix_automation_contract import FinancialOperationBlocked

CONTRACT="AI_STUDIO_M6200_TENANT_LOAN_LIQUIDITY_PREFLIGHT_V1"
_MAX=999999999999
_MP=re.compile(r"[0-9]{1,40}\Z")
_HASH=re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True)
class AuthenticatedCashSnapshot:
    tenant_id:UUID
    cycle_id:UUID
    provider_account_id:str
    balance_cents:int
    existing_credit_reservations_cents:int
    pending_payouts_cents:int
    mandatory_liabilities_cents:int
    snapshot_hash:str
    verified_at:datetime
    authenticated_provider:bool
    independent_bank_source:bool
    source_kind:str="EXTERNAL_ACCOUNT_AUTHENTICATED_BALANCE"


@dataclass(frozen=True)
class LoanReservationRequest:
    tenant_id:UUID
    cycle_id:UUID
    loan_id:UUID
    member_id:UUID
    provider_account_id:str
    principal_cents:int
    loan_status:str
    cycle_status:str
    admin_review_verified:bool
    active_member_verified:bool
    beneficiary_ownership_verified:bool
    recipient_consent_current:bool
    is_admin_self_loan:bool
    collective_self_loan_consent_verified:bool
    existing_payout_attempts:int


@dataclass(frozen=True)
class LoanLiquidityPreview:
    tenant_id:UUID
    loan_id:UUID
    free_cash_cents:int
    requested_cents:int
    eligible_for_atomic_reservation_attempt:bool
    bank_balance_is_authenticated:bool
    reserve_written:bool=False
    payout_authorized:bool=False
    money_transferred:bool=False
    ledger_written:bool=False


def credit_liquidity_preflight(
    *,request:LoanReservationRequest,snapshot:AuthenticatedCashSnapshot,
    checked_at:datetime,
)->LoanLiquidityPreview:
    if (type(request) is not LoanReservationRequest
            or type(snapshot) is not AuthenticatedCashSnapshot
            or any(type(x) is not UUID for x in (
                request.tenant_id,request.cycle_id,request.loan_id,request.member_id,
                snapshot.tenant_id,snapshot.cycle_id))
            or snapshot.tenant_id!=request.tenant_id
            or snapshot.cycle_id!=request.cycle_id
            or type(snapshot.provider_account_id) is not str
            or type(request.provider_account_id) is not str
            or not _MP.fullmatch(snapshot.provider_account_id)
            or snapshot.provider_account_id!=request.provider_account_id
            or type(checked_at) is not datetime or checked_at.tzinfo is None
            or checked_at.utcoffset() is None
            or type(snapshot.verified_at) is not datetime
            or snapshot.verified_at.tzinfo is None
            or snapshot.verified_at.utcoffset() is None
            or not timedelta(0)<=checked_at-snapshot.verified_at<=timedelta(minutes=5)
            or type(snapshot.snapshot_hash) is not str
            or not _HASH.fullmatch(snapshot.snapshot_hash)
            or snapshot.source_kind!="EXTERNAL_ACCOUNT_AUTHENTICATED_BALANCE"
            or snapshot.authenticated_provider is not True
            or snapshot.independent_bank_source is not True):
        raise FinancialOperationBlocked("Liquidez sem prova bancária recente da caixinha")
    amounts=(
        snapshot.balance_cents,snapshot.existing_credit_reservations_cents,
        snapshot.pending_payouts_cents,snapshot.mandatory_liabilities_cents,
        request.principal_cents,
    )
    if (any(type(n) is not int or not 0<=n<=_MAX for n in amounts)
            or request.principal_cents==0
            or type(request.existing_payout_attempts) is not int
            or request.existing_payout_attempts<0
            or request.loan_status!="APROVADO"
            or request.cycle_status!="ABERTO"
            or request.admin_review_verified is not True
            or request.active_member_verified is not True
            or request.beneficiary_ownership_verified is not True
            or request.recipient_consent_current is not True
            or type(request.is_admin_self_loan) is not bool
            or type(request.collective_self_loan_consent_verified) is not bool
            or (request.is_admin_self_loan
                and request.collective_self_loan_consent_verified is not True)
            or request.existing_payout_attempts!=0):
        raise FinancialOperationBlocked("Reserva de crédito não autorizada")
    committed=sum((
        snapshot.existing_credit_reservations_cents,
        snapshot.pending_payouts_cents,
        snapshot.mandatory_liabilities_cents,
    ))
    if committed>snapshot.balance_cents:
        raise FinancialOperationBlocked("Caixa conciliado inferior às obrigações reservadas")
    free=snapshot.balance_cents-committed
    if request.principal_cents>free:
        raise FinancialOperationBlocked("Saldo livre insuficiente")
    return LoanLiquidityPreview(
        tenant_id=request.tenant_id,loan_id=request.loan_id,
        free_cash_cents=free,requested_cents=request.principal_cents,
        eligible_for_atomic_reservation_attempt=True,
        bank_balance_is_authenticated=True,
    )
