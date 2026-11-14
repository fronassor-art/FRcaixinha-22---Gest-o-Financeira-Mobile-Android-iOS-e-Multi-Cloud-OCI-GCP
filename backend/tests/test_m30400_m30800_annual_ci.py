"""M30400-M30800: schema and nonproduction gate tests, DB E2E in CI shell."""
from pathlib import Path
from app.annual_consent import ActiveMember,ConsentEvent,assess_annual_consent
from datetime import datetime,timezone,timedelta
import pytest
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/staging_migrations/058_annual_self_loan_consent_staging_only.sql").read_text()
SCRIPT=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
@pytest.mark.parametrize("snippet",(
 "frcaixinha_staging","session_user<>'postgres'",
 "session_user<>'frcaixinha_annual_ci'","FOR UPDATE",
 "FORCE ROW LEVEL SECURITY","REPLAY_CI","M30400_APPEND_ONLY",
 "real_authorized',false","payout_authorized',false",
 "reserve_authorized',false","loan_approval_authorized',false",
 "CHECK(NOT payout_authorized)","GRANT EXECUTE ON FUNCTION",
))
def test_schema_invariant(snippet): assert snippet in SQL
def test_role_and_disposable_ci_integration():
 assert "CREATE ROLE frcaixinha_annual_ci" in SCRIPT
 assert "058_annual_self_loan_consent_staging_only.sql" in SCRIPT
 assert "057_annual_self_loan_fixture_ci_only.sql" in SCRIPT
 assert "M30800_CI_ANNUAL_CONSENT_POSTGRES=PASS" in SCRIPT
 assert "GRANT SELECT ON public.annual_self_loan_events_staging" not in SQL
 assert "GRANT INSERT ON public.annual_self_loan_events_staging" not in SQL
def test_public_route_remains_blocked():
 s=(ROOT/"backend/app/routers/consents.py").read_text()
 assert "BLOQUEADO_ASSINATURA_ANUAL_INDISPONIVEL" in s
 assert "annual_event_record_ci" not in s
@pytest.mark.parametrize("decision",("SIGNED","REVOKED","OTHER"))
def test_legacy_pure_annual_checks_fail_closed(decision):
 now=datetime(2027,6,1,tzinfo=timezone.utc)
 result=assess_annual_consent(
 tenant_id="tenant",cycle_year=2027,admin_user_id="a",
 members=(ActiveMember("admin","a"),ActiveMember("voter","v")),
 events=(ConsentEvent("tenant",2027,"a","voter","v1",decision,now-timedelta(minutes=1)),),
 terms_version="v1",at=now)
 assert result.authorized is (decision=="SIGNED")
