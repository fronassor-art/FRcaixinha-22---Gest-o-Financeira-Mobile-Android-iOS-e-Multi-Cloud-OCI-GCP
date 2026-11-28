"""M14000: REAL PostgreSQL concurrency, RLS and immutability in fake CI ONLY.

Runs ONLY in ephemeral GitHub Actions frcaixinha_staging clone.
Never connect to Termux/OCI/production; no real payment or provider access.
All evidence, principals, identifiers and amounts are 100% fabricated.
"""
from __future__ import annotations

import asyncio
import os
from uuid import UUID

import asyncpg
import pytest

TENANT=UUID("ffffffff-0000-4000-8000-000000000011")
OTHER=UUID("ffffffff-0000-4000-8000-000000000012")
OP="P_"+"a"*32
GENESIS="0"*64
ADMIN=os.environ.get("CI_MP_DISPOSABLE_DATABASE_URL","")
WORKER=os.environ.get("CI_MP_AUDIT_WORKER_URL","")
ENABLED=(
    os.environ.get("GITHUB_ACTIONS")=="true"
    and os.environ.get("FRCAIXINHA_CI_ISOLATED")=="1"
    and ADMIN=="postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
    and WORKER=="postgresql://frcaixinha_mp_financial_worker:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
)
pytestmark=[
    pytest.mark.asyncio,
    pytest.mark.skipif(not ENABLED,reason="CI disposable DB only"),
]


async def connection(url, principal):
    if not ENABLED:
        pytest.skip("disposable GitHub Actions database required")
    conn=await asyncpg.connect(url,timeout=8,command_timeout=10)
    assert await conn.fetchval(
        "SELECT current_database()='frcaixinha_staging' AND session_user=$1",
        principal,
    ) is True
    return conn


async def as_worker():
    return await connection(WORKER,"frcaixinha_mp_financial_worker")


async def as_admin():
    return await connection(ADMIN,"postgres")


async def hold(conn,reason,hash_value="a"*64):
    return await conn.fetchval(
        "SELECT public.mp_orders_staging_record_hold("
        "$1::uuid,$2::varchar,$3::varchar,$4::varchar)",
        TENANT,OP,reason,hash_value,
    )


async def append(conn,reason,kind,claim,prev=GENESIS,tenant=TENANT):
    return await conn.fetchval(
        "SELECT public.mp_orders_staging_append_incident_audit("
        "$1::uuid,$2::varchar,$3::varchar,$4::varchar,$5::varchar,$6::varchar)",
        tenant,OP,reason,kind,claim,prev,
    )


async def rows(conn,reason):
    return await conn.fetch(
        "SELECT sequence,event_kind,claim_sha256,previous_sha256,event_sha256,"
        "hold_active,bank_reconciled,financial_effect_applied,"
        "ledger_written,payout_authorized "
        "FROM public.mp_orders_incident_audit_staging "
        "WHERE tenant_id=$1 AND operation_id=$2 AND reason_code=$3 "
        "ORDER BY sequence",
        TENANT,OP,reason,
    )


async def test_concurrent_identical_append_is_exactly_once():
    reason="TIMEOUT_UNKNOWN"
    seed=await as_worker()
    try:
        assert await hold(seed,reason) in ("NEW","REPLAY")
    finally:
        await seed.close()

    async def contender():
        c=await as_worker()
        try:
            return await append(c,reason,"OPENED","1"*64)
        finally:
            await c.close()
    results=await asyncio.gather(*[contender() for _ in range(12)])
    new=[r for r in results if r.startswith("NEW:")]
    replay=[r for r in results if r.startswith("REPLAY:")]
    assert len(new)==1
    assert len(replay)==11
    assert len({r.split(":")[1] for r in results})==1
    admin=await as_admin()
    try:
        events=await rows(admin,reason)
        assert len(events)==1
        assert events[0]["sequence"]==1
        assert events[0]["previous_sha256"].strip()==GENESIS
        assert events[0]["hold_active"] is True
        for key in ("bank_reconciled","financial_effect_applied",
                    "ledger_written","payout_authorized"):
            assert events[0][key] is False
    finally:
        await admin.close()


async def test_competing_forks_cannot_both_be_committed():
    reason="FEE_MISMATCH"
    seed=await as_worker()
    try:
        assert await hold(seed,reason) in ("NEW","REPLAY")
    finally:
        await seed.close()

    async def fork(kind,hash_value):
        c=await as_worker()
        try:
            return await append(c,reason,kind,hash_value)
        except asyncpg.PostgresError:
            return "REJECTED"
        finally:
            await c.close()

    out=await asyncio.gather(
        fork("OPENED","2"*64),fork("SECURITY_ESCALATED","3"*64)
    )
    assert sum(r.startswith("NEW:") for r in out)==1
    assert out.count("REJECTED")==1
    admin=await as_admin()
    try:
        assert len(await rows(admin,reason))==1
    finally:
        await admin.close()


async def test_predecessor_and_ordered_sequences_checked_by_database():
    reason="STATUS_CONFLICT"
    c=await as_worker()
    try:
        assert await hold(c,reason) in ("NEW","REPLAY")
        r1=await append(c,reason,"OPENED","4"*64)
        assert r1.startswith("NEW:")
        h1=r1.split(":",1)[1]
        with pytest.raises(asyncpg.PostgresError):
            await append(c,reason,"SECURITY_ESCALATED","5"*64,GENESIS)
        r2=await append(c,reason,"EVIDENCE_REVIEW_REQUESTED","6"*64,h1)
        assert r2.startswith("NEW:")
        assert r2!=r1
        with pytest.raises(asyncpg.PostgresError):
            await append(c,reason,"OPENED","4"*64,h1)
    finally:
        await c.close()
    admin=await as_admin()
    try:
        events=await rows(admin,reason)
        assert [r["sequence"] for r in events]==[1,2]
        assert events[1]["previous_sha256"].strip()==h1
        assert events[1]["event_sha256"].strip()==r2.split(":",1)[1]
    finally:
        await admin.close()


async def test_direct_user_role_has_no_table_dml_or_read():
    c=await as_worker()
    try:
        for privilege in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE"):
            allowed=await c.fetchval(
                "SELECT has_table_privilege("
                "current_user,'public.mp_orders_incident_audit_staging',$1)",
                privilege,
            )
            assert allowed is False, privilege
        assert await c.fetchval(
            "SELECT has_function_privilege(current_user,"
            "'public.mp_orders_staging_append_incident_audit("
            "uuid,varchar,varchar,varchar,varchar,varchar)','EXECUTE')"
        ) is True
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await c.fetchval(
                "SELECT count(*) FROM public.mp_orders_incident_audit_staging"
            )
    finally:
        await c.close()


async def test_admin_dml_cannot_change_committed_audit_rows():
    admin=await as_admin()
    try:
        assert len(await rows(admin,"TIMEOUT_UNKNOWN"))==1
        for sql in (
            "UPDATE public.mp_orders_incident_audit_staging "
            "SET claim_sha256=repeat('f',64) WHERE reason_code='TIMEOUT_UNKNOWN'",
            "DELETE FROM public.mp_orders_incident_audit_staging "
            "WHERE reason_code='TIMEOUT_UNKNOWN'",
            "TRUNCATE public.mp_orders_incident_audit_staging",
        ):
            with pytest.raises(asyncpg.PostgresError):
                await admin.execute(sql)
        assert len(await rows(admin,"TIMEOUT_UNKNOWN"))==1
    finally:
        await admin.close()


async def test_transaction_rollback_drops_both_hold_and_audit():
    reason="PROVIDER_MISMATCH"
    c=await as_worker()
    try:
        with pytest.raises(RuntimeError):
            async with c.transaction():
                assert await hold(c,reason)=="NEW"
                result=await append(c,reason,"OPENED","7"*64)
                assert result.startswith("NEW:")
                raise RuntimeError("synthetic crash")
    finally:
        await c.close()
    admin=await as_admin()
    try:
        assert len(await rows(admin,reason))==0
        assert await admin.fetchval(
            "SELECT count(*) FROM public.mp_orders_reconciliation_holds_staging "
            "WHERE tenant_id=$1 AND operation_id=$2 AND reason_code=$3",
            TENANT,OP,reason,
        )==0
    finally:
        await admin.close()


async def test_cross_tenant_and_unknown_action_fail_closed():
    reason="REVERSAL_PENDING"
    c=await as_worker()
    try:
        assert await hold(c,reason)=="NEW"
        with pytest.raises(asyncpg.PostgresError):
            await append(c,reason,"OPENED","8"*64,tenant=OTHER)
        with pytest.raises(asyncpg.PostgresError):
            await append(c,reason,"RELEASE_HOLD","8"*64)
        with pytest.raises(asyncpg.PostgresError):
            await append(c,reason,"LEDGER_POST","8"*64)
        with pytest.raises(asyncpg.PostgresError):
            await append(c,reason,"PAYOUT","8"*64)
    finally:
        await c.close()
    admin=await as_admin()
    try:
        assert len(await rows(admin,reason))==0
    finally:
        await admin.close()
