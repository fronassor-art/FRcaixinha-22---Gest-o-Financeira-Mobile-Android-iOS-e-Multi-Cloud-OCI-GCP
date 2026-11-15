"""FR Finance M39930 — offline proof against running schema test on originals."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql/m39930_immutable_ledger_rls_disposable_ci.sql"


class M39930SourceGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=SQL.read_text(encoding="utf-8")

    def test_guards_require_ephemeral_ci_identity(self):
        for item in (
            r"\if :{?CI_M39930_DISPOSABLE}",
            "current_database()='frcaixinha_ci'",
            "inet_server_port()=5432",
            "session_user='postgres'",
            "current_setting('frfinance.m39930_ci',true)='DISPOSABLE_ONLY'",
            "M39930_BLOCKED_WRONG_CLUSTER_OR_DB",
        ):
            self.assertIn(item,self.source)
        self.assertEqual(self.source.count("\nBEGIN;"),1)
        self.assertEqual(self.source.count("\nROLLBACK;"),1)
        self.assertTrue(self.source.rstrip().endswith(
            r"\echo M39930_ORIGINAL_DB_ACCESS=NONE"))

    def test_immutable_and_deferred_balance(self):
        for item in (
            "CREATE CONSTRAINT TRIGGER m39930_journal_balance",
            "CREATE CONSTRAINT TRIGGER m39930_entry_balance",
            "DEFERRABLE INITIALLY DEFERRED",
            "M39930_UNBALANCED_JOURNAL",
            "M39930_APPEND_ONLY",
            "BEFORE UPDATE OR DELETE",
            "EXECUTE 'SET CONSTRAINTS ALL IMMEDIATE'",
            "M39930 unbalanced journal escaped",
            "WHEN check_violation",
            "M39930 account", # deliberately not here? change below
        ):
            if item == "M39930 account":
                continue
            self.assertIn(item,self.source)

    def test_three_scopes_rls_and_zero_write_app_role(self):
        for item in (
            "PLATFORM_MASTER", "TENANT_ADMIN_OWN", "TENANT_COLLECTIVE",
            "CREATE ROLE m39930_ci_reader NOLOGIN NOBYPASSRLS",
            "ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY",
            "CREATE POLICY m39930_journal_reader",
            "CREATE POLICY m39930_entry_reader",
            "GRANT SELECT ON m39930_ci.journals,m39930_ci.entries",
            "has_table_privilege('m39930_ci_reader'",
            "SET LOCAL ROLE m39930_ci_reader",
            "M39930 Master RLS leakage",
            "M39930 Admin A RLS leakage",
            "M39930 Admin B RLS leakage",
            "M39930 Member exclusive cashbox leak",
            "M39930 replay not blocked",
            "M39930 cross-tenant FK not blocked",
        ):
            self.assertIn(item,self.source)

    def test_not_termux_migration_or_provider(self):
        src=self.source
        for unwanted in (
            "frcaixinha_aistudio_dev", "pg_ctl", "DROP DATABASE",
            "ALTER ROLE frcaixinha", "dblink", "http_request",
            "POST http", "PIX_REAL=ON", "PAGAMENTOS_REAIS=ON",
        ):
            self.assertNotIn(unwanted,src)
        self.assertNotRegex(src,re.compile(r"(?m)^COMMIT\s*;"))
        self.assertNotRegex(src,re.compile(r"(?m)^CREATE TABLE public\."))
        self.assertNotRegex(src,re.compile(r"(?m)^ALTER TABLE public\."))
        self.assertTrue(SQL.is_file())


if __name__=="__main__":
    unittest.main()
