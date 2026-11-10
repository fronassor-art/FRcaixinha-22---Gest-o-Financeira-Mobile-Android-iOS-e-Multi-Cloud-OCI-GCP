"""M37461: adversarial server-owned session/offer readback, CI only."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID
import importlib.util

import pytest

from app.dependencies import AuthenticatedSession
from app.routers.saas_authenticated_contract_ci import check_server_identity_binding
from app.saas_server_context_readback_ci import (
    READBACK_SQL,build_ci_trusted_context,
)

NOW=datetime(2026,11,10,16,0,tzinfo=timezone.utc)
S=UUID("daba0000-0000-4000-8000-000000000581")
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
R=UUID("daba0000-0000-4000-8000-000000000594")
C=UUID("daba0000-0000-4000-8000-000000000595")
D=UUID("daba0000-0000-4000-8000-000000000030")
P=UUID("daba0000-0000-4000-8000-000000000060")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")


def row():
    return {
        "session_id":S,"tenant_id":T,"admin_id":A,
        "session_role":"TENANT_ADMIN", "session_active":True,
        "email_verified":True,"server_issued_at":NOW-timedelta(hours=1),
        "server_expires_at":NOW+timedelta(minutes=30),
        "tenant_admin":A,"tenant_status":"ATIVO","admin_status":"ACTIVE",
        "admin_membership_active":True,
        "request_id":R,"challenge_id":C,"challenge_session":S,
        "challenge_tenant":T,"challenge_admin":A,
        "document_id":D,"document_sha":"a"*64,
        "price_version_id":P,"billing_period":"MONTHLY",
        "challenge_issued_at":NOW-timedelta(minutes=4),
        "challenge_expires_at":NOW+timedelta(minutes=1),
        "document_kind":"PLATFORM_LICENSE",
        "version_label":"FR-M30900-CI-PUBLISHED",
        "published_sha":"a"*64,
        "published_at":NOW-timedelta(days=2),
        "version_id":P,"plan_tier":"ESSENCIAL",
        "monthly_price":Decimal("199.37"),
        "annual_price":Decimal("1993.70"),
        "plan_status":"ACTIVE",
    }


def review(mod=None,**kwargs):
    record=row() if mod is None else mod
    return build_ci_trusted_context(
        record,session_id=kwargs.get("session_id",S),
        tenant_id=kwargs.get("tenant_id",T),
        admin_id=kwargs.get("admin_id",A),
        request_id=kwargs.get("request_id",R),
        checked_at=kwargs.get("checked_at",NOW),
    )


def assert_denied(result,expected):
    status,context=result
    assert status==expected
    assert context is None


def test_hypothetical_server_offer_and_session_from_db():
    state,context=review()
    assert state=="CI_DISPOSABLE_SERVER_CONTEXT_READBACK_ONLY"
    assert context is not None
    assert context.tenant_id==T and context.administrator_id==A
    assert context.session_id==S and context.challenge_id==C
    assert context.offer.document_id==D and context.offer.price_version_id==P
    assert context.offer.price_cents==19937
    assert context.offer.document_sha256=="a"*64
    assert context.source=="CI_SYNTHETIC_SERVER_DB_READBACK"
    assert context.offer.source=="CI_SYNTHETIC_SERVER_OFFER_READBACK"
    synthetic=AuthenticatedSession(
        str(A),"TENANT_ADMIN",str(T),"admin@example.invalid","CI",False,
        verified_session_id=str(S),
        verified_session_at=NOW-timedelta(seconds=1),
        verified_session_expires_at=context.session_expires_at,
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    principal=check_server_identity_binding(synthetic,context,now=NOW)
    assert principal is not None
    assert principal.source=="CI_SYNTHETIC_SERVER_AUTH_READBACK"
    assert principal.user_id==A
    assert review()==(state,context)


def test_annual_frozen_offer_uses_annual_cents():
    r=row()
    r["billing_period"]="ANNUAL"
    state,context=review(r)
    assert state=="CI_DISPOSABLE_SERVER_CONTEXT_READBACK_ONLY"
    assert context.offer.price_cents==199370
    assert context.offer.billing_period=="ANNUAL"


@pytest.mark.parametrize("field",[
    "session_id","tenant_id","admin_id","tenant_admin",
    "request_id","challenge_id","challenge_session","challenge_tenant",
    "challenge_admin","document_id","price_version_id","version_id",
])
def test_malformed_ids_rejected(field):
    r=row()
    r[field]=None
    assert_denied(review(r),"MALFORMED_CI_DATABASE_CONTEXT")


@pytest.mark.parametrize("field",[
    "session_id","tenant_id","admin_id","tenant_admin",
    "request_id","challenge_session","challenge_tenant",
    "challenge_admin","version_id",
])
def test_cross_scope_ids_rejected(field):
    r=row()
    r[field]=OTHER
    assert_denied(review(r),"CI_SCOPE_DOCUMENT_OR_PRICE_MISMATCH")


@pytest.mark.parametrize("field",[
    "session_active","email_verified","admin_membership_active",
])
def test_active_checks_deny_bool_subclasses_and_false(field):
    for value,expected in ((False,"CI_ADMIN_SESSION_NOT_ACTIVE"),
                           (1,"MALFORMED_CI_DATABASE_CONTEXT")):
        r=row()
        r[field]=value
        assert_denied(review(r),expected)


@pytest.mark.parametrize("field,value",[
    ("session_role","MASTER"),
    ("session_role","TENANT_MEMBER"),
    ("tenant_status","INATIVO"),
    ("admin_status","BLOCKED"),
])
def test_admin_readback_requires_current_roles_and_status(field,value):
    r=row()
    r[field]=value
    assert_denied(review(r),"CI_ADMIN_SESSION_NOT_ACTIVE")


@pytest.mark.parametrize("field,value",[
    ("document_kind","TENANT_MEMBERSHIP"),
    ("plan_status","INACTIVE"),
    ("plan_tier","UNKNOWN"),
    ("version_label",""),
    ("version_label"," bad "),
    ("billing_period","WEEKLY"),
])
def test_canonical_offer_requires_published_license(field,value):
    r=row()
    r[field]=value
    assert_denied(review(r),"CI_OFFER_NOT_PUBLISHED_OR_ACTIVE")


@pytest.mark.parametrize("field,value,reason",[
    ("published_sha","f"*64,"CI_SCOPE_DOCUMENT_OR_PRICE_MISMATCH"),
    ("document_sha","notsha","MALFORMED_CI_DATABASE_CONTEXT"),
    ("published_at",NOW+timedelta(hours=2),"CI_SESSION_OR_CHALLENGE_TIME_INVALID"),
    ("server_issued_at",NOW+timedelta(hours=2),"CI_SESSION_OR_CHALLENGE_TIME_INVALID"),
    ("server_expires_at",NOW-timedelta(seconds=1),"CI_SESSION_OR_CHALLENGE_TIME_INVALID"),
    ("challenge_expires_at",NOW-timedelta(minutes=5),"CI_SESSION_OR_CHALLENGE_TIME_INVALID"),
    ("challenge_expires_at",NOW+timedelta(minutes=10),"CI_SESSION_OR_CHALLENGE_TIME_INVALID"),
    ("server_issued_at",NOW-timedelta(days=2),"CI_SESSION_OR_CHALLENGE_TIME_INVALID"),
    ("published_at",datetime(2026,11,10),"MALFORMED_CI_DATABASE_CONTEXT"),
    ("server_expires_at","tomorrow","MALFORMED_CI_DATABASE_CONTEXT"),
])
def test_unpublished_expired_or_out_of_order_server_time(field,value,reason):
    r=row()
    r[field]=value
    assert_denied(review(r),reason)


@pytest.mark.parametrize("field,value",[
    ("monthly_price",Decimal("0")),
    ("monthly_price",Decimal("-1")),
    ("monthly_price",Decimal("12.345")),
    ("monthly_price",Decimal("NaN")),
    ("monthly_price",Decimal("Infinity")),
    ("monthly_price",1.0),
    ("annual_price",Decimal("1993.71")),
    ("annual_price",Decimal("0")),
    ("annual_price",None),
])
def test_invalid_frozen_price_never_confirmed(field,value):
    r=row()
    r[field]=value
    assert_denied(review(r),"CI_FROZEN_PRICE_INVALID")


@pytest.mark.parametrize("kwargs",[
    {"session_id":OTHER},
    {"tenant_id":OTHER},
    {"admin_id":OTHER},
    {"request_id":OTHER},
])
def test_query_scope_must_equal_row(kwargs):
    assert_denied(review(**kwargs),"CI_SCOPE_DOCUMENT_OR_PRICE_MISMATCH")


def test_missing_or_naive_checked_at_denied():
    assert_denied(review(None,checked_at=NOW.replace(tzinfo=None)),
                  "INVALID_CI_READBACK_INPUT")
    assert_denied(review({}),"MALFORMED_CI_DATABASE_CONTEXT")
    assert_denied(review("not-a-database-row"),"INVALID_CI_READBACK_INPUT")


@pytest.mark.parametrize("field",[
    "server_issued_at","server_expires_at",
    "challenge_issued_at","challenge_expires_at","published_at",
])
def test_naive_db_times_denied(field):
    r=row()
    r[field]=NOW.replace(tzinfo=None)
    assert_denied(review(r),"MALFORMED_CI_DATABASE_CONTEXT")


def test_sql_has_only_scoped_select_and_no_dynamic_interpolation():
    sql=READBACK_SQL
    assert sql.count("%s")==4
    assert "WHERE s.session_id=%s AND s.tenant_id=%s" in sql
    assert "AND s.admin_id=%s AND c.request_id=%s" in sql
    assert "LIMIT 2" in sql
    for token in ("INSERT ","UPDATE ","DELETE ","CREATE ","DROP ","TRUNCATE ","ALTER "):
        assert token not in sql.upper()
    for table in (
        "saas_preprep_sessions_m37458_ci",
        "saas_preprep_challenges_m37458_ci",
        "contract_documents",
        "platform_license_price_versions",
        "platform_license_plans",
        "memberships",
        "tenants",
        "users",
    ):
        assert table in sql


def _runner():
    root=Path(__file__).resolve().parents[2]
    script=root/"backend/scripts/aistudio_m37461_server_context_readback_ci.py"
    spec=importlib.util.spec_from_file_location("m37461",script)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module,script.read_text()


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"not-ci"},
    {"PGOPTIONS":"-c frcaixinha.saas_preprep_ci=0"},
])
def test_local_db_never_enters_disposable_runner(change):
    runner,_=_runner()
    assert runner.environment_allowed(dict(runner.EXPECTED_ENV))
    assert not runner.environment_allowed({**runner.EXPECTED_ENV,**change})


def test_runner_refuses_termux_without_db_connection(monkeypatch):
    runner,_=_runner()
    for k in runner.EXPECTED_ENV:
        monkeypatch.delenv(k,raising=False)
    assert runner.main()==1


def test_runner_confirms_no_money_and_read_only_sql():
    _,source=_runner()
    for required in (
        "default_transaction_read_only=on",
        "M37461_DISPOSABLE_SERVER_SESSION_AND_OFFER_READBACK=PASS",
        "M37461_ROLE_TENANT_REQUEST_ISOLATION=PASS",
        "M37461_BEARER_SESSION_IDENTITY=NOT_VERIFIED",
        "M37461_CONSENT_AND_LICENSE_REAL=OFF",
        "M37461_ORIGINAL_LOCAL_DATABASE=UNTOUCHED",
        "check_server_identity_binding",
    ):
        assert required in source
    for forbidden in (
        "INSERT INTO ","UPDATE public.","DELETE FROM ","CREATE TABLE ",
        "ALTER TABLE ","DROP TABLE ","APIRouter(",
    ):
        assert forbidden not in source
