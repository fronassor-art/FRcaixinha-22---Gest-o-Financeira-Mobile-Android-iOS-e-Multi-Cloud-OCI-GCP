"""M37468 — historical frozen quote/receipt readback must never grant rights."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID
import importlib.util
import re

import pytest

from app.saas_frozen_receipt_audit_ci import (
    FROZEN_RECEIPT_AUDIT_SQL,
    HistoricalReceiptEvidenceCI,
    historical_receipt_view_ci,
    verify_frozen_receipt_ci,
)

ROOT=Path(__file__).resolve().parents[2]
NOW=datetime(2026,11,10,17,0,tzinfo=timezone.utc)
REQUEST=UUID("daba0000-0000-4000-8000-000000000675")
ADMIN=UUID("daba0000-0000-4000-8000-000000000001")
TENANT=UUID("daba0000-0000-4000-8000-000000000010")
SESSION=UUID("daba0000-0000-4000-8000-000000000664")
OTHER=UUID("daba0000-0000-4000-8000-000000000699")
ENV=dict(GITHUB_ACTIONS="true",FRCAIXINHA_CI_ISOLATED="1",
         ENVIRONMENT="ci",FR_FINANCE_SAAS_REAL="OFF",
         FR_FINANCE_PIX_REAL="OFF",FR_FINANCE_LICENSE_REAL="OFF")


def _baseline():
    # Reuse the previously homologated M37466 historical contract fixture.
    path=ROOT/"backend/tests/test_m37466_post_commit_audit_ci.py"
    spec=importlib.util.spec_from_file_location("m37466fixture_for_m37468",path)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evidence()


def evidence(**changes):
    row=_baseline()
    row.update({
        "frozen_request_id":row["request_id"],
        "frozen_challenge_id":row["challenge_id"],
        "frozen_session_id":row["session_id"],
        "frozen_tenant_id":row["tenant_id"],
        "frozen_admin_id":row["admin_id"],
        "frozen_document_id":row["document_id"],
        "frozen_document_sha":row["document_sha"],
        "frozen_price_version_id":row["price_version_id"],
        "frozen_billing_period":row["billing_period"],
        "frozen_price_cents":19937,
        "frozen_recorded_at":NOW-timedelta(minutes=3,seconds=30),
        "frozen_evidence_source":"CI_FROZEN_SYNTHETIC_NOT_LEGAL",
    })
    row.update(changes)
    return row


def evaluate(row=None,*,now=NOW,ids=None):
    ids=ids or {}
    return verify_frozen_receipt_ci(
        evidence() if row is None else row,
        request_id=ids.get("request_id",REQUEST),
        tenant_id=ids.get("tenant_id",TENANT),
        administrator_id=ids.get("administrator_id",ADMIN),
        session_id=ids.get("session_id",SESSION),
        observed_at=now,
    )


def denied(r):
    assert type(r) is HistoricalReceiptEvidenceCI
    assert not r.historical_consistency
    assert not r.frozen_offer_consistent
    assert not r.issuer_session_revoked
    assert r.synthetic_record_count==0
    assert r.diagnostic_sha256 is None
    assert r.historical_price_cents is None
    assert not any((
        r.real_identity_verified,r.legal_consent_verified,
        r.payment_authorized,r.license_authorized,r.pix_authorized,
        r.activation_authorized,r.production_authorized,
        r.real_writes_performed,
    ))


def test_four_records_consistent_but_never_production_authority():
    r=evaluate()
    assert r.state=="CI_FROZEN_RECEIPT_HISTORY_CONSISTENT_NOT_AUTHORITY"
    assert r.historical_consistency
    assert r.frozen_offer_consistent
    assert r.issuer_session_revoked
    assert r.synthetic_record_count==4
    assert r.historical_price_cents==19937
    assert re.fullmatch("[0-9a-f]{64}",r.diagnostic_sha256)
    assert not r.real_identity_verified
    assert not r.legal_consent_verified
    assert not r.payment_authorized
    assert not r.license_authorized
    assert not r.pix_authorized
    assert not r.activation_authorized
    assert not r.production_authorized
    assert not r.real_writes_performed


def test_digest_is_deterministic_and_not_signed():
    a,b=evaluate(),evaluate()
    assert a==b and a.diagnostic_sha256==b.diagnostic_sha256
    assert "NOT_AUTHORITY" in a.state


def test_server_only_view_exposes_no_session_token_or_authorization():
    r=evaluate()
    view=historical_receipt_view_ci(r,env=ENV)
    assert view["state"]==r.state
    assert view["kind"]=="CI_SYNTHETIC_HISTORICAL_ONLY"
    assert view["historical_price_cents"]==19937
    assert view["real_authorization"] is False
    assert view["synthetic_record_count"]==4
    assert set(view)=={
        "state","kind","synthetic_record_count","diagnostic_sha256",
        "historical_price_cents","real_authorization",
    }


@pytest.mark.parametrize("field",[
    "frozen_request_id","frozen_challenge_id","frozen_session_id",
    "frozen_tenant_id","frozen_admin_id","frozen_document_id",
    "frozen_price_version_id",
])
@pytest.mark.parametrize("invalid",[OTHER,None,UUID(int=0),str(OTHER)])
def test_frozen_scope_fields_must_match_historical_records(field,invalid):
    denied(evaluate(evidence(**{field:invalid})))


@pytest.mark.parametrize("field",[
    "frozen_document_sha","frozen_billing_period","frozen_evidence_source",
])
@pytest.mark.parametrize("invalid",[
    None,True,"", "b"*64,"A"*64, "CI_LEGAL_CONSENT_REAL",
])
def test_frozen_document_period_or_evidence_tampering_denied(field,invalid):
    denied(evaluate(evidence(**{field:invalid})))


@pytest.mark.parametrize("invalid",[
    -1,0,1,19936,19938,199370,2**64,True,False,None,
    "19937",Decimal("199.37"),19937.0,
])
def test_price_cents_must_match_exact_published_amount(invalid):
    denied(evaluate(evidence(frozen_price_cents=invalid)))


@pytest.mark.parametrize("invalid",[
    NOW-timedelta(minutes=5),
    NOW-timedelta(minutes=2),
    NOW-timedelta(minutes=1),
    NOW+timedelta(seconds=1),
    NOW.replace(tzinfo=None),
    None,"2026-11-10T16:56:30+00:00",
])
def test_frozen_snapshot_chronology_cannot_be_forged(invalid):
    denied(evaluate(evidence(frozen_recorded_at=invalid)))


@pytest.mark.parametrize("changed",[
    {"receipt_sha":"b"*64},
    {"document_sha":"b"*64},
    {"published_sha":"b"*64},
    {"receipt_period":"ANNUAL"},
    {"draft_period":"ANNUAL"},
    {"live_revoked_at":NOW-timedelta(minutes=5)},
    {"live_revoked_at":None},
    {"payment_authorized":True},
    {"license_authorized":True},
    {"legal_consent_verified":True},
    {"activation_authorized":True},
    {"confirmation_text":"AUTOMATICO"},
    {"evidence_source":"LEGAL_CONSENT"},
    {"published_price_version":OTHER},
    {"monthly_price":Decimal("199.38")},
    {"annual_price":Decimal("1993.71")},
])
def test_original_receipt_and_contract_must_also_remain_valid(changed):
    denied(evaluate(evidence(**changed)))


def test_annual_frozen_amount_validates_exactly_ten_times_monthly():
    row=evidence(billing_period="ANNUAL",receipt_period="ANNUAL",
                 draft_period="ANNUAL",frozen_billing_period="ANNUAL",
                 frozen_price_cents=199370)
    r=evaluate(row)
    assert r.historical_consistency
    assert r.historical_price_cents==199370
    assert r.diagnostic_sha256!=evaluate().diagnostic_sha256
    denied(evaluate(dict(row,frozen_price_cents=19937)))


@pytest.mark.parametrize("scope",[
    {"request_id":OTHER},
    {"tenant_id":OTHER},
    {"administrator_id":OTHER},
    {"session_id":OTHER},
    {"request_id":None},
])
def test_caller_cannot_swap_server_ids(scope):
    denied(evaluate(ids=scope))


def test_missing_or_untyped_database_evidence_denied():
    denied(evaluate({}))
    denied(evaluate("anything"))
    r=evidence()
    r.pop("frozen_price_version_id")
    denied(evaluate(r))
    denied(evaluate(evidence(),now=NOW.replace(tzinfo=None)))
    denied(evaluate(evidence(),now=NOW-timedelta(minutes=2)))


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"ENVIRONMENT":"production"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FR_FINANCE_LICENSE_REAL":"ON"},
])
def test_historical_view_unavailable_in_any_real_environment(change):
    r=evaluate()
    view=historical_receipt_view_ci(r,env={**ENV,**change})
    assert view=={"state":"CI_HISTORICAL_READBACK_UNAVAILABLE"}


@pytest.mark.parametrize("field",[
    "legal_consent_verified","real_identity_verified",
    "payment_authorized","license_authorized","pix_authorized",
    "activation_authorized","production_authorized",
    "real_writes_performed",
])
def test_historical_view_denies_any_injected_authorization_flag(field):
    view=historical_receipt_view_ci(
        replace(evaluate(),**{field:True}),env=ENV,
    )
    assert view=={"state":"CI_HISTORICAL_READBACK_UNAVAILABLE"}


def test_query_joins_all_four_records_and_has_no_write_operations():
    sql=FROZEN_RECEIPT_AUDIT_SQL
    assert sql.count("%s")==4
    assert "FROM (" in sql and "JOIN public.saas_frozen_offer_m37467_ci q" in sql
    assert all(x in sql for x in (
        "q.request_id=h.request_id","q.challenge_id=h.challenge_id",
        "q.session_id=h.session_id","q.tenant_id=h.tenant_id",
        "q.admin_id=h.admin_id","q.document_id=h.document_id",
        "q.document_sha=h.document_sha","q.price_version_id=h.price_version_id",
        "q.billing_period=h.billing_period","LIMIT 2",
        "JOIN public.saas_preprep_receipts_m37458_ci r",
        "JOIN public.saas_preprep_drafts_m37458_ci d",
        "JOIN public.sessions s ON s.id=c.session_id",
    ))
    assert "token_hash" not in sql and "raw_bearer" not in sql
    for x in ("INSERT ","UPDATE ","DELETE ","DROP ","TRUNCATE ","ALTER "):
        assert x not in sql.upper()


def load_runner():
    p=ROOT/"backend/scripts/aistudio_m37468_frozen_receipt_readback_ci.py"
    spec=importlib.util.spec_from_file_location("m37468",p)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj,p.read_text()


def test_runner_rejects_termux_and_non_github(monkeypatch):
    mod,_=load_runner()
    for k in mod.CI_ENV:
        monkeypatch.delenv(k,raising=False)
    assert mod.main()==1
    assert mod.allowed(dict(mod.CI_ENV))
    assert not mod.allowed({})


@pytest.mark.parametrize("bad",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"not-test"},
    {"PGOPTIONS":"-c frcaixinha.saas_frozen_ci=0"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_LICENSE_REAL":"ON"},
])
def test_runner_disposable_allowlist(bad):
    mod,_=load_runner()
    assert not mod.allowed({**mod.CI_ENV,**bad})


def test_runner_guards_readonly_trigger_rls_and_scope():
    mod,source=load_runner()
    for item in (
        "default_transaction_read_only=on",
        "FROZEN_RECEIPT_AUDIT_SQL",
        "M37468_FROZEN_OFFER_TO_RECEIPT_READBACK=PASS",
        "M37468_DOCUMENT_HASH_PRICE_VERSION_CENTS=PASS",
        "M37468_CROSS_SCOPE_HISTORICAL_READBACK=DENIED",
        "M37468_RLS_APPEND_ONLY=PASS",
        "M37468_POSTGRESQL_READ_ONLY=PASS",
        "M37468_DIGEST=DIAGNOSTIC_NOT_SIGNATURE",
        "M37468_REAL_IDENTITY_AND_LEGAL_CONSENT=NOT_ATTESTED",
        "M37468_PAYMENT_LICENSE_PIX_ACTIVATION=OFF",
        "M37468_TERMUX_ORIGINAL_DATABASE=UNTOUCHED",
        "pg_trigger","relrowsecurity","relforcerowsecurity",
    ):
        assert item in source
    for forbidden in ("INSERT INTO public.","UPDATE public.","DELETE FROM public.",
                      "DROP DATABASE","CREATE TABLE","ALTER TABLE"):
        assert forbidden not in source
    assert len(mod.TABLES)==4 and len(mod.FROZEN_TRIGGERS)==2


def test_staging_chain_orders_m37468_post_frozen_contract_commit():
    s=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "aistudio_m37468_frozen_receipt_readback_ci.py" in s
    assert (s.index("aistudio_m37467_frozen_offer_ci.py")
            < s.index("aistudio_m37468_frozen_receipt_readback_ci.py")
            < s.index("M37461: servidor PostgreSQL"))
    assert "aistudio_m37468_frozen_receipt_readback_ci.py" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()
