"""M32900-M33300 static checks keep stale-hold recovery synthetic only."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
CLAIM=(ROOT/"backend/staging_migrations/062_saas_capacity_claim_staging_only.sql").read_text()
SQL=(ROOT/"backend/staging_migrations/063_saas_capacity_expiry_staging_only.sql").read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
WORKFLOW=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()

@pytest.mark.parametrize("fragment", [
 "M32900_DISPOSABLE_CI_ONLY","frcaixinha_staging","M32900_CI_WORKER_DENIED",
 "frcaixinha.saas_expiry_ci","FOR UPDATE","interval '60 minutes'",
 "CLAIMED_HOLD_DENIED","REPLAY_RECOVERY_CI","REQUEST_COLLISION_DENIED",
 "ALREADY_RELEASED_DENIED","TOO_EARLY","INVALID_HOLD",
 "RECOVERED_CI_NO_REAL_CREATION","M33200_EXPIRY_HISTORY_IMMUTABLE",
 "BEFORE TRUNCATE","FORCE ROW LEVEL SECURITY",
 "public.saas_capacity_release_ci(", "CHECK(NOT real_member_created)",
 "CHECK(NOT real_quota_created)","CHECK(NOT real_charge_created)",
 "CHECK(NOT real_ledger_changed)"])
def test_expiry_sql_guards(fragment):
    assert fragment in SQL

def test_claim_disallows_old_unreleased_holds():
    assert "EXPIRED_HOLD_DENIED" in CLAIM
    assert "h.created_at INTO held_event" in CLAIM
    assert "interval '60 minutes'" in CLAIM

def test_ci_pipeline_never_grants_real_dml():
    assert "063_saas_capacity_expiry_staging_only.sql" in CHAIN
    assert "test_m33300_saas_capacity_expiry_pg_ci.py" in CHAIN
    assert "M33300_EXPIRY_PG=PASS" in CHAIN
    assert "test_m32900_m33300_saas_expiry_static_ci.py" in WORKFLOW
    assert "PGDATABASE=frcaixinha_ci" in CHAIN
    for fragment in ("GRANT INSERT ON public.memberships",
                     "GRANT INSERT ON public.quotas",
                     "GRANT INSERT ON public.ledger_entries",
                     "GRANT UPDATE ON public.saas_payment_intents",
                     "GRANT SELECT ON public.saas_capacity_expiry_events_staging"):
        assert fragment not in SQL
