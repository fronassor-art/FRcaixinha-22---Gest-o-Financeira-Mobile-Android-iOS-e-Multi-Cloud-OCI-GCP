"""M16000 staging migration design and explicit runtime nondeployment."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"staging_migrations/041_notifications_inbox_outbox_staging_ci_only.sql"

def test_041_is_staging_only_strict_sql():
 assert SQL.is_file()
 assert not list((ROOT/"migrations").glob("041_*.sql"))
 s=SQL.read_text()
 for x in (
  "current_database()<>'frcaixinha_staging'",
  "frcaixinha.notifications_staging_ci",
  "UNIQUE NULLS NOT DISTINCT","ENABLE ROW LEVEL SECURITY",
  "FORCE ROW LEVEL SECURITY","notification_recipient_context_ci",
  "notification_enqueue_staging_ci","notification_mark_read_staging_ci",
  "pg_advisory_xact_lock","M041 DENIED: conflicting event replay",
  "REVOKE ALL ON public.notification_outbox_staging",
  "GRANT SELECT ON public.notification_inbox_staging TO frcaixinha_app_role",
  "HELD_CI_NO_DELIVERY","bank_reconciled boolean NOT NULL DEFAULT false",
  "financial_effect_applied boolean NOT NULL DEFAULT false",
 ):
  assert x in s,x
 for x in ("GRANT UPDATE ON public.notification_inbox_staging",
           "GRANT INSERT ON public.notification_outbox_staging",
           "CREATE POLICY notification_outbox"):
  assert x not in s,x

def test_staging_script_guards_and_runs_both_postgres_versions():
 s=(ROOT/"scripts/aistudio_staging_chain_ci.sh").read_text()
 for x in ('GITHUB_ACTIONS','FRCAIXINHA_CI_ISOLATED',
           '041_notifications_inbox_outbox_staging_ci_only.sql',
           'test_m16000_notifications_postgres_ci.py'):
  assert x in s

def test_m16000_health_reports_no_real_inbox():
 with TestClient(app) as c:
  response=c.get("/api/health/features/m16000")
 assert response.status_code==200
 d=response.json()
 assert d["contract"]=="AI_STUDIO_M16000_NOTIFICATION_STAGING_PG_CI_ONLY_V1"
 assert d["workstream"]=="AI_STUDIO"
 assert all(d[x] is True for x in (
  "disposable_outbox_inbox_schema_prepared","disposable_pg16_pg18_tests_registered",
  "ci_only_recipient_rls_policy","ci_only_read_receipt_contract"))
 assert all(d[x] is False for x in (
  "local_migration_applied","oci_staging_deployed","real_inbox_api_connected",
  "authenticated_producer_connected","in_app_delivery_active",
  "email_send_active","push_send_active","whatsapp_send_active",
  "real_payments_enabled","bank_reconciled","financial_closing_authorized",
  "payout_authorized"))
