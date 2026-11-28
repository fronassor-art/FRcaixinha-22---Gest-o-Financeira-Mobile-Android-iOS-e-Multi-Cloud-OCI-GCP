"""M39900: no database, no payment provider, only cross-cashbox tests."""
from pathlib import Path
import unittest
from uuid import UUID

from backend.app.exclusive_cashbox_provenance import (
    EVENT_SCOPE, PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE,
    classify_cashbox_source,
)

TENANT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class ThreeCashboxFence(unittest.TestCase):
    def test_every_known_source_is_classified_but_never_postable(self):
        self.assertEqual(len(EVENT_SCOPE), 7)
        for event, scope in EVENT_SCOPE.items():
            tenant = None if scope == PLATFORM_MASTER else TENANT_A
            with self.subTest(event=event):
                evidence = classify_cashbox_source(event, scope, tenant)
                self.assertEqual(evidence.scope, scope)
                self.assertEqual(evidence.tenant_id, tenant)
                self.assertFalse(evidence.posting_authorized)
                self.assertFalse(evidence.withdrawal_authorized)
                self.assertIsNone(evidence.reconciled_balance_cents)
                self.assertEqual(evidence.evidence_state, "SOURCE_CLASSIFIED_ONLY")

    def test_platform_never_mix_with_tenant_balance(self):
        for event in ("SAAS_SETTLEMENT", "PLATFORM_OPERATING_EXPENSE"):
            for bad_tenant in (TENANT_A, TENANT_B):
                with self.assertRaises(ValueError):
                    classify_cashbox_source(event, PLATFORM_MASTER, bad_tenant)
            for bad_scope in (TENANT_ADMIN_OWN, TENANT_COLLECTIVE):
                with self.assertRaises(ValueError):
                    classify_cashbox_source(event, bad_scope, TENANT_A)

    def test_admin_remuneration_is_not_collective_cash(self):
        for event in ("ADMIN_CLOSING_REMUNERATION", "ADMIN_OWN_EXPENSE"):
            for bad_scope in (PLATFORM_MASTER, TENANT_COLLECTIVE):
                with self.assertRaises(ValueError):
                    classify_cashbox_source(event, bad_scope, TENANT_A)
            with self.assertRaises(ValueError):
                classify_cashbox_source(event, TENANT_ADMIN_OWN, None)

    def test_member_contributions_never_become_admin_income(self):
        for event in ("MEMBER_CONTRIBUTION", "TENANT_LOAN_REPAYMENT",
                      "TENANT_OPERATING_EXPENSE"):
            for bad_scope in (PLATFORM_MASTER, TENANT_ADMIN_OWN):
                with self.assertRaises(ValueError):
                    classify_cashbox_source(event, bad_scope, TENANT_A)

    def test_invalid_or_missing_identity_blocked(self):
        for event in ("", "UNKNOWN", "SAAS_SETTLEMENT "):
            with self.assertRaises(ValueError):
                classify_cashbox_source(event, PLATFORM_MASTER, None)
        for tenant in (None, str(TENANT_A), 123, True):
            with self.assertRaises(ValueError):
                classify_cashbox_source("ADMIN_CLOSING_REMUNERATION",
                                        TENANT_ADMIN_OWN, tenant)

    def test_no_mutating_or_database_source(self):
        root = Path(__file__).resolve().parents[1] / "app"
        src = (root / "exclusive_cashbox_provenance.py").read_text()
        for forbidden in ("asyncpg", "psycopg", "subprocess", "requests",
                          "CREATE TABLE", "INSERT INTO", "UPDATE public.",
                          "DELETE FROM", "os.kill", "pg_ctl", "fetch("):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
