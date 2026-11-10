"""M37453: fail-closed persisted staging SaaS readback, no live acceptance."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from app.saas_disposable_checkout_readback_ci import (
    READBACK_SQL, evaluate_disposable_readback,
)

T = UUID("daba0000-0000-4000-8000-000000000010")
A = UUID("daba0000-0000-4000-8000-000000000001")
R = UUID("daba0000-0000-4000-8000-000000000050")
P = UUID("daba0000-0000-4000-8000-000000000051")
D = UUID("daba0000-0000-4000-8000-000000000030")
C = UUID("daba0000-0000-4000-8000-000000000040")
V = UUID("daba0000-0000-4000-8000-000000000060")
OTHER = UUID("daba0000-0000-4000-8000-000000000099")
NOW = datetime(2026, 11, 10, 16, 0, tzinfo=timezone.utc)


def row():
    return {
        "request_id":R,"tenant_id":T,"admin_user_id":A,
        "price_version_id":V,"contract_acceptance_id":C,"preparation_id":P,
        "billing_period":"MONTHLY","payment_created":False,
        "entitlement_created":False,
        "prepared_tenant":T,"prepared_admin":A,"prepared_price":V,
        "prepared_acceptance":C,"prepared_period":"MONTHLY",
        "prepared_tier":"ESSENCIAL","preparation_status":"PENDING_PAYMENT",
        "prepared_at":NOW-timedelta(hours=1),
        "accepted_document_id":D,"accepted_by":A,"accepted_tenant":None,
        "accepted_kind":"PLATFORM_LICENSE",
        "accepted_at":NOW-timedelta(hours=2),
        "evidence_method":"CI_VERIFIED_IDENTITY","evidence_hash":"b"*64,
        "published_document_id":D,"published_kind":"PLATFORM_LICENSE",
        "published_at":NOW-timedelta(days=2),"published_sha":"a"*64,
        "version_id":V,"version_tier":"ESSENCIAL",
        "monthly_price":Decimal("199.37"),
        "annual_price":Decimal("1993.70"),
        "plan_tier":"ESSENCIAL","plan_status":"ACTIVE",
        "tenant_admin":A,"tenant_status":"ATIVO",
        "admin_status":"ACTIVE","admin_membership_active":True,
        "payment_count":0,"license_count":0,"tenant_ledger_entries":0,
    }


def result(**changes):
    data=row()
    data.update(changes)
    return evaluate_disposable_readback(
        data, request_id=R, tenant_id=T, admin_id=A, now=NOW)


def deny_real(x):
    assert x.published_contract_operationally_verified is False
    assert x.explicit_consent_operationally_verified is False
    assert x.payment_verified is False
    assert x.license_activated is False
    assert x.member_activated is False
    assert x.pix_authorized is False
    assert x.production_authorized is False
    assert x.writes_performed is False


def test_ci_preparation_does_not_activate_or_claim_contract():
    x=result()
    assert x.state=="CI_PERSISTED_PREPARATION_REVIEW_ONLY"
    assert x.structure_consistent_in_ci is True
    assert result()==x
    deny_real(x)


def test_monthly_and_annual_versions_are_immutable_evidence_only():
    x=result(billing_period="ANNUAL",prepared_period="ANNUAL")
    assert x.structure_consistent_in_ci
    deny_real(x)


@pytest.mark.parametrize("field,value,state",[
 ("request_id",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("tenant_id",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("admin_user_id",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("prepared_tenant",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("prepared_admin",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("tenant_admin",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("accepted_by",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("prepared_price",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("version_id",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("prepared_acceptance",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("published_document_id",OTHER,"CROSS_SCOPE_OR_VERSION_MISMATCH"),
 ("accepted_tenant",T,"CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("accepted_kind","TENANT_MEMBERSHIP","CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("published_kind","TENANT_MEMBERSHIP","CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("published_at",None,"CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("published_at",NOW,"CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("accepted_at",NOW+timedelta(days=1),"CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("accepted_at",datetime(2026,11,10),"CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("evidence_method","PROVIDER_VERIFIED","CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("evidence_hash","xyz","CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("published_sha","0"*63,"CONTRACT_RECORD_NOT_CONSISTENT_IN_CI"),
 ("tenant_status","SUSPENSO","TENANT_ADMIN_INACTIVE"),
 ("admin_status","BLOCKED","TENANT_ADMIN_INACTIVE"),
 ("admin_membership_active",1,"TENANT_ADMIN_INACTIVE"),
 ("billing_period","WEEKLY","INVALID_PLAN_OR_PREPARATION"),
 ("prepared_period","ANNUAL","INVALID_PLAN_OR_PREPARATION"),
 ("prepared_tier","INTERMEDIARIO","INVALID_PLAN_OR_PREPARATION"),
 ("version_tier","INTERMEDIARIO","INVALID_PLAN_OR_PREPARATION"),
 ("plan_status","BLOCKED_PENDING_CEILING","INVALID_PLAN_OR_PREPARATION"),
 ("preparation_status","CANCELED","INVALID_PLAN_OR_PREPARATION"),
 ("monthly_price",Decimal("NaN"),"INVALID_FROZEN_PRICE_VERSION"),
 ("monthly_price",Decimal("199.371"),"INVALID_FROZEN_PRICE_VERSION"),
 ("monthly_price",199.37,"INVALID_FROZEN_PRICE_VERSION"),
 ("annual_price",Decimal("1993.71"),"INVALID_FROZEN_PRICE_VERSION"),
 ("payment_created",True,"FINANCIAL_OR_ENTITLEMENT_RECORD_PRESENT"),
 ("entitlement_created",True,"FINANCIAL_OR_ENTITLEMENT_RECORD_PRESENT"),
 ("payment_count",1,"FINANCIAL_OR_ENTITLEMENT_RECORD_PRESENT"),
 ("license_count",1,"FINANCIAL_OR_ENTITLEMENT_RECORD_PRESENT"),
 ("tenant_ledger_entries",1,"FINANCIAL_OR_ENTITLEMENT_RECORD_PRESENT"),
 ("payment_count",True,"FINANCIAL_OR_ENTITLEMENT_RECORD_PRESENT"),
])
def test_any_inconsistent_persisted_evidence_fails_closed(field,value,state):
    x=result(**{field:value})
    assert x.state==state
    assert not x.structure_consistent_in_ci
    deny_real(x)


@pytest.mark.parametrize("case", [None, {}, 22, "fake"])
def test_incomplete_or_non_database_records_denied(case):
    x=evaluate_disposable_readback(
        case, request_id=R, tenant_id=T, admin_id=A, now=NOW)
    assert x.state in ("NO_SINGLE_DATABASE_RECORD","MALFORMED_DATABASE_IDENTIFIERS")
    deny_real(x)


def test_wrong_caller_scope_and_naive_time_denied():
    for kwargs in (
        {"request_id":OTHER}, {"tenant_id":OTHER}, {"admin_id":OTHER},
        {"now":NOW.replace(tzinfo=None)}, {"request_id":str(R)},
    ):
        params=dict(request_id=R,tenant_id=T,admin_id=A,now=NOW)
        params.update(kwargs)
        x=evaluate_disposable_readback(row(),**params)
        assert x.state!="CI_PERSISTED_PREPARATION_REVIEW_ONLY"
        deny_real(x)


def test_query_is_binded_join_and_read_only():
    sql=READBACK_SQL.lower()
    for s in (
        "from public.saas_enrollment_requests_staging",
        "join public.saas_subscription_preparations",
        "join public.contract_acceptances",
        "join public.contract_documents",
        "join public.platform_license_price_versions",
        "join public.platform_license_plans",
        "join public.tenants",
        "join public.users",
        "from public.memberships",
        "from public.saas_payment_intents",
        "from public.saas_license_entitlements",
        "from public.ledger_entries",
        "where e.request_id=%s and e.tenant_id=%s and e.admin_user_id=%s",
        "limit 2",
    ):
        assert s in sql
    assert sql.count("%s")==3
    for forbidden in ("insert into", "update ", "delete ", "truncate ",
                      "create ", "drop ", "alter ", "grant ", "execute "):
        assert forbidden not in sql


def test_script_fail_closed_and_staging_chain_only():
    root=Path(__file__).resolve().parents[2]
    code=(root/"backend/scripts/aistudio_m37453_disposable_saas_readback.py").read_text()
    chain=(root/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "default_transaction_read_only=on" in code
    assert "GITHUB_ACTIONS" in code and "FRCAIXINHA_CI_ISOLATED" in code
    assert "frcaixinha_staging" in code and '"PGPORT": "5432"' in code
    assert "M37453_CI_STAGING_READBACK=PASS" in code
    assert "aistudio_m37453_disposable_saas_readback.py" in chain
    for forbidden in ("DROP DATABASE", "CREATE DATABASE", "INSERT INTO",
                      "UPDATE public.", "DELETE FROM", "TRUNCATE "):
        assert forbidden not in code


def test_isolation_guard_without_network():
    import importlib.util
    root=Path(__file__).resolve().parents[2]
    path=root/"backend/scripts/aistudio_m37453_disposable_saas_readback.py"
    spec=importlib.util.spec_from_file_location("m37453_ci_script",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not module.environment_allowed({})
    assert not module.environment_allowed({"GITHUB_ACTIONS":"true"})
    assert not module.environment_allowed({
        **module.EXPECTED_ENV, "PGDATABASE":"frcaixinha_aistudio_dev"})
    assert not module.environment_allowed({
        **module.EXPECTED_ENV, "PGPORT":"5433"})
    assert module.environment_allowed(dict(module.EXPECTED_ENV))
