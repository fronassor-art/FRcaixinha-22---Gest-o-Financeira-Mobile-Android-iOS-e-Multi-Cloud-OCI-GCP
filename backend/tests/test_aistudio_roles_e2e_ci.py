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
    emails = [f"{role}-{tag}@example.com" for role in ("master","admin","member")]
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

            def onboard(name,admin,member,master_password=passwords[0],
                        owner_box=False):
                return onboard_tenant_with_roles(
                    db,master_email=emails[0],master_password=master_password,
                    tenant_name=name,contracting_party_id=str(uuid4()),
                    admin=admin,member=member,owner_box=owner_box)
            first=onboard("Caixinha Principal CI",
                          new(emails[1],"99988877765",passwords[1]),
                          new(emails[2],"99988877764",passwords[2]))
            people.extend([first["admin_id"],first["member_id"]])
            tenants.append(first["tenant_id"])
            assert len(set(people)) == 2
            assert db.execute("SELECT count(*) FROM public.memberships WHERE tenant_id=%s",
                              (first["tenant_id"],)).fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s "
                              "AND action IN ('AI_STUDIO_LOCAL_ROLE_ENROLLED','AI_STUDIO_LOCAL_TENANT_CREATED')",
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
            # O mesmo usuario Master recebe os DOIS vinculos para a mesma
            # caixinha, sem gerar novo usuario, CPF, credencial ou e-mail.
            owner = onboard(
                "Caixinha Inaugural CI",
                existing(emails[0], passwords[0]),
                existing(emails[0], passwords[0]),
                owner_box=True,
            )
            tenants.append(owner["tenant_id"])
            assert owner["is_owner_box"] is True
            assert owner["admin_id"] == owner["member_id"] == master_id
            assert db.execute(
                "SELECT count(*) FROM public.users WHERE lower(email)=%s",
                (emails[0],),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM public.credentials WHERE user_id=%s",
                (master_id,),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT is_owner_box,admin_user_id FROM public.tenants WHERE id=%s",
                (owner["tenant_id"],),
            ).fetchone() == (True, master_id)
            assert db.execute(
                "SELECT count(*) FROM public.memberships "
                "WHERE tenant_id=%s AND user_id=%s AND status='ATIVA'",
                (owner["tenant_id"],master_id),
            ).fetchone()[0] == 2
            assert set(
                r[0] for r in db.execute(
                    "SELECT role FROM public.memberships WHERE tenant_id=%s "
                    "AND user_id=%s",
                    (owner["tenant_id"],master_id),
                ).fetchall()
            ) == {"TENANT_ADMIN","TENANT_MEMBER"}
            assert db.execute(
                "SELECT count(*) FROM public.tenants WHERE is_owner_box=TRUE"
            ).fetchone()[0] == 1
            before = db.execute(
                "SELECT count(*) FROM public.tenants"
            ).fetchone()[0]
            with pytest.raises(OnboardingDenied,match="ja existente"):
                onboard(
                    "Outra inaugural nao autorizada",
                    existing(emails[0],passwords[0]),
                    existing(emails[0],passwords[0]),
                    owner_box=True,
                )
            with pytest.raises(OnboardingDenied,match="exige o Master"):
                onboard(
                    "Falsa inaugural",
                    existing(emails[1],passwords[1]),
                    existing(emails[2],passwords[2]),
                    owner_box=True,
                )
            assert db.execute(
                "SELECT count(*) FROM public.tenants"
            ).fetchone()[0] == before

            async with AsyncClient(
                transport=ASGITransport(app=app),base_url="http://ci"
            ) as client:
                assert (await client.get("/api/v1/auth/me")).status_code == 401

                # Tres identidades distintas: cada login fixa o papel requerido.
                for email,password,role in zip(
                    emails,passwords,("MASTER","TENANT_ADMIN","TENANT_MEMBER")
                ):
                    login = await client.post("/api/v1/auth/login", json={
                        "usernameOrEmail":email,
                        "password":password,
                        "requestedRole":role,
                    })
                    assert login.status_code == 200,(role,login.text)
                    body = login.json()
                    assert body["user"]["role"] == role
                    headers={"Authorization":"Bearer "+body["token"]}
                    selected_tenant=body["user"]["tenant_id"]
                    if role!="MASTER":
                        assert selected_tenant is not None
                    else:
                        assert selected_tenant is None
                    current=await client.get("/api/v1/auth/me",headers=headers)
                    assert current.status_code==200
                    assert current.json()["role"]==role
                    listed=await client.get("/api/v1/auth/contexts",headers=headers)
                    assert listed.status_code==200
                    assert len(listed.json())==1
                    assert listed.json()[0]["role"]==role
                    assert listed.json()[0]["tenant_id"]==selected_tenant

                    platform=await client.get("/api/v1/master/overview",headers=headers)
                    assert platform.status_code == (200 if role=="MASTER" else 403)
                    if selected_tenant:
                        own_members=await client.get(
                            f"/api/v1/tenants/{selected_tenant}/members",headers=headers)
                        assert own_members.status_code==(200 if role=="TENANT_ADMIN" else 403)
                        overview=await client.get(
                            f"/api/v1/tenants/{selected_tenant}/dashboard",headers=headers)
                        assert overview.status_code==200
                        if role=="TENANT_MEMBER":
                            assert "member_count_visible" not in overview.json()
                            closing=await client.get(
                                f"/api/v1/tenants/{selected_tenant}/closings/{uuid4()}",
                                headers=headers)
                            assert closing.status_code==403
                    # Ate escolher o mesmo papel por switch-context e proibido:
                    # novo acesso exige logout e senha novamente.
                    forbidden=await client.post(
                        "/api/v1/auth/switch-context",headers=headers,
                        json={"target_role":"MASTER","target_tenant_id":None})
                    assert forbidden.status_code==403,(role,forbidden.text)
                    still=await client.get("/api/v1/auth/me",headers=headers)
                    assert still.json()["role"]==role
                    assert (await client.post(
                        "/api/v1/auth/logout",headers=headers)).status_code==200
                    assert (await client.get(
                        "/api/v1/auth/me",headers=headers)).status_code==401

                # A mesma identidade Master possui os 3 vinculos ja existentes.
                # Cada papel requer NOVO login com senha, nunca troca de sessao.
                for role in ("MASTER","TENANT_ADMIN","TENANT_MEMBER"):
                    login=await client.post("/api/v1/auth/login",json={
                        "usernameOrEmail":emails[0],
                        "password":passwords[0],
                        "requestedRole":role})
                    assert login.status_code==200,(role,login.text)
                    body=login.json()
                    assert body["user"]["id"]==str(master_id)
                    assert body["user"]["role"]==role
                    assert body["user"]["tenant_id"]==(
                        None if role=="MASTER" else str(owner["tenant_id"]))
                    headers={"Authorization":"Bearer "+body["token"]}
                    listed=await client.get("/api/v1/auth/contexts",headers=headers)
                    assert listed.status_code==200
                    assert {(item["role"],item["tenant_id"]) for item in
                            listed.json()}=={(role,body["user"]["tenant_id"])}
                    platform=await client.get("/api/v1/master/overview",headers=headers)
                    assert platform.status_code==(200 if role=="MASTER" else 403)
                    members=await client.get(
                        f"/api/v1/tenants/{owner['tenant_id']}/members",
                        headers=headers)
                    assert members.status_code==(200 if role=="TENANT_ADMIN" else 403)
                    dashboard=await client.get(
                        f"/api/v1/tenants/{owner['tenant_id']}/dashboard",
                        headers=headers)
                    assert dashboard.status_code==(403 if role=="MASTER" else 200)
                    target_role=("MASTER" if role!="MASTER" else "TENANT_MEMBER")
                    target_id=(None if target_role=="MASTER"
                               else str(owner["tenant_id"]))
                    switch=await client.post(
                        "/api/v1/auth/switch-context",headers=headers,
                        json={"target_role":target_role,
                              "target_tenant_id":target_id})
                    assert switch.status_code==403,(role,switch.text)
                    me=await client.get("/api/v1/auth/me",headers=headers)
                    assert me.status_code==200 and me.json()["role"]==role
                    assert (await client.post(
                        "/api/v1/auth/logout",headers=headers)).status_code==200
                    assert (await client.get(
                        "/api/v1/auth/me",headers=headers)).status_code==401

                # Um usuario Admin nao pode autenticar como Master, mesmo
                # escolhendo o botao Master do cliente.
                denied=await client.post("/api/v1/auth/login",json={
                    "usernameOrEmail":emails[1],
                    "password":passwords[1],
                    "requestedRole":"MASTER",
                })
                assert denied.status_code==401
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
