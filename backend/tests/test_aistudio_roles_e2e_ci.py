"""Teste E2E (3 perfis), exclusivamente PostgreSQL descartavel CI."""
import os
from uuid import uuid4
from urllib.parse import urlparse

import psycopg
import pytest
from httpx import AsyncClient, ASGITransport

from app.aistudio_onboarding import onboard_tenant_with_roles, OnboardingDenied
from app.config import settings
from app.database import close_db_pool
from app.main import app
from app.security import hash_password_secure


@pytest.mark.asyncio
async def test_local_onboarding_three_roles_and_auth(monkeypatch):
    if os.getenv("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("Somente CI descartavel")
    dsn = os.environ["CI_ADMIN_DATABASE_URL"]
    parsed = urlparse(dsn)
    assert (parsed.username,parsed.hostname,parsed.port,parsed.path) == (
        "postgres","127.0.0.1",5432,"/frcaixinha_ci")
    tag = uuid4().hex
    emails = [f"{role}-{tag}@example.invalid" for role in ("master","admin","member")]
    passwords = ["ci-pass-master-0123456789", "ci-pass-admin-0123456789",
                 "ci-pass-member-0123456789"]
    master_id = uuid4()
    tenants = []
    people = []
    await close_db_pool()
    monkeypatch.setattr(settings, "DATABASE_URL", os.environ["DATABASE_URL"])
    monkeypatch.setenv("AUTH_DATABASE_URL", os.environ["CI_AUTH_DATABASE_URL"])
    monkeypatch.setenv("AUTH_VERIFIER_DATABASE_URL", os.environ["CI_VERIFIER_DATABASE_URL"])
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH", "1")
    monkeypatch.setenv("ENVIRONMENT", "homologation")
    monkeypatch.setenv("AUTH_RATE_LIMIT_HMAC_KEY",
                       "ci-only-test-hmac-secret-of-40-bytes-placeholder")

    def new(email, cpf, password):
        return dict(mode="new",email=email,cpf=cpf,phone="11999999999",
                    full_name="Pessoa Sintetica CI",password=password)
    def existing(email, password):
        return dict(mode="existing",email=email,password=password)

    with psycopg.connect(dsn, autocommit=True) as db:
        try:
            db.execute(
                "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master) "
                "VALUES(%s,%s,'Master CI','99988877766','11999999999',TRUE)",
                (master_id, emails[0]))
            db.execute("INSERT INTO public.credentials(user_id,password_hash) "
                       "VALUES(%s,%s)",(master_id,hash_password_secure(passwords[0])))

            def onboard(name,admin,member,master_password=passwords[0]):
                return onboard_tenant_with_roles(
                    db,master_email=emails[0],master_password=master_password,
                    tenant_name=name,contracting_party_id=str(uuid4()),
                    admin=admin,member=member)
            first=onboard("Caixinha Principal CI",
                          new(emails[1],"99988877765",passwords[1]),
                          new(emails[2],"99988877764",passwords[2]))
            people.extend([first["admin_id"],first["member_id"]])
            tenants.append(first["tenant_id"])
            assert len(set(people)) == 2
            assert db.execute("SELECT count(*) FROM public.memberships WHERE tenant_id=%s",
                              (first["tenant_id"],)).fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s "
                              "AND action LIKE 'AI_STUDIO_LOCAL_%'",
                              (first["tenant_id"],)).fetchone()[0] == 3
            before=db.execute("SELECT count(*) FROM public.tenants").fetchone()[0]
            with pytest.raises(OnboardingDenied):
                onboard("Duplicado deve falhar",new(emails[1],"99988877765",passwords[1]),
                        new("extra-"+emails[2],"99988877763",passwords[2]))
            assert db.execute("SELECT count(*) FROM public.tenants").fetchone()[0] == before
            assert db.execute("SELECT count(*) FROM public.users WHERE email=%s",
                              ("extra-"+emails[2],)).fetchone()[0] == 0
            with pytest.raises(OnboardingDenied,match="Autorizacao"):
                onboard("Master com senha falsa",existing(emails[1],passwords[1]),
                        existing(emails[2],passwords[2]),master_password="invalida")
            second=onboard("Segundo tenant mesma identidade",
                           existing(emails[1],passwords[1]),existing(emails[2],passwords[2]))
            tenants.append(second["tenant_id"])
            assert second["admin_id"] == first["admin_id"]
            assert second["member_id"] == first["member_id"]
            with pytest.raises(OnboardingDenied,match="nao comprovada"):
                onboard("Senha admin errada",existing(emails[1],"invalida"),
                        existing(emails[2],passwords[2]))
            async with AsyncClient(
                transport=ASGITransport(app=app),base_url="http://ci"
            ) as client:
                assert (await client.get("/api/v1/auth/me")).status_code == 401
                for email,password,role in zip(
                    emails,passwords,("MASTER","TENANT_ADMIN","TENANT_MEMBER")
                ):
                    login=await client.post("/api/v1/auth/login",json={
                        "usernameOrEmail":email,"password":password})
                    assert login.status_code == 200,(role,login.text)
                    body=login.json()
                    assert body["user"]["role"] == role
                    headers={"Authorization":"Bearer "+body["token"]}
                    assert (await client.get("/api/v1/auth/me",headers=headers)).status_code == 200
                    overview=await client.get("/api/v1/master/overview",headers=headers)
                    assert overview.status_code == (200 if role=="MASTER" else 403),(
                        role,overview.text)
                    members=await client.get(
                        f"/api/v1/tenants/{first['tenant_id']}/members",headers=headers)
                    assert members.status_code == (200 if role=="TENANT_ADMIN" else 403),(
                        role,members.text)
                    dashboard=await client.get(
                        f"/api/v1/tenants/{first['tenant_id']}/dashboard",headers=headers)
                    assert dashboard.status_code == (403 if role=="MASTER" else 200),(
                        role,dashboard.text)
                    contexts=await client.get("/api/v1/auth/contexts",headers=headers)
                    assert contexts.status_code == 200,contexts.text
                    assert len(contexts.json()) == (1 if role=="MASTER" else 2)
                    logout=await client.post("/api/v1/auth/logout",headers=headers)
                    assert logout.status_code == 200,logout.text
                    assert (await client.get("/api/v1/auth/me",
                                             headers=headers)).status_code == 401
        finally:
            await close_db_pool()
            if tenants:
                db.execute("DELETE FROM public.audit_events WHERE tenant_id=ANY(%s::uuid[])",
                           (tenants,))
                db.execute("DELETE FROM public.tenants WHERE id=ANY(%s::uuid[])",
                           (tenants,))
            db.execute("DELETE FROM public.audit_events WHERE actor_id=%s",(master_id,))
            db.execute("DELETE FROM public.users WHERE id=ANY(%s::uuid[])",
                       ([master_id,*people],))
