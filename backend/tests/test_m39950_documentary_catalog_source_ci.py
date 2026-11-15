"""M39950 source gate: evidence catalog cannot be run on original clusters."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql/m39950_documentary_review_catalog_disposable_ci.sql"

class M39950DisposableContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=SQL.read_text(encoding="utf-8")

    def test_sql_requires_separate_database_and_disposable_flag(self):
        for code in (
            r"\if :{?CI_M39950_DISPOSABLE}",
            "current_database()='frcaixinha_ci'",
            "inet_server_port()=5432",
            "session_user='postgres'",
            "current_setting('frfinance.m39950_ci',true)='DISPOSABLE_ONLY'",
            "M39950_BLOCKED_WRONG_CLUSTER",
            "M39950_ORIGINAL_DB_ACCESS=NONE",
        ):
            self.assertIn(code,self.src)
        self.assertEqual(self.src.count("\nBEGIN;"),1)
        self.assertEqual(self.src.count("\nROLLBACK;"),1)
        self.assertNotRegex(self.src,r"(?m)^\s*COMMIT\s*;")

    def test_immutable_review_catalog_and_provenance(self):
        for code in (
            "CREATE SCHEMA m39950_ci",
            "CREATE TABLE m39950_ci.documents",
            "CREATE TABLE m39950_ci.review_claims",
            "UNIQUE(scope,cashbox_key,evidence_reference)",
            "FOREIGN KEY(document_id,scope,cashbox_key,journal_fingerprint,document_digest)",
            "m39950_preparer_diff_reviewer",
            "CREATE TRIGGER m39950_claim_no_preparer",
            "BEFORE UPDATE OR DELETE",
            "M39950_APPEND_ONLY",
            "M39950 replay accepted",
            "M39950 cross-tenant FK accepted",
            "M39950 duplicate reviewer accepted",
            "M39950 false approval accepted",
            "M39950 self-review accepted",
            "M39950 mutable document",
            "M39950 mutable review",
            "CHECK(journal_posted=false)",
            "CHECK(payout_enabled=false)",
            "CHECK(available_balance_cents IS NULL)",
        ):
            self.assertIn(code,self.src)

    def test_role_scope_and_no_real_reconciliation(self):
        for code in (
            "PLATFORM_MASTER", "TENANT_ADMIN_OWN", "TENANT_COLLECTIVE",
            "CREATE ROLE m39950_ci_reader NOLOGIN NOBYPASSRLS",
            "ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY",
            "GRANT SELECT ON m39950_ci.documents,m39950_ci.review_claims",
            "SET LOCAL ROLE m39950_ci_reader",
            "M39950 master RLS leak",
            "M39950 admin tenant A RLS leak",
            "M39950 admin tenant B RLS leak",
            "M39950 member exclusive RLS leak",
        ):
            self.assertIn(code,self.src)
        for bad in (
            "frcaixinha_aistudio_dev","DROP DATABASE",
            "frcaixinha_2_2","pg_ctl","dblink",
            "http_request", "POST http", "PIX_REAL=ON",
        ):
            self.assertNotIn(bad,self.src)
        self.assertNotRegex(self.src,re.compile(r"(?m)^CREATE TABLE public\."))
        self.assertNotRegex(self.src,re.compile(r"(?m)^ALTER TABLE public\."))
        self.assertTrue(SQL.is_file())

if __name__=="__main__":
    unittest.main()
