"""M2041–M2200: conservação de centavos em 3 provas exclusivamente fictícias."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.financial_cashboxes import CashboxRoute, DuePayment
from app.financial_sandbox_reconciliation import SandboxIntent, ProviderFixture
from app.financial_three_source_preflight import (
    CONTRACT, SettlementFixture, AccountingFixture, preview_three_source_evidence,
)

T = UUID("00000000-0000-4000-8000-0000000000a1")
B = UUID("00000000-0000-4000-8000-0000000000b1")
NOW = datetime(2027, 8, 20, 12, tzinfo=timezone.utc)
COLLECTOR = "2002"
TENANTS = {T:"2002", B:"3003"}
MASTER_COLLECTOR="1001"


def intention(cents=15000, *, id="900001", tenant=T, op="operation-001",
              idem="idempotent_000001", ref=None, collector=None):
    if tenant is None:
        route=CashboxRoute("PLATFORM_SAAS", MASTER_COLLECTOR, None)
        ref=ref or "saas:licensed-001"
    else:
        route=CashboxRoute("TENANT_CONTRIBUTION", collector or TENANTS[tenant], tenant)
        ref=ref or f"tenant:{tenant}:contribution-001"
    return SandboxIntent(
        op, DuePayment(route, ref, id, cents, False), idem)


def provider(op, **updates):
    p=op.payment
    body={
        "id":int(p.provider_payment_id), "collector_id":int(p.route.collector_id),
        "external_reference":p.external_reference,
        "transaction_amount":Decimal(p.amount_cents)/100,
        "currency_id":"BRL", "status":"approved", "live_mode":False}
    body.update(updates)
    return ProviderFixture(p.provider_payment_id, body)


def settlement(op, *, fee=0, **changes):
    p=op.payment
    row=SettlementFixture(
        p.provider_payment_id,p.route.tenant_id,p.route.collector_id,
        p.external_reference,p.amount_cents,fee,p.amount_cents-fee,
        f"statement-{p.provider_payment_id}",
        NOW-timedelta(days=1))
    return replace(row, **changes)


def accounting(op, **changes):
    p=op.payment
    row=AccountingFixture(
        p.provider_payment_id,p.route.tenant_id,p.route.collector_id,
        p.external_reference,p.amount_cents,p.amount_cents,
        f"ledger-{p.provider_payment_id}",NOW-timedelta(days=1))
    return replace(row, **changes)


def preview(ops, providers=None, statements=None, ledgers=None, **kwargs):
    ops=tuple(ops)
    arguments=dict(
        intents=ops,
        provider_get_fixtures=tuple(providers or ()),
        settlement_fixtures=tuple(statements or ()),
        accounting_fixtures=tuple(ledgers or ()),
        platform_collector_id=MASTER_COLLECTOR,
        tenant_collectors=TENANTS, as_of=NOW)
    arguments.update(kwargs)
    return preview_three_source_evidence(**arguments)


def test_3_source_exact_match_never_marks_any_money_as_paid():
    op=intention()
    report=preview((op,), (provider(op),), (settlement(op,fee=300),),
                   (accounting(op),))
    assert report.contract==CONTRACT
    assert report.status=="SYNTHETIC_CROSS_SOURCE_MATCH_ONLY"
    assert report.total_expected_cents==15000
    assert report.total_synthetic_gross_cents==15000
    assert report.total_synthetic_fees_cents==300
    assert report.total_synthetic_net_cents==14700
    assert report.items[0].finding=="SYNTHETIC_CROSS_SOURCE_MATCH_ONLY"
    assert report.all_sources_synthetic is True
    assert report.settlement_is_bank_proof is False
    assert report.accounting_is_posted_ledger is False
    assert report.bank_reconciled is False
    assert report.capital_confirmed_cents is None
    assert report.real_payments_enabled is False
    assert report.financial_effect_applied is False
    assert report.financial_closing_authorized is False
    assert report.payout_authorized is False
    assert report.items[0].can_mark_paid is False
    assert report.items[0].ledger_written is False


@pytest.mark.parametrize("cents", range(1,401))
def test_400_exact_cent_amounts(cents):
    op=intention(cents)
    r=preview((op,), (provider(op),), (settlement(op),), (accounting(op),))
    assert r.total_expected_cents==cents
    assert r.total_synthetic_net_cents==cents
    assert r.bank_reconciled is False


@pytest.mark.parametrize("fee", range(0,301))
def test_301_net_fee_exactness(fee):
    op=intention(300)
    r=preview((op,), (provider(op),), (settlement(op,fee=fee),),
              (accounting(op),))
    assert r.total_synthetic_gross_cents==300
    assert r.total_synthetic_fees_cents==fee
    assert r.total_synthetic_net_cents==300-fee
    assert r.total_synthetic_gross_cents == (
        r.total_synthetic_fees_cents+r.total_synthetic_net_cents)


@pytest.mark.parametrize("fee",range(0,101))
def test_101_fee_over_gross_rejected(fee):
    op=intention(100)
    with pytest.raises(ValueError):
        settlement(op,fee=101+fee)


@pytest.mark.parametrize("change",[
    {"tenant_id":B},{"collector_id":"3003"},{"external_reference":"tenant:wrong:pay"},
    {"gross_cents":15001,"net_cents":15001},{"status":"synthetic_disputed"},
    {"status":"synthetic_pending"},{"settled_at":NOW+timedelta(days=2)},
])
def test_settlement_conflicts_review_required(change):
    op=intention()
    r=preview((op,), (provider(op),), (settlement(op,**change),), (accounting(op),))
    assert r.status=="REVIEW_REQUIRED"
    assert r.items[0].finding=="SETTLEMENT_FIXTURE_MISMATCH_OR_PENDING"
    assert r.bank_reconciled is False


@pytest.mark.parametrize("change",[
    {"tenant_id":B},{"collector_id":"3003"},
    {"external_reference":"tenant:wrong:payment"},
    {"debit_cents":15001,"credit_cents":15001},
    {"effective_at":NOW+timedelta(days=2)},
])
def test_accounting_conflicts_review_required(change):
    op=intention()
    r=preview((op,), (provider(op),), (settlement(op),), (accounting(op,**change),))
    assert r.status=="REVIEW_REQUIRED"
    assert r.items[0].finding=="ACCOUNTING_FIXTURE_MISMATCH"


@pytest.mark.parametrize("change",[
    {"status":"pending"},{"status":"refunded"},{"status":"charged_back"},
    {"status":"in_mediation"},{"status":"rejected"},{"status":"invalid"},
    {"id":30},{"collector_id":3003},{"currency_id":"USD"},{"live_mode":True},
    {"transaction_amount":Decimal("150.01")},
    {"transaction_amount":float(150)},
])
def test_providers_not_approved_or_not_identical(change):
    op=intention()
    r=preview((op,), (provider(op,**change),), (settlement(op),), (accounting(op),))
    assert r.status=="REVIEW_REQUIRED"
    assert r.items[0].finding=="PROVIDER_FIXTURE_MISMATCH_OR_NOT_APPROVED"


@pytest.mark.parametrize("which,expected",[
    ("provider","MISSING_GET_FIXTURE"),("settlement","MISSING_SETTLEMENT_FIXTURE"),
    ("accounting","MISSING_ACCOUNTING_FIXTURE")])
def test_missing_evidence_is_never_an_approval(which,expected):
    op=intention()
    sources={"provider":(provider(op),),"settlement":(settlement(op),),
             "accounting":(accounting(op),)}
    sources[which]=()
    result=preview((op,), sources["provider"],sources["settlement"],
                   sources["accounting"])
    assert result.items[0].finding==expected
    assert result.bank_reconciled is False


def test_empty_evidence_or_orphans_never_prove_finance():
    assert preview(()).status=="REVIEW_REQUIRED"
    op=intention()
    unexpected=intention(op="op-other",id="123444",idem="idempotent_000002")
    report=preview((op,), (provider(op),provider(unexpected)),
                   (settlement(op),settlement(unexpected)),
                   (accounting(op),accounting(unexpected)))
    assert report.status=="REVIEW_REQUIRED"
    assert report.orphan_provider_ids==("123444",)
    assert report.orphan_settlement_ids==("123444",)
    assert report.orphan_accounting_ids==("123444",)


def test_2_tenants_separate_and_saas_collector_remains_independent():
    a=intention(15000,id="90001")
    b=intention(100,id="90002",tenant=B,op="operation-002",
                idem="idempotent_000002")
    s=intention(999,id="90003",tenant=None,op="operation-003",
                idem="idempotent_000003")
    r=preview((b,s,a),tuple(provider(x) for x in (a,b,s)),
              tuple(settlement(x) for x in (a,b,s)),
              tuple(accounting(x) for x in (a,b,s)))
    assert r.total_expected_cents==16099
    assert [x.operation_key for x in r.items]==[
        "operation-001","operation-002","operation-003"]
    assert r.status=="SYNTHETIC_CROSS_SOURCE_MATCH_ONLY"
    assert [x.collector_id for x in r.items]==["2002","3003","1001"]


def test_duplicate_identity_and_document_references_rejected():
    op=intention()
    second=intention(op="operation-002",id="900002",
                     idem="idempotent_000002",
                     ref=f"tenant:{T}:contribution-002")
    with pytest.raises(ValueError):
        preview((op,op))
    with pytest.raises(ValueError):
        preview((op,second), (provider(op),provider(second)),
                (settlement(op),replace(settlement(second),
                        statement_reference=settlement(op).statement_reference)))
    with pytest.raises(ValueError):
        preview((op,second), (provider(op),provider(second)),
                (settlement(op),settlement(second)),
                (accounting(op),replace(accounting(second),
                     ledger_reference=accounting(op).ledger_reference)))
    with pytest.raises(ValueError):
        preview((op,), (provider(op),provider(op)))
    with pytest.raises(ValueError):
        preview((op,), tenant_collectors={T:"1001"})


@pytest.mark.parametrize("amount",[-1,True,1.2,9999999999999])
def test_malformed_accounting_values_cannot_enter_lab(amount):
    op=intention()
    with pytest.raises(ValueError):
        accounting(op,debit_cents=amount,credit_cents=amount)


def test_3_source_contract_health_disables_real_money():
    from app.main import app
    response=TestClient(app).get("/api/health/features/m2200")
    assert response.status_code==200
    assert response.headers["Cache-Control"]=="no-store"
    body=response.json()
    assert body["contract"]==CONTRACT
    assert body["workstream"]=="AI_STUDIO"
    assert body["three_source_preflight_only"] is True
    for field in ("bank_reconciled","real_payments_enabled",
                  "closing_authorized","ledger_written",
                  "pix_enabled","provider_connected"):
        assert body[field] is False
