"""Static fail-closed source check, no network or database."""
from pathlib import Path
import ast
import unittest
R=Path(__file__).resolve().parents[2]
class TestM40340(unittest.TestCase):
 def test_driver(self):
  s=(R/"backend/tests/m40340_bearer_credit_runtime_ci.py").read_text()
  ast.parse(s)
  for x in ("require_disposable_ci()", "from app.main import app",
   "Depends(get_current_session)", "Depends(get_rls_db_connection)",
   "not app.dependency_overrides", "with TestClient(app) as client:",
   "M40340_SESSION_BOUND_VISIBILITY=PASS_60_OF_60",
   "M40340_AUTH_SQL_HELPERS=SYNTHETIC_NOT_PRODUCTION_PROOF"):
   self.assertIn(x,s)
  for x in ("frcaixinha_aistudio_dev","app.dependency_overrides[",
            "DROP DATABASE","subprocess.run(","os.kill("):
   self.assertNotIn(x,s)
 def test_sql(self):
  s=(R/"backend/tests/sql/m40340_bearer_credit_ci.sql").read_text()
  for x in ("current_database()<>'frfinance_ci_credit'",
   "inet_server_port()<>5432","session_user<>'postgres'",
   "M40340_BLOCKED_NOT_DISPOSABLE","CREATE ROLE fr_m40340_auth",
   "CREATE FUNCTION public.auth_active_memberships",
   "CREATE FUNCTION public.auth_refresh_session",
   "BLOCKED_EXTERNAL"):
   self.assertIn(x,s)
  self.assertEqual(s.count("\nCOMMIT;"),1)
  self.assertNotIn("DROP DATABASE",s)
 def test_workflow(self):
  s=(R/".github/workflows/frfinance-m40340-bearer-credit-rls-ci.yml").read_text()
  for x in ("image: postgres:18","PGDATABASE: frfinance_ci_credit",
   "PGPORT: '5432'","FR_FINANCE_ACCESS_MAIL_WORKER: 'OFF'",
   "m40340_bearer_credit_runtime_ci.py",
   "m39020_special_credit_integrity_ci.sql"):
   self.assertIn(x,s)
  for x in ("ssh ","pg_ctl","frcaixinha_aistudio_dev","PIX_REAL: 'ON'"):
   self.assertNotIn(x,s)
