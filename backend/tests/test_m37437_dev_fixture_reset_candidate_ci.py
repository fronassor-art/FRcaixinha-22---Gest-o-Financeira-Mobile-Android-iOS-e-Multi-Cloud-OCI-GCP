"""M37437: SQL proposal contract. Never run the destructive candidate in CI."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/scripts/aistudio_dev_price_fixture_reset_candidate.sql"
def test_sql_only_one_exclusive_original_local_pg18():
 s=SQL.read_text()
 for marker in (
  "current_database()='frcaixinha_aistudio_dev'",
  "session_user='frc_ai_owner'",
  "inet_server_port()=5433",
  "frcaixinha_aistudio_pg18",
  "EXPLICIT_DEV_ONLY_PURGE_APPROVED",
  "frfinance.m37437_verified_backup_sha",
  "714bc50de8dfc42d25f1b9bbe54e9841df883f0d606f467015c0e153b4d9b88b",
  "pg_advisory_xact_lock(37437,2027)",
  "ACCESS EXCLUSIVE MODE","BEGIN;","COMMIT;",
 ):
  assert marker in s,marker
 for illegal in ("DROP DATABASE","CREATE DATABASE","ALTER DATABASE","TRUNCATE ",
                 "DELETE FROM public.users","DELETE FROM public.memberships",
                 "DELETE FROM public.sessions","DELETE FROM public.tenants",
                 "DELETE FROM public.audit_events"):
  assert illegal not in s
 assert s.index("EXPLICIT_DEV_ONLY_PURGE_APPROVED") < s.index("DELETE FROM public.contributions")
def test_exact_synthetic_baselines_and_financial_gate():
 s=SQL.read_text()
 assert "contribution_per_quota<150" in s
 assert "amount_due<150" in s
 assert "v_before_sessions" in s
 for marker in (
  "payment_status='QUITADA'","SELECT count(*) FROM public.pix_payment_intents",
  "SELECT count(*) FROM public.ledger_transactions",
  "SELECT count(*) FROM public.ledger_entries",
  "SELECT count(*) FROM public.loans",
  "SELECT count(*) FROM public.cycle_opening_audit",
  "change_status='PENDING_REVIEW'",
  "v_before_audit_events+1","AND c.year=2027 AND c.status='ABERTO'",
  "WHERE a.tenant_id=v_tenant",
 ):
  assert marker in s,marker
def test_exception_protected_and_audited_inside_one_transaction():
 s=SQL.read_text()
 disabled="DISABLE TRIGGER cycle_price_immutable_row;"
 enabled="ENABLE TRIGGER cycle_price_immutable_row;"
 assert s.count(disabled)==1 and s.count(enabled)==1
 start=s.index("DELETE FROM public.contributions")
 assert start<s.index(disabled)<s.index("DELETE FROM public.cycle_contribution_price_audit")<s.index(enabled)<s.index("DELETE FROM public.policies")
 assert s.count("GET DIAGNOSTICS n=ROW_COUNT;")==5
 assert "INSERT INTO public.audit_events" in s
 assert "BACKUP_SHA256:" in s
 assert "VALIDATE CONSTRAINT policy_minimum_150_new" in s
 assert "VALIDATE CONSTRAINT quota_minimum_150_new" in s
 assert s.rstrip().endswith("COMMIT;")
def test_candidate_not_exposed_as_termux_installer():
 wf=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()
 assert "M37437" in wf
 assert "psql -f backend/scripts/aistudio_dev_price_fixture_reset_candidate.sql" not in wf
 assert "M37437" not in (ROOT/"backend/scripts/aistudio_local_migration.sh").read_text()
