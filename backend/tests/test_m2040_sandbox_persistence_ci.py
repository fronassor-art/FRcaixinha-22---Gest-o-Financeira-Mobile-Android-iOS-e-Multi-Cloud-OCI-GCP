"""M1881–M2040: RLS, idempotência e paginação em banco descartável CI.

Sem contas reais, sem Pix, sem mutação de cotas, empréstimos ou ledger.
"""
import os
from uuid import UUID, uuid4

import asyncpg
import pytest

from app.dependencies import AuthenticatedSession
from app.routers.sandbox_evidence_ci import (
    read_admin_sandbox_evidence, read_my_sandbox_evidence,
)

CI = os.getenv("FRCAIXINHA_CI_ISOLATED") == "1"
FN = ("SELECT public.append_mp_sandbox_evidence_ci("
      "$1::uuid,$2::uuid,$3::varchar,$4::uuid,$5::varchar,"
      "$6::varchar,$7::varchar,$8::bigint,$9::varchar)")
pytestmark = pytest.mark.skipif(not CI, reason="Banco descartável CI obrigatório")


async def context(conn, tenant, user, role="TENANT_ADMIN"):
    await conn.execute("SELECT set_config('frcaixinha.ci_sandbox','1',true)")
    await conn.execute(
        "SELECT set_config('app.current_tenant_id',$1,true)",
        str(tenant) if tenant is not None else "")
    await conn.execute(
        "SELECT set_config('app.current_user_id',$1,true)", str(user))
    await conn.execute("SELECT set_config('app.current_role',$1,true)", role)


def session(tenant, user, role):
    return AuthenticatedSession(
        str(user), role, str(tenant) if tenant else None,
        "synthetic@example.invalid", "Test Actor", role == "MASTER")


async def insert_fixture(conn, tenant, membership, payment, kind, amount,
                         *, key=None, collector="2002", ref=None, evidence=None):
    return await conn.fetchval(
        FN, tenant, membership, kind, key or uuid4(),
        collector, payment, ref or f"tenant:{tenant}:contribution-1",
        amount, evidence or "CI-SYNTHETIC-DOCUMENT-2027")


@pytest.mark.asyncio
async def test_m2040_pg_ci_only_persistence_rls_idempotency_and_api():
    admin_dsn = os.environ["CI_ADMIN_DATABASE_URL"]
    app_dsn = os.environ["DATABASE_URL"]
    admin = await asyncpg.connect(admin_dsn)
    ids = {name: uuid4() for name in (
        "tenant_a", "tenant_b", "admin_a", "admin_b",
        "member_a", "member_a2", "member_b", "master",
        "membership_admin_a", "membership_admin_b",
        "membership_a", "membership_a2", "membership_b",
    )}
    a,b = ids["tenant_a"],ids["tenant_b"]
    try:
        for k in ("admin_a","admin_b","member_a","member_a2","member_b"):
            u=ids[k]
            await admin.execute(
                "INSERT INTO public.users(id,email,full_name,cpf,phone) "
                "VALUES($1,$2,$3,$4,$5)",
                u,f"{u}@example.invalid",f"CI {k}",str(u.int % 10**14).zfill(14),
                str(u.int % 10**11).zfill(11))
        for tenant,owner in ((a,ids["admin_a"]),(b,ids["admin_b"])):
            await admin.execute(
                "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id) "
                "VALUES($1,$2,$3,$4)",tenant,"CI M2040",str(tenant),owner)
        for tenant,user,role,mid in (
            (a,ids["admin_a"],"TENANT_ADMIN",ids["membership_admin_a"]),
            (b,ids["admin_b"],"TENANT_ADMIN",ids["membership_admin_b"]),
            (a,ids["member_a"],"TENANT_MEMBER",ids["membership_a"]),
            (a,ids["member_a2"],"TENANT_MEMBER",ids["membership_a2"]),
            (b,ids["member_b"],"TENANT_MEMBER",ids["membership_b"]),
        ):
            await admin.execute(
                "INSERT INTO public.memberships(id,tenant_id,user_id,role) "
                "VALUES($1,$2,$3,$4)",mid,tenant,user,role)

        app = await asyncpg.connect(app_dsn)
        try:
            # Roles não possuem DML direto; writes passam pela função validada.
            assert await app.fetchval(
                "SELECT has_table_privilege(current_user,"
                "'public.mp_sandbox_evidence_events','SELECT')")
            for privilege in ("INSERT","UPDATE","DELETE"):
                assert not await app.fetchval(
                    "SELECT has_table_privilege(current_user,"
                    "'public.mp_sandbox_evidence_events',$1)",privilege)
            async with app.transaction():
                await context(app,a,ids["admin_a"])
                key=uuid4()
                first=await insert_fixture(
                    app,a,ids["membership_a"],"98123451","APPROVED_FIXTURE",
                    15000,key=key)
                same=await insert_fixture(
                    app,a,ids["membership_a"],"98123451","APPROVED_FIXTURE",
                    15000,key=key)
                assert first==same
                with pytest.raises(asyncpg.PostgresError):
                    async with app.transaction():
                        await insert_fixture(
                            app,a,ids["membership_a"],"98123451",
                            "APPROVED_FIXTURE",14999,key=key)
                with pytest.raises(asyncpg.PostgresError):
                    async with app.transaction():
                        await insert_fixture(
                            app,a,ids["membership_a"],"98123451",
                            "APPROVED_FIXTURE",15000)
                refund=await insert_fixture(
                    app,a,ids["membership_a"],"98123451","REFUND_FIXTURE",1000)
                assert refund!=first
                with pytest.raises(asyncpg.PostgresError):
                    async with app.transaction():
                        await insert_fixture(
                            app,a,ids["membership_a"],"98123451",
                            "REFUND_FIXTURE",14001)
                await insert_fixture(app,a,ids["membership_a"],"98123451",
                                     "DISPUTE_FIXTURE",0)
                await insert_fixture(app,a,ids["membership_a2"],"98123452",
                                     "APPROVED_FIXTURE",15000)
                # RBAC: admin do outro tenant não pode inventar eventos de A.
                await context(app,b,ids["admin_b"])
                with pytest.raises(asyncpg.PostgresError):
                    async with app.transaction():
                        await insert_fixture(
                            app,a,ids["membership_a"],"98123453",
                            "APPROVED_FIXTURE",15000)
                await insert_fixture(
                    app,b,ids["membership_b"],"98123454",
                    "APPROVED_FIXTURE",15000,collector="3003",
                    ref=f"tenant:{b}:contribution-1")
                # SELECT estritamente RLS por tenant e papel.
                await context(app,a,ids["admin_a"])
                assert await app.fetchval(
                    "SELECT count(*) FROM public.mp_sandbox_evidence_events")==4
                await context(app,a,ids["member_a"],"TENANT_MEMBER")
                assert await app.fetchval(
                    "SELECT count(*) FROM public.mp_sandbox_evidence_events")==3
                with pytest.raises(asyncpg.PostgresError):
                    async with app.transaction():
                        await insert_fixture(app,a,ids["membership_a"],
                                             "98123455","APPROVED_FIXTURE",100)
                page=await read_my_sandbox_evidence(
                    a,2,None,session(a,ids["member_a"],"TENANT_MEMBER"),app)
                assert page.has_more is True and len(page.events)==2
                assert page.bank_reconciled is False
                assert page.real_payments_enabled is False
                assert page.events[0].source=="SYNTHETIC_FIXTURE_ONLY"
                after=await read_my_sandbox_evidence(
                    a,2,page.next_before_seq,
                    session(a,ids["member_a"],"TENANT_MEMBER"),app)
                assert len(after.events)==1 and not after.has_more
                assert {x.event_id for x in page.events}.isdisjoint(
                    x.event_id for x in after.events)
                await context(app,a,ids["admin_a"])
                admin_page=await read_admin_sandbox_evidence(
                    a,ids["membership_a2"],25,None,
                    session(a,ids["admin_a"],"TENANT_ADMIN"),app)
                assert len(admin_page.events)==1
                await context(app,None,ids["master"],"MASTER")
                assert await app.fetchval(
                    "SELECT count(*) FROM public.mp_sandbox_evidence_events")==0
                await context(app,b,ids["admin_b"])
                assert await app.fetchval(
                    "SELECT count(*) FROM public.mp_sandbox_evidence_events")==1
                # Leitura de membro A sob tenant B não revela nada.
                assert await app.fetchval(
                    "SELECT count(*) FROM public.mp_sandbox_evidence_events "
                    "WHERE tenant_id=$1",a)==0
        finally:
            await app.close()
    finally:
        await admin.close()


def test_m2040_schema_contract_disabled_on_local_project():
    from pathlib import Path
    migration = Path("backend/ci_migrations/031_mp_sandbox_evidence_ci_only.sql").read_text()
    assert "current_database() <> 'frcaixinha_ci'" in migration
    assert "frcaixinha.ci_sandbox" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL ON TABLE" in migration
    assert "financial_effect_applied=false" in migration
    assert "bank_reconciled=false" in migration
    assert "settlement_authorized=false" in migration
    assert "SECURITY DEFINER" in migration
