"""M37463: fail-closed token-scoped SaaS contract context and CI-only SQL."""
from __future__ import annotations

from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID
import importlib.util

import pytest

from app.dependencies import AuthenticatedSession
from app.saas_token_scoped_offer_readback_ci import (
    TOKEN_SCOPE_SQL,token_scope_params,build_token_scoped_ci_context,
)

NOW=datetime(2026,11,10,17,0,tzinfo=timezone.utc)
S=UUID("daba0000-0000-4000-8000-000000000581")
S2=UUID("daba0000-0000-4000-8000-000000000588")
A=UUID("daba0000-0000-4000-8000-000000000001")
T=UUID("daba0000-0000-4000-8000-000000000010")
R=UUID("daba0000-0000-4000-8000-000000000594")
C=UUID("daba0000-0000-4000-8000-000000000595")
D=UUID("daba0000-0000-4000-8000-000000000030")
P=UUID("daba0000-0000-4000-8000-000000000060")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")
H="c"*64


def session(**changes):
    data=dict(
        user_id=str(A),role="TENANT_ADMIN",tenant_id=str(T),
        email="ci@example.invalid",name="Synthetic",is_master=False,
        verified_session_id=str(S),
        verified_session_at=NOW-timedelta(seconds=1),
        verified_session_expires_at=NOW+timedelta(minutes=8),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    data.update(changes)
    return AuthenticatedSession(**data)


def row(**changes):
    data={
        "session_id":S,"tenant_id":T,"admin_id":A,
        "session_role":"TENANT_ADMIN","session_active":True,
        "email_verified":True,
        "server_issued_at":NOW-timedelta(minutes=7),
        "server_expires_at":NOW+timedelta(minutes=20),
        "tenant_admin":A,"tenant_status":"ATIVO","admin_status":"ACTIVE",
        "admin_membership_active":True,
        "request_id":R,"challenge_id":C,
        "challenge_session":S,"challenge_tenant":T,"challenge_admin":A,
        "document_id":D,"document_sha":"a"*64,
        "price_version_id":P,"billing_period":"MONTHLY",
        "challenge_issued_at":NOW-timedelta(minutes=2),
        "challenge_expires_at":NOW+timedelta(minutes=2),
        "document_kind":"PLATFORM_LICENSE","version_label":"FR-CI-M37463",
        "published_sha":"a"*64,"published_at":NOW-timedelta(days=1),
        "version_id":P,"plan_tier":"ESSENCIAL",
        "monthly_price":Decimal("199.37"),
        "annual_price":Decimal("1993.70"),
        "plan_status":"ACTIVE",
        "live_session_id":S,"live_user_id":A,"live_tenant_id":T,
        "live_role":"TENANT_ADMIN",
        "live_expires_at":NOW+timedelta(minutes=10),
        "live_created_at":NOW-timedelta(minutes=20),
        "live_revoked_at":None,"live_is_master":False,
    }
    data.update(changes)
    return data


def judge(r=None,s=None,request=R,digest=H,now=NOW):
    return build_token_scoped_ci_context(
        row() if r is None else r,
        session() if s is None else s,
        request,digest,now=now,
    )


def denied(output):
    state,context=output
    assert state!="CI_TOKEN_HASH_SESSION_CONTRACT_READBACK_ONLY"
    assert context is None


def test_success_token_bound_server_context_and_frozen_price():
    state,context=judge()
    assert state=="CI_TOKEN_HASH_SESSION_CONTRACT_READBACK_ONLY"
    assert context is not None and context.session_id==S
    assert context.tenant_id==T and context.administrator_id==A
    assert context.offer.price_cents==19937
    assert context.session_expires_at==NOW+timedelta(minutes=8)
    assert context.source=="CI_SYNTHETIC_SERVER_DB_READBACK"


def test_annual_period_immutable_postgres_price():
    r=row(billing_period="ANNUAL")
    state,context=judge(r)
    assert state=="CI_TOKEN_HASH_SESSION_CONTRACT_READBACK_ONLY"
    assert context.offer.price_cents==199370


@pytest.mark.parametrize("changed",[
    {"role":"MASTER"},
    {"role":"TENANT_MEMBER"},
    {"role":"PENDING_CONTEXT"},
    {"is_master":True},
    {"user_id":str(OTHER)},
    {"tenant_id":str(OTHER)},
    {"tenant_id":None},
    {"verified_session_id":str(S2)},
    {"verified_session_id":None},
    {"verified_session_id":str(UUID(int=0))},
    {"verified_session_id":"invalid"},
    {"verified_session_at":NOW-timedelta(minutes=6)},
    {"verified_session_at":NOW+timedelta(seconds=10)},
    {"verified_session_at":NOW.replace(tzinfo=None)},
    {"verified_session_expires_at":NOW-timedelta(seconds=1)},
    {"verified_session_expires_at":NOW.replace(tzinfo=None)},
    {"verification_source":"LEGACY_NO_SESSION_BINDING"},
    {"verification_source":"CLIENT_ASSERTED"},
])
def test_invalid_verified_principal_never_builds_query(changed):
    params=token_scope_params(session(**changed),R,H,now=NOW)
    # Another valid principal/session is allowed to form a *scoped query*
    # but cannot adopt the original request/contract because SQL and row
    # validation bind identity, tenant and session ID separately.
    if set(changed).intersection({"user_id","tenant_id","verified_session_id"}) and (
        next(iter(changed.values())) in (str(OTHER),str(S2))
    ):
        assert params is not None
    else:
        assert params is None
    denied(judge(s=session(**changed)))


@pytest.mark.parametrize("request_id,digest",[
    (OTHER,H),
    (UUID(int=0),H),
    ("not-a-uuid",H),
    (R,"0"*65),
    (R,"A"*64),
    (R,"NaN"),
    (R,None),
    (R,123),
])
def test_caller_request_or_digest_constraints(request_id,digest):
    if request_id==OTHER:
        assert token_scope_params(session(),request_id,digest,now=NOW) is not None
        denied(judge(request=request_id))
    else:
        assert token_scope_params(session(),request_id,digest,now=NOW) is None
        denied(judge(request=request_id,digest=digest))


@pytest.mark.parametrize("field",[
    "live_session_id","live_user_id","live_tenant_id",
])
def test_missing_live_uuid_denied(field):
    r=row(**{field:None})
    denied(judge(r))
    r=row()
    r.pop(field)
    denied(judge(r))


@pytest.mark.parametrize("field,wrong",[
    ("live_session_id",S2),
    ("live_user_id",OTHER),
    ("live_tenant_id",OTHER),
    ("live_role","MASTER"),
    ("live_role","TENANT_MEMBER"),
    ("live_expires_at",NOW-timedelta(seconds=1)),
    ("live_created_at",NOW+timedelta(minutes=1)),
    ("live_created_at",NOW+timedelta(minutes=30)),
    ("live_revoked_at",NOW-timedelta(minutes=1)),
    ("live_is_master",True),
    ("live_is_master",1),
])
def test_db_cannot_reassign_live_session_or_revocation(field,wrong):
    denied(judge(row(**{field:wrong})))


@pytest.mark.parametrize("field,wrong",[
    ("server_expires_at",NOW-timedelta(minutes=1)),
    ("challenge_tenant",OTHER),
    ("challenge_admin",OTHER),
    ("challenge_session",S2),
    ("tenant_admin",OTHER),
    ("session_role","TENANT_MEMBER"),
    ("session_active",False),
    ("email_verified",False),
    ("admin_membership_active",False),
    ("tenant_status","INATIVO"),
    ("admin_status","BLOCKED"),
    ("published_sha","b"*64),
    ("document_sha","invalid"),
    ("document_kind","OTHER"),
    ("plan_status","INACTIVE"),
    ("billing_period","MONTHLY_INVALID"),
    ("monthly_price",Decimal("0")),
    ("annual_price",Decimal("1.00")),
])
def test_db_offer_tampering_or_missing_membership_denied(field,wrong):
    denied(judge(row(**{field:wrong})))


@pytest.mark.parametrize("field",[
    "live_expires_at","live_created_at",
])
def test_naive_live_db_timestamps_rejected(field):
    denied(judge(row(**{field:NOW.replace(tzinfo=None)})))


def test_stale_claim_expiry_bound_to_verified_bearer_expiry():
    r=row(live_expires_at=NOW+timedelta(minutes=2))
    # Returned row expiry is stale relative to the token's refreshed expiry
    denied(judge(r))
    s=session(verified_session_expires_at=NOW+timedelta(minutes=2))
    state,c=judge(r,s=s)
    assert state=="CI_TOKEN_HASH_SESSION_CONTRACT_READBACK_ONLY"
    assert c.session_expires_at==NOW+timedelta(minutes=2)


def test_sql_binds_token_hash_and_session_without_returning_hash():
    sql=TOKEN_SCOPE_SQL
    assert sql.count("%s")==5
    assert "s.id=%s AND s.user_id=%s AND s.active_tenant_id=%s" in sql
    assert "c.request_id=%s AND s.token_hash=%s" in sql
    assert "s.revoked_at IS NULL" in sql
    assert "s.expires_at>clock_timestamp()" in sql
    assert "c.server_expires_at>clock_timestamp()" in sql
    assert "JOIN public.saas_preprep_sessions_m37458_ci f" in sql
    assert "JOIN public.saas_preprep_challenges_m37458_ci c" in sql
    assert "JOIN public.platform_license_price_versions v" in sql
    assert "u.is_master=false" in sql
    assert "LIMIT 2" in sql
    assert "s.token_hash AS" not in sql
    assert "raw_bearer" not in sql
    for disallowed in ("INSERT ","UPDATE ","DELETE ","DROP ","CREATE ","ALTER ","TRUNCATE "):
        assert disallowed not in sql.upper()


ROOT=Path(__file__).resolve().parents[2]


def _runner():
    p=ROOT/"backend/scripts/aistudio_m37463_token_scoped_offer_ci.py"
    spec=importlib.util.spec_from_file_location("m37463",p)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m,p.read_text()


def test_runner_fails_closed_outside_ci(monkeypatch):
    mod,_=_runner()
    for k in mod.EXPECTED_ENV:
        monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(mod.sys,"argv",["m37463"])
    assert mod.main()==1
    assert not mod.environment_allowed({},"before-revoke")
    assert not mod.environment_allowed(dict(mod.EXPECTED_ENV),"wrong-mode")


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"not-test"},
    {"PGOPTIONS":"-c frcaixinha.saas_token_ci=0"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_PIX_REAL":"ON"},
])
def test_runner_only_disposable_github_credentials(change):
    mod,_=_runner()
    env={**mod.EXPECTED_ENV,**change}
    assert not mod.environment_allowed(env,"before-revoke")
    assert not mod.environment_allowed(env,"after-revoke")


def test_runner_scoped_only_readonly_and_true_post_revocation():
    mod,source=_runner()
    assert mod.environment_allowed(dict(mod.EXPECTED_ENV),"before-revoke")
    assert mod.environment_allowed(dict(mod.EXPECTED_ENV),"after-revoke")
    for key in (
        "get_current_session",
        "hash_token(TOKEN1)",
        "default_transaction_read_only=on",
        "M37463_TOKEN_SESSION_TENANT_OFFER_SINGLE_READBACK=PASS",
        "M37463_REVOKED_BEARER_CANNOT_READ_CONTRACT=PASS",
        "M37463_OTHER_ACTIVE_SESSION_CANNOT_ADOPT_CHALLENGE=PASS",
        "M37463_ORIGINAL_TERMUX_DATABASE=UNTOUCHED",
        "M37463_REAL_SAAS_PAYMENT_LICENSE_PIX_ACTIVATION=OFF",
    ):
        assert key in source
    for forbidden in (
        "INSERT INTO public.","UPDATE public.","DELETE FROM public.",
        "CREATE TABLE","DROP DATABASE","ALTER TABLE",
    ):
        assert forbidden not in source


def test_ci_chain_orders_pre_revocation_and_post_revocation():
    chain=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "aistudio_m37463_token_scoped_offer_ci.py before-revoke" in chain
    assert "aistudio_m37463_token_scoped_offer_ci.py after-revoke" in chain
    assert (chain.index("aistudio_m37463_token_scoped_offer_ci.py before-revoke")
            < chain.index("aistudio_m37462_verified_token_session_ci.py")
            < chain.index("aistudio_m37463_token_scoped_offer_ci.py after-revoke"))
    assert "m37463_token_scoped_offer_ci.py" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()
