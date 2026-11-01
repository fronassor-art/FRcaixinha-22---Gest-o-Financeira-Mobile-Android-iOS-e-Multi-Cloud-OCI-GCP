"""RLS integration checks with actual synthetic rows in the disposable CI database."""

import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("FRCAIXINHA_CI_ISOLATED") != "1",
    reason="Requer o banco descartável isolado do CI",
)


def _ci_dsn(name: str) -> str:
    dsn = os.environ[name]
    parsed = urlparse(dsn)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.path != "/frcaixinha_ci":
        raise RuntimeError("Os testes só podem ser executados no banco local descartável frcaixinha_ci")
    return dsn


@pytest.fixture
async def isolated_rows():
    admin = await asyncpg.connect(_ci_dsn("CI_ADMIN_DATABASE_URL"))
    app = await asyncpg.connect(_ci_dsn("DATABASE_URL"))
    ids = {key: uuid.uuid4() for key in (
        "admin_a", "admin_b", "member_a", "member_a2", "member_b", "master",
        "tenant_a", "tenant_b", "membership_a", "membership_a2", "membership_b",
        "membership_admin_a", "membership_admin_b", "membership_master",
        "quota_a", "quota_a2", "quota_b",
    )}
    try:
        role = await app.fetchrow(
            "SELECT r.rolsuper, r.rolbypassrls, r.rolname, c.relowner = r.oid AS is_owner "
            "FROM pg_roles r CROSS JOIN pg_class c "
            "WHERE r.rolname = current_user AND c.oid = 'public.quotas'::regclass"
        )
        assert role and not role["rolsuper"] and not role["rolbypassrls"] and not role["is_owner"]
        users = ["admin_a", "admin_b", "member_a", "member_a2", "member_b", "master"]
        for name in users:
            uid = ids[name]
            await admin.execute(
                "INSERT INTO users (id,email,full_name,cpf,phone,is_master) VALUES ($1,$2,$3,$4,$5,$6)",
                uid, f"{uid}@example.com", f"Teste {name}", uid.hex[:14], "00000000000", name == "master",
            )
        for suffix in ("a", "b"):
            await admin.execute(
                "INSERT INTO tenants (id,display_name,contracting_party_id,admin_user_id) VALUES ($1,$2,$3,$4)",
                ids[f"tenant_{suffix}"], f"Tenant teste {suffix}", str(uuid.uuid4()), ids[f"admin_{suffix}"],
            )
        membership_rows = [
            ("membership_admin_a", "tenant_a", "admin_a", "TENANT_ADMIN"),
            ("membership_admin_b", "tenant_b", "admin_b", "TENANT_ADMIN"),
            ("membership_a", "tenant_a", "member_a", "TENANT_MEMBER"),
            ("membership_a2", "tenant_a", "member_a2", "TENANT_MEMBER"),
            ("membership_b", "tenant_b", "member_b", "TENANT_MEMBER"),
            ("membership_master", "tenant_a", "master", "TENANT_MEMBER"),
        ]
        for membership, tenant, user, role_name in membership_rows:
            await admin.execute(
                "INSERT INTO memberships (id,tenant_id,user_id,role) VALUES ($1,$2,$3,$4)",
                ids[membership], ids[tenant], ids[user], role_name,
            )
        for quota, tenant, membership, number in [
            ("quota_a", "tenant_a", "membership_a", 1),
            ("quota_a2", "tenant_a", "membership_a2", 2),
            ("quota_b", "tenant_b", "membership_b", 1),
        ]:
            await admin.execute(
                "INSERT INTO quotas (id,tenant_id,membership_id,quota_number,value_brl) VALUES ($1,$2,$3,$4,100)",
                ids[quota], ids[tenant], ids[membership], number,
            )
        yield app, ids
    finally:
        await app.close()
        await admin.execute("DELETE FROM tenants WHERE id = ANY($1::uuid[])", [ids["tenant_a"], ids["tenant_b"]])
        await admin.execute("DELETE FROM users WHERE id = ANY($1::uuid[])", [ids[name] for name in (
            "admin_a", "admin_b", "member_a", "member_a2", "member_b", "master",
        )])
        await admin.close()


async def _visible_quotas(conn, user_id, tenant_id, role):
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.current_user_id', $1, true)", str(user_id))
        await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", str(tenant_id))
        await conn.execute("SELECT set_config('app.current_role', $1, true)", role)
        rows = await conn.fetch("SELECT id FROM quotas ORDER BY id")
        return {row["id"] for row in rows}


async def test_tenant_admin_sees_only_authorized_tenant(isolated_rows):
    conn, ids = isolated_rows
    assert await _visible_quotas(conn, ids["admin_a"], ids["tenant_a"], "TENANT_ADMIN") == {
        ids["quota_a"], ids["quota_a2"],
    }
    assert await _visible_quotas(conn, ids["admin_a"], ids["tenant_b"], "TENANT_ADMIN") == set()


async def test_member_sees_only_own_quota_in_same_tenant(isolated_rows):
    conn, ids = isolated_rows
    assert await _visible_quotas(conn, ids["member_a"], ids["tenant_a"], "TENANT_MEMBER") == {ids["quota_a"]}


async def test_master_context_cannot_read_member_quotas(isolated_rows):
    conn, ids = isolated_rows
    assert await _visible_quotas(conn, ids["master"], ids["tenant_a"], "MASTER") == set()
    assert await _visible_quotas(conn, ids["master"], ids["tenant_a"], "TENANT_MEMBER") == set()


async def test_application_role_cannot_access_password_hashes_or_rewrite_audit(isolated_rows):
    conn, _ = isolated_rows
    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        assert not await conn.fetchval("SELECT has_table_privilege(current_user, 'public.credentials', $1)", privilege)
    for privilege in ("UPDATE", "DELETE"):
        assert not await conn.fetchval("SELECT has_table_privilege(current_user, 'public.audit_events', $1)", privilege)


async def test_contributions_restricted_by_user_and_tenant(isolated_rows):
    from datetime import date
    conn, ids = isolated_rows
    admin = await asyncpg.connect(_ci_dsn("CI_ADMIN_DATABASE_URL"))
    cycle, first, second = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        await admin.execute("INSERT INTO cycles(id,tenant_id,year,start_date,end_date,settlement_date) VALUES($1,$2,2027,$3,$4,$5)", cycle, ids['tenant_a'], date(2027,1,1), date(2027,12,31), date(2028,1,10))
        for item, membership in ((first, ids['membership_a']), (second, ids['membership_a2'])):
            await admin.execute("INSERT INTO contributions(id,tenant_id,cycle_id,membership_id,competence,due_date,amount_due) VALUES($1,$2,$3,$4,'2027-01',$5,100)", item, ids['tenant_a'], cycle, membership, date(2027,1,10))
        async def visible(user, tenant, role):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(user))
                await conn.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(tenant))
                await conn.execute("SELECT set_config('app.current_role',$1,true)", role)
                return {row['id'] for row in await conn.fetch('SELECT id FROM contributions')}
        assert await visible(ids['admin_a'], ids['tenant_a'], 'TENANT_ADMIN') == {first, second}
        assert await visible(ids['member_a'], ids['tenant_a'], 'TENANT_MEMBER') == {first}
        assert await visible(ids['member_b'], ids['tenant_a'], 'TENANT_MEMBER') == set()
        assert await visible(ids['master'], ids['tenant_a'], 'TENANT_MEMBER') == set()
        assert not await conn.fetchval("SELECT has_table_privilege(current_user,'public.contributions','UPDATE')")
    finally:
        await admin.close()


async def test_experimental_login_real_database_roles_and_logout(isolated_rows, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from datetime import date
    from app.main import app
    from app.config import settings
    from app.database import close_db_pool
    from app.security import hash_password_secure
    conn, ids = isolated_rows
    monkeypatch.setattr(settings, "DATABASE_URL", _ci_dsn("DATABASE_URL"))
    monkeypatch.setenv("AUTH_DATABASE_URL", _ci_dsn("CI_AUTH_DATABASE_URL"))
    monkeypatch.setenv("FRCAIXINHA_TEST_AUTH", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    admin = await asyncpg.connect(_ci_dsn("CI_ADMIN_DATABASE_URL"))
    try:
        password = "senha-sintetica-apenas-para-ci"
        hashed = hash_password_secure(password)
        for name in ("master", "admin_a", "member_a"):
            await admin.execute("INSERT INTO credentials(user_id,password_hash) VALUES($1,$2)", ids[name], hashed)
        cycle = uuid.uuid4()
        await admin.execute("INSERT INTO cycles(id,tenant_id,year,start_date,end_date,settlement_date) VALUES($1,$2,2027,$3,$4,$5)", cycle, ids['tenant_a'], date(2027,1,1), date(2027,12,31), date(2028,1,10))
        for membership in (ids['membership_a'], ids['membership_a2']):
            await admin.execute("INSERT INTO contributions(id,tenant_id,cycle_id,membership_id,competence,due_date,amount_due) VALUES($1,$2,$3,$4,'2027-01',$5,100)", uuid.uuid4(), ids['tenant_a'], cycle, membership, date(2027,1,10))
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for name, role in (("master", "MASTER"), ("admin_a", "TENANT_ADMIN"), ("member_a", "TENANT_MEMBER")):
                email = f"{ids[name]}@example.com"
                bad = await client.post('/api/v1/auth/login', json={'usernameOrEmail': email, 'password': 'senha-incorreta'})
                assert bad.status_code == 401
                response = await client.post('/api/v1/auth/login', json={'usernameOrEmail': email, 'password': password})
                assert response.status_code == 200, response.text
                body = response.json()
                assert body['user']['role'] == role
                token = body['token']
                assert token and token != password
                headers = {'Authorization': f'Bearer {token}'}
                me = await client.get('/api/v1/auth/me', headers=headers)
                assert me.status_code == 200 and me.json()['role'] == role
                contributions = await client.get(f"/api/v1/tenants/{ids['tenant_a']}/contributions", headers=headers)
                if role == 'MASTER':
                    assert contributions.status_code == 403
                else:
                    assert contributions.status_code == 200, contributions.text
                    assert len(contributions.json()) == (2 if role == 'TENANT_ADMIN' else 1)
                logout = await client.post('/api/v1/auth/logout', headers=headers)
                assert logout.status_code == 200
                assert (await client.get('/api/v1/auth/me', headers=headers)).status_code == 401
    finally:
        await close_db_pool()
        await admin.close()
