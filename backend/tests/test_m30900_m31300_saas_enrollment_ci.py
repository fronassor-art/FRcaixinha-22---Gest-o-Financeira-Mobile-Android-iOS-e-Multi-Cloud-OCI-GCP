"""FR Finance M30900-M31300: SaaS enrollment and strict zero-grace gates."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID
import pytest

from app.saas_contract_gate import SaaSReadinessSnapshot,evaluate_saas_readiness
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/staging_migrations/059_saas_enrollment_staging_only.sql").read_text()
CI=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
NOW=datetime(2027,3,8,12,tzinfo=timezone.utc)

def valid_snapshot():
    t=UUID("daba0000-0000-4000-8000-000000000010")
    return SaaSReadinessSnapshot(
      tenant_id=t,preparation_tenant_id=t,payment_tenant_id=t,entitlement_tenant_id=t,
      administrator_active=True,admin_membership_active=True,tenant_status="ATIVO",
      published_contract_sha="a"*64,accepted_contract_sha="a"*64,
      offer_plan_tier="ESSENCIAL",entitlement_plan_tier="ESSENCIAL",
      plan_status="ACTIVE",payment_status="APPROVED",provider_readback_confirmed=True,
      provider_collector_id="123456",platform_collector_id="123456",
      currency="BRL",chargeback_or_refund=False,entitlement_status="ACTIVE",
      valid_from=NOW-timedelta(days=1),valid_until=NOW+timedelta(days=1),
      checked_at=NOW,members_count=20,quotas_count=40,
      members_limit=20,quotas_limit=40)

def test_inclusive_capacity_and_staging_only():
    x=evaluate_saas_readiness(valid_snapshot())
    assert x.state=="STAGING_PREFLIGHT_ONLY"
    assert x.staging_preflight_eligible is True
    assert not any((x.real_registration_authorized,x.real_billing_authorized,
                    x.real_pix_authorized,x.tenant_ledger_write_authorized,
                    x.production_release_authorized))

@pytest.mark.parametrize("changes,expected",[
 ({"source":"USER_HTTP_PAYLOAD"},"UNTRUSTED_EVIDENCE"),
 ({"payment_tenant_id":UUID("daba0000-0000-4000-8000-000000000020")},"TENANT_CROSS_SCOPE"),
 ({"tenant_status":"SUSPENSO"},"TENANT_OR_ADMIN_INACTIVE"),
 ({"administrator_active":False},"TENANT_OR_ADMIN_INACTIVE"),
 ({"admin_membership_active":False},"TENANT_OR_ADMIN_INACTIVE"),
 ({"accepted_contract_sha":"b"*64},"CONTRACT_VERSION_UNVERIFIED"),
 ({"offer_plan_tier":"AMPLIADO","entitlement_plan_tier":"AMPLIADO",
   "plan_status":"BLOCKED_PENDING_CEILING"},"PLAN_UNAPPROVED_OR_UNCAPPED"),
 ({"members_limit":None},"PLAN_UNAPPROVED_OR_UNCAPPED"),
 ({"quotas_limit":None},"PLAN_UNAPPROVED_OR_UNCAPPED"),
 ({"members_count":21},"PLAN_CAPACITY_EXCEEDED"),
 ({"quotas_count":41},"PLAN_CAPACITY_EXCEEDED"),
 ({"payment_status":"PENDING"},"PROVIDER_PAYMENT_NOT_ATTESTED"),
 ({"provider_readback_confirmed":False},"PROVIDER_PAYMENT_NOT_ATTESTED"),
 ({"provider_collector_id":"999"},"PROVIDER_PAYMENT_NOT_ATTESTED"),
 ({"currency":"USD"},"PROVIDER_PAYMENT_NOT_ATTESTED"),
 ({"chargeback_or_refund":True},"REFUND_OR_CHARGEBACK_HOLD"),
 ({"entitlement_status":"SUSPENDED"},"LICENSE_NOT_ACTIVE"),
 ({"checked_at":NOW-timedelta(days=2)},"LICENSE_NOT_STARTED"),
 ({"checked_at":NOW+timedelta(days=1)},"LICENSE_EXPIRED_ZERO_GRACE"),
 ({"checked_at":NOW+timedelta(days=2)},"LICENSE_EXPIRED_ZERO_GRACE"),
])
def test_every_release_risk_fails_closed(changes,expected):
    x=evaluate_saas_readiness(replace(valid_snapshot(),**changes))
    assert x.state==expected
    assert x.staging_preflight_eligible is False
    assert not x.production_release_authorized and not x.real_billing_authorized

@pytest.mark.parametrize("changes",[
 {"members_count":True},{"quotas_count":-1},{"members_limit":0},
 {"checked_at":datetime(2027,3,8)},{"valid_from":NOW+timedelta(days=2)}
])
def test_invalid_snapshot_not_auto_cured(changes):
    with pytest.raises(ValueError,match="INVALID_SAAS_READINESS_SNAPSHOT"):
        evaluate_saas_readiness(replace(valid_snapshot(),**changes))

@pytest.mark.parametrize("required",[
 "M30900_DISPOSABLE_CI_ONLY","M30900_CI_ROLE_DENIED",
 "frcaixinha_staging","frcaixinha_saas_enroll_ci",
 "FOR UPDATE","FORCE ROW LEVEL SECURITY",
 "a.document_kind='PLATFORM_LICENSE'","d.published_at IS NOT NULL",
 "a.user_id=p_admin","m.role='TENANT_ADMIN'","p.status","REPLAY_CI_NO_PAYMENT",
 "EXISTING_PREPARATION_REQUIRES_REVIEW","M30900_APPEND_ONLY_CI",
 "PREPARED_CI_NO_PAYMENT","real_pix_enabled',false",
])
def test_staging_sql_guards(required):
    assert required in SQL
def test_catalog_and_pipeline_declared():
    assert "059_saas_enrollment_staging_only.sql" in CI
    assert "058_saas_enrollment_fixture_ci_only.sql" in CI
    assert "M31300_SAAS_ENROLLMENT_POSTGRES=PASS" in CI
    assert "CREATE ROLE frcaixinha_saas_enroll_ci" in CI
    assert "GRANT INSERT ON public.saas_enrollment_requests_staging" not in SQL
    assert "GRANT SELECT ON public.saas_enrollment_requests_staging" not in SQL
def test_no_real_api_call_or_tenant_ledger_write():
    s=(ROOT/"backend/app/saas_contract_gate.py").read_text()
    assert "INSERT INTO" not in s and "UPDATE public." not in s
    routes=(ROOT/"backend/app/platform_provider_adapters.py").read_text()
    assert "DESLIGADOS por padrão" in routes
