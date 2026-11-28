"""M37466: post-commit historical consistency is NOT legal/production authority."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID
import importlib.util
import re

import pytest

from app.saas_post_commit_audit_ci import (
    POST_COMMIT_AUDIT_SQL,PostCommitAudit,audit_post_commit_ci,
)

NOW=datetime(2026,11,10,17,0,tzinfo=timezone.utc)
S=UUID("daba0000-0000-4000-8000-000000000664")
A=UUID("daba0000-0000-4000-8000-000000000001")
T=UUID("daba0000-0000-4000-8000-000000000010")
REQUEST=UUID("daba0000-0000-4000-8000-000000000675")
CHALLENGE=UUID("daba0000-0000-4000-8000-000000000674")
DOCUMENT=UUID("daba0000-0000-4000-8000-000000000030")
PRICE=UUID("daba0000-0000-4000-8000-000000000060")
OTHER=UUID("daba0000-0000-4000-8000-000000000099")
HEX="a"*64
ROOT=Path(__file__).resolve().parents[2]


def evidence(**changes):
    data=dict(
        challenge_id=CHALLENGE,request_id=REQUEST,session_id=S,
        tenant_id=T,admin_id=A,document_id=DOCUMENT,
        document_sha=HEX,price_version_id=PRICE,billing_period="MONTHLY",
        challenge_issued_at=NOW-timedelta(minutes=4),
        challenge_expires_at=NOW+timedelta(minutes=1),
        receipt_challenge=CHALLENGE,receipt_request=REQUEST,
        receipt_session=S,receipt_tenant=T,receipt_admin=A,
        receipt_document=DOCUMENT,receipt_sha=HEX,
        receipt_price_version=PRICE,receipt_period="MONTHLY",
        confirmation_text="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE",
        server_recorded_at=NOW-timedelta(minutes=3),
        evidence_source="CI_SYNTHETIC_NOT_LEGAL_CONSENT",
        draft_request=REQUEST,draft_challenge=CHALLENGE,
        draft_tenant=T,draft_admin=A,draft_document=DOCUMENT,
        draft_price_version=PRICE,draft_period="MONTHLY",
        server_prepared_at=NOW-timedelta(minutes=2),
        draft_status="CI_DRAFT_NO_PAYMENT",
        legal_consent_verified=False,payment_authorized=False,
        license_authorized=False,activation_authorized=False,
        fixture_session=S,fixture_tenant=T,fixture_admin=A,
        fixture_role="TENANT_ADMIN",fixture_session_active=True,
        fixture_email_verified=True,
        fixture_issued_at=NOW-timedelta(minutes=15),
        fixture_expires_at=NOW+timedelta(minutes=30),
        live_session=S,live_user=A,live_tenant=T,
        live_role="TENANT_ADMIN",
        live_revoked_at=NOW-timedelta(minutes=1),
        live_expires_at=NOW+timedelta(minutes=20),
        published_sha=HEX,document_kind="PLATFORM_LICENSE",
        published_at=NOW-timedelta(days=1),
        version_label="CI-VERSION-1",published_price_version=PRICE,
        plan_tier="ESSENCIAL",monthly_price=Decimal("199.37"),
        annual_price=Decimal("1993.70"),plan_status="ACTIVE",
        tenant_admin=A,tenant_status="ATIVO",
        admin_status="ACTIVE",is_master=False,
        admin_membership_active=True,
    )
    data.update(changes)
    return data


def evaluate(data=None,*,ids=None,now=NOW):
    ids=ids or {}
    return audit_post_commit_ci(
        evidence() if data is None else data,
        request_id=ids.get("request_id",REQUEST),
        tenant_id=ids.get("tenant_id",T),
        administrator_id=ids.get("administrator_id",A),
        session_id=ids.get("session_id",S),
        observed_at=now,
    )


def denied(result):
    assert type(result) is PostCommitAudit
    assert result.historical_consistency is False
    assert result.evidence_sha256 is None
    assert result.synthetic_record_count==0
    assert result.issuer_session_revoked is False
    assert not any((
        result.legal_consent_verified,result.real_identity_verified,
        result.payment_authorized,result.license_authorized,
        result.pix_authorized,result.activation_authorized,
        result.production_authorized,result.financial_writes_performed,
    ))


def test_valid_historical_post_commit_audit_is_not_any_real_permission():
    x=evaluate()
    assert x.state=="CI_POST_COMMIT_SYNTHETIC_HISTORY_CONSISTENT_NOT_AUTHORITY"
    assert x.historical_consistency is True
    assert x.issuer_session_revoked is True
    assert x.synthetic_record_count==3
    assert re.fullmatch("[0-9a-f]{64}",x.evidence_sha256)
    assert not any((
        x.legal_consent_verified,x.real_identity_verified,
        x.payment_authorized,x.license_authorized,x.pix_authorized,
        x.activation_authorized,x.production_authorized,
        x.financial_writes_performed,
    ))


def test_repeat_readback_digest_is_deterministic_not_signature():
    x=evaluate()
    y=evaluate()
    assert x.evidence_sha256==y.evidence_sha256
    assert x.state==y.state
    assert "NOT_AUTHORITY" in x.state


@pytest.mark.parametrize("field",[
    "challenge_id","request_id","session_id","tenant_id","admin_id",
    "document_id","price_version_id","receipt_challenge",
    "receipt_request","receipt_session","receipt_tenant","receipt_admin",
    "receipt_document","receipt_price_version","draft_request",
    "draft_challenge","draft_tenant","draft_admin","draft_document",
    "draft_price_version","fixture_session","fixture_tenant",
    "fixture_admin","live_session","live_user","live_tenant",
    "published_price_version","tenant_admin",
])
def test_cross_record_uuid_tamper_denied(field):
    denied(evaluate(evidence(**{field:OTHER})))


@pytest.mark.parametrize("field",[
    "challenge_id","request_id","session_id","tenant_id","admin_id",
    "document_id","price_version_id","receipt_challenge",
    "receipt_request","receipt_session","receipt_tenant","receipt_admin",
    "receipt_document","receipt_price_version","draft_request",
    "draft_challenge","draft_tenant","draft_admin","draft_document",
    "draft_price_version","fixture_session","fixture_tenant",
    "fixture_admin","live_session","live_user","live_tenant",
    "published_price_version","tenant_admin",
])
def test_null_or_nil_uuid_denied(field):
    for invalid in (None,UUID(int=0),str(OTHER)):
        denied(evaluate(evidence(**{field:invalid})))


@pytest.mark.parametrize("field",[
    "document_sha","receipt_sha","published_sha",
])
def test_wrong_document_digest_denied(field):
    for invalid in ("b"*64,"A"*64,"bad","",None):
        denied(evaluate(evidence(**{field:invalid})))


@pytest.mark.parametrize("field",[
    "billing_period","receipt_period","draft_period",
])
def test_wrong_or_unbound_billing_period_denied(field):
    denied(evaluate(evidence(**{field:"ANNUAL"})))
    denied(evaluate(evidence(**{field:"WEEKLY"})))


@pytest.mark.parametrize("field,invalid",[
    ("confirmation_text","AUTO_ACCEPT"),
    ("confirmation_text","ACEITO "),
    ("evidence_source","LEGAL_CONSENT_REAL"),
    ("draft_status","PENDING_PAYMENT"),
    ("fixture_role","MASTER"),
    ("fixture_role","TENANT_MEMBER"),
    ("live_role","MASTER"),
    ("document_kind","OTHER"),
    ("plan_tier","INEXISTENTE"),
    ("plan_status","INACTIVE"),
    ("tenant_status","INATIVO"),
    ("admin_status","BLOCKED"),
    ("version_label",""),
    ("version_label"," space"),
    ("version_label","x"*97),
])
def test_malformed_source_contract_or_role_denied(field,invalid):
    denied(evaluate(evidence(**{field:invalid})))


@pytest.mark.parametrize("field",[
    "legal_consent_verified","payment_authorized",
    "license_authorized","activation_authorized",
    "is_master",
])
def test_real_authority_flags_never_accepted(field):
    denied(evaluate(evidence(**{field:True})))
    denied(evaluate(evidence(**{field:1})))


@pytest.mark.parametrize("field",[
    "fixture_session_active","fixture_email_verified",
    "admin_membership_active",
])
def test_admin_claim_inconsistent_or_inactive(field):
    denied(evaluate(evidence(**{field:False})))
    denied(evaluate(evidence(**{field:None})))


@pytest.mark.parametrize("field,invalid",[
    ("fixture_issued_at",NOW-timedelta(minutes=1)),
    ("challenge_issued_at",NOW+timedelta(minutes=1)),
    ("challenge_expires_at",NOW-timedelta(minutes=4)),
    ("challenge_expires_at",NOW+timedelta(minutes=4)),
    ("server_recorded_at",NOW-timedelta(minutes=5)),
    ("server_recorded_at",NOW+timedelta(minutes=1)),
    ("server_recorded_at",NOW+timedelta(minutes=2)),
    ("server_prepared_at",NOW-timedelta(minutes=5)),
    ("server_prepared_at",NOW+timedelta(minutes=1)),
    ("live_revoked_at",NOW-timedelta(minutes=5)),
    ("live_revoked_at",NOW+timedelta(minutes=1)),
    ("fixture_expires_at",NOW-timedelta(minutes=3)),
    ("live_expires_at",NOW-timedelta(minutes=3)),
    ("published_at",NOW-timedelta(minutes=1)),
])
def test_invalid_time_order_denied(field,invalid):
    denied(evaluate(evidence(**{field:invalid})))


@pytest.mark.parametrize("field",[
    "fixture_issued_at","fixture_expires_at","challenge_issued_at",
    "challenge_expires_at","server_recorded_at","server_prepared_at",
    "live_revoked_at","live_expires_at","published_at",
])
def test_naive_or_null_datetime_denied(field):
    denied(evaluate(evidence(**{field:NOW.replace(tzinfo=None)})))
    denied(evaluate(evidence(**{field:None})))


@pytest.mark.parametrize("monthly,annual",[
    (Decimal("0"),Decimal("1993.70")),
    (Decimal("NaN"),Decimal("1993.70")),
    (Decimal("Infinity"),Decimal("1993.70")),
    (Decimal("-0.01"),Decimal("1993.70")),
    (Decimal("199.371"),Decimal("1993.70")),
    (Decimal("199.37"),Decimal("1993.71")),
    (Decimal("199.37"),Decimal("199.37")),
    (None,Decimal("1993.70")),
    (199.37,Decimal("1993.70")),
])
def test_frozen_published_price_fail_closed(monthly,annual):
    denied(evaluate(evidence(monthly_price=monthly,annual_price=annual)))


def test_annual_period_uses_published_version_and_is_historical():
    x=evidence(billing_period="ANNUAL",receipt_period="ANNUAL",
               draft_period="ANNUAL")
    result=evaluate(x)
    assert result.historical_consistency is True
    assert result.evidence_sha256!=evaluate().evidence_sha256
    assert not result.payment_authorized


@pytest.mark.parametrize("changed",[
    {"request_id":OTHER},{"tenant_id":OTHER},
    {"administrator_id":OTHER},{"session_id":OTHER},
])
def test_wrong_caller_ids_never_pass_even_with_consistent_db_row(changed):
    denied(evaluate(ids=changed))


def test_missing_and_malformed_rows_fail_closed():
    denied(evaluate({}))
    denied(evaluate(None,ids={"request_id":None}))
    denied(evaluate(evidence(),now=NOW.replace(tzinfo=None)))
    denied(evaluate(evidence(),now=NOW-timedelta(minutes=2)))
    d=evidence()
    d.pop("draft_status")
    denied(evaluate(d))


def test_readonly_query_uses_four_scopes_no_token_or_writes():
    sql=POST_COMMIT_AUDIT_SQL
    assert sql.count("%s")==4
    assert all(x in sql for x in (
        "c.request_id=%s","c.tenant_id=%s",
        "c.admin_id=%s","c.session_id=%s",
        "JOIN public.saas_preprep_receipts_m37458_ci r",
        "JOIN public.saas_preprep_drafts_m37458_ci d",
        "JOIN public.saas_preprep_sessions_m37458_ci f",
        "JOIN public.sessions s ON s.id=c.session_id",
        "JOIN public.contract_documents contract",
        "JOIN public.platform_license_price_versions v",
        "live_revoked_at","LIMIT 2",
    ))
    assert "token_hash" not in sql and "raw_bearer" not in sql
    for forbidden in ("INSERT ","UPDATE ","DELETE ","DROP ","ALTER ","TRUNCATE "):
        assert forbidden not in sql.upper()


def _script():
    p=ROOT/"backend/scripts/aistudio_m37466_post_commit_readback_ci.py"
    spec=importlib.util.spec_from_file_location("m37466",p)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj,p.read_text()


def test_termux_command_cannot_run_disposable_db_audit(monkeypatch):
    mod,_=_script()
    for k in mod.CI_ENV:
        monkeypatch.delenv(k,raising=False)
    assert mod.main()==1
    assert not mod.environment_allowed({})


@pytest.mark.parametrize("bad",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},{"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},{"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"wrong"},
    {"PGOPTIONS":"-c frcaixinha.saas_atomic_ci=0"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_LICENSE_REAL":"ON"},
])
def test_ci_connection_allowlist(bad):
    mod,_=_script()
    assert mod.environment_allowed(dict(mod.CI_ENV))
    assert not mod.environment_allowed({**mod.CI_ENV,**bad})


def test_postcommit_script_is_readonly_and_guards_original_db():
    mod,s=_script()
    for marker in (
        "default_transaction_read_only=on",
        "POST_COMMIT_AUDIT_SQL",
        "M37466_POST_COMMIT_HISTORICAL_READBACK=PASS",
        "M37466_REVOKED_SESSION_HISTORY_IMMUTABLE=PASS",
        "M37466_APPEND_ONLY_TRIGGERS=PASS",
        "M37466_CROSS_TENANT_AND_REQUEST_READBACK=DENIED",
        "M37466_POSTGRESQL_TRANSACTION=READ_ONLY",
        "M37466_LICENSE_PAYMENT_PIX_ACTIVATION=OFF",
        "M37466_TERMUX_ORIGINAL_DATABASE=UNTOUCHED",
        "pg_trigger","has_table_privilege",
    ):
        assert marker in s
    for forbidden in (
        "INSERT INTO public.","UPDATE public.","DELETE FROM public.",
        "CREATE TABLE","DROP DATABASE","ALTER TABLE",
    ):
        assert forbidden not in s
    assert len(mod.GUARD_TRIGGER_NAMES)==6


def test_ci_staging_orders_postcommit_after_atomic_lock_before_next_stage():
    script=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "python backend/scripts/aistudio_m37466_post_commit_readback_ci.py" in script
    assert (script.index("python backend/scripts/aistudio_m37464_atomic_consent_ci.py")
            < script.index("python backend/scripts/aistudio_m37466_post_commit_readback_ci.py")
            < script.index("M37461: servidor PostgreSQL"))
    assert "m37466_post_commit_readback_ci.py" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()
