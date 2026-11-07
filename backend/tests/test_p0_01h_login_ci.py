"""Verificação E2E do limite de login em CI PostgreSQL descartável."""
import os
import uuid
from urllib.parse import urlparse
import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.config import settings
from app.security import auth_rate_limit_key, hash_password_secure, clear_rate_limit


def disposable(name):
    if os.getenv("FRCAIXINHA_CI_ISOLATED")!="1": pytest.skip("CI descartavel apenas")
    u=os.environ[name]
    p=urlparse(u)
    if p.hostname not in ("127.0.0.1","localhost") or p.port!=5432 or p.path!="/frcaixinha_ci":
        raise RuntimeError("DSN invalido para CI")
    return u


@pytest.mark.asyncio
async def test_login_five_failed_attempts_block_even_valid_password(monkeypatch):
    uid=uuid.uuid4()
    email=f"ci-rate-{uid}@example.com"
    password="synthetic-only-CI-password"
    monkeypatch.setattr(settings,"DATABASE_URL",disposable("DATABASE_URL"))
    monkeypatch.setenv("AUTH_DATABASE_URL",disposable("CI_AUTH_DATABASE_URL"))
    monkeypatch.setenv("AUTH_VERIFIER_DATABASE_URL",disposable("CI_VERIFIER_DATABASE_URL"))
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH","1")
    monkeypatch.setenv("ENVIRONMENT","homologation")
    monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_KEY","ci-only-test-hmac-secret-of-40-bytes-placeholder")
    admin=await asyncpg.connect(disposable("CI_ADMIN_DATABASE_URL"))
    auth=await asyncpg.connect(disposable("CI_AUTH_DATABASE_URL"))
    try:
        await admin.execute(
            "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master) "
            "VALUES($1,$2,'CI Master sintetico',$3,'00000000000',TRUE)",
            uid,email,uid.hex[:14],
        )
        await admin.execute(
            "INSERT INTO public.credentials(user_id,password_hash) VALUES($1,$2)",
            uid,hash_password_secure(password),
        )
        async with AsyncClient(transport=ASGITransport(app=app),base_url="http://ci") as client:
            for i in range(5):
                r=await client.post("/api/v1/auth/login",json={
                    "usernameOrEmail":email,"password":"bad-password"})
                assert r.status_code==401,(i,r.text)
            locked=await client.post("/api/v1/auth/login",json={
                "usernameOrEmail":email,"password":password,
                "requestedRole":"MASTER"})
            assert locked.status_code==429,locked.text
            key=auth_rate_limit_key(email)
            assert await auth.fetchval("SELECT public.auth_login_rate_check($1)",key)>0
            assert await auth.fetchval("SELECT public.auth_login_rate_success($1)",key)
            clear_rate_limit(email) # Simula somente o cooldown no CI.
            ok=await client.post("/api/v1/auth/login",json={
                "usernameOrEmail":email,"password":password,
                "requestedRole":"MASTER"})
            assert ok.status_code==200,ok.text
            token=ok.json()["token"]
            assert len(token)>24
            assert await auth.fetchval("SELECT public.auth_login_rate_check($1)",key)==0
            goodbye=await client.post("/api/v1/auth/logout",
                    headers={"Authorization":"Bearer "+token})
            assert goodbye.status_code==200,goodbye.text
    finally:
        clear_rate_limit(email)
        await auth.close()
        await admin.execute("DELETE FROM public.users WHERE id=$1",uid)
        await admin.close()
