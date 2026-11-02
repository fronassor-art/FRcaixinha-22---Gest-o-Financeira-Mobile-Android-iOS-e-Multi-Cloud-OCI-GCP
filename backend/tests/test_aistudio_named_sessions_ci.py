"""Acesso único nomeado e sessões: apenas PostgreSQL 16 efêmero de CI."""
import asyncio
import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest


def _ci_url(name: str) -> str:
    if os.getenv("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("Somente banco descartável de GitHub Actions")
    url = os.environ[name]
    parsed = urlparse(url)
    if (parsed.hostname not in ("localhost","127.0.0.1") or parsed.port != 5432
            or parsed.path != "/frcaixinha_ci"):
        raise RuntimeError("Conexão fora do banco isolado")
    return url


@pytest.mark.asyncio
async def test_named_contexts_session_listing_and_owner_only_revocation(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.config import settings
    from app.database import close_db_pool
    from app.security import hash_token

    admin = await asyncpg.connect(_ci_url("CI_ADMIN_DATABASE_URL"))
    auth = await asyncpg.connect(_ci_url("CI_AUTH_DATABASE_URL"))
    app_db = await asyncpg.connect(_ci_url("DATABASE_URL"))
    actor, outsider = uuid.uuid4(), uuid.uuid4()
    a,b,c = uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    tokens = ["ci-session-"+uuid.uuid4().hex for _ in range(3)]
    ids = [uuid.uuid4() for _ in range(3)]
    monkeypatch.setattr(settings, "DATABASE_URL", _ci_url("DATABASE_URL"))
    monkeypatch.setenv("AUTH_DATABASE_URL", _ci_url("CI_AUTH_DATABASE_URL"))
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH", "1")
    monkeypatch.setenv("ENVIRONMENT", "homologation")
    try:
        assert not await auth.fetchval(
            "SELECT has_table_privilege(current_user,'public.tenants','SELECT')")
        assert not await app_db.fetchval(
            "SELECT has_function_privilege(current_user,"
            "'public.auth_active_membership_contexts(text)','EXECUTE')")
        for user,name in ((actor,"Pessoa única"),(outsider,"Pessoa distinta")):
            await admin.execute(
                "INSERT INTO public.users(id,email,full_name,cpf,phone)"
                "VALUES($1,$2,$3,$4,'00000000000')",
                user,f"{user}@example.com",name,user.hex[:14],
            )
        for tenant,name in ((a,"Caixinha Pará"),(b,"Caixinha Maranhão"),(c,"Caixinha Privada")):
            await admin.execute(
                "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id)"
                "VALUES($1,$2,$3,$4)",tenant,name,str(uuid.uuid4()),outsider,
            )
        for tenant,user,role in (
            (a,actor,"TENANT_MEMBER"),(b,actor,"TENANT_ADMIN"),
            (b,outsider,"TENANT_MEMBER"),(c,outsider,"TENANT_ADMIN"),
        ):
            await admin.execute(
                "INSERT INTO public.memberships(tenant_id,user_id,role)"
                "VALUES($1,$2,$3)",tenant,user,role,
            )
        for sid,raw,user,role,tenant in (
            (ids[0],tokens[0],actor,"TENANT_MEMBER",a),
            (ids[1],tokens[1],actor,"TENANT_ADMIN",b),
            (ids[2],tokens[2],outsider,"TENANT_ADMIN",c),
        ):
            await admin.execute(
                "INSERT INTO public.sessions(id,token_hash,user_id,active_role,"
                "active_tenant_id,expires_at) VALUES($1,$2,$3,$4,$5,"
                "now()+interval '20 minutes')",
                sid,hash_token(raw),user,role,tenant,
            )
        # Emissão de sessão ATIVA pelo papel Auth deve ser recusada por RLS.
        # Não há autenticação nem concessão implícita apenas pela posse do DSN.
        with pytest.raises(asyncpg.PostgresError) as invalid_active:
            await auth.execute(
                "INSERT INTO public.sessions(id,token_hash,user_id,active_role,"
                "active_tenant_id,expires_at) VALUES($1,$2,$3,'TENANT_MEMBER',$4,"
                "now()+interval '20 minutes')",
                uuid.uuid4(), hash_token("ci-forged-" + uuid.uuid4().hex), actor, a)
        assert invalid_active.value.sqlstate == "42501"

        with pytest.raises(asyncpg.PostgresError) as invalid_pending:
            await auth.execute(
                "INSERT INTO public.sessions(id,token_hash,user_id,active_role,"
                "active_tenant_id,expires_at) VALUES($1,$2,$3,'PENDING_CONTEXT',NULL,"
                "now()+interval '3 minutes')",
                uuid.uuid4(), hash_token("ci-bad-pending-" + uuid.uuid4().hex), actor)
        assert invalid_pending.value.sqlstate == "42501"

        # Serviço Auth não enumera outros usuários usando UUID arbitrário
        # nem usando hash armazenado como se fosse o token bruto.
        assert await auth.fetch(
            "SELECT * FROM public.auth_active_membership_contexts($1::text)",
            str(outsider),
        ) == []
        assert await auth.fetch(
            "SELECT * FROM public.auth_active_membership_contexts($1::text)",
            hash_token(tokens[2]),
        ) == []
        assert await auth.fetch(
            "SELECT * FROM public.auth_active_membership_contexts($1::text)",
            "ci-invalid-" + uuid.uuid4().hex,
        ) == []
        # Também protege o lookup utilizado pelo login e switch-context.
        assert not await auth.fetch(
            "SELECT * FROM public.auth_active_memberships($1::text)",
            str(outsider),
        )
        assert not await auth.fetch(
            "SELECT * FROM public.auth_active_memberships($1::text)",
            hash_token(tokens[2]),
        )
        assert {(x["tenant_id"], x["role"]) for x in await auth.fetch(
            "SELECT * FROM public.auth_active_memberships($1::text)",
            tokens[0],
        )} == {(a, "TENANT_MEMBER"), (b, "TENANT_ADMIN")}
        pending_token = "ci-pending-" + uuid.uuid4().hex
        pending_id = uuid.uuid4()
        await admin.execute(
            "INSERT INTO public.sessions(id,token_hash,user_id,active_role,"
            "active_tenant_id,expires_at) VALUES($1,$2,$3,'PENDING_CONTEXT',NULL,"
            "now()+interval '90 seconds')",
            pending_id,hash_token(pending_token),actor,
        )
        assert {(x["tenant_id"], x["role"]) for x in await auth.fetch(
            "SELECT * FROM public.auth_active_memberships($1::text)",
            pending_token,
        )} == {(a, "TENANT_MEMBER"), (b, "TENANT_ADMIN")}
        actor_rows = await auth.fetch(
            "SELECT * FROM public.auth_active_membership_contexts($1::text)",
            tokens[0],
        )
        assert {(x["role"], x["tenant_id"], x["tenant_name"]) for x in actor_rows} == {
            ("TENANT_MEMBER", a, "Caixinha Pará"),
            ("TENANT_ADMIN", b, "Caixinha Maranhão"),
        }
        outsider_rows = await auth.fetch(
            "SELECT * FROM public.auth_active_membership_contexts($1::text)",
            tokens[2],
        )
        assert {(x["role"], x["tenant_id"]) for x in outsider_rows} == {
            ("TENANT_MEMBER", b), ("TENANT_ADMIN", c),
        }
        headers = {"Authorization":"Bearer "+tokens[0]}
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://ci") as client:
            assert (await client.get(
                "/api/v1/auth/me",
                headers={"Authorization":"Bearer "+pending_token},
            )).status_code == 401, "Token provisório nunca autoriza endpoints"
            await admin.execute(
                "UPDATE public.sessions SET expires_at=now()-interval '1 second' "
                "WHERE id=$1", pending_id)
            assert not await auth.fetch(
                "SELECT * FROM public.auth_active_memberships($1::text)",
                pending_token,
            )
            contexts = await client.get("/api/v1/auth/contexts",headers=headers)
            assert contexts.status_code == 200,contexts.text
            assert {
                (row["role"],row["tenant_id"],row["tenant_name"])
                for row in contexts.json()
            } == {
                ("TENANT_MEMBER",str(a),"Caixinha Pará"),
                ("TENANT_ADMIN",str(b),"Caixinha Maranhão"),
            }
            assert "Caixinha Privada" not in contexts.text
            # O timeout de inatividade desliza, mas nunca passa do teto
            # absoluto de 8 horas desde a criação da sessão.
            await admin.execute(
                "UPDATE public.sessions SET created_at=NOW()-INTERVAL '7 hours 58 minutes',"
                "expires_at=NOW()+INTERVAL '1 minute' WHERE id=$1",
                ids[0],
            )
            assert (await client.get(
                "/api/v1/auth/me", headers=headers)).status_code == 200
            limits = await admin.fetchrow(
                "SELECT created_at,expires_at FROM public.sessions WHERE id=$1",
                ids[0],
            )
            assert limits["expires_at"] <= (
                limits["created_at"] + __import__("datetime").timedelta(hours=8)
            ), "Refresh prolongou a sessão além do teto absoluto"
            assert limits["expires_at"] > limits["created_at"]

            assert not await auth.fetchval(
                "SELECT has_table_privilege(current_user,'public.tenants','SELECT')")

            all_sessions = await client.get("/api/v1/auth/sessions",headers=headers)
            assert all_sessions.status_code == 200,all_sessions.text
            body=all_sessions.json()
            assert body["source"] == "POSTGRESQL_AUTH"
            assert {s["id"] for s in body["sessions"]} == {str(ids[0]),str(ids[1])}
            assert sum(s["current"] for s in body["sessions"]) == 1
            assert "token_hash" not in all_sessions.text
            assert "ip_address" not in all_sessions.text

            foreign = await client.post(
                f"/api/v1/auth/sessions/{ids[2]}/revoke",headers=headers)
            assert foreign.status_code == 404
            assert await auth.fetchval(
                "SELECT revoked_at IS NULL FROM public.sessions WHERE id=$1",ids[2])

            other = await client.post(
                f"/api/v1/auth/sessions/{ids[1]}/revoke",headers=headers)
            assert other.status_code == 200 and not other.json()["current_revoked"]
            assert await auth.fetch(
                "SELECT * FROM public.auth_active_membership_contexts($1::text)",
                tokens[1],
            ) == []
            assert (await client.get("/api/v1/auth/me",
                headers={"Authorization":"Bearer "+tokens[1]})).status_code==401
            assert (await client.get("/api/v1/auth/me",headers=headers)).status_code==200

            current=await client.post(
                f"/api/v1/auth/sessions/{ids[0]}/revoke",headers=headers)
            assert current.status_code==200 and current.json()["current_revoked"]
            assert (await client.get("/api/v1/auth/me",headers=headers)).status_code==401
            assert (await client.get("/api/v1/auth/sessions",headers=headers)).status_code==401

            # Concorrência: a validação deve aguardar o row lock do logout
            # e jamais reativar a sessão revogada após o COMMIT.
            outsider_headers = {"Authorization": "Bearer " + tokens[2]}
            async with admin.transaction():
                assert await admin.fetchval(
                    "SELECT id FROM public.sessions WHERE id=$1 FOR UPDATE",
                    ids[2],
                ) == ids[2]
                pending_me = asyncio.create_task(
                    client.get("/api/v1/auth/me", headers=outsider_headers))
                await asyncio.sleep(0.10)
                assert not pending_me.done(), "Consulta ignorou o bloqueio da sessao"
                await admin.execute(
                    "UPDATE public.sessions SET revoked_at=NOW() WHERE id=$1",
                    ids[2],
                )
            assert (await asyncio.wait_for(pending_me, timeout=5)).status_code == 401
            assert await auth.fetch(
                "SELECT * FROM public.auth_active_memberships($1::text)",
                tokens[2],
            ) == []

    finally:
        await close_db_pool()
        await auth.close()
        await app_db.close()
        await admin.execute(
            "DELETE FROM public.tenants WHERE id=ANY($1::uuid[])",[a,b,c])
        await admin.execute(
            "DELETE FROM public.users WHERE id=ANY($1::uuid[])",[actor,outsider])
        await admin.close()
