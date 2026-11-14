"""M32400-M32800: SQL and CI safety checklist (no production effects)."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/staging_migrations/062_saas_capacity_claim_staging_only.sql").read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
WORKFLOW=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()

@pytest.mark.parametrize("fragment",[
"M32400_DISPOSABLE_CI_ONLY","frcaixinha_staging","session_user<>'postgres'",
"frcaixinha.saas_claim_ci","M32400_CI_WORKER_DENIED","FOR UPDATE",
"HOLD_ALREADY_CLAIMED","REPLAY_CI_NO_REAL_CREATION",
"REQUEST_COLLISION_DENIED","INVALID_HOLD","RELEASED_HOLD_DENIED",
"LICENSE_UNVERIFIED","PLAN_UNVERIFIED","CAPACITY_EXCEEDED",
"CLAIMED_CI_NO_REAL_CREATION","M32700_CLAIMED_HOLD_RELEASE_DENIED",
"M32800_IMMUTABLE_CLAIM_HISTORY","BEFORE TRUNCATE",
"FORCE ROW LEVEL SECURITY","CHECK(NOT real_member_created)",
"CHECK(NOT real_quota_created)","CHECK(NOT real_charge_created)",
"CHECK(NOT real_ledger_changed)"])
def test_all_safety_contracts(fragment):
    assert fragment in SQL

def test_worker_cannot_write_real_tables():
    for grant in ("GRANT INSERT ON public.memberships","GRANT INSERT ON public.quotas",
        "GRANT UPDATE ON public.saas_payment_intents",
        "GRANT INSERT ON public.ledger_entries",
        "GRANT SELECT ON public.saas_capacity_claims_staging",
        "GRANT INSERT ON public.saas_capacity_claims_staging"):
        assert grant not in SQL
    assert "GRANT EXECUTE ON FUNCTION public.saas_capacity_claim_ci(" in SQL

def test_disposable_postgres_pipeline():
    for fragment in ("CREATE ROLE frcaixinha_saas_claim_ci",
        "062_saas_capacity_claim_staging_only.sql",
        "test_m32800_saas_capacity_claim_pg_ci.py",
        "M32800_SAAS_CLAIM_PG=PASS","M32800_REAL_USERS_AND_PIX=OFF"):
        assert fragment in CHAIN
    assert "test_m32400_m32800_saas_claim_static_ci.py" in WORKFLOW
