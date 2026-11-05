"""M19000 static guards and HTTP disabled when local auth absent."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
ROOT=Path(__file__).resolve().parents[1]
def test_schema_and_atomic_local_wrapper():
 sql=(ROOT/"migrations/031_notification_inbox_local_sandbox.sql").read_text()
 for x in ("frcaixinha_aistudio_dev","frcaixinha_aistudio_pg18",
    "inet_server_port()=5433","frcaixinha.notifications_local_ci",
    "FORCE ROW LEVEL SECURITY","notification_local_read_own",
    "notification_local_active_context","notification_local_create_selftest",
    "notification_local_mark_read","daily synthetic notice rate limit",
    "UNIQUE NULLS NOT DISTINCT"):
  assert x in sql,x
 assert "GRANT INSERT ON TABLE public.notification_inbox" not in sql
 assert "notification_local_session_issued" in sql
 assert "session_user NOT IN ('frc_ai_auth'" in sql
 assert "GRANT EXECUTE ON FUNCTION public.notification_local_session_issued(text)" in sql
 assert "frcaixinha_auth_role" in sql
 auth=(ROOT/"app/routers/auth.py").read_text()
 assert "notification_local_session_issued" in auth
 assert auth.index("auth_promote_pending_session")<auth.index("notification_local_session_issued")

 assert not sql.lstrip().startswith("BEGIN;") and not sql.strip().endswith("COMMIT;")
 body=(ROOT/"scripts/aistudio_db_local.sh").read_text()
 assert "027 031; do" in body and "--single-transaction" in body
 script=(ROOT/"scripts/aistudio_local_migration.sh").read_text()
 for x in ("AI_STUDIO_APPROVED_SHA","BACKUP_ENCRYPTED_VERIFIED","pg_restore --list"):
  assert x in script
def test_auth_required_and_financial_flags_off():
 with TestClient(app) as c:
  for route in ("/api/v1/notifications","/api/v1/notifications/capabilities","/api/v1/notifications/readiness"):
   assert c.get(route).status_code==401
  assert c.post("/api/v1/notifications/self-test").status_code==401
  assert c.post("/api/v1/notifications/eeeeeeee-0000-4000-8000-000000000001/read").status_code==401
  r=c.get("/api/health/features/m19000")
  assert r.status_code==200
  d=r.json()
  assert d["contract"]=="AI_STUDIO_M19000_LOCAL_IN_APP_NOTIFICATIONS_V1"
  assert d["local_notification_flag_configured"] is False
  for x in ("external_email_active","external_push_active","external_whatsapp_active",
            "provider_events_authenticated","real_payments_enabled","bank_reconciled",
            "ledger_written","financial_closing_authorized","payout_authorized",
            "oci_staging_deployed"):
   assert d[x] is False,x
