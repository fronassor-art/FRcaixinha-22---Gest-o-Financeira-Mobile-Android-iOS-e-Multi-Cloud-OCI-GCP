"""M1721–M1880 — verificações offline, determinísticas e fail-closed."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.financial_cashboxes import CashboxRoute, DuePayment
from app.financial_sandbox_reconciliation import SandboxIntent
from app.synthetic_financial_journal import (
    CONTRACT as JOURNAL_CONTRACT, ZERO_HASH, LabJournalEvent, LabJournalLink,
    seal_synthetic_journal, audit_synthetic_journal, preview_exit_evidence_gate,
)
from app.annual_evidence_preflight import (
    CONTRACT as ANNUAL_CONTRACT, RegisteredAnnualEvidence,
    preview_registered_annual_result,
)

A = UUID("00000000-0000-4000-8000-0000000000a1")
B = UUID("00000000-0000-4000-8000-0000000000b1")
M = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2027, 1, 11, 18, 0, tzinfo=timezone.utc)
START = date(2027, 1, 1)
END = date(2028, 1, 1)
ROUTE = CashboxRoute("TENANT_CONTRIBUTION", "2002", A)


def make_intent(*, amount=15000, op="op-1", provider_id="9001",
                idem="stable_key_0001", ref=None, route=ROUTE):
    if ref is None:
        ref = f"tenant:{route.tenant_id}:contribution-1"
    return SandboxIntent(
        op, DuePayment(route, ref, provider_id, amount, False), idem)


def make_event(seq, kind, amount, *, op="op-1", provider_id="9001",
               tenant=A, collector="2002", event_id=None, occurred_at=None):
    return LabJournalEvent(
        event_id or UUID(int=1000+seq), seq, op, provider_id,
        collector, tenant, kind, amount,
        occurred_at or (NOW + timedelta(seconds=seq)))


def audit(events, intents=None, route=ROUTE):
    if intents is None:
        intents = (make_intent(),)
    return audit_synthetic_journal(
        route=route, intents=tuple(intents),
        links=seal_synthetic_journal(tuple(events)))


def registered(num=1, kind="INTEREST_RECEIPT", amount=100, *,
               tenant=A, at=NOW, provider=None, reviewer=None,
               ledger=None, source="REGISTERED_ONLY"):
    return RegisteredAnnualEvidence(
        UUID(int=2000+num), tenant, kind, amount, at,
        ledger or f"ledger-{num:06}", provider,
        reviewer, source)


def annual(events=(), **extra):
    kwargs = dict(tenant_id=A, start=START, end_exclusive=END,
                  events=tuple(events))
    kwargs.update(extra)
    return preview_registered_annual_result(**kwargs)


def test_journal_approved_is_never_bank_or_liquidity():
    result = audit((make_event(1, "APPROVED", 15000),))
    assert result.contract == JOURNAL_CONTRACT
    assert result.status == "SYNTHETIC_CHAIN_MATCH_ONLY"
    assert result.chain_head != ZERO_HASH
    assert result.approved_cents == 15000
    assert result.unreversed_cents == 15000
    assert result.blocked_count == 0
    assert result.positions[0].status == "APPROVED_FIXTURE_ONLY"
    assert result.synthetic_only is True
    assert result.chain_is_provenance is False
    assert result.bank_reconciled is False
    assert result.real_payments_enabled is False
    assert result.payout_authorized is False
    assert result.financial_closing_authorized is False
    assert result.capital_confirmed_cents is None
    assert result.ledger_written is False


@pytest.mark.parametrize("amount", range(1, 251))
def test_250_journal_amounts_conserve_exact_cents(amount):
    row = make_intent(amount=amount)
    result = audit((make_event(1, "APPROVED", amount),), (row,))
    assert result.approved_cents == result.unreversed_cents == amount
    assert result.refunded_cents == result.chargeback_cents == 0
    assert result.bank_reconciled is False


@pytest.mark.parametrize("refund", range(1, 201))
def test_200_partial_and_full_refunds_preserve_balance(refund):
    row = make_intent(amount=200)
    result = audit((
        make_event(1, "APPROVED", 200),
        make_event(2, "REFUNDED", refund),
    ), (row,))
    assert result.approved_cents == 200
    assert result.refunded_cents == refund
    assert result.unreversed_cents == 200-refund
    assert result.status == "REVIEW_REQUIRED"
    assert result.positions[0].status == (
        "FULLY_REFUNDED" if refund == 200 else "PARTIALLY_REFUNDED")


def test_chargeback_dispute_and_refund_are_holds():
    rows = (
        make_event(1, "APPROVED", 15000),
        make_event(2, "REFUNDED", 1000),
        make_event(3, "CHARGEBACK", 5000),
    )
    report = audit(rows)
    assert report.chargeback_cents == 5000
    assert report.refunded_cents == 1000
    assert report.unreversed_cents == 9000
    assert report.positions[0].status == "DISPUTE_HOLD"
    assert report.positions[0].disputed is True
    assert report.status == "REVIEW_REQUIRED"


def test_dispute_without_money_movement_still_blocks():
    report = audit((
        make_event(1, "APPROVED", 15000),
        make_event(2, "DISPUTE_OPEN", 0),
    ))
    assert report.unreversed_cents == 15000
    assert report.blocked_count == 1
    assert report.positions[0].disputed is True


def test_replayed_or_out_of_order_event_rejected():
    good = make_event(1, "APPROVED", 15000)
    with pytest.raises(ValueError):
        audit((good, good))
    with pytest.raises(ValueError):
        seal_synthetic_journal((make_event(2, "APPROVED", 15000),))
    with pytest.raises(ValueError):
        audit_synthetic_journal(route=ROUTE, intents=(make_intent(),),
                                links=(LabJournalLink(good, "0"*64, "f"*64),))


@pytest.mark.parametrize("delta", range(1, 151))
def test_150_hash_tampering_cases_detected(delta):
    good = seal_synthetic_journal((make_event(1, "APPROVED", 15000),))
    forged = (replace(good[0], event=replace(
        good[0].event, amount_cents=15000+delta)),)
    with pytest.raises(ValueError, match="hash"):
        audit_synthetic_journal(route=ROUTE, intents=(make_intent(),),
                                links=forged)


def test_intent_or_route_collision_fails_closed():
    p = make_intent()
    q = make_intent(op="op-2", provider_id="9002",
                    ref=f"tenant:{A}:contribution-2", idem="stable_key_0002")
    e1 = make_event(1, "APPROVED", 15000)
    e2 = make_event(2, "APPROVED", 15000, op="op-2", provider_id="9002")
    report = audit((e1, e2), (q, p))
    assert [x.operation_key for x in report.positions] == ["op-1", "op-2"]
    assert report.approved_cents == 30000
    with pytest.raises(ValueError):
        audit((e1, e2), (p, make_intent(
            op="op-2", provider_id="9002",
            ref=f"tenant:{A}:contribution-2", idem=p.idempotency_key)))
    with pytest.raises(ValueError):
        audit((e1,), (p, p))
    with pytest.raises(ValueError):
        audit((e1,), (p,), route=CashboxRoute("TENANT_CONTRIBUTION", "3003", B))
    with pytest.raises(ValueError):
        audit((make_event(1, "APPROVED", 15000, collector="3003"),))


def test_orphans_duplicate_approval_and_illegal_reversals_rejected():
    with pytest.raises(ValueError):
        audit((make_event(1, "REFUNDED", 100),))
    with pytest.raises(ValueError):
        audit((make_event(1, "APPROVED", 15000),
               make_event(2, "APPROVED", 15000)))
    with pytest.raises(ValueError):
        audit((make_event(1, "APPROVED", 15000),
               make_event(2, "REFUNDED", 15001)))
    with pytest.raises(ValueError):
        audit((make_event(1, "APPROVED", 15000),
               make_event(2, "CHARGEBACK", 9000),
               make_event(3, "REFUNDED", 9000)))
    with pytest.raises(ValueError):
        audit((make_event(1, "APPROVED", 15000, op="missing"),))
    with pytest.raises(ValueError):
        audit((make_event(1, "APPROVED", 15000, tenant=B),))


def test_reverse_time_after_approval_rejected():
    a = make_event(1, "APPROVED", 15000, occurred_at=NOW)
    b = make_event(2, "REFUNDED", 100, occurred_at=NOW-timedelta(days=1))
    with pytest.raises(ValueError):
        audit((a, b))


@pytest.mark.parametrize("bad", [True, -1, 1.25, 0, 9999999999991])
def test_event_amount_validation(bad):
    with pytest.raises(ValueError):
        make_event(1, "APPROVED", bad)


def test_empty_chain_is_explicitly_unproven():
    result = audit((), ())
    assert result.chain_head == ZERO_HASH
    assert result.status == "REVIEW_REQUIRED"
    assert result.bank_reconciled is False


def test_exit_never_computes_payment_even_with_three_reviewer_references():
    data = dict(tenant_id=A, membership_id=M, registered_capital_cents=50000,
                registered_loan_due_cents=10000, disputed_cents=2500)
    result = preview_exit_evidence_gate(
        **data, reviewer_refs=("review-0001", "review-0002", "review-0003"))
    assert result.status == "DECLARED_REFERENCES_REQUIRE_EXTERNAL_VERIFICATION"
    assert result.candidate_restitution_cents is None
    assert result.confirmed_payout_cents is None
    assert result.rights_preserved
    assert result.payment_authorized is False
    assert result.automatic_setoff_allowed is False
    assert result.independent_reconciliation_verified is False
    pending = preview_exit_evidence_gate(**data, reviewer_refs=())
    assert pending.status == "INDEPENDENT_EVIDENCE_PENDING"
    with pytest.raises(ValueError):
        preview_exit_evidence_gate(
            **data, reviewer_refs=("review-0001", "review-0001"))


def test_registered_annual_preflight_keeps_capital_out_of_profit():
    events = (
        registered(1, "MEMBER_QUOTA_PRINCIPAL", 15000,
                   provider="provider-0001", reviewer="review-0001"),
        registered(2, "LOAN_PRINCIPAL_REPAYMENT", 5000,
                   provider="provider-0002", reviewer="review-0002"),
        registered(3, "INTEREST_RECEIPT", 2500,
                   provider="provider-0003", reviewer="review-0003"),
        registered(4, "ELIGIBLE_EXPENSE", 1000,
                   provider="provider-0004", reviewer="review-0004"),
    )
    r = annual(events)
    assert r.contract == ANNUAL_CONTRACT
    assert r.events_count == 4
    assert r.recorded_member_capital_cents == 15000
    assert r.recorded_loan_principal_cents == 5000
    assert r.recorded_revenue_cents == 2500
    assert r.recorded_expense_loss_reversal_cents == 1000
    assert r.recorded_net_result_cents == 1500
    assert r.status == "DECLARED_REFERENCES_NEED_INDEPENDENT_VERIFICATION"
    assert r.distributable_profit_cents is None
    assert r.bank_reconciled is False
    assert r.annual_closing_authorized is False
    assert r.pix_enabled is False
    assert r.master_saas_revenue_cents is None


@pytest.mark.parametrize("cents", range(1, 251))
def test_250_annual_interest_exact_amounts(cents):
    r = annual((registered(1, "INTEREST_RECEIPT", cents),))
    assert r.recorded_net_result_cents == cents
    assert r.recorded_member_capital_cents == 0
    assert r.distributable_profit_cents is None
    assert r.status == "EVIDENCE_REFERENCES_MISSING"


@pytest.mark.parametrize("costs", range(1, 251))
def test_250_costs_can_exceed_registered_revenue_without_fictitious_profit(costs):
    r = annual((registered(1, "INTEREST_RECEIPT", 100),
                registered(2, "ADMISSIBLE_LOSS", costs)))
    assert r.recorded_net_result_cents == 100-costs
    assert r.distributable_profit_cents is None
    assert r.available_cash_cents is None


def test_duplicate_provider_ledger_or_cross_tenant_rejected():
    with pytest.raises(ValueError):
        annual((registered(1), registered(1)))
    with pytest.raises(ValueError):
        annual((registered(1, provider="provider-0001"),
                registered(2, provider="provider-0001")))
    with pytest.raises(ValueError):
        annual((registered(1, ledger="ledger-0001"),
                registered(2, ledger="ledger-0001")))
    with pytest.raises(ValueError):
        annual((registered(1, tenant=B),))
    with pytest.raises(ValueError):
        annual((registered(1, kind="PLATFORM_SAAS"),))


def test_time_in_belem_controls_period_and_disputes():
    # 02:00 UTC em 01/jan equivale a 23:00 de 31/dez em Belém.
    with pytest.raises(ValueError):
        annual((registered(1, at=datetime(2027, 1, 1, 2,
                                          tzinfo=timezone.utc)),))
    with pytest.raises(ValueError):
        annual((registered(1, at=datetime(2028, 1, 1, 4,
                                          tzinfo=timezone.utc)),))
    event = registered(1, provider="provider-0001", reviewer="review-0001")
    report = annual((event,), disputed_event_ids=(event.event_id,))
    assert report.declared_disputes_count == 1
    assert report.status == "DISPUTES_REQUIRE_REVIEW"
    with pytest.raises(ValueError):
        annual((event,), disputed_event_ids=(UUID(int=9999),))


@pytest.mark.parametrize("bad", [-1, True, 1.0, 0, 9999999999991])
def test_bad_annual_amounts_fail_closed(bad):
    with pytest.raises(ValueError):
        registered(1, amount=bad)


def test_empty_registered_period_stays_blocked():
    r = annual()
    assert r.status == "NO_REGISTERED_EVENTS"
    assert r.recorded_net_result_cents == 0
    assert r.distributable_profit_cents is None
    assert r.annual_closing_authorized is False


def test_runtime_health_m1880_is_only_a_contract():
    from app.main import app
    response = TestClient(app).get("/api/health/features/m1880")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()
    assert data["workstream"] == "AI_STUDIO"
    assert data["journal_contract"] == JOURNAL_CONTRACT
    assert data["annual_contract"] == ANNUAL_CONTRACT
    assert data["synthetic_only"] is True
    for field in ("bank_reconciled", "real_payments_enabled",
                  "financial_closing_authorized", "payout_authorized",
                  "runtime_git_sha_verified", "ledger_written"):
        assert data[field] is False
