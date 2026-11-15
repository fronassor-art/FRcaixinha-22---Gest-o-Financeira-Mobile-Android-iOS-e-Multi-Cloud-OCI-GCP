"""M40050 CI source contract: loopback HTTP, commit-before-drop and no money."""
from pathlib import Path
import ast
import unittest

ROOT=Path(__file__).resolve().parents[2]
DRIVER=ROOT/"backend/tests/m40050_loopback_http_retry_pg18_ci.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40050-loopback-http-retry-ci.yml"


class M40050LoopbackSourceGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver=DRIVER.read_text(encoding="utf-8")
        cls.workflow=WORKFLOW.read_text(encoding="utf-8")
        cls.tree=ast.parse(cls.driver)

    def test_isolation_and_disposable_pg18_identity(self):
        for marker in (
            '"GITHUB_ACTIONS": "true"',
            '"PGHOST": "127.0.0.1"',
            '"PGPORT": "5432"',
            '"PGUSER": "postgres"',
            '"PGDATABASE": "frcaixinha_ci"',
            '"CI_M40050_DISPOSABLE": "1"',
            "frfinance.m40050_ci",
            "DISPOSABLE_ONLY",
            "M40050_BLOCKED_",
            "require_ephemeral_environment()",
            "connect_timeout=3",
        ):
            self.assertIn(marker,self.driver)
        for forbidden in (
            "frcaixinha_aistudio_dev",
            "frcaixinha_2_2",
            "socket.gethostbyname(",
            "DROP DATABASE",
            "subprocess.run(",
            "os.kill(",
            "PIX_REAL=ON",
            "ACTIVATION_REAL=ON",
            "FastAPI(",
        ):
            self.assertNotIn(forbidden,self.driver)

    def test_local_http_listener_and_server_derived_roles_only(self):
        for marker in (
            '("127.0.0.1", 0)',
            "class TestServer(ThreadingHTTPServer)",
            "class Handler(BaseHTTPRequestHandler)",
            "X-CI-Token",
            '"ci-actor-a": "m40010_a_a"',
            '"ci-actor-b": "m40010_a_b"',
            '"ci-tenant-b": "m40010_b_a"',
            '"ci-master": "m40010_m_a"',
            "SET LOCAL ROLE ",
            'role != "m40010_a_a"',
            "CI_WRITER_NOT_DESIGNATED",
            "NOT_FOUND_OR_NOT_VISIBLE",
            "CI_TOKEN_REQUIRED",
        ):
            self.assertIn(marker,self.driver)
        self.assertNotIn('0.0.0.0',self.driver)
        self.assertNotIn("https://",self.driver)

    def test_reply_drop_only_after_transaction_context_manager(self):
        methods={
            node.name:node for node in ast.walk(self.tree)
            if isinstance(node,ast.FunctionDef)
        }
        self.assertIn("do_POST",methods)
        node=methods["do_POST"]
        self.assertIsInstance(node,ast.FunctionDef)
        source=ast.get_source_segment(self.driver,node)
        self.assertIn("with conn.transaction():",source)
        self.assertIn("INSERT INTO m40010_ci.review_receipts",source)
        self.assertIn("INSERT INTO m40040_ci.receipt_ack",source)
        self.assertIn("self.connection.shutdown(socket.SHUT_RDWR)",source)
        self.assertLess(source.index("with conn.transaction():"),
                        source.index("self.connection.shutdown(socket.SHUT_RDWR)"))
        self.assertIn("self.server.drop_first_response = False",source)
        self.assertIn("except psycopg.errors.UniqueViolation:",source)
        self.assertIn("SELECT m40040_ci.inspect_uncertain_commit(%s,%s)",source)

    def test_replayed_body_fingerprint_and_financial_flags(self):
        for marker in (
            "sort_keys=True",
            'separators=(",", ":")',
            "hashlib.sha256",
            "EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE",
            "CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE",
            "M40050_HTTP_REPLY_LOST_AFTER_DATABASE_COMMIT=PASS",
            "M40050_HTTP_RETRY_RETURNS_EXISTING_RECEIPT=PASS",
            "M40050_CHANGED_HTTP_REQUEST_IS_CONFLICT=PASS",
            "M40050_CROSS_REVIEWER_TENANT_MASTER_RLS=PASS",
            "M40050_ONE_COMMITTED_SYNTHETIC_RECEIPT=PASS",
            "M40050_REAL_HUMAN_AUTHENTICATION=NOT_ATTESTED",
            "M40050_REAL_REVIEW_APPROVAL=FALSE",
            "M40050_PRODUCTION=BLOCKED",
            '"real_review_approved": False',
            '"payout_enabled": False',
        ):
            self.assertIn(marker,self.driver)

    def test_workflow_uses_exclusively_disposable_postgres(self):
        for marker in (
            "image: postgres:18",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "CI_M40050_DISPOSABLE: '1'",
            "m40010_disposable_init_pg18_ci.sql",
            "m40020_disposable_lock_init_pg18_ci.sql",
            "m40040_disposable_ack_init_pg18_ci.sql",
            "m40050_loopback_http_retry_pg18_ci.py",
            "frfinance.m40050_ci=DISPOSABLE_ONLY",
            "M40050_TERMUX_ACCESS=NONE",
            "M40050_ORIGINAL_DB_ACCESS=NONE",
            "M40050_PRODUCTION=BLOCKED",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker,self.workflow)
        for forbidden in (
            "ssh ","frcaixinha_aistudio_dev","migrate upgrade",
            "pg_ctl","https://api.mercadopago",
        ):
            self.assertNotIn(forbidden,self.workflow)


if __name__=="__main__":
    unittest.main()
