"""M37462 — token-bound PostgreSQL session ID and synthetic SaaS isolation."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID
import importlib.util

from fastapi import HTTPException
import pytest
from starlette.requests import Request

from app import dependencies as deps
from app.routers.saas_authenticated_contract_ci import (
    CITrustedServerContext,check_server_identity_binding,
)
from app.saas_acceptance_api_contract_ci import CIPublishedOffer

ROOT=Path(__file__).resolve().parents[2]
NOW=lambda:datetime.now(timezone.utc)
A=UUID("daba0000-0000-4000-8000-000000000001")
T=UUID("daba0000-0000-4000-8000-000000000010")
S=UUID("daba0000-0000-4000-8000-000000000581")
S2=UUID("daba0000-0000-4000-8000-000000000588")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")
R=UUID("daba0000-0000-4000-8000-000000000594")
C=UUID("daba0000-0000-4000-8000-000000000595")
D=UUID("daba0000-0000-4000-8000-000000000030")
P=UUID("daba0000-0000-4000-8000-000000000060")
RAW="m37462-ci-only-first-bearer-NEVER-REAL-01"

class Tx:
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False

class FakeDB:
    def __init__(self, row=None, links=None, expires="DEFAULT"):
        self.row=row if row is not None else session_row()
        self.links=[{"tenant_id":T,"role":"TENANT_ADMIN"}] if links is None else links
        self.expires=NOW()+timedelta(minutes=10) if expires=="DEFAULT" else expires
        self.queries=[]
        self.closed=False
    def transaction(self):return Tx()
    async def fetchrow(self,sql,*params):
        self.queries.append((sql,params))
        return self.row
    async def fetch(self,sql,*params):
        self.queries.append((sql,params))
        return self.links
    async def fetchval(self,sql,*params):
        self.queries.append((sql,params))
        return self.expires
    async def close(self):self.closed=True


def session_row(**kwargs):
    row={
        "verified_session_id":S,"user_id":A,
        "active_role":"TENANT_ADMIN","active_tenant_id":T,
        "expires_at":NOW()+timedelta(minutes=20),"revoked_at":None,
        "email":"ci@example.invalid","full_name":"CI A",
        "is_master":False,"status":"ACTIVE",
    }
    row.update(kwargs)
    return row


def bearer_request(value=RAW):
    return Request({
        "type":"http","method":"POST","path":"/test",
        "headers":[(b"authorization",("Bearer "+value).encode("ascii"))],
        "query_string":b"",
    })


async def run_auth(monkeypatch,db):
    async def connection(*_args,**_kwargs):return db
    monkeypatch.setattr(deps.asyncpg,"connect",connection)
    monkeypatch.setattr(deps,"auth_database_url",lambda:"postgresql://ci-isolated")
    result=await deps.get_current_session(bearer_request())
    assert db.closed
    return result


def make_context(*,session=S):
    now=NOW()
    return CITrustedServerContext(
        tenant_id=T,administrator_id=A,session_id=session,
        session_role="TENANT_ADMIN",session_active=True,email_verified=True,
        session_checked_at=now-timedelta(seconds=1),
        session_expires_at=now+timedelta(minutes=8),
        request_id=R,challenge_id=C,
        offer=CIPublishedOffer(
            tenant_id=T,document_id=D,document_sha256="a"*64,
            price_version_id=P,billing_period="MONTHLY",price_cents=19937,
            published_at=now-timedelta(days=1),state="ACTIVE",
        ),
    )


def principal(*,session=S):
    now=NOW()
    return deps.AuthenticatedSession(
        user_id=str(A),role="TENANT_ADMIN",tenant_id=str(T),
        email="ci@example.invalid",name="CI",is_master=False,
        verified_session_id=str(session),
        verified_session_at=now-timedelta(seconds=3),
        verified_session_expires_at=now+timedelta(minutes=13),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )


@pytest.mark.asyncio
async def test_actual_get_current_session_returns_database_session_id(monkeypatch):
    db=FakeDB()
    result=await run_auth(monkeypatch,db)
    assert result.verified_session_id==str(S)
    assert result.verification_source=="POSTGRES_TOKEN_HASH_REFRESH"
    assert result.verified_session_expires_at==db.expires
    assert result.verified_session_at.tzinfo is not None
    assert result.user_id==str(A) and result.tenant_id==str(T)
    assert result.role=="TENANT_ADMIN" and not result.is_master
    assert len(db.queries)==3
    assert "s.id AS verified_session_id" in db.queries[0][0]
    assert "WHERE s.token_hash=$1" in db.queries[0][0]
    assert "auth_active_memberships($1::text)" in db.queries[1][0]
    assert "auth_refresh_session($1::text)" in db.queries[2][0]
    assert db.queries[0][1]==(deps.hash_token(RAW),)
    assert db.queries[1][1]==(RAW,)
    assert db.queries[2][1]==(RAW,)
    assert RAW not in repr(result.__dict__)


@pytest.mark.asyncio
async def test_real_db_principal_matches_test_context(monkeypatch):
    result=await run_auth(monkeypatch,FakeDB())
    ctx=make_context()
    # The context must be fetched AFTER the bearer/session was verified.
    ctx=replace(ctx,session_checked_at=NOW(),
                session_expires_at=min(ctx.session_expires_at,
                                       result.verified_session_expires_at))
    assert check_server_identity_binding(result,ctx,now=NOW()) is not None


@pytest.mark.asyncio
async def test_different_token_id_same_user_denied(monkeypatch):
    result=await run_auth(monkeypatch,FakeDB(session_row(verified_session_id=S2)))
    assert result.verified_session_id==str(S2)
    assert check_server_identity_binding(result,make_context(),now=NOW()) is None


@pytest.mark.parametrize("mod",[
    {"verified_session_id":None},
    {"verified_session_id":str(S)},
    {"verified_session_id":UUID(int=0)},
])
@pytest.mark.asyncio
async def test_non_uuid_or_missing_db_session_id_cannot_bind_ci_contract(monkeypatch,mod):
    result=await run_auth(monkeypatch,FakeDB(session_row(**mod)))
    assert result.verified_session_id is None
    assert result.verification_source=="LEGACY_NO_SESSION_BINDING"
    assert check_server_identity_binding(result,make_context(),now=NOW()) is None


@pytest.mark.asyncio
async def test_legacy_constructor_retains_old_endpoints_but_not_saas():
    x=deps.AuthenticatedSession(str(A),"TENANT_ADMIN",str(T),"ci@example.invalid","CI",False)
    assert x.role=="TENANT_ADMIN"
    assert x.verified_session_id is None
    assert check_server_identity_binding(x,make_context(),now=NOW()) is None


@pytest.mark.parametrize("change",[
    {"verification_source":"LEGACY_NO_SESSION_BINDING"},
    {"verification_source":"CLIENT_SUPPLIED"},
    {"verified_session_id":str(S2)},
    {"verified_session_id":str(UUID(int=0))},
    {"verified_session_id":"not-a-uuid"},
    {"verified_session_id":None},
    {"verified_session_at":None},
    {"verified_session_at":NOW()+timedelta(seconds=4)},
    {"verified_session_at":NOW()-timedelta(minutes=6)},
    {"verified_session_at":NOW().replace(tzinfo=None)},
    {"verified_session_expires_at":None},
    {"verified_session_expires_at":NOW()-timedelta(seconds=1)},
    {"verified_session_expires_at":NOW().replace(tzinfo=None)},
])
def test_verified_token_binding_mismatch_or_age_denied(change):
    p=principal()
    for k,v in change.items():setattr(p,k,v)
    assert check_server_identity_binding(p,make_context(),now=NOW()) is None


@pytest.mark.parametrize("change",[
    {"session_id":S2},
    {"tenant_id":OTHER},
    {"administrator_id":OTHER},
    {"session_checked_at":NOW()-timedelta(minutes=2)},
    {"session_checked_at":NOW()+timedelta(seconds=1)},
    {"session_expires_at":NOW()+timedelta(hours=2)},
    {"session_role":"TENANT_MEMBER"},
    {"session_active":False},
    {"email_verified":False},
    {"source":"CLIENT"},
])
def test_postgres_session_does_not_authorize_mismatched_server_context(change):
    c=replace(make_context(),**change)
    assert check_server_identity_binding(principal(),c,now=NOW()) is None


@pytest.mark.parametrize("change",[
    {"role":"MASTER"},
    {"role":"TENANT_MEMBER"},
    {"tenant_id":str(OTHER)},
    {"user_id":str(OTHER)},
    {"is_master":True},
])
def test_postgres_session_principal_still_checks_role_and_tenant(change):
    p=principal()
    for k,v in change.items():setattr(p,k,v)
    assert check_server_identity_binding(p,make_context(),now=NOW()) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("change",[
    {"revoked_at":NOW()},
    {"expires_at":NOW()-timedelta(seconds=1)},
    {"status":"SUSPENDED"},
    {"active_role":"MASTER"},
    {"active_tenant_id":OTHER},
])
async def test_db_role_revoked_invalid_expired_sessions_fail_before_refresh(monkeypatch,change):
    db=FakeDB(session_row(**change))
    with pytest.raises(HTTPException) as exc:
        await run_auth(monkeypatch,db)
    assert exc.value.status_code==401
    assert not any("auth_refresh_session" in q[0] for q in db.queries)


@pytest.mark.asyncio
async def test_master_account_cannot_reuse_tenant_admin_saas_context(monkeypatch):
    db=FakeDB(session_row(is_master=True))
    s=await run_auth(monkeypatch,db)
    assert s.is_master is True
    assert check_server_identity_binding(s,make_context(),now=NOW()) is None


@pytest.mark.asyncio
async def test_lost_membership_denied_before_refresh(monkeypatch):
    db=FakeDB(links=[])
    with pytest.raises(HTTPException) as exc:
        await run_auth(monkeypatch,db)
    assert exc.value.status_code==401
    assert not any("auth_refresh_session" in q[0] for q in db.queries)


@pytest.mark.asyncio
async def test_revocation_during_refresh_is_denied(monkeypatch):
    db=FakeDB(expires=None)
    with pytest.raises(HTTPException) as exc:
        await run_auth(monkeypatch,db)
    assert exc.value.status_code==401


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid",[
    False,"not-a-timestamp",
    datetime(2026,11,10,16,0),
    NOW()-timedelta(seconds=1),
])
async def test_invalid_refresh_expiry_fails_closed_for_all_routes(monkeypatch,invalid):
    db=FakeDB(expires=invalid)
    with pytest.raises(HTTPException) as exc:
        await run_auth(monkeypatch,db)
    assert exc.value.status_code==401
    assert db.closed


def _runner():
    p=ROOT/"backend/scripts/aistudio_m37462_verified_token_session_ci.py"
    spec=importlib.util.spec_from_file_location("m37462",p)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m,p.read_text()


def test_termux_never_launches_disposable_auth_script(monkeypatch):
    runner,_=_runner()
    for key in runner.CI_ENV:monkeypatch.delenv(key,raising=False)
    assert runner.main()==1


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"other"},
    {"PGOPTIONS":"-c frcaixinha.saas_token_ci=0"},
])
def test_script_requires_disposable_github_ci_credentials(change):
    runner,_=_runner()
    assert runner.environment_allowed(dict(runner.CI_ENV))
    assert not runner.environment_allowed({**runner.CI_ENV,**change})


def test_legacy_session_role_is_nonprivileged():
    p=principal()
    assert getattr(p,"token_hash",None) is None
    assert getattr(p,"raw_token",None) is None


def test_ci_sql_guard_and_privilege_limits():
    sql=(ROOT/"backend/tests/sql/m37462_disposable_bearer_session_ci.sql").read_text()
    for marker in (
        "M37462_DISPOSABLE_POSTGRESQL_ONLY",
        "current_database()<>'frcaixinha_staging'",
        "session_user<>'postgres'",
        "frcaixinha.saas_token_ci",
        "CREATE ROLE frcaixinha_auth_token_ci LOGIN INHERIT",
        "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE",
        "GRANT frcaixinha_auth_role TO frcaixinha_auth_token_ci",
        "has_table_privilege('frcaixinha_app_role','public.sessions','SELECT')",
        "M37462_AUTH_ROLE_OR_SESSION_PRIVILEGES",
        "public.digest(",
        "public.sessions",
        "COMMIT;",
    ):
        assert marker in sql
    assert "GRANT SELECT ON public.sessions TO frcaixinha_app_role" not in sql


def test_staging_chain_and_no_new_local_migration():
    shell=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "BLOCKED=M37462_WRONG_DATABASE_ACCEPTED" in shell
    assert "backend/tests/sql/m37462_disposable_bearer_session_ci.sql" in shell
    assert "python backend/scripts/aistudio_m37462_verified_token_session_ci.py" in shell
    assert "M37462_PRODUCTION_SAAS_IDENTITY=NOT_ATTESTED" in shell
    assert shell.index("M37461: servidor PostgreSQL") < shell.index(
        "M37462: verificar token hash")
    assert "m37462_disposable_bearer_session_ci.sql" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()


def test_integration_uses_live_homologation_auth_dependency():
    _,source=_runner()
    for marker in (
        "get_current_session",
        "default_transaction_read_only=on",
        "AUTH_DATABASE_URL",
        "auth_revoke_session($1::text)",
        "M37462_DISPOSABLE_TOKEN_HASH_TO_SESSION_ID=PASS",
        "M37462_EXPIRED_AND_REVOKED_TOKEN=401",
        "M37462_PAYMENT_PIX_LICENSE_ACTIVATION=OFF",
        "M37462_REAL_SAAS_CONSENT=NOT_ATTESTED",
    ):
        assert marker in source
    for forbidden in ("DROP DATABASE","CREATE DATABASE",
                      "INSERT INTO public.contract_acceptances",
                      "UPDATE public.contract_acceptances",
                      "INSERT INTO public.saas_payment_intents"):
        assert forbidden not in source
