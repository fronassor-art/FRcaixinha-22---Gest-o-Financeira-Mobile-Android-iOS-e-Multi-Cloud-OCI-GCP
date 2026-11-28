"""M35900-M36300: review evidence is CI-only and never a release token."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/staging_migrations/065_saas_reconciliation_review_staging_only.sql").read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
WF=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()

@pytest.mark.parametrize("required",[
 "M35900_ONLY_DISPOSABLE_STAGING_CI",
 "M35900_REVIEW_WORKER_DENIED",
 "frcaixinha_staging","session_user",
 "saas_reconciliation_reviews_staging",
 "FORCE ROW LEVEL SECURITY","GET_MATCH_CANDIDATE",
 "REVERSAL_HOLD","PROVIDER_UNAVAILABLE_HOLD",
 "FOR UPDATE","REPLAY_NO_FINANCIAL_WRITE",
 "REVIEW_REQUEST_COLLISION_DENIED",
 "DUPLICATE_EVIDENCE_DENIED",
 "REVERSAL_HOLD_ACTIVE",
 "M36200_REVIEW_APPEND_ONLY",
 "BEFORE TRUNCATE",
 "CHECK (NOT real_license_activated)",
 "CHECK (NOT real_payment_settled)",
 "CHECK (NOT real_pix_authorized)",
 "provider_readback_live_attested boolean NOT NULL DEFAULT false",
 "GRANT EXECUTE ON FUNCTION public.saas_reconciliation_review_ci",
])
def test_strict_ci_migration_guards(required):
    assert required in SQL

def test_no_real_payment_or_license_mutations():
    for forbidden in (
        "INSERT INTO public.saas_payment_intents",
        "UPDATE public.saas_payment_intents",
        "INSERT INTO public.saas_license_entitlements",
        "UPDATE public.saas_license_entitlements",
        "INSERT INTO public.memberships",
        "INSERT INTO public.quotas",
        "INSERT INTO public.ledger_entries",
        "UPDATE public.ledger_entries",
    ):
        assert forbidden not in SQL
    assert "activation_authorized',false" in SQL
    assert "real_pix_authorized boolean NOT NULL DEFAULT false" in SQL
    assert "UNIQUE(payment_intent_id,event_kind,evidence_digest)" in SQL
    assert "request_key varchar(100) NOT NULL UNIQUE" in SQL

def test_ci_chain_and_static_pipeline_present():
    assert "065_saas_reconciliation_review_staging_only.sql" in CHAIN
    assert "test_m36300_saas_reconciliation_pg_ci.py" in CHAIN
    assert "M36300_RECONCILIATION_EVIDENCE_CI=PASS" in CHAIN
    assert "test_m35900_m36300_saas_reconciliation_static_ci.py" in WF
