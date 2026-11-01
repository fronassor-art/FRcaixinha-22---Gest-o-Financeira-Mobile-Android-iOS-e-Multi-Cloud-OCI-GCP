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


async def test_persistent_sessions_contexts_expiry_and_revocation(isolated_rows, monkeypatch):
    """Duas caixinhas reais no PostgreSQL descartável, sem sessão de processo."""
    from datetime import datetime, timedelta, timezone
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.config import settings
    from app.database import close_db_pool
    from app.security import hash_password_secure, hash_token

    app_role, ids = isolated_rows
    monkeypatch.setattr(settings, 'DATABASE_URL', _ci_dsn('DATABASE_URL'))
    monkeypatch.setenv('AUTH_DATABASE_URL', _ci_dsn('CI_AUTH_DATABASE_URL'))
    monkeypatch.setenv('FRCAIXINHA_TEST_AUTH', '1')
    monkeypatch.setenv('ENVIRONMENT', 'development')
    admin = await asyncpg.connect(_ci_dsn('CI_ADMIN_DATABASE_URL'))
    auth = await asyncpg.connect(_ci_dsn('CI_AUTH_DATABASE_URL'))
    try:
        extra = uuid.uuid4()
        await admin.execute(
            "INSERT INTO memberships(id,tenant_id,user_id,role) VALUES($1,$2,$3,'TENANT_MEMBER')",
            extra, ids['tenant_b'], ids['member_a'])
        password = 'somente-teste-descartavel'
        for name in ('member_a', 'master'):
            await admin.execute(
                'INSERT INTO credentials(user_id,password_hash) VALUES($1,$2)',
                ids[name], hash_password_secure(password))
        assert not await app_role.fetchval(
            "SELECT has_table_privilege(current_user,'public.sessions','SELECT')")
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            member = await client.post('/api/v1/auth/login', json={
                'usernameOrEmail': f"{ids['member_a']}@example.com", 'password': password})
            assert member.status_code == 200, member.text
            token = member.json()['token']
            headers = {'Authorization': f'Bearer {token}'}
            stored = await auth.fetchrow(
                'SELECT user_id,revoked_at,expires_at FROM public.sessions WHERE token_hash=$1',
                hash_token(token))
            assert stored['user_id'] == ids['member_a'] and stored['revoked_at'] is None
            contexts = await client.get('/api/v1/auth/contexts', headers=headers)
            assert contexts.status_code == 200
            assert {item['tenant_id'] for item in contexts.json()} == {
                str(ids['tenant_a']), str(ids['tenant_b'])}
            denied = await client.post('/api/v1/auth/switch-context', headers=headers,
                json={'target_role':'TENANT_ADMIN','target_tenant_id':str(ids['tenant_b'])})
            assert denied.status_code == 403
            switched = await client.post('/api/v1/auth/switch-context', headers=headers,
                json={'target_role':'TENANT_MEMBER','target_tenant_id':str(ids['tenant_b'])})
            assert switched.status_code == 200, switched.text
            assert switched.json()['tenant_id'] == str(ids['tenant_b'])
            assert (await client.get(
                f"/api/v1/tenants/{ids['tenant_a']}/contributions", headers=headers)).status_code == 403
            assert (await client.get('/api/v1/auth/me', headers=headers)).json()['tenant_id'] == str(ids['tenant_b'])
            await admin.execute(
                "UPDATE memberships SET status='DESLIGADA' WHERE id=$1", extra)
            assert (await client.get('/api/v1/auth/me', headers=headers)).status_code == 401
            await admin.execute(
                "UPDATE memberships SET status='ATIVA' WHERE id=$1", extra)
            await admin.execute(
                'UPDATE sessions SET expires_at=$2 WHERE token_hash=$1',
                hash_token(token), datetime.now(timezone.utc)-timedelta(seconds=1))
            assert (await client.get('/api/v1/auth/me', headers=headers)).status_code == 401

            master = await client.post('/api/v1/auth/login', json={
                'usernameOrEmail': f"{ids['master']}@example.com", 'password': password})
            assert master.status_code == 200, master.text
            master_headers = {'Authorization': f"Bearer {master.json()['token']}"}
            assert (await client.get(
                f"/api/v1/tenants/{ids['tenant_a']}/contributions", headers=master_headers)).status_code == 403
            own_member = await client.post('/api/v1/auth/switch-context', headers=master_headers,
                json={'target_role':'TENANT_MEMBER','target_tenant_id':str(ids['tenant_a'])})
            assert own_member.status_code == 200, own_member.text
            assert (await client.get(
                f"/api/v1/tenants/{ids['tenant_a']}/contributions", headers=master_headers)).status_code == 200
            assert (await client.post('/api/v1/auth/logout', headers=master_headers)).status_code == 200
            assert (await client.get('/api/v1/auth/me', headers=master_headers)).status_code == 401
    finally:
        await close_db_pool()
        await auth.close()
        await admin.close()


async def test_financial_rows_rls_and_composite_tenant_references(isolated_rows):
    """Leituras com dados de dois tenants e FKs entre tenant, ciclo e vínculo."""
    from datetime import date
    conn, ids = isolated_rows
    admin = await asyncpg.connect(_ci_dsn('CI_ADMIN_DATABASE_URL'))
    cycle_a, cycle_b = uuid.uuid4(), uuid.uuid4()
    policy_a, policy_b = uuid.uuid4(), uuid.uuid4()
    loan_a, loan_a2, loan_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    inst_a, inst_a2, inst_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        for tenant, cycle, policy, year in (
            (ids['tenant_a'], cycle_a, policy_a, 2027),
            (ids['tenant_b'], cycle_b, policy_b, 2027),
        ):
            await admin.execute(
                'INSERT INTO cycles(id,tenant_id,year,start_date,end_date,settlement_date) '
                'VALUES($1,$2,$3,$4,$5,$6)', cycle, tenant, year,
                date(2027,1,1), date(2027,12,31), date(2028,1,10))
            await admin.execute(
                'INSERT INTO policies(id,tenant_id,cycle_id) VALUES($1,$2,$3)',
                policy, tenant, cycle)
        for loan, tenant, cycle, policy, member in (
            (loan_a, ids['tenant_a'], cycle_a, policy_a, ids['membership_a']),
            (loan_a2, ids['tenant_a'], cycle_a, policy_a, ids['membership_a2']),
            (loan_b, ids['tenant_b'], cycle_b, policy_b, ids['membership_b']),
        ):
            await admin.execute(
                'INSERT INTO loans(id,tenant_id,cycle_id,borrower_membership_id,policy_id,'
                'principal,monthly_rate,term_months,monthly_payment,last_payment,total_interest) '
                'VALUES($1,$2,$3,$4,$5,500,0.2,5,167.19,167.20,335.96)',
                loan, tenant, cycle, member, policy)
        for inst, tenant, loan in (
            (inst_a, ids['tenant_a'], loan_a),
            (inst_a2, ids['tenant_a'], loan_a2),
            (inst_b, ids['tenant_b'], loan_b),
        ):
            await admin.execute(
                'INSERT INTO loan_installments(id,tenant_id,loan_id,installment_number,due_date,'
                'principal_due,interest_due,total_due) VALUES($1,$2,$3,1,$4,67.19,100,167.19)',
                inst, tenant, loan, date(2027,2,10))
        async def visible(table, user, tenant, role):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(user))
                await conn.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(tenant))
                await conn.execute("SELECT set_config('app.current_role',$1,true)", role)
                return {row['id'] for row in await conn.fetch('SELECT id FROM public.'+table)}
        assert await visible('loans', ids['admin_a'], ids['tenant_a'], 'TENANT_ADMIN') == {loan_a, loan_a2}
        assert await visible('loans', ids['admin_a'], ids['tenant_b'], 'TENANT_ADMIN') == set()
        assert await visible('loans', ids['member_a'], ids['tenant_a'], 'TENANT_MEMBER') == {loan_a}
        assert await visible('loans', ids['master'], ids['tenant_a'], 'MASTER') == set()
        assert await visible('loan_installments', ids['member_a'], ids['tenant_a'], 'TENANT_MEMBER') == {inst_a}
        assert await visible('loan_installments', ids['member_a'], ids['tenant_b'], 'TENANT_MEMBER') == set()
        assert await visible('memberships', ids['member_a'], ids['tenant_a'], 'TENANT_MEMBER') == {ids['membership_a']}
        assert await visible('quotas', ids['master'], ids['tenant_a'], 'MASTER') == set()
        assert not await conn.fetchval("SELECT has_table_privilege(current_user,'public.ledger_entries','DELETE')")
        assert not await conn.fetchval("SELECT has_table_privilege(current_user,'public.ledger_transactions','UPDATE')")
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await admin.execute(
                'INSERT INTO quotas(tenant_id,membership_id,quota_number,value_brl) VALUES($1,$2,99,100)',
                ids['tenant_a'], ids['membership_b'])
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await admin.execute(
                'INSERT INTO contributions(tenant_id,cycle_id,membership_id,competence,due_date,amount_due) '
                "VALUES($1,$2,$3,'2027-01',$4,100)",
                ids['tenant_a'], cycle_b, ids['membership_a'], date(2027,1,10))
    finally:
        await admin.close()


async def test_ledger_atomic_balance_idempotence_and_rollback(isolated_rows):
    """Invariantes PostgreSQL com lançamentos sintéticos, sem operação financeira."""
    _, ids = isolated_rows
    admin = await asyncpg.connect(_ci_dsn('CI_ADMIN_DATABASE_URL'))
    try:
        account_a = await admin.fetchval(
            "SELECT id FROM ledger_accounts WHERE tenant_id=$1 AND account_code='1.1.1'",
            ids['tenant_a'])
        equity_a = await admin.fetchval(
            "SELECT id FROM ledger_accounts WHERE tenant_id=$1 AND account_code='2.1.1'",
            ids['tenant_a'])
        account_b = await admin.fetchval(
            "SELECT id FROM ledger_accounts WHERE tenant_id=$1 AND account_code='1.1.1'",
            ids['tenant_b'])
        assert account_a and equity_a and account_b
        reference = str(uuid.uuid4())
        tx = uuid.uuid4()
        async with admin.transaction():
            await admin.execute(
                "INSERT INTO ledger_transactions(id,tenant_id,description,reference_id) VALUES($1,$2,'CI sintético',$3)",
                tx, ids['tenant_a'], reference)
            for account, kind in ((account_a, 'DR'), (equity_a, 'CR')):
                await admin.execute(
                    'INSERT INTO ledger_entries(tenant_id,transaction_id,account_id,entry_type,amount_cents) '
                    'VALUES($1,$2,$3,$4,10000)',
                    ids['tenant_a'], tx, account, kind)
        assert await admin.fetchval(
            'SELECT count(*) FROM ledger_entries WHERE transaction_id=$1', tx) == 2
        with pytest.raises(asyncpg.UniqueViolationError):
            await admin.execute(
                "INSERT INTO ledger_transactions(tenant_id,description,reference_id) VALUES($1,'duplicado',$2)",
                ids['tenant_a'], reference)

        unbalanced = uuid.uuid4()
        with pytest.raises(asyncpg.PostgresError):
            async with admin.transaction():
                await admin.execute(
                    "INSERT INTO ledger_transactions(id,tenant_id,description,reference_id) VALUES($1,$2,'falha',$3)",
                    unbalanced, ids['tenant_a'], str(uuid.uuid4()))
                await admin.execute(
                    "INSERT INTO ledger_entries(tenant_id,transaction_id,account_id,entry_type,amount_cents) "
                    "VALUES($1,$2,$3,'DR',10000)",
                    ids['tenant_a'], unbalanced, account_a)
        assert await admin.fetchval(
            'SELECT count(*) FROM ledger_transactions WHERE id=$1', unbalanced) == 0
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await admin.execute(
                "INSERT INTO ledger_entries(tenant_id,transaction_id,account_id,entry_type,amount_cents) "
                "VALUES($1,$2,$3,'DR',100)",
                ids['tenant_a'], tx, account_b)
    finally:
        await admin.close()


async def test_admin_member_loan_is_marked_and_blocked_in_real_postgres(isolated_rows):
    """O vínculo de membro do admin não transforma crédito próprio em crédito comum."""
    from datetime import date
    from decimal import Decimal
    from fastapi import HTTPException
    from app.dependencies import AuthenticatedSession
    from app.models import LoanRequestPayload
    from app.routers.loans import request_loan, approve_loan

    conn, ids = isolated_rows
    admin = await asyncpg.connect(_ci_dsn('CI_ADMIN_DATABASE_URL'))
    cycle, policy, member_link = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        await admin.execute(
            "INSERT INTO memberships(id,tenant_id,user_id,role) VALUES($1,$2,$3,'TENANT_MEMBER')",
            member_link, ids['tenant_a'], ids['admin_a'])
        await admin.execute(
            "INSERT INTO cycles(id,tenant_id,year,start_date,end_date,settlement_date) VALUES($1,$2,2027,$3,$4,$5)",
            cycle, ids['tenant_a'], date(2027,1,1), date(2027,12,31), date(2028,1,10))
        await admin.execute("INSERT INTO policies(id,tenant_id,cycle_id) VALUES($1,$2,$3)",
                            policy, ids['tenant_a'], cycle)
        member = AuthenticatedSession(str(ids['admin_a']), 'TENANT_MEMBER', str(ids['tenant_a']),
                                      'synthetic@example.invalid', 'Administrador sintético', False)
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(ids['admin_a']))
            await conn.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(ids['tenant_a']))
            await conn.execute("SELECT set_config('app.current_role',$1,true)", 'TENANT_MEMBER')
            result = await request_loan(
                str(ids['tenant_a']), LoanRequestPayload(principal=Decimal('500.00'), term_months=5),
                member, conn)
            assert result.is_admin_loan is True
            assert result.status == 'SOLICITADO'
        tenant_admin = AuthenticatedSession(str(ids['admin_a']), 'TENANT_ADMIN', str(ids['tenant_a']),
                                            'synthetic@example.invalid', 'Administrador sintético', False)
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(ids['admin_a']))
            await conn.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(ids['tenant_a']))
            await conn.execute("SELECT set_config('app.current_role',$1,true)", 'TENANT_ADMIN')
            with pytest.raises(HTTPException) as error:
                await approve_loan(str(ids['tenant_a']), result.id, tenant_admin, conn)
            assert error.value.status_code == 503
            assert await conn.fetchval('SELECT status FROM loans WHERE id=$1', uuid.UUID(result.id)) == 'SOLICITADO'
    finally:
        # audit_events preserva a referência por FK; limpar só os eventos sintéticos
        # deste tenant descartável antes do teardown do fixture.
        await admin.execute("DELETE FROM audit_events WHERE tenant_id=$1", ids['tenant_a'])
        await admin.close()
