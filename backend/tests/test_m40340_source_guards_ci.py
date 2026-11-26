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
   "app.state.frfinance_ci_disposable_read_test = True",
   "current_setting('frfinance.m40340_ci',true)",
   "Depends(get_current_session)", "Depends(get_rls_db_connection)",
   "not app.dependency_overrides", "with TestClient(app) as client:",
   "M40340_SESSION_BOUND_VISIBILITY=PASS_60_OF_60",
   "M40340_AUTH_SQL_HELPERS=SYNTHETIC_NOT_PRODUCTION_PROOF"):
   self.assertIn(x,s)
  self.assertLess(
   s.index("current_setting('frfinance.m40340_ci',true)"),
   s.index("app.state.frfinance_ci_disposable_read_test = True"))
  self.assertLess(
   s.index("app.state.frfinance_ci_disposable_read_test = True"),
   s.index("with TestClient(app) as client:"))
  for x in ("frcaixinha_aistudio_dev","app.dependency_overrides[",
            "DROP DATABASE","subprocess.run(","os.kill("):
   self.assertNotIn(x,s)

 def test_m40380_marker_follows_its_disposable_pg18_preflight(self):
  s=(R/"backend/tests/m40380_real_auth_credit_rls_ci.py").read_text()
  ast.parse(s)
  main=next(n for n in ast.walk(ast.parse(s))
            if isinstance(n,ast.FunctionDef) and n.name=="main")
  self.assertEqual(main.body[0].value.func.id,"require_ci")
  marker="app.state.frfinance_ci_disposable_read_test = True"
  self.assertIn(marker,s)
  self.assertLess(
   s.index("current_setting('frfinance.m40380_ci',true)"),
   s.index(marker))
  self.assertLess(s.index(marker),s.index("with TestClient(app) as client:"))
  self.assertIn("not app.dependency_overrides",s)

 def test_m40350_pool_boundaries_and_no_service_loss_false_positive(self):
  s=(R/"backend/tests/m40340_bearer_credit_runtime_ci.py").read_text()
  for expected in (
   "from app.database import get_db_pool, get_rls_db_connection",
   '/__ci_m40340/pool-clean',
   '/__ci_m40340/abort',
   "M40350_POOL_GUC_CLEAN_AFTER_CROSS_USER_AND_ROLLBACK=PASS",
   "M40350_ORIGINAL_POOL_REUSED=YES",
   "M40350_SQL_SESSION_SETTING_LEAK=DENIED",
  ):
   self.assertIn(expected,s)
  service=(R/"backend/scripts/frfinance_m40300_termux_readonly.sh").read_text()
  for expected in (
   "pg_ctl -D \"$PGDATA\" status",
   "pg_isready -q -h 127.0.0.1 -p 5433",
   "http://127.0.0.1:8000/api/health",
   "M40300_STATUS=SERVICES_INACTIVE_OR_UNVERIFIED_NOT_DATABASE_LOSS",
   "ANDROID_TERMUX_TERMINATION_CAN_STOP_BOTH_SERVICES",
   "M40300_NEW_DATABASES=NONE",
   "M40300_FASTAPI_RESTART=NONE",
   "M40300_POSTGRESQL_RESTART=NONE",
  ):
   self.assertIn(expected,service)
  for forbidden in ("initdb ", "createdb ", "pg_ctl start",
                    "pg_ctl restart", "pg_ctl stop", "dropdb "):
   self.assertNotIn(forbidden,service)

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
