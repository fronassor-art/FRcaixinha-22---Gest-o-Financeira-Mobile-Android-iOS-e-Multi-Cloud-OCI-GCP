"""M18000: CI-only PostgreSQL 16/18 physical read adapter and receipts.

All records synthetic. SQL session context is simulated and forgeable by
anyone holding the app DB password, so these tests are NOT production auth.
"""
from datetime import datetime, timezone, timedelta
import os
from uuid import UUID
import asyncpg
import pytest

from app.notification_ci_reader import (
    read_disposable_notification_page, mark_disposable_notification_read,
)
from app.notification_inbox_page_boundary import RecipientScope
from app.notifications_policy import NoticeRole
from app.pix_automation_contract import FinancialOperationBlocked

T=UUID("ffffffff-0000-4000-8000-000000000011")
B=UUID("ffffffff-0000-4000-8000-000000000012")
U=UUID("ffffffff-0000-4000-8000-000000000001")
V=UUID("ffffffff-0000-4000-8000-000000000002")
MASTER=UUID("ffffffff-0000-4000-8000-000000000003")
KEY=b"CI_ONLY_NEVER_PRODUCTION_M18000_CURSOR_SIGN_KEY_2026"
APP=os.getenv("CI_MP_NOTIFICATION_APP_URL","")
PROD=os.getenv("CI_MP_NOTIFICATION_PRODUCER_URL","")
A="postgresql://frcaixinha_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
P="postgresql://frcaixinha_pg18_app:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
WORKER="postgresql://frcaixinha_notify_producer_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
READY=(
    os.getenv("GITHUB_ACTIONS")=="true"
    and os.getenv("FRCAIXINHA_CI_ISOLATED")=="1"
    and APP in (A,P)
    and PROD==WORKER
)
pytestmark=[pytest.mark.asyncio,pytest.mark.skipif(not READY,reason="Disposable PG16/18 CI only")]

SU=RecipientScope(U,NoticeRole.TENANT_MEMBER,T)
SV=RecipientScope(V,NoticeRole.TENANT_MEMBER,B)
SM=RecipientScope(MASTER,NoticeRole.MASTER,None)


async def open_connection(url):
    c=await asyncpg.connect(url,timeout=8,command_timeout=10)
    assert await c.fetchval("SELECT current_database()")=="frcaixinha_staging"
    return c


async def emit(n,tenant=T,user=U,role="TENANT_MEMBER",kind="CONTRIBUTION_DUE_INFO",cycle=2027):
    c=await open_connection(WORKER)
    try:
        await c.execute("SELECT set_config('frcaixinha.notifications_staging_ci','1',false)")
        return await c.fetchval(
            "SELECT public.notification_enqueue_staging_ci("
            "$1::uuid,$2::integer,$3::uuid,$4::uuid,"
            "$5::varchar,$6::varchar,$7::varchar)",
            tenant,cycle,UUID(f"dddddddd-0000-4000-8000-{n:012d}"),
            user,role,kind,"c"*64,
        )
    finally:
        await c.close()


async def test_01_seed_synthetic_ci_notifications():
    assert (await emit(801)).startswith("NEW:")
    assert (await emit(802)).startswith("NEW:")
    assert (await emit(803)).startswith("NEW:")
    assert (await emit(804)).startswith("NEW:")
    assert (await emit(805,tenant=B,user=V)).startswith("NEW:")
    assert (await emit(806,tenant=None,user=MASTER,role="MASTER",
                       kind="SECURITY_SESSION_ALERT",cycle=None)).startswith("NEW:")


async def test_02_ci_read_can_paginate_two_pages():
    c=await open_connection(APP)
    try:
        now=datetime.now(timezone.utc)
        page1=await read_disposable_notification_page(
            c,SU,secret=KEY,now=now,limit=2
        )
        assert len(page1.items)==2
        assert page1.has_more
        assert page1.next_cursor
        assert page1.scope["recipient_user_id"]==str(U)
        assert page1.unread_count is None
        assert page1.inbox_api_connected is False
        assert page1.production_auth_verified is False
        page2=await read_disposable_notification_page(
            c,SU,secret=KEY,now=now,limit=2,after=page1.next_cursor
        )
        assert len(page2.items)==2
        assert not set(x["id"] for x in page1.items)&set(x["id"] for x in page2.items)
        assert page2.scope["tenant_id"]==str(T)
    finally:await c.close()


async def test_03_forged_stale_connection_context_overwritten_by_ci_adapter():
    c=await open_connection(APP)
    try:
        await c.execute("SELECT set_config('app.current_user_id',$1,false)",str(V))
        await c.execute("SELECT set_config('app.current_role','TENANT_MEMBER',false)")
        await c.execute("SELECT set_config('app.current_tenant_id',$1,false)",str(B))
        page=await read_disposable_notification_page(
            c,SU,secret=KEY,now=datetime.now(timezone.utc),limit=3
        )
        assert page.items
        assert page.scope["recipient_user_id"]==str(U)
        assert page.scope["tenant_id"]==str(T)
        other=await read_disposable_notification_page(
            c,SV,secret=KEY,now=datetime.now(timezone.utc),limit=3
        )
        assert other.items
        assert other.scope["recipient_user_id"]==str(V)
        assert other.scope["tenant_id"]==str(B)
        again=await read_disposable_notification_page(
            c,SU,secret=KEY,now=datetime.now(timezone.utc),limit=3
        )
        assert again.scope["recipient_user_id"]==str(U)
    finally:await c.close()


async def test_04_cursor_from_other_tenant_must_not_be_accepted():
    c=await open_connection(APP)
    try:
        result=await read_disposable_notification_page(
            c,SU,secret=KEY,now=datetime.now(timezone.utc),limit=2)
        assert result.next_cursor
        with pytest.raises(FinancialOperationBlocked):
            await read_disposable_notification_page(
                c,SV,secret=KEY,now=datetime.now(timezone.utc),
                limit=2,after=result.next_cursor)
    finally:await c.close()


async def test_05_real_ci_mark_read_scoped_and_idempotent():
    c=await open_connection(APP)
    try:
        p=await read_disposable_notification_page(
            c,SU,secret=KEY,now=datetime.now(timezone.utc),limit=3
        )
        identifier=UUID(p.items[0]["id"])
        first=await mark_disposable_notification_read(c,SU,identifier)
        assert first in ("READ","ALREADY_READ")
        assert await mark_disposable_notification_read(c,SU,identifier)=="ALREADY_READ"
        assert await mark_disposable_notification_read(c,SV,identifier)=="NOT_FOUND"
        fresh=await read_disposable_notification_page(
            c,SU,secret=KEY,now=datetime.now(timezone.utc),limit=3)
        got=next(x for x in fresh.items if x["id"]==str(identifier))
        assert got["read_at"] is not None
    finally:await c.close()


async def test_06_master_sees_only_platform_security_events():
    c=await open_connection(APP)
    try:
        p=await read_disposable_notification_page(
            c,SM,secret=KEY,now=datetime.now(timezone.utc),limit=5
        )
        assert p.items
        assert all(x["kind"]=="SECURITY_SESSION_ALERT" for x in p.items)
        assert p.scope["tenant_id"] is None
        assert all(x["kind"]!="CONTRIBUTION_DUE_INFO" for x in p.items)
    finally:await c.close()


async def test_07_invalid_pagination_refused_before_db_query():
    c=await open_connection(APP)
    try:
        for invalid in (0,-1,51,True,2.5):
            with pytest.raises(FinancialOperationBlocked):
                await read_disposable_notification_page(
                    c,SU,secret=KEY,now=datetime.now(timezone.utc),limit=invalid
                )
        with pytest.raises(FinancialOperationBlocked):
            await read_disposable_notification_page(
                c,SU,secret=b"bad",now=datetime.now(timezone.utc)
            )
    finally:await c.close()


async def test_08_notification_context_failure_stays_fail_closed(monkeypatch):
    c=await open_connection(APP)
    try:
        monkeypatch.setenv("FRCAIXINHA_CI_ISOLATED","0")
        with pytest.raises(FinancialOperationBlocked):
            await read_disposable_notification_page(
                c,SU,secret=KEY,now=datetime.now(timezone.utc)
            )
        with pytest.raises(FinancialOperationBlocked):
            await mark_disposable_notification_read(
                c,SU,UUID("dddddddd-0000-4000-8000-000000000801")
            )
    finally:await c.close()


async def test_09_app_role_has_no_direct_table_mutation_or_outbox_read():
    c=await open_connection(APP)
    try:
        for priv in ("INSERT","UPDATE","DELETE","TRUNCATE"):
            assert await c.fetchval(
                "SELECT has_table_privilege(current_user,"
                "'public.notification_inbox_staging',$1)",priv
            ) is False
        assert await c.fetchval(
            "SELECT has_table_privilege(current_user,"
            "'public.notification_outbox_staging','SELECT')"
        ) is False
        assert await c.fetchval(
            "SELECT has_table_privilege(current_user,"
            "'public.users','SELECT')"
        ) is False
    finally:await c.close()
