"""FR Finance M40000: source gates for ephemeral PostgreSQL18-only receipts."""
from pathlib import Path
import re
import unittest

SQL = Path(__file__).resolve().parents[1] / "tests/sql/m40000_disposable_review_receipts_pg18_ci.sql"
WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/frfinance-m40000-review-receipts-disposable-ci.yml"


class TestM40000DisposableReceiptsSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SQL.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_database_identity_gates_and_rollback(self):
        s=self.source
        for required in (
            r"\if :{?CI_M40000_DISPOSABLE}",
            "current_database()='frcaixinha_ci'",
            "inet_server_port()=5432",
            "session_user='postgres'",
            "current_setting('frfinance.m40000_ci',true)='DISPOSABLE_ONLY'",
            "M40000_BLOCKED_WRONG_CLUSTER",
            "M40000_ORIGINAL_DATABASE_ACCESS=NONE",
        ):
            self.assertIn(required,s)
        self.assertEqual(s.count("\nBEGIN;"),1)
        self.assertEqual(s.count("\nROLLBACK;"),1)
        self.assertNotRegex(s,r"(?m)^\s*COMMIT\s*;")
        self.assertNotRegex(s,r"(?m)^\s*CREATE TABLE public\.")
        self.assertNotRegex(s,r"(?m)^\s*ALTER TABLE public\.")

    def test_database_enforces_uniqueness_and_append_only(self):
        for required in (
            "CREATE SCHEMA m40000_ci",
            "CREATE TABLE m40000_ci.review_packets",
            "CREATE TABLE m40000_ci.review_receipts",
            "FOREIGN KEY(packet_id,scope,cashbox_key,journal_fingerprint,",
            "UNIQUE(packet_id,reviewer_id)",
            "UNIQUE(packet_id,session_id)",
            "UNIQUE(scope,cashbox_key,nonce)",
            "UNIQUE(scope,cashbox_key,idempotency_key)",
            "FOR UPDATE",
            "existing_count >= 2",
            "M40000_SELF_REVIEW_FORBIDDEN",
            "M40000_MORE_THAN_TWO_REVIEW_CLAIMS",
            "M40000 idempotency replay accepted",
            "M40000 session replay accepted",
            "M40000 duplicate reviewer accepted",
            "M40000 nonce replay accepted",
            "M40000 cross-tenant document accepted",
            "M40000 false approval accepted",
            "M40000 mutable packet",
            "M40000 mutable receipt",
            "BEFORE UPDATE OR DELETE",
            "M40000_APPEND_ONLY_CI",
        ):
            with self.subTest(contract=required):
                self.assertIn(required,self.source)

    def test_read_only_role_and_no_financial_authority(self):
        for required in (
            "CREATE ROLE m40000_ci_reader NOLOGIN NOBYPASSRLS",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "GRANT SELECT ON m40000_ci.review_packets,m40000_ci.review_receipts",
            "SET LOCAL ROLE m40000_ci_reader",
            "M40000 master RLS leak",
            "M40000 tenant A RLS leak",
            "M40000 tenant B RLS leak",
            "M40000 member RLS leak",
            "CHECK(session_authenticated=false)",
            "CHECK(reviewer_mandate_verified=false)",
            "CHECK(document_authenticated=false)",
            "CHECK(approval_verified=false)",
            "CHECK(journal_posted=false)",
            "CHECK(payout_enabled=false)",
            "CHECK(available_balance_cents IS NULL)",
        ):
            with self.subTest(required=required):
                self.assertIn(required,self.source)

        for forbidden in (
            "frcaixinha_aistudio_dev",
            "frcaixinha_2_2",
            "DROP DATABASE",
            "dblink(",
            "pg_ctl",
            "PIX_REAL=ON",
            "CREATE POLICY m40000_writer",
            "GRANT INSERT",
            "GRANT UPDATE",
            "GRANT DELETE",
        ):
            self.assertNotIn(forbidden,self.source)

    def test_workflow_uses_only_ephemeral_pg18(self):
        for required in (
            "postgres:18",
            "POSTGRES_PASSWORD: postgres",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "frfinance.m40000_ci=DISPOSABLE_ONLY",
            "CI_M40000_DISPOSABLE=1",
            "backend/tests/sql/m40000_disposable_review_receipts_pg18_ci.sql",
            "M40000_TERMUX_ACCESS=NONE",
            "M40000_PRODUCTION=BLOCKED",
        ):
            with self.subTest(required=required):
                self.assertIn(required,self.workflow)
        self.assertNotIn("ssh ",self.workflow)
        self.assertNotIn("frcaixinha_aistudio_dev",self.workflow)
        self.assertNotIn("migrate upgrade",self.workflow)
        self.assertNotIn("git merge",self.workflow)


if __name__=="__main__":
    unittest.main()
