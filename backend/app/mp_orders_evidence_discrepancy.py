"""M8000-M8300: three-source discrepancy review, pure and non-authoritative.

An uploaded statement, digest, label or GET response is NOT bank-origin
proof. This module only compares claims to identify why a financial case
must remain on hold. No provider, SQL, file or network I/O is permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from re import fullmatch
from uuid import UUID

from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M8300_THREE_SOURCE_DISCREPANCY_QUARANTINE_V1"


class ClaimedChannel(str, Enum):
    PROVIDER_GET = "PROVIDER_GET"
    SETTLEMENT_REPORT = "SETTLEMENT_REPORT"
    BANK_STATEMENT = "BANK_STATEMENT"


class ReviewOutcome(str, Enum):
    SELLER_REVOKED = "SELLER_REVOKED"
    PROVIDER_NOT_PROCESSED = "PROVIDER_NOT_PROCESSED"
    DISPUTE_PENDING = "DISPUTE_PENDING"
    REVERSAL_PENDING = "REVERSAL_PENDING"
    DUPLICATE_EVIDENCE = "DUPLICATE_EVIDENCE"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    SETTLEMENT_DATE_REVIEW = "SETTLEMENT_DATE_REVIEW"
    UNVERIFIED_SOURCE = "UNVERIFIED_SOURCE"


@dataclass(frozen=True)
class ClaimedFinancialRecord:
    channel: ClaimedChannel
    tenant_id: UUID
    provider_account_id: str
    operation_id: str
    order_id: str
    payment_id: str
    gross_cents: int
    fee_cents: int
    net_cents: int
    evidence_sha256: str
    record_reference: str
    observed_at: datetime


@dataclass(frozen=True)
class DiscrepancyContext:
    provider: ClaimedFinancialRecord
    settlement: ClaimedFinancialRecord
    bank: ClaimedFinancialRecord
    seller_revoked: bool
    provider_processed: bool
    dispute_pending: bool
    reversal_pending: bool


@dataclass(frozen=True)
class DiscrepancyReview:
    tenant_id: UUID
    operation_id: str
    outcome: ReviewOutcome
    case_fingerprint: str
    hold_required: bool = True
    independent_origin_verified: bool = False
    bank_reconciled: bool = False
    ledger_written: bool = False
    mark_paid_authorized: bool = False
    payout_authorized: bool = False
    financial_closing_authorized: bool = False


def _aware(v: datetime) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _validate(r: ClaimedFinancialRecord) -> None:
    if (
        type(r) is not ClaimedFinancialRecord
        or type(r.channel) is not ClaimedChannel
        or type(r.tenant_id) is not UUID or r.tenant_id.int == 0
        or type(r.provider_account_id) is not str
        or fullmatch(r"[0-9]{1,40}", r.provider_account_id) is None
        or type(r.operation_id) is not str
        or fullmatch(r"P_[a-f0-9]{32}", r.operation_id) is None
        or type(r.order_id) is not str
        or fullmatch(r"ORD[A-Z0-9]{12,77}", r.order_id) is None
        or type(r.payment_id) is not str
        or fullmatch(r"PAY[A-Z0-9]{12,77}", r.payment_id) is None
        or type(r.evidence_sha256) is not str
        or fullmatch(r"[a-f0-9]{64}", r.evidence_sha256) is None
        or type(r.record_reference) is not str
        or fullmatch(r"[A-Za-z0-9._:/-]{8,128}", r.record_reference) is None
        or not _aware(r.observed_at)
        or any(type(n) is not int or not 0 <= n <= 999999999999 for n in (
            r.gross_cents, r.fee_cents, r.net_cents
        ))
        or r.gross_cents == 0
        or r.fee_cents >= r.gross_cents
        or r.gross_cents != r.fee_cents + r.net_cents
    ):
        raise FinancialOperationBlocked("Fonte de conciliação declarada sem integridade")


def review_claimed_three_source(ctx: DiscrepancyContext) -> DiscrepancyReview:
    """Consistent claims stay UNVERIFIED, and never become settlement."""
    if type(ctx) is not DiscrepancyContext:
        raise FinancialOperationBlocked("Conjunto de fontes inválido")
    records = (ctx.provider, ctx.settlement, ctx.bank)
    for record in records:
        _validate(record)
    if (
        tuple(r.channel for r in records) != tuple(ClaimedChannel)
        or any(type(v) is not bool for v in (
            ctx.seller_revoked, ctx.provider_processed,
            ctx.dispute_pending, ctx.reversal_pending
        ))
    ):
        raise FinancialOperationBlocked("Origem ou sinalização de caso inválida")
    provider = ctx.provider
    for other in records[1:]:
        if (
            other.tenant_id != provider.tenant_id
            or other.provider_account_id != provider.provider_account_id
            or other.operation_id != provider.operation_id
            or other.order_id != provider.order_id
            or other.payment_id != provider.payment_id
        ):
            raise FinancialOperationBlocked("Fonte cruza conta, tenant ou transação")
    hashes = {r.evidence_sha256 for r in records}
    references = {r.record_reference for r in records}
    money = {(r.gross_cents, r.fee_cents, r.net_cents) for r in records}
    times = [r.observed_at for r in records]
    if ctx.seller_revoked:
        outcome = ReviewOutcome.SELLER_REVOKED
    elif not ctx.provider_processed:
        outcome = ReviewOutcome.PROVIDER_NOT_PROCESSED
    elif ctx.dispute_pending:
        outcome = ReviewOutcome.DISPUTE_PENDING
    elif ctx.reversal_pending:
        outcome = ReviewOutcome.REVERSAL_PENDING
    elif len(hashes) != 3 or len(references) != 3:
        outcome = ReviewOutcome.DUPLICATE_EVIDENCE
    elif len(money) != 1:
        outcome = ReviewOutcome.AMOUNT_MISMATCH
    elif max(times) - min(times) > timedelta(days=30):
        outcome = ReviewOutcome.SETTLEMENT_DATE_REVIEW
    else:
        # Three consistent documents do NOT prove three independent sources.
        outcome = ReviewOutcome.UNVERIFIED_SOURCE
    joined = "|".join([
        "AI_STUDIO_M8300_CLAIMED_RECORDS",
        str(provider.tenant_id), provider.provider_account_id,
        provider.operation_id, provider.order_id, provider.payment_id,
        *(f"{r.channel.value}:{r.record_reference}:{r.evidence_sha256}:"
          f"{r.gross_cents}:{r.fee_cents}:{r.net_cents}:"
          f"{r.observed_at.isoformat()}" for r in records),
        outcome.value,
    ])
    return DiscrepancyReview(
        tenant_id=provider.tenant_id, operation_id=provider.operation_id,
        outcome=outcome, case_fingerprint=sha256(joined.encode("ascii")).hexdigest(),
    )
