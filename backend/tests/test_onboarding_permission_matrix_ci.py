"""Testes em PostgreSQL 16 DESCARTÁVEL: grants e RLS de convites.

Proibido rodar em PostgreSQL pessoal/produtivo ou sem flag CI.
Nenhuma migration é executada neste teste.
"""
import os
from urllib.parse import urlparse
import asyncpg
import pytest

pytestmark = [
    pytest.mark.skipif(
        os.getenv("FRCAIXINHA_CI_ISOLATED") != "1",
        reason="Exclusivo do PostgreSQL descartável CI",
    ),
    pytest.mark.asyncio,
]
CI_USERS = (
    ("DATABASE_URL", "frcaixinha_ci"),
    ("CI_AUTH_DATABASE_URL", "frcaixinha_auth_ci"),
    ("CI_VERIFIER_DATABASE_URL", "frcaixinha_verifier_ci"),
)
PROTECTED = (
    "public.invitations",
    "public.invite_email_verification",
    "public.password_reset_tokens",
)
OPS = ("SELECT", "INSERT", "UPDATE", "DELETE")


def ci_url(name, expected_user):
    url = os.environ[name]
    parsed = urlparse(url)
    assert parsed.scheme in ("postgresql", "postgres")
    assert parsed.hostname in ("127.0.0.1", "localhost")
    assert parsed.port == 5432 and parsed.path == "/frcaixinha_ci"
    assert parsed.username == expected_user
    return url


@pytest.mark.parametrize("name,username", CI_USERS)
async def test_token_tables_force_rls_and_cannot_be_accessed_by_app_roles(name, username):
    conn = await asyncpg.connect(ci_url(name, username))
    try:
        role = await conn.fetchrow(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert role and not role["rolsuper"] and not role["rolbypassrls"]
        for table in PROTECTED:
            flags = await conn.fetchrow(
                "SELECT c.relrowsecurity,c.relforcerowsecurity,"
                "c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user) AS owner "
                "FROM pg_class c WHERE c.oid=$1::regclass", table
            )
            assert flags and flags["relrowsecurity"] and flags["relforcerowsecurity"]
            assert not flags["owner"]
            for op in OPS:
                grant = await conn.fetchval(
                    "SELECT has_table_privilege(current_user,$1::text,$2::text)",
                    table, op,
                )
                assert grant is False, (username, table, op)
    finally:
        await conn.close()


@pytest.mark.parametrize("name,username", CI_USERS)
async def test_actual_select_and_insert_are_rejected_inside_transactions(name, username):
    """Not simply checking GRANT metadata: attempt real SQL and assert 42501."""
    conn = await asyncpg.connect(ci_url(name, username))
    try:
        for table in PROTECTED:
            for query in (
                f"SELECT 1 FROM {table} LIMIT 1",
                f"INSERT INTO {table} DEFAULT VALUES",
            ):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.execute(query)
    finally:
        await conn.close()


async def test_local_transaction_context_cannot_leak_between_requests():
    conn = await asyncpg.connect(ci_url("DATABASE_URL", "frcaixinha_ci"))
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_role',$1,true)", "MASTER"
            )
            await conn.execute(
                "SELECT set_config('app.current_tenant_id',$1,true)", ""
            )
            role = await conn.fetchval(
                "SELECT current_setting('app.current_role',true)"
            )
            assert role == "MASTER"
        after = await conn.fetchval(
            "SELECT current_setting('app.current_role',true)"
        )
        assert after != "MASTER"
    finally:
        await conn.close()
