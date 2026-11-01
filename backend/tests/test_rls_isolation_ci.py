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
                uid, f"{uid}@example.invalid", f"Teste {name}", uid.hex[:14], "00000000000", name == "master",
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
