"""M40070: CI identity, disposable SQL and no app migration review."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "backend/tests/m40070_pg18_policy_runtime_ci.py"
SQL = ROOT / "backend/tests/sql/m40070_disposable_auth_policy_pg18_ci.sql"
FLOW = ROOT / ".github/workflows/frfinance-m40070-actual-auth-disposable-ci.yml"
ROUTER = ROOT / "backend/app/routers/exclusive_cashbox_review_gaps.py"


class M40070StaticReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = DRIVER.read_text(encoding="utf-8")
        cls.sql = SQL.read_text(encoding="utf-8")
        cls.workflow = FLOW.read_text(encoding="utf-8")
        cls.router = ROUTER.read_text(encoding="utf-8")
        ast.parse(cls.driver)

    def test_guard_is_before_all_imported_network_clients(self):
        main = next(n for n in ast.walk(ast.parse(self.driver))
                    if isinstance(n,ast.FunctionDef) and n.name=="main")
        first = main.body[0]
        self.assertIsInstance(first,ast.Expr)
        self.assertIsInstance(first.value,ast.Call)
        self.assertEqual(first.value.func.id,"require_disposable_ci")
        for mark in ('"GITHUB_ACTIONS": "true"', '"PGPORT": "5432"',
                     '"PGDATABASE": "frcaixinha_ci"',
                     '"CI_M40070_DISPOSABLE": "1"',
                     '"FRCAIXINHA_TEST_AUTH": "1"',
                     "M40070_BLOCKED_UNSAFE_ENVIRONMENT",
                     "frfinance.m40070_ci=DISPOSABLE_ONLY",
                     "M40070_POSTGRESQL_18_REQUIRED"):
            self.assertIn(mark,self.driver)

    def test_exercises_unmodified_application_auth_and_rls(self):
        for name in (
            "from app.main import app", "from app.database import get_rls_db_connection",
            "from app.dependencies import get_current_session, require_master",
            "not app.dependency_overrides", "with TestClient(app) as client:",
            "M40070_REAL_BEARER_HASH_MASTER_SAAS=PASS",
            "M40070_RLS_TENANT_AND_OWNER_BARRIERS=PASS",
            "M40070_EXPIRED_REVOKED_UNKNOWN_ANONYMOUS=DENIED",
            "M40070_QUERY_TAMPERING_AND_POST_APPROVAL=DENIED",
            "M40070_CI_AUTH_REFRESH_ONLY_EXPECTED=TRUE",
        ):
            self.assertIn(name,self.driver)
        for forbidden in (
            "app.dependency_overrides[", "mock.patch(", "monkeypatch",
            "http://example.com", "https://api.mercadopago",
            "os.kill(", "subprocess.run(", "DROP DATABASE",
            "frcaixinha_aistudio_dev", "frcaixinha_2_2",
        ):
            self.assertNotIn(forbidden,self.driver)

    def test_synthetic_sql_is_ci_only_and_roles_least_privilege(self):
        for mark in (
            "M40070_BLOCKED_NOT_DISPOSABLE_PG18",
            "current_database() <> 'frcaixinha_ci'",
            "session_user <> 'postgres'",
            "IS DISTINCT FROM 'DISPOSABLE_ONLY'",
            "CREATE ROLE fr_m40070_auth LOGIN",
            "CREATE ROLE fr_m40070_app LOGIN",
            "NOSUPERUSER NOBYPASSRLS",
            "ALTER TABLE public.tenants FORCE ROW LEVEL SECURITY",
            "CREATE POLICY m40070_tenant_owner_view",
            "current_setting('app.current_tenant_id',true)",
            "current_setting('app.current_user_id',true)",
            "current_setting('app.current_role',true)",
            "M40070_LEAST_PRIVILEGE_DENIED",
        ):
            self.assertIn(mark,self.sql)
        for forbidden in (
            "DROP DATABASE", "DROP SCHEMA", "frcaixinha_aistudio_dev",
            "frcaixinha_2_2", "GRANT ALL PRIVILEGES",
            "GRANT SUPERUSER", "GRANT BYPASSRLS",
        ):
            self.assertNotIn(forbidden,self.sql)

    def test_workflow_does_not_touch_termux_or_migrate_original(self):
        for mark in (
            "image: postgres:18",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "CI_M40070_DISPOSABLE: '1'",
            "m40070_disposable_auth_policy_pg18_ci.sql",
            "m40070_pg18_policy_runtime_ci.py",
            "test_m40070_disposable_source_ci.py",
            "M40070_TERMUX_ACCESS=NONE",
            "M40070_ORIGINAL_DATABASE_ACCESS=NONE",
            "M40070_REAL_PIX=OFF",
        ):
            self.assertIn(mark,self.workflow)
        for forbidden in (
            "ssh ", "pg_ctl", "frcaixinha_aistudio_dev", "migrate upgrade",
            "https://api.mercadopago", "PIX_REAL: 'ON'",
        ):
            self.assertNotIn(forbidden,self.workflow)


if __name__ == "__main__":
    unittest.main()
