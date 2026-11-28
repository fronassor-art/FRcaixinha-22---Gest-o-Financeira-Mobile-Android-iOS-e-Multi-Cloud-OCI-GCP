"""M31400-M31800: capacity reservations + SaaS lifecycle policy, CI-only."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID
import pytest
from app.saas_change_policy import SaaSChangeSnapshot,review_saas_change

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/staging_migrations/060_saas_capacity_staging_only.sql").read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
T=UUID("daba0000-0000-4000-8000-000000000010")
ADMIN=UUID("daba0000-0000-4000-8000-000000000001")
REVIEW=UUID("daba0000-0000-4000-8000-000000000002")
NOW=datetime(2027,4,12,tzinfo=timezone.utc)

def snapshot(**change):
    x=SaaSChangeSnapshot(
      action="RENEW_PREPARE",tenant_id=T,current_entitlement_tenant_id=T,
      actor_id=ADMIN,tenant_admin_id=ADMIN,reviewer_id=REVIEW,
      actor_role="TENANT_ADMIN",current_status="ACTIVE",
      current_plan_tier="ESSENCIAL",proposed_plan_tier="INTERMEDIARIO",
      proposed_plan_active=True,
      proposal_price_version_id=UUID("daba0000-0000-4000-8000-000000000050"),
      current_price_version_id=UUID("daba0000-0000-4000-8000-000000000051"),
      acceptance_sha256="a"*64,offer_sha256="a"*64,
      current_valid_until=NOW+timedelta(days=3),checked_at=NOW,
      current_member_count=20,current_quota_count=35,
      held_member_count=0,held_quota_count=0,
      proposed_members_limit=50,proposed_quotas_limit=50,
      pending_action=False,refund_or_chargeback=False,
      provider_verified=True,independent_approval=True,
      reason="Pedido de revisão de assinatura homologação",
    )
    return replace(x,**change)

@pytest.mark.parametrize("action,changes,state",[
 ("RENEW_PREPARE",{},"RENEWAL_REVIEW_ONLY"),
 ("UPGRADE_PREPARE",{},"UPGRADE_REVIEW_ONLY"),
 ("CANCEL_AT_END",{},"CANCEL_REVIEW_NO_REFUND"),
 ("RESUME_REVIEW",{"actor_role":"MASTER","current_status":"SUSPENDED"},
  "RESUME_REVIEW_NO_ENTITLEMENT_WRITE"),
 ("REFUND_REVIEW",{"actor_role":"MASTER","refund_or_chargeback":True},
  "REFUND_REVIEW_NO_MONEY_MOVED"),
])
def test_positive_review_never_authorizes_operation(action,changes,state):
    d=review_saas_change(snapshot(action=action,**changes))
    assert d.state==state and d.review_candidate
    assert not any((d.persisted,d.real_charge_authorized,
                    d.real_entitlement_mutation_authorized,d.real_pix_authorized,
                    d.tenant_ledger_write_authorized,d.production_authorized))

@pytest.mark.parametrize("changes,state",[
 ({"source":"HTTP_USER"},"UNTRUSTED_SOURCE"),
 ({"current_entitlement_tenant_id":REVIEW},"TENANT_SCOPE_MISMATCH"),
 ({"pending_action":True},"EXISTING_ACTION_PENDING"),
 ({"current_status":"DRAFT"},"UNKNOWN_LICENSE_STATE"),
 ({"reason":"short"},"AUDIT_REASON_MISSING"),
 ({"action":"UNKNOWN"},"UNKNOWN_ACTION"),
 ({"actor_id":REVIEW},"ACTOR_NOT_AUTHORIZED"),
 ({"offer_sha256":"b"*64},"OFFER_OR_CONSENT_UNVERIFIED"),
 ({"proposal_price_version_id":None},"OFFER_OR_CONSENT_UNVERIFIED"),
 ({"proposal_price_version_id":UUID("daba0000-0000-4000-8000-000000000051")},"OFFER_OR_CONSENT_UNVERIFIED"),
 ({"proposed_plan_active":False},"OFFER_OR_CONSENT_UNVERIFIED"),
 ({"proposed_members_limit":None},"OFFER_OR_CONSENT_UNVERIFIED"),
 ({"current_member_count":50,"held_member_count":1},"PROPOSED_PLAN_UNDERCAPACITY"),
 ({"current_quota_count":50,"held_quota_count":1},"PROPOSED_PLAN_UNDERCAPACITY"),
 ({"refund_or_chargeback":True},"LICENSE_REVOKED_OR_REFUNDED"),
 ({"current_status":"REVOKED"},"LICENSE_REVOKED_OR_REFUNDED"),
 ({"action":"UPGRADE_PREPARE","proposed_plan_tier":"ESSENCIAL"},"UPGRADE_NOT_ELIGIBLE"),
 ({"action":"UPGRADE_PREPARE","checked_at":NOW+timedelta(days=3)},"UPGRADE_NOT_ELIGIBLE"),
 ({"action":"CANCEL_AT_END","current_status":"EXPIRED"},"CANCELLATION_NOT_ELIGIBLE"),
 ({"action":"RESUME_REVIEW","actor_role":"MASTER","reviewer_id":ADMIN,"actor_id":ADMIN},"INDEPENDENT_REVIEW_REQUIRED"),
 ({"action":"RESUME_REVIEW","actor_role":"MASTER","independent_approval":False},"INDEPENDENT_REVIEW_REQUIRED"),
 ({"action":"RESUME_REVIEW","actor_role":"MASTER","current_status":"SUSPENDED","checked_at":NOW+timedelta(days=3)},"RESUME_DENIED"),
 ({"action":"RESUME_REVIEW","actor_role":"MASTER","current_status":"SUSPENDED","provider_verified":False},"RESUME_DENIED"),
 ({"action":"REFUND_REVIEW","actor_role":"MASTER","refund_or_chargeback":False},"VERIFIED_REFUND_REQUIRED"),
 ({"action":"REFUND_REVIEW","actor_role":"MASTER","refund_or_chargeback":True,"provider_verified":False},"VERIFIED_REFUND_REQUIRED"),
])
def test_denies_adversarial_changes(changes,state):
    d=review_saas_change(snapshot(**changes))
    assert d.state==state and not d.review_candidate and not d.production_authorized

@pytest.mark.parametrize("changes",[
 {"current_member_count":-1},{"held_quota_count":True},
 {"checked_at":datetime(2027,4,12)},{"proposed_members_limit":0},
 {"reviewer_id":"fake"},{"provider_verified":"true"},
])
def test_malformed_change_is_not_coerced(changes):
    with pytest.raises(ValueError,match="INVALID_SAAS_CHANGE_EVIDENCE"):
        review_saas_change(snapshot(**changes))

@pytest.mark.parametrize("s",[
 "M31400_DISPOSABLE_CI_ONLY","M31400_CI_WORKER_DENIED",
 "FOR UPDATE","FORCE ROW LEVEL SECURITY","related_hold_event_id",
 "UNIQUE INDEX saas_capacity_one_release_ci",
 "M31400_IMMUTABLE_EVENTS_CI","REPLAY_CI","CAPACITY_EXCEEDED",
 "saas_capacity_release_ci","real_membership_created",
 "real_quota_created","real_charge_created",
])
def test_sql_fail_closed_and_audit(s):
    assert s in SQL

def test_ci_invokes_pg_and_safety_gates():
    assert "CREATE ROLE frcaixinha_saas_capacity_ci" in CHAIN
    assert "060_saas_capacity_staging_only.sql" in CHAIN
    assert "059_saas_capacity_fixture_ci_only.sql" in CHAIN
    assert "M31800_SAAS_CAPACITY_PG=PASS" in CHAIN
    assert "GRANT INSERT ON public.memberships" not in SQL
    assert "GRANT INSERT ON public.quotas" not in SQL
    assert "GRANT INSERT ON public.saas_payment_intents" not in SQL

def test_no_production_side_effects():
    policy=(ROOT/"backend/app/saas_change_policy.py").read_text()
    assert "INSERT INTO" not in policy and "requests.post(" not in policy
    assert "UPDATE public." not in policy
    assert "os.environ" not in policy
