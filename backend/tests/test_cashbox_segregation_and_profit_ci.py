"""Fronteiras do caixa Master/Tenant e rateio 15/85, SEM pagamentos reais."""
import json
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from app.financial_cashboxes import (
    CashboxRoute, DuePayment, MemberCapitalDays, PLATFORM_SAAS,
    TENANT_CONTRIBUTION, TENANT_LOAN_REPAYMENT,
    simulate_annual_profit_split, validate_payment_against_cashbox,
)
from app.mercado_pago_adapter import (
    PixCollectionRequest, build_create_pix_request,
    build_get_payment_request, parse_collection_response,
)
from app.mercado_pago_safety import verify_webhook_signature

A = UUID("00000000-0000-4000-8000-0000000000a1")
B = UUID("00000000-0000-4000-8000-0000000000b1")
M1 = UUID("00000000-0000-4000-8000-000000000001")
M2 = UUID("00000000-0000-4000-8000-000000000002")
M3 = UUID("00000000-0000-4000-8000-000000000003")
MASTER_COLLECTOR = "1001"
A_COLLECTOR = "2002"
B_COLLECTOR = "3003"
COLLECTORS = {A: A_COLLECTOR, B: B_COLLECTOR}


def member(tenant, membership, weight, eligible=True):
    return MemberCapitalDays(
        tenant, membership, Decimal(weight), eligible
    )


def payment(route, ref, ident, amount):
    return DuePayment(route, ref, ident, amount, False)


def response(due, **updates):
    data = dict(
        id=int(due.provider_payment_id),
        collector_id=int(due.route.collector_id),
        external_reference=due.external_reference,
        transaction_amount=Decimal(due.amount_cents) / 100,
        currency_id="BRL", status="approved", live_mode=False,
    )
    data.update(updates)
    return data


def checked(due, **updates):
    return validate_payment_against_cashbox(
        due, response(due, **updates),
        platform_collector_id=MASTER_COLLECTOR,
        tenant_collectors=COLLECTORS,
    )


def test_treasuries_are_distinct_and_do_not_split_member_contributions():
    saas = payment(CashboxRoute(PLATFORM_SAAS, MASTER_COLLECTOR, None),
                   "saas:license-abc", "101", 8990)
    monthly = payment(CashboxRoute(TENANT_CONTRIBUTION, A_COLLECTOR, A),
                      f"tenant:{A}:contribution-1", "102", 15000)
    repayment = payment(CashboxRoute(TENANT_LOAN_REPAYMENT, B_COLLECTOR, B),
                        f"tenant:{B}:installment-1", "103", 18250)
    for due in (saas, monthly, repayment):
        assert checked(due)
        assert not checked(due, status="pending")
        assert not checked(due, live_mode=True)
        assert not checked(due, currency_id="USD")
        assert not checked(due, transaction_amount=Decimal(due.amount_cents + 1) / 100)
        assert not checked(due, external_reference="outro-contrato")
        assert not checked(due, id=901)
    assert not validate_payment_against_cashbox(
        monthly, response(monthly), platform_collector_id=A_COLLECTOR,
        tenant_collectors=COLLECTORS,
    )
    assert not validate_payment_against_cashbox(
        saas, response(saas), platform_collector_id=MASTER_COLLECTOR,
        tenant_collectors={A: MASTER_COLLECTOR},
    )
    assert not validate_payment_against_cashbox(
        monthly, response(monthly), platform_collector_id=MASTER_COLLECTOR,
        tenant_collectors={B: B_COLLECTOR},
    )
    # Não existe comissão de 15% em uma contribuição de cota (R$150).
    assert monthly.amount_cents == 15000
    assert saas.route.tenant_id is None and monthly.route.tenant_id == A
    assert repayment.route.tenant_id == B


@pytest.mark.parametrize("purpose,collector,tenant,valid", [
    (PLATFORM_SAAS, MASTER_COLLECTOR, None, True),
    (PLATFORM_SAAS, MASTER_COLLECTOR, A, False),
    (TENANT_CONTRIBUTION, A_COLLECTOR, A, True),
    (TENANT_CONTRIBUTION, A_COLLECTOR, None, False),
    (TENANT_LOAN_REPAYMENT, B_COLLECTOR, B, True),
    ("MASTER_TAKES_MEMBER_CAPITAL", MASTER_COLLECTOR, None, False),
    (PLATFORM_SAAS, "200\n3", None, False),
    (PLATFORM_SAAS, "not_numeric", None, False),
])
def test_route_validation(purpose, collector, tenant, valid):
    if valid:
        assert CashboxRoute(purpose, collector, tenant).purpose == purpose
    else:
        with pytest.raises(ValueError):
            CashboxRoute(purpose, collector, tenant)


def test_prevent_cross_tenant_reference_and_amount_or_float_inputs():
    route = CashboxRoute(TENANT_CONTRIBUTION, A_COLLECTOR, A)
    with pytest.raises(ValueError):
        payment(route, f"tenant:{B}:contribution-1", "105", 15000)
    for amount in (True, 1.50, 0, -1, 9999999999991):
        with pytest.raises(ValueError):
            payment(route, f"tenant:{A}:contribution-1", "105", amount)
    with pytest.raises(ValueError):
        payment(CashboxRoute(PLATFORM_SAAS, MASTER_COLLECTOR, None),
                "tenant:unrelated", "106", 10000)


def test_profit_10000_real_net_example_never_becomes_master_saas_revenue():
    result = simulate_annual_profit_split(
        A, 1_000_000,
        (member(A, M1, "50.0000"), member(A, M2, "30.0000"),
         member(A, M3, "20.0000")),
    )
    assert result.administrator_share_cents == 150_000
    assert result.members_pool_cents == 850_000
    assert dict(result.shares_cents) == {
        M1: 425_000, M2: 255_000, M3: 170_000
    }
    assert sum(dict(result.shares_cents).values()) + result.administrator_share_cents == 1_000_000
    assert result.tenant_id == A
    assert result.simulation_only is True
    assert result.bank_reconciled is False
    assert result.closing_authorized is False


def test_largest_remainders_use_exact_cents_and_stable_membership_tiebreak():
    three = (member(A, M3, "1.0000"), member(A, M1, "1.0000"), member(A, M2, "1.0000"))
    result = simulate_annual_profit_split(A, 100, three)
    # R$1,00 lucro = 15 c admin + 85 centavos divididos entre tres membros.
    assert result.administrator_share_cents == 15
    assert result.members_pool_cents == 85
    assert dict(result.shares_cents) == {M1: 29, M2: 28, M3: 28}
    assert sum(v for _, v in result.shares_cents) == 85
    assert simulate_annual_profit_split(A, 100, tuple(reversed(three))).shares_cents == result.shares_cents


def test_ineligible_member_receives_zero_and_admin_does_not_self_approve():
    result = simulate_annual_profit_split(
        A, 10_000, (member(A, M1, "100.0000", False), member(A, M2, "1.0000")),
    )
    assert result.administrator_share_cents == 1500
    assert dict(result.shares_cents) == {M1: 0, M2: 8500}
    with pytest.raises(ValueError, match="Pool sem membro"):
        simulate_annual_profit_split(A, 10_000, (member(A, M1, "100.0000", False),))


def test_zero_profit_no_fictitious_income_and_invalid_inputs_rejected():
    z = simulate_annual_profit_split(A, 0, tuple())
    assert (z.administrator_share_cents, z.members_pool_cents, z.shares_cents) == (0, 0, ())
    invalid = (
        (A, -1, tuple()),
        (A, 1.0, tuple()),
        (A, True, tuple()),
        (A, 100, (member(B, M1, "1.0000"),)),
        (A, 100, (member(A, M1, "1.0000"), member(A, M1, "1.0000"))),
    )
    for tenant, value, users in invalid:
        with pytest.raises(ValueError):
            simulate_annual_profit_split(tenant, value, users)
    with pytest.raises(ValueError):
        member(A, M1, "0.00001")
    with pytest.raises(ValueError):
        member(A, M1, "NaN")
    with pytest.raises(ValueError):
        member(A, M1, "-1.0000")


def test_mock_mercado_pago_pix_collection_routes_require_merchant_and_not_webhook():
    # Duas contas recebedoras diferentes; nenhum token real nem saída HTTP.
    for route, ref, cost in (
        (CashboxRoute(PLATFORM_SAAS, MASTER_COLLECTOR, None), "saas:license-x", 8990),
        (CashboxRoute(TENANT_CONTRIBUTION, A_COLLECTOR, A),
         f"tenant:{A}:contribution-x", 15000),
    ):
        query = PixCollectionRequest(
            operation_id=ref, amount_cents=cost,
            payer_email="pagador-ficticio@example.invalid",
            description="Laboratorio sem pagamento",
            idempotency_key="estavel_id_" + route.collector_id,
        )
        post = build_create_pix_request(access_token="TOKEN_FICTICIO_NAO_ENVIE",
                                        payment=query)
        payload = json.loads(post.content, parse_float=Decimal)
        assert payload["transaction_amount"] == Decimal(cost) / 100
        assert payload["external_reference"] == ref
        assert post.headers["X-Idempotency-Key"] == query.idempotency_key
        assert "TOKEN_FICTICIO_NAO_ENVIE" not in post.content.decode()
        assert str(post.url) == "https://api.mercadopago.com/v1/payments"
        assert build_get_payment_request(
            access_token="TOKEN_FICTICIO_NAO_ENVIE",
            provider_payment_id="1234567",
        ).url.path == "/v1/payments/1234567"
        mock = httpx.Response(201, content=json.dumps({
            "id": 1234567,
            "collector_id": int(route.collector_id),
            "transaction_amount": str(Decimal(cost) / 100),
            "currency_id": "BRL", "status": "pending", "live_mode": False,
            "external_reference": ref,
            "point_of_interaction": {
                "transaction_data": {"qr_code": "QR_FICTICIO_INUTILIZAVEL"}
            },
        }).encode())
        parsed = parse_collection_response(
            mock, expected=query, collector_id=route.collector_id, live_mode=False,
        )
        assert parsed.status == "pending"
        assert parsed.qr_code == "QR_FICTICIO_INUTILIZAVEL"
        # Mesmo um QR gerado e uma notificação não autorizam baixa:
        due = DuePayment(route, ref, "1234567", cost, False)
        assert not validate_payment_against_cashbox(
            due, response(due, status="pending"),
            platform_collector_id=MASTER_COLLECTOR,
            tenant_collectors=COLLECTORS,
        )
    assert not verify_webhook_signature(
        secret="secret-ficticio", signature="ts=123,v1=" + "0" * 64,
        request_id="event", resource_id="123",
    )
