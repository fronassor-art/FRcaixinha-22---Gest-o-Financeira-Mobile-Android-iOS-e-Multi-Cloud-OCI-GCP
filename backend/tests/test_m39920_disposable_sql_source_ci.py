"""M39920: verify disposable proof can never target a real FR Finance database."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql/m39920_three_cashbox_journal_disposable_ci.sql"


class DisposableSchemaSourceContract(unittest.TestCase):
    def test_ci_ownership_gate_and_rollback(self):
        src=SQL.read_text()
        for required in (
            r"\if :{?CI_M39920_DISPOSABLE}",
            "current_database()='frcaixinha_ci'",
            "inet_server_port()=5432",
            "session_user='postgres'",
            "current_setting('frfinance.m39920_ci',true)='DISPOSABLE_ONLY'",
            "CREATE TEMP TABLE m39920_cashbox_candidate",
            "CREATE TEMP TABLE m39920_cashbox_candidate_line",
            "ROLLBACK;",
            "M39920_SYNTHETIC_PERSISTENCE=NONE",
        ):
            self.assertIn(required,src)
        self.assertEqual(src.count("BEGIN;"),1)
        self.assertEqual(src.count("ROLLBACK;"),1)
        self.assertNotRegex(src,r"(?mi)^\s*COMMIT\s*;")
        self.assertNotRegex(src,r"(?mi)^\s*CREATE\s+TABLE\s+(?:public\.|[a-z])")
        self.assertNotRegex(src,r"(?mi)^\s*(?:DROP|ALTER|TRUNCATE)\s+(?:TABLE|ROLE|DATABASE)\b")

    def test_journal_scope_and_double_entry_invariants(self):
        src=SQL.read_text()
        for term in ("PLATFORM_MASTER","TENANT_ADMIN_OWN","TENANT_COLLECTIVE",
                     "m39920_scope_key","m39920_scope_event",
                     "m39920_account_prefix","entry_side IN ('DR','CR')",
                     "CHECK (posting_authorized=false)",
                     "CHECK (provider_reconciled=false)",
                     "CHECK (withdraw_enabled=false)",
                     "available_balance_cents IS NULL",
                     "sum(amount_cents) FILTER(WHERE entry_side='DR')",
                     "sum(amount_cents) FILTER(WHERE entry_side='CR')",
                     "unique", "foreign_key_violation", "check_violation"):
            self.assertIn(term.lower(),src.lower())

    def test_no_local_database_script_or_provider_calls(self):
        src=SQL.read_text().lower()
        for bad in ("frcaixinha_aistudio_dev","pg_ctl","oci", "pix_real=on",
                    "frcaixinha_2_2", "dblink", "copy ", "listen ", "notify "):
            self.assertNotIn(bad,src)
        self.assertTrue(SQL.is_file())


if __name__=="__main__":
    unittest.main()
