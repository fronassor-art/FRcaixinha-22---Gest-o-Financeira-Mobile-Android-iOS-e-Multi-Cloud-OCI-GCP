"""Regressões P0: simulação Price usa exclusivamente política/ciclo do PostgreSQL."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.models import LoanSimulateRequest
from app.routers.loans import simulate_loan_price


class FakePolicyConnection:
    def __init__(self, *, cycle=True, policy=True, interest="0.20", max_installments=6,
                 start=date(2027, 1, 1), end=date(2027, 12, 31)):
        self.cycle = cycle
        self.policy = policy
        self.interest = interest
        self.max_installments = max_installments
        self.start = start
        self.end = end
        self.queries = []

    async def fetchrow(self, sql, *args):
        self.queries.append((sql, args))
        if "FROM public.cycles" in sql:
            return {
                "id": uuid.uuid4(), "start_date": self.start, "end_date": self.end
            } if self.cycle else None
        if "FROM public.policies" in sql:
            return {
                "id": uuid.uuid4(), "monthly_interest_rate": Decimal(self.interest),
                "max_installments": self.max_installments
            } if self.policy else None
        raise AssertionError("Consulta não prevista: " + sql)

    async def execute(self, *args, **kwargs):
        raise AssertionError("Simulação não pode escrever no PostgreSQL")


TENANT = str(uuid.uuid4())


def member(tenant=TENANT, role="TENANT_MEMBER", is_master=False):
    return AuthenticatedSession(
        str(uuid.uuid4()), role, tenant,
        "synthetic@example.invalid", "Pessoa sintética", is_master
    )


@pytest.mark.asyncio
async def test_policy_rate_is_authoritative_and_preview_is_read_only():
    conn = FakePolicyConnection(interest="0.15")
    result = await simulate_loan_price(
        TENANT, LoanSimulateRequest(principal="500.00", term_months=5), member(), conn
    )
    assert result.monthly_rate == Decimal("0.15")
    assert result.total_payable != Decimal("835.96")
    assert result.schedule[0].due_date == "2027-01-10"
    assert len(conn.queries) == 2
    assert "status='ACTIVE'" in conn.queries[1][0]
    assert conn.queries[0][1][0] == conn.queries[1][1][0] == uuid.UUID(TENANT)


@pytest.mark.asyncio
async def test_legacy_client_rate_cannot_override_tenant_policy():
    conn = FakePolicyConnection()
    with pytest.raises(HTTPException) as err:
        await simulate_loan_price(
            TENANT, LoanSimulateRequest(
                principal="500.00", term_months=5, monthly_rate="0.01"
            ), member(), conn,
        )
    assert err.value.status_code == 422
    assert conn.queries == []


@pytest.mark.asyncio
async def test_policy_max_installments_and_inactive_state_fail_closed():
    too_short = FakePolicyConnection(max_installments=3)
    with pytest.raises(HTTPException) as err:
        await simulate_loan_price(
            TENANT, LoanSimulateRequest(principal="500.00", term_months=5),
            member(), too_short,
        )
    assert err.value.status_code == 422
    no_policy = FakePolicyConnection(policy=False)
    with pytest.raises(HTTPException) as err:
        await simulate_loan_price(
            TENANT, LoanSimulateRequest(principal="500.00", term_months=5),
            member(), no_policy,
        )
    assert err.value.status_code == 409
    no_cycle = FakePolicyConnection(cycle=False)
    with pytest.raises(HTTPException) as err:
        await simulate_loan_price(
            TENANT, LoanSimulateRequest(principal="500.00", term_months=5),
            member(), no_cycle,
        )
    assert err.value.status_code == 409


@pytest.mark.asyncio
async def test_wrong_tenant_or_master_cannot_read_policy():
    for who in (member(str(uuid.uuid4())), member(None, "MASTER", True)):
        conn = FakePolicyConnection()
        with pytest.raises(HTTPException) as err:
            await simulate_loan_price(
                TENANT, LoanSimulateRequest(principal="500.00", term_months=5),
                who, conn,
            )
        assert err.value.status_code == 403
        assert conn.queries == []


@pytest.mark.asyncio
async def test_cycle_year_uses_actual_postgresql_calendar_not_hardcoded_2027():
    conn = FakePolicyConnection(start=date(2028, 1, 1), end=date(2028, 12, 31))
    result = await simulate_loan_price(
        TENANT, LoanSimulateRequest(principal="500.00", term_months=5),
        member(), conn,
    )
    assert result.schedule[0].due_date == "2028-01-10"
    assert result.schedule[-1].due_date == "2028-05-10"


@pytest.mark.asyncio
async def test_irregular_disbursement_cannot_leave_tenant_cycle():
    conn = FakePolicyConnection()
    with pytest.raises(HTTPException) as err:
        await simulate_loan_price(
            TENANT, LoanSimulateRequest(
                principal="500.00", term_months=5,
                disbursement_date=date(2027, 11, 28)
            ), member(), conn,
        )
    assert err.value.status_code == 422
    assert len(conn.queries) == 2
