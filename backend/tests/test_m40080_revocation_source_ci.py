"""M40080 — keep CI-only revocation and runtime marker boundaries."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "backend/tests/m40080_revocation_sequence_pg18_ci.py"
FLOW = ROOT / ".github/workflows/frfinance-m40080-runtime-revocation-ci.yml"

class M40080SourceGate(unittest.TestCase):
    def test_revocation_driver_guards_before_opening_database(self):
        s=DRIVER.read_text(encoding="utf-8")
        tree=ast.parse(s)
        fun=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef)
                 and x.name=="main")
        first=fun.body[0]
        self.assertIsInstance(first,ast.Expr)
        self.assertEqual(first.value.func.id,"require_disposable_ci")
        for mark in (
            "m40070_pg18_policy_runtime_ci import require_disposable_ci",
            "SELECT current_database(),session_user,",
            "current_setting('frfinance.m40070_ci',true)",
            "M40080_REVOKED_TOKEN_DENIED_AFTER_COMMIT=PASS",
            "M40080_OWNER_TRANSFER_RLS_NEXT_REQUEST_DENIED=PASS",
            "M40080_REAL_REVOCATION=NOT_ATTESTED",
            "M40080_ORIGINAL_DATABASE_ACCESS=NONE",
        ):
            self.assertIn(mark,s)
        for forbidden in (
            "frcaixinha_aistudio_dev","frcaixinha_2_2",
            "DROP DATABASE","CREATE DATABASE","os.kill(",
            "subprocess.run(","app.dependency_overrides[",
            "https://api.mercadopago",
        ):
            self.assertNotIn(forbidden,s)

    def test_workflow_runs_ci_fixture_only(self):
        w=FLOW.read_text(encoding="utf-8")
        for mark in (
            "image: postgres:18",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "CI_M40070_DISPOSABLE: '1'",
            "m40070_disposable_auth_policy_pg18_ci.sql",
            "m40070_pg18_policy_runtime_ci.py",
            "m40080_revocation_sequence_pg18_ci.py",
            "test_m40080_loaded_source_ci.py",
            "test_m40080_revocation_source_ci.py",
            "M40080_TERMUX_ACCESS=NONE",
            "M40080_ORIGINAL_DATABASE_ACCESS=NONE",
            "M40080_PRODUCTION=BLOCKED",
        ):
            self.assertIn(mark,w)
        for forbidden in ("ssh ","pg_ctl","5433","migrate upgrade",
                          "frcaixinha_aistudio_dev","PIX_REAL: 'ON'"):
            self.assertNotIn(forbidden,w)

if __name__ == "__main__":
    unittest.main()
