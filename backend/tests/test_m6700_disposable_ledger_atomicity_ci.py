"""M6700: ACTUAL deferred-balance PostgreSQL journal tests, DISPOSABLE CI ONLY.

Tests verify transaction atomicity, replay, rollback, foreign tenant FK and
concurrent duplicate references. Real ledger posting remains UNIMPLEMENTED:
DB connections here use the synthetic CI postgres principal; never mount
these helpers in the FastAPI runtime or use real statements.
"""
from __future__ import annotations

import asyncio
import os
from uuid import UUID,uuid4

import asyncpg
import pytest

T=UUID("ffffffff-0000-4000-8000-000000000011")
OTHER=UUID("ffffffff-0000-4000-8000-000000000012")
ENABLED=(
    os.environ.get("GITHUB_ACTIONS")=="true"
    and os.environ.get("FRCAIXINHA_CI_ISOLATED")=="1"
    and os.environ.get("CI_MP_DISPOSABLE_DATABASE_URL","").startswith(
        "postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
    )
)
pytestmark=[
    pytest.mark.asyncio,
    pytest.mark.skipif(not ENABLED,reason="only isolated Actions PostgreSQL")
]


async def conn():
    if not ENABLED:
        pytest.skip("requires isolated GitHub CI PostgreSQL")
    c=await asyncpg.connect(os.environ["CI_MP_DISPOSABLE_DATABASE_URL"])
    if await c.fetchval(
        "SELECT current_database()='frcaixinha_staging' AND "
        "session_user='postgres' AND "
        "to_regclass('public.mp_pix_collection_operations_staging') IS NOT NULL"
    ) is not True:
        await c.close()
        raise AssertionError("M6700: invalid disposable database")
    return c


async def accounts(c,tenant):
    cash=await c.fetchval(
        "SELECT id FROM public.ledger_accounts "
        "WHERE tenant_id=$1 AND account_code='1.1.1'",tenant)
    capital=await c.fetchval(
        "SELECT id FROM public.ledger_accounts "
        "WHERE tenant_id=$1 AND account_code='2.1.1'",tenant)
    assert cash is not None and capital is not None
    return cash,capital


async def insert_post(c,tenant,reference,*,cash,capital,
                      debit_cents=15000,credit_cents=15000):
    trans_id=uuid4()
    await c.execute(
        "INSERT INTO public.ledger_transactions "
        "(id,tenant_id,description,reference_id) "
        "VALUES ($1,$2,'SYNTHETIC CI LEDGER',$3)",
        trans_id,tenant,reference,
    )
    await c.executemany(
        "INSERT INTO public.ledger_entries "
        "(id,tenant_id,transaction_id,account_id,entry_type,amount_cents) "
        "VALUES ($1,$2,$3,$4,$5,$6)",[
            (uuid4(),tenant,trans_id,cash,"DR",debit_cents),
            (uuid4(),tenant,trans_id,capital,"CR",credit_cents),
        ],
    )
    return trans_id


async def count_tx(c,tenant,ref):
    return await c.fetchval(
        "SELECT COUNT(*) FROM public.ledger_transactions "
        "WHERE tenant_id=$1 AND reference_id=$2",tenant,ref)


async def test_valid_double_entry_commits_and_is_queryable():
    c=await conn()
    try:
        cash,capital=await accounts(c,T)
        ref="CI-VALID-"+uuid4().hex
        async with c.transaction(isolation="serializable"):
            tx=await insert_post(c,T,ref,cash=cash,capital=capital)
        assert await count_tx(c,T,ref)==1
        rows=await c.fetch(
            "SELECT entry_type,amount_cents FROM public.ledger_entries "
            "WHERE tenant_id=$1 AND transaction_id=$2",T,tx)
        assert len(rows)==2
        assert sum(r["amount_cents"] for r in rows if r["entry_type"]=="DR")==15000
        assert sum(r["amount_cents"] for r in rows if r["entry_type"]=="CR")==15000
        # No effect on any real/tenant owed dues, proof or receipt.
        assert await c.fetchval(
            "SELECT count(*) FROM public.mp_pix_receipts_staging"
        )==0
    finally:
        await c.close()


async def test_imbalanced_deferred_trigger_rolls_back_all_rows():
    c=await conn()
    try:
        cash,capital=await accounts(c,T)
        ref="CI-IMBALANCED-"+uuid4().hex
        with pytest.raises(asyncpg.PostgresError):
            async with c.transaction(isolation="serializable"):
                await insert_post(c,T,ref,cash=cash,capital=capital,
                                  debit_cents=14999,credit_cents=15000)
        assert await count_tx(c,T,ref)==0
    finally:
        await c.close()


async def test_tenant_fk_prevents_cross_box_posting():
    c=await conn()
    try:
        _,capital=await accounts(c,T)
        other_cash,_=await accounts(c,OTHER)
        ref="CI-CROSS-"+uuid4().hex
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            async with c.transaction(isolation="serializable"):
                await insert_post(c,T,ref,cash=other_cash,capital=capital)
        assert await count_tx(c,T,ref)==0
    finally:
        await c.close()


async def test_same_business_reference_cannot_post_twice():
    c=await conn()
    try:
        cash,capital=await accounts(c,T)
        ref="CI-DUPLICATE-"+uuid4().hex
        async with c.transaction(isolation="serializable"):
            await insert_post(c,T,ref,cash=cash,capital=capital)
        with pytest.raises(asyncpg.UniqueViolationError):
            async with c.transaction(isolation="serializable"):
                await insert_post(c,T,ref,cash=cash,capital=capital)
        assert await count_tx(c,T,ref)==1
    finally:
        await c.close()


async def test_parallel_same_reference_exactly_one_ledger_transaction():
    initial=await conn()
    try:
        cash,capital=await accounts(initial,T)
    finally:
        await initial.close()
    reference="CI-RACE-"+uuid4().hex

    async def race_one():
        c=await conn()
        try:
            async with c.transaction(isolation="serializable"):
                await insert_post(c,T,reference,cash=cash,capital=capital)
            return "NEW"
        except (asyncpg.UniqueViolationError,
                asyncpg.SerializationError):
            return "REPLAY_OR_RACE"
        finally:
            await c.close()

    results=await asyncio.gather(*[race_one() for _ in range(12)])
    assert results.count("NEW")==1
    assert results.count("REPLAY_OR_RACE")==11
    c=await conn()
    try:
        assert await count_tx(c,T,reference)==1
        assert await c.fetchval(
            "SELECT COUNT(*) FROM public.ledger_entries e "
            "JOIN public.ledger_transactions t ON t.id=e.transaction_id "
            "WHERE t.tenant_id=$1 AND t.reference_id=$2",T,reference)==2
    finally:
        await c.close()
