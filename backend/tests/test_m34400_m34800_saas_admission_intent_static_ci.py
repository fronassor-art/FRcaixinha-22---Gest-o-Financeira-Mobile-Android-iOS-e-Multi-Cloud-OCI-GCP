"""M34400-M34800 CI: admission intent is not real account activation."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/staging_migrations/064_saas_member_admission_intent_staging_only.sql").read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
WF=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()

@pytest.mark.parametrize("token",[
 "M34400_DISPOSABLE_CI_ONLY","M34400_WORKER_DENIED",
 "frcaixinha_staging","saas_member_admission_intents_staging",
 "FOR UPDATE","saas_capacity_claims_staging",
 "saas_license_entitlements","saas_payment_intents",
 "saas_capacity_budgets_staging","invite_email_verification",
 "contract_acceptances","contract_documents","invitations",
 "email_verified_at","TENANT_MEMBERSHIP","CI_VERIFIED_IDENTITY",
 "FORCE ROW LEVEL SECURITY","PROOF_OR_CAPACITY_ALREADY_USED",
 "LICENSE_OR_MEMBER_CLAIM_DENIED","CAPACITY_DENIED",
 "CONTRACT_DENIED","EMAIL_OWNERSHIP_DENIED",
 "M34700_ADMISSION_INTENT_IMMUTABLE","REPLAY_CI_NO_ACTIVATION",
 "VERIFIED_INTENT_CI_NO_ACTIVATION","BEFORE TRUNCATE",
 "CHECK(NOT real_member_created)","CHECK(NOT real_quota_created)",
 "CHECK(NOT real_charge_created)","CHECK(NOT real_pix_enabled)",
])
def test_sql_gates(token):
    assert token in SQL

def test_no_real_membership_or_financial_dml():
    forbidden=("INSERT INTO public.memberships","UPDATE public.memberships",
               "DELETE FROM public.memberships","INSERT INTO public.quotas",
               "UPDATE public.quotas","INSERT INTO public.users",
               "UPDATE public.users","INSERT INTO public.saas_payment_intents",
               "UPDATE public.saas_payment_intents","INSERT INTO public.ledger_entries")
    assert all(f not in SQL for f in forbidden)
    assert "activation_authorized',false" in SQL
    assert "provider_verified_live',false" in SQL
    assert "real_pix_enabled boolean NOT NULL DEFAULT false" in SQL

def test_implemented_in_postgres_disposable_chain():
    assert "064_saas_member_admission_intent_staging_only.sql" in CHAIN
    assert "test_m34800_saas_admission_intent_pg_ci.py" in CHAIN
    assert "M34800_INTENT_PG=PASS" in CHAIN
    assert "test_m34400_m34800_saas_admission_intent_static_ci.py" in WF
