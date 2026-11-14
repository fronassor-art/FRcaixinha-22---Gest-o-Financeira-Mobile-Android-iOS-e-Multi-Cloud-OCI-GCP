"""P0-01h: PostgreSQL CI descartavel, sem dados ou operacao real."""
import asyncio
import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest
from app.security import auth_rate_limit_key


def ci_url(name):
    if os.getenv("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("Somente CI descartavel")
    value=os.environ[name]
    u=urlparse(value)
    if u.hostname not in ("127.0.0.1","localhost") or u.port!=5432 or u.path!="/frcaixinha_ci":
        raise RuntimeError("DSN fora do CI")
    return value


@pytest.mark.asyncio
async def test_shared_limit_and_role_isolation(monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_KEY","ci-only-synthetic-secret-p0-01h-123456")
    key=auth_rate_limit_key(str(uuid.uuid4())+"@example.invalid")
    other=auth_rate_limit_key(str(uuid.uuid4())+"@example.invalid")
    a=await asyncpg.connect(ci_url("CI_AUTH_DATABASE_URL"))
    b=await asyncpg.connect(ci_url("CI_AUTH_DATABASE_URL"))
    v=await asyncpg.connect(ci_url("CI_VERIFIER_DATABASE_URL"))
    admin=await asyncpg.connect(ci_url("CI_ADMIN_DATABASE_URL"))
    try:
        assert await a.fetchval("SELECT public.auth_login_rate_check($1)",key)==0
        assert await a.fetchval("SELECT public.auth_login_rate_check($1)","bad")==-1
        for conn in (a,b,a,b):
            assert await conn.fetchval("SELECT public.auth_login_rate_failure($1)",key)==0
        assert await b.fetchval("SELECT public.auth_login_rate_failure($1)",key)>0
        assert await a.fetchval("SELECT public.auth_login_rate_check($1)",key)>0
        assert await b.fetchval("SELECT public.auth_login_rate_check($1)",other)==0
        assert not await a.fetchval(
            "SELECT has_table_privilege(current_user,'public.auth_login_rate_limits','SELECT')")
        assert not await v.fetchval(
            "SELECT has_function_privilege(current_user,'public.auth_login_rate_check(text)','EXECUTE')")
        assert await a.fetchval("SELECT public.auth_login_rate_success($1)",key) is True
        assert await b.fetchval("SELECT public.auth_login_rate_check($1)",key)==0
    finally:
        await admin.execute("DELETE FROM public.auth_login_rate_limits WHERE key_hash=ANY($1::text[])",[key,other])
        for conn in (a,b,v,admin):
            await conn.close()


@pytest.mark.asyncio
async def test_parallel_failed_attempts_are_atomic(monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_KEY","ci-only-synthetic-secret-p0-01h-123456")
    key=auth_rate_limit_key(str(uuid.uuid4())+"@example.invalid")
    cs=[await asyncpg.connect(ci_url("CI_AUTH_DATABASE_URL")) for _ in range(5)]
    admin=await asyncpg.connect(ci_url("CI_ADMIN_DATABASE_URL"))
    try:
        results=await asyncio.wait_for(asyncio.gather(*[
            c.fetchval("SELECT public.auth_login_rate_failure($1)",key) for c in cs
        ]),timeout=10)
        assert sum(1 for n in results if n>0)==1
        assert await admin.fetchval(
            "SELECT attempts FROM public.auth_login_rate_limits WHERE key_hash=$1",key)==5
    finally:
        await admin.execute("DELETE FROM public.auth_login_rate_limits WHERE key_hash=$1",key)
        for c in cs:
            await c.close()
        await admin.close()
