"""M2500: persistência CI isolada (PostgreSQL 16 e 18), sem dinheiro ou provedor."""
import asyncio
import hashlib
import os
from uuid import uuid4

import asyncpg
import pytest

CI = os.getenv("FRCAIXINHA_CI_ISOLATED") == "1"
pytestmark = pytest.mark.skipif(not CI, reason="Teste exclusivo do banco CI descartável")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


async def context(conn, tenant, actor, role="TENANT_ADMIN"):
    await conn.execute("SELECT set_config('frcaixinha.ci_sandbox','1',true)")
    await conn.execute("SELECT set_config('app.current_tenant_id',$1,true)",str(tenant))
    await conn.execute("SELECT set_config('app.current_user_id',$1,true)",str(actor))
    await conn.execute("SELECT set_config('app.current_role',$1,true)",role)


async def setup_synthetic_tenants(admin):
    ids={k:uuid4() for k in ("tenant_a","tenant_b","admin_a","admin_b","member","membership_a","membership_b")}
    for actor in (ids["admin_a"],ids["admin_b"],ids["member"]):
        await admin.execute(
            "INSERT INTO public.users(id,email,full_name,cpf,phone) VALUES($1,$2,$3,$4,$5)",
            actor,f"{actor}@example.invalid","M2500 synthetic",
            str(actor.int % 10**14).zfill(14),str(actor.int % 10**11).zfill(11))
    for tenant,actor in ((ids["tenant_a"],ids["admin_a"]),(ids["tenant_b"],ids["admin_b"])):
        await admin.execute(
            "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id) VALUES($1,$2,$3,$4)",
            tenant,"CI M2500",str(tenant),actor)
    for tenant,actor,role,membership in (
        (ids["tenant_a"],ids["admin_a"],"TENANT_ADMIN",ids["membership_a"]),
        (ids["tenant_b"],ids["admin_b"],"TENANT_ADMIN",ids["membership_b"]),
    ):
        await admin.execute(
            "INSERT INTO public.memberships(id,tenant_id,user_id,role) VALUES($1,$2,$3,$4)",
            membership,tenant,actor,role)
    return ids


async def call(conn,query,*args):
    return await conn.fetchval(query,*args)


OPEN = ("SELECT public.mp_ci_open_oauth($1::uuid,$2::text,$3::text,$4::text,$5::int)")
CONSUME = ("SELECT public.mp_ci_consume_oauth($1::uuid,$2::text,$3::text)")
BIND = ("SELECT public.mp_ci_bind_seller($1::uuid,$2::varchar)")
REVOKE = ("SELECT public.mp_ci_revoke_seller($1::uuid,$2::varchar)")
INBOX = ("SELECT public.mp_ci_append_webhook($1::uuid,$2::varchar,$3::varchar,"
         "$4::varchar,$5::varchar,$6::varchar,$7::text)")
CHALLENGE = "A"*43


@pytest.mark.asyncio
async def test_m2500_durable_ci_only_oauth_sellers_inbox_and_rls():
    admin=await asyncpg.connect(os.environ["CI_ADMIN_DATABASE_URL"])
    app=await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        ids=await setup_synthetic_tenants(admin)
        a,b=ids["tenant_a"],ids["tenant_b"]
        ua,ub=ids["admin_a"],ids["admin_b"]
        assert await admin.fetchval("SELECT current_database()") == "frcaixinha_ci"

        # Quem atende a API não lê/insere diretamente, nem em OAuth nem no inbox.
        for table in ("mp_ci_oauth_attempts","mp_ci_seller_bindings","mp_ci_webhook_inbox"):
            for privilege in ("SELECT","INSERT","UPDATE","DELETE"):
                assert await app.fetchval(
                    "SELECT has_table_privilege(current_user,$1,$2)",
                    "public."+table,privilege) is False
        assert not await app.fetchval(
            "SELECT has_function_privilege(current_user,'public.mp_ci_guard_admin(uuid)','EXECUTE')")
        for role in ("frcaixinha_auth_role","frcaixinha_verifier_role"):
            assert not await admin.fetchval(
                "SELECT has_function_privilege($1,'public.mp_ci_open_oauth(uuid,text,text,text,integer)','EXECUTE')",role)
            assert not await admin.fetchval(
                "SELECT has_table_privilege($1,'public.mp_ci_webhook_inbox','SELECT')",role)

        async with app.transaction():
            await context(app,a,ua)
            state_hash=sha("ci-state-"+str(uuid4()))
            redirect_hash=sha("https://example.invalid/callback")
            event_id=await call(app,OPEN,a,state_hash,redirect_hash,CHALLENGE,600)
            assert event_id
            assert await call(app,CONSUME,a,state_hash,redirect_hash) is True
            assert await call(app,CONSUME,a,state_hash,redirect_hash) is False
            assert await call(app,CONSUME,a,state_hash,sha("wrong")) is False
            assert await call(app,BIND,a,"2002")==a
            assert await call(app,BIND,a,"2002")==a
            first=await call(app,INBOX,a,"2002","M2500NOTICE1","900001",
                             "M2500-REQUEST-1","payment.updated",sha("payload-1"))
            assert first
            assert await call(app,INBOX,a,"2002","M2500NOTICE1","900001",
                              "M2500-REQUEST-1","payment.updated",sha("payload-1"))==first
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,INBOX,a,"2002","M2500NOTICE1","900002",
                               "M2500-REQUEST-1","payment.updated",sha("payload-1"))
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,INBOX,a,"2002","M2500NOTICE2","900001",
                               "M2500-REQUEST-1","payment.updated",sha("payload-2"))
            assert await call(app,REVOKE,a,"2002") is True
            assert await call(app,REVOKE,a,"2002") is False
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,INBOX,a,"2002","M2500NOTICE3","900003",
                               "M2500-REQUEST-3","payment.updated",sha("payload-3"))
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,BIND,a,"2002")
            # Tenant B não pode usar o seller de A, nem mesmo após revogação.
            await context(app,b,ub)
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,BIND,b,"2002")
            assert await call(app,BIND,b,"3003")==b
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,INBOX,b,"3003","M2500NOTICE1","900001",
                               "M2500-REQUEST-1","payment.updated",sha("payload-1"))
            assert await call(app,INBOX,b,"3003","M2500NOTICE4","900004",
                              "M2500-REQUEST-4","payment.created",sha("payload-4"))
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,OPEN,a,sha("cross-tenant"),redirect_hash,CHALLENGE,600)
            await context(app,a,ua,role="MASTER")
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,OPEN,a,sha("master-no"),redirect_hash,CHALLENGE,600)
            await context(app,a,ids["member"],role="TENANT_MEMBER")
            with pytest.raises(asyncpg.PostgresError):
                async with app.transaction():
                    await call(app,BIND,a,"4004")

        info=await admin.fetchrow(
            "SELECT source,consumed_at IS NOT NULL AS consumed, state_sha256,"
            "pkce_challenge FROM public.mp_ci_oauth_attempts WHERE attempt_id=$1",event_id)
        assert info["source"]=="SYNTHETIC_OAUTH_DRAFT_ONLY"
        assert info["consumed"] is True
        assert info["state_sha256"]==state_hash
        assert info["pkce_challenge"]==CHALLENGE
        rows=await admin.fetch(
            "SELECT tenant_id,seller_id,source,provider_get_authenticated,"
            "bank_reconciled,ledger_written,paid,closing_authorized "
            "FROM public.mp_ci_webhook_inbox ORDER BY notification_id")
        assert len(rows)==2
        assert {x["tenant_id"] for x in rows}=={a,b}
        for row in rows:
            assert row["source"]=="SYNTHETIC_SIGNED_ENVELOPE_FIXTURE"
            for flag in ("provider_get_authenticated","bank_reconciled",
                         "ledger_written","paid","closing_authorized"):
                assert row[flag] is False
    finally:
        await app.close()
        await admin.close()


@pytest.mark.asyncio
async def test_m2500_oauth_atomic_consume_under_concurrency():
    admin=await asyncpg.connect(os.environ["CI_ADMIN_DATABASE_URL"])
    try:
        ids=await setup_synthetic_tenants(admin)
        a,actor=ids["tenant_a"],ids["admin_a"]
        state=sha("concurrent-"+str(uuid4()))
        redirect=sha("https://example.invalid/cb")
        async def worker(fn):
            connection=await asyncpg.connect(os.environ["DATABASE_URL"])
            try:
                async with connection.transaction():
                    await context(connection,a,actor)
                    return await fn(connection)
            finally:
                await connection.close()
        await worker(lambda conn:call(conn,OPEN,a,state,redirect,CHALLENGE,600))
        results=await asyncio.gather(*[
            worker(lambda conn:call(conn,CONSUME,a,state,redirect))
            for _ in range(2)])
        assert sorted(results)==[False,True]
    finally:
        await admin.close()
