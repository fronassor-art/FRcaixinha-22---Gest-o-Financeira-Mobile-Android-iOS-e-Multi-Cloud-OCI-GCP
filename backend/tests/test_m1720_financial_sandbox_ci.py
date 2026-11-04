"""M1561–M1720: testes de oráculos SEM rede, banco, credenciais ou Pix."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
import hashlib
import hmac

import pytest

from app.financial_cashboxes import CashboxRoute, DuePayment
from app.financial_sandbox_reconciliation import (
    LAB_CONTRACT, SandboxIntent, ProviderFixture, WebhookFixture,
    preview_sandbox_reconciliation, preview_loan_allocation,
    preview_exit_restitution_readiness,
)
from app.loan_arrears_contract import LoanArrearsPolicy, LoanInstallmentState

A = UUID("00000000-0000-4000-8000-0000000000a1")
B = UUID("00000000-0000-4000-8000-0000000000b1")
MEMBER = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
SECRET = "segredo-estritamente-sintetico"
COLLECTORS = {A: "2002", B: "3003"}
PLATFORM = "1001"
POLICY = LoanArrearsPolicy(Decimal("0.20"), 1000, "owner-policy-2027")


def intent(*, tenant=A, amount=15000, op="op-1", idem="stable_id_001",
           payment_id="90001", purpose="TENANT_CONTRIBUTION", live=False):
    if purpose == "PLATFORM_SAAS":
        route = CashboxRoute(purpose, PLATFORM, None)
        ref = "saas:license-1"
    else:
        route = CashboxRoute(purpose, COLLECTORS[tenant], tenant)
        ref = f"tenant:{tenant}:contribution-1"
    return SandboxIntent(
        op, DuePayment(route, ref, payment_id, amount, live), idem)


def payload(op, **changes):
    p = op.payment
    record = dict(
        id=int(p.provider_payment_id), collector_id=int(p.route.collector_id),
        external_reference=p.external_reference,
        currency_id="BRL", transaction_amount=Decimal(p.amount_cents) / Decimal(100),
        status="approved", live_mode=False)
    record.update(changes)
    return record


def fixture(op, **changes):
    return ProviderFixture(op.payment.provider_payment_id, payload(op, **changes))


def webhook(op, *, request="request-1", ts=None, secret=SECRET, resource=None):
    resource = resource or op.payment.provider_payment_id
    timestamp = str(int(NOW.timestamp())) if ts is None else ts
    content = f"id:{resource};request-id:{request};ts:{timestamp};".encode()
    digest = hmac.new(secret.encode(), content, hashlib.sha256).hexdigest()
    return WebhookFixture(request, resource, f"ts={timestamp},v1={digest}", NOW)


def preview(intents, fixtures, webhooks=(), **changes):
    args = dict(
        intents=tuple(intents), fixtures=tuple(fixtures), webhooks=tuple(webhooks),
        platform_collector_id=PLATFORM, tenant_collectors=COLLECTORS,
        synthetic_webhook_secret=SECRET, as_of=NOW)
    args.update(changes)
    return preview_sandbox_reconciliation(**args)


def test_sandbox_match_is_not_bank_reconciliation_or_ledger():
    op = intent()
    report = preview((op,), (fixture(op),), (webhook(op),))
    assert report.status == "SYNTHETIC_MATCH_ONLY"
    assert report.lab_contract == LAB_CONTRACT
    assert report.items[0].finding == "APPROVED_FIXTURE_ONLY"
    assert report.items[0].tenant_id == A
    assert report.accepted_webhook_count == 1
    assert report.bank_reconciled is False
    assert report.real_payments_enabled is False
    assert report.closing_authorized is False
    assert report.payout_authorized is False
    assert report.ledger_written is False
    assert report.items[0].registered_as_paid is False


@pytest.mark.parametrize("amount", range(1, 201))
def test_200_cent_exactness_checks(amount):
    op = intent(amount=amount)
    good = preview((op,), (fixture(op),))
    assert good.items[0].finding == "APPROVED_FIXTURE_ONLY"
    bad = preview((op,), (fixture(op, transaction_amount=Decimal(amount + 1) / 100),))
    assert bad.items[0].finding == "PROVIDER_IDENTITY_OR_AMOUNT_MISMATCH"
    assert bad.bank_reconciled is False


@pytest.mark.parametrize("change", [
    {"id": 5}, {"collector_id": 3003}, {"external_reference": "tenant:other:pay"},
    {"currency_id": "USD"}, {"live_mode": True}, {"status": "unknown"},
    {"transaction_amount": Decimal("150.01")},
    {"transaction_amount": float(150)}, {"transaction_amount": True},
    {"transaction_amount": Decimal("NaN")}, {"transaction_amount": Decimal("Infinity")},
    {"transaction_amount": "150.001"}, {"transaction_amount": None},
])
def test_fail_closed_provider_data(change):
    op = intent()
    result = preview((op,), (fixture(op, **change),))
    assert result.status == "REVIEW_REQUIRED"
    assert result.items[0].finding == "PROVIDER_IDENTITY_OR_AMOUNT_MISMATCH"


@pytest.mark.parametrize("status,expected", [
    ("pending", "PROVIDER_PENDING"),
    ("in_process", "PROVIDER_IN_PROCESS"),
    ("rejected", "PROVIDER_REJECTED"),
    ("cancelled", "PROVIDER_CANCELLED"),
    ("in_mediation", "DISPUTE_OR_CHARGEBACK_HOLD"),
    ("charged_back", "DISPUTE_OR_CHARGEBACK_HOLD"),
])
def test_non_approved_states_never_mark_as_paid(status, expected):
    op = intent()
    result = preview((op,), (fixture(op, status=status),))
    assert result.items[0].finding == expected
    assert result.items[0].registered_as_paid is False


def test_full_refund_never_authorizes_payment_or_payout():
    op = intent()
    full = fixture(op, status="refunded", transaction_amount_refunded=Decimal("150.00"))
    result = preview((op,), (full,))
    assert result.items[0].finding == "FULL_REFUND_FIXTURE_ONLY"
    assert result.payout_authorized is False
    assert result.bank_reconciled is False
    partial = fixture(op, status="refunded", transaction_amount_refunded=Decimal("149.99"))
    result = preview((op,), (partial,))
    assert result.items[0].finding == "REFUND_NOT_FULLY_ATTESTED"
    assert result.status == "REVIEW_REQUIRED"


def test_cross_tenant_platform_segregation_and_orphans():
    a = intent(op="a", idem="idem_a_0001", payment_id="901")
    b = intent(tenant=B, op="b", idem="idem_b_0001", payment_id="902")
    p = intent(purpose="PLATFORM_SAAS", op="p", idem="idem_p_0001", payment_id="903")
    good = preview((b, p, a), (fixture(p), fixture(a), fixture(b)))
    assert [x.operation_key for x in good.items] == ["a", "b", "p"]
    assert good.status == "SYNTHETIC_MATCH_ONLY"
    # Mesmo usando o mesmo valor, não é permitido cruzar contas recebedoras.
    with pytest.raises(ValueError, match="Recebedor compartilhado"):
        preview((a,), (fixture(a),), tenant_collectors={A: PLATFORM})
    assert preview((a,), (fixture(a, collector_id=3003),)).status == "REVIEW_REQUIRED"
    unknown = ProviderFixture("777", dict(id=777, status="approved"))
    result = preview((a,), (fixture(a), unknown))
    assert result.provider_orphans == ("777",)
    assert result.status == "REVIEW_REQUIRED"


def test_missing_get_and_unsigned_webhook_do_not_mark_paid():
    op = intent()
    result = preview((op,), (), (webhook(op),))
    assert result.items[0].finding == "NO_SYNTHETIC_GET"
    assert result.accepted_webhook_count == 1
    assert result.bank_reconciled is False


def test_valid_invalid_replay_and_conflicting_webhooks():
    op = intent()
    good = webhook(op)
    bad = webhook(op, request="bad-1", secret="wrong-secret")
    replay = webhook(op)
    conflict = webhook(op, resource="99999")
    result = preview((op,), (fixture(op),), (good, bad, replay, conflict))
    assert result.accepted_webhook_count == 1
    assert result.rejected_webhook_count == 1
    assert result.replayed_webhook_count == 2
    assert "WEBHOOK_REPLAY" in result.webhook_findings
    assert "WEBHOOK_ID_CONFLICT" in result.webhook_findings
    assert result.status == "REVIEW_REQUIRED"


@pytest.mark.parametrize("bad_ts", ["0", "9999999999", "123abc", "1" * 15])
def test_stale_malformed_webhooks_rejected(bad_ts):
    op = intent()
    result = preview((op,), (fixture(op),), (webhook(op, ts=bad_ts),))
    assert result.rejected_webhook_count == 1
    assert result.bank_reconciled is False


def test_no_live_mode_or_malformed_fixtures():
    with pytest.raises(ValueError, match="sandbox"):
        intent(live=True)
    with pytest.raises(ValueError):
        SandboxIntent("x", intent().payment, "short")
    with pytest.raises(ValueError):
        ProviderFixture("123", {}, source="REAL_PROVIDER_GET")
    with pytest.raises(ValueError):
        preview((intent(),), (fixture(intent()), fixture(intent())))
    with pytest.raises(ValueError):
        preview((intent(), intent()))
    with pytest.raises(ValueError):
        preview((intent(),), (), as_of=datetime(2026, 11, 4, 18))
    with pytest.raises(ValueError):
        preview((intent(),), (), synthetic_webhook_secret="")


def installment(ident, due, *, principal, interest, mora=0, fine=0):
    return LoanInstallmentState(
        A, UUID(int=ident), due, principal, interest, mora, fine, True)


def test_allocation_oldest_first_and_cent_conservation():
    rows = (
        installment(3, date(2027, 3, 10), principal=300, interest=40),
        installment(2, date(2027, 2, 10), principal=200, interest=20),
        installment(1, date(2027, 1, 10), principal=100, interest=30),
    )
    # Mora synthetic = 0 no dia do vencimento? Primeiro vencimento ficou em atraso.
    no_mora = LoanArrearsPolicy(Decimal("0"), 0, "contract-2027")
    result = preview_loan_allocation(
        tenant_id=A, loan_status="DESEMBOLSADO", installment_rows=rows,
        amount_cents=140, as_of=date(2027, 2, 10), policy=no_mora)
    assert result.future_installment_count == 1
    assert result.applied_cents == 140
    assert result.unapplied_cents == 0
    assert [x.installment_id.int for x in result.allocations] == [1, 2]
    assert (result.allocations[0].interest_cents,
            result.allocations[0].principal_cents) == (30, 100)
    assert (result.allocations[1].interest_cents,
            result.allocations[1].principal_cents) == (10, 0)
    assert result.principal_amortized_in_ledger is False


@pytest.mark.parametrize("amount", range(0, 151))
def test_allocation_property_151_payment_sizes(amount):
    row = installment(1, date(2027, 1, 10), principal=100, interest=50)
    result = preview_loan_allocation(
        tenant_id=A, loan_status="INADIMPLENTE",
        installment_rows=(row,), amount_cents=amount,
        as_of=date(2027, 1, 10), policy=POLICY)
    assert result.applied_cents == amount
    assert result.unapplied_cents == 0
    assert sum(x.applied_cents for x in result.allocations) == amount
    if amount:
        x = result.allocations[0]
        assert x.interest_cents == min(amount, 50)
        assert x.principal_cents == max(0, amount-50)


def test_future_credit_and_proposed_credit_never_collectible():
    row = installment(1, date(2027, 3, 10), principal=50000, interest=5000)
    future = preview_loan_allocation(
        tenant_id=A, loan_status="DESEMBOLSADO", installment_rows=(row,),
        amount_cents=100, as_of=date(2027, 2, 1), policy=POLICY)
    assert future.applied_cents == 0 and future.unapplied_cents == 100
    assert future.future_installment_count == 1
    assert future.status == "SURPLUS_REQUIRES_REVIEW"
    for state in ("SOLICITADO", "APROVADO", "RESERVADO"):
        proposal = preview_loan_allocation(
            tenant_id=A, loan_status=state, installment_rows=(row,),
            amount_cents=100, as_of=date(2027, 4, 1), policy=POLICY)
        assert proposal.status == "PROPOSAL_NOT_COLLECTIBLE"
        assert proposal.applied_cents == 0


def test_surplus_blocked_and_cross_tenant_loan_rejected():
    row = installment(1, date(2027, 1, 10), principal=100, interest=50)
    result = preview_loan_allocation(
        tenant_id=A, loan_status="DESEMBOLSADO", installment_rows=(row,),
        amount_cents=200, as_of=date(2027, 1, 10), policy=POLICY)
    assert result.applied_cents == 150 and result.unapplied_cents == 50
    assert result.status == "SURPLUS_REQUIRES_REVIEW"
    with pytest.raises(ValueError):
        preview_loan_allocation(
            tenant_id=B, loan_status="DESEMBOLSADO", installment_rows=(row,),
            amount_cents=10, as_of=date(2027, 1, 10), policy=POLICY)


@pytest.mark.parametrize("capital,due,disputed", [
    (0, 0, 0), (15000, 1000, 0), (15000, 1000, 100), (999999999999, 0, 0)])
def test_exit_readiness_never_invents_restitution(capital, due, disputed):
    result = preview_exit_restitution_readiness(
        tenant_id=A, membership_id=MEMBER,
        registered_capital_cents=capital, registered_due_loan_cents=due,
        disputed_cents=disputed, has_bank_proof=True,
        has_final_contract_decision=True, independent_review_complete=True)
    assert result.net_exit_restitution_cents is None
    assert result.rights_preserved is True
    assert result.setoff_authorized is False
    assert result.payout_authorized is False
    assert result.bank_reconciled is False
    assert result.evidence_complete == (disputed == 0)


def test_exit_unverified_stays_pending():
    result = preview_exit_restitution_readiness(
        tenant_id=A, membership_id=MEMBER,
        registered_capital_cents=15000, registered_due_loan_cents=500,
        disputed_cents=0, has_bank_proof=False,
        has_final_contract_decision=True, independent_review_complete=True)
    assert result.status == "EVIDENCE_OR_DISPUTE_PENDING"
    with pytest.raises(ValueError):
        preview_exit_restitution_readiness(
            tenant_id=A, membership_id=MEMBER,
            registered_capital_cents=True, registered_due_loan_cents=0,
            disputed_cents=0, has_bank_proof=False,
            has_final_contract_decision=False, independent_review_complete=False)


def test_empty_report_is_not_a_matched_bank_position():
    result = preview((), ())
    assert result.status == "REVIEW_REQUIRED"
    assert result.bank_reconciled is False


def test_m1720_health_contract_never_claims_real_money():
    from fastapi.testclient import TestClient
    from app.main import app
    response = TestClient(app).get("/api/health/features/m1720")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()
    assert data["contract"] == LAB_CONTRACT
    for name in ("real_payments_enabled", "bank_reconciled",
                 "ledger_written", "financial_closing_authorized",
                 "payout_authorized", "runtime_git_sha_verified"):
        assert data[name] is False
    assert data["sandbox_preview_only"] is True
