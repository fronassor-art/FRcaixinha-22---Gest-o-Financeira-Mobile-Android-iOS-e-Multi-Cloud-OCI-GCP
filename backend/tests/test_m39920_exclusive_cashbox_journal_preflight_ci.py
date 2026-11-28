"""M39920: synthetic journal preparation only, no connection to any database."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest
from uuid import UUID

from backend.app.exclusive_cashbox_journal_preflight import (
    CandidateLine, review_journal_candidate,
)
from backend.app.exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE,
)

A=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CASES=(
    ("SAAS_SETTLEMENT",PLATFORM_MASTER,None,"PM_"),
    ("PLATFORM_OPERATING_EXPENSE",PLATFORM_MASTER,None,"PM_"),
    ("ADMIN_CLOSING_REMUNERATION",TENANT_ADMIN_OWN,A,"TA_"),
    ("ADMIN_OWN_EXPENSE",TENANT_ADMIN_OWN,A,"TA_"),
    ("MEMBER_CONTRIBUTION",TENANT_COLLECTIVE,A,"TC_"),
    ("TENANT_LOAN_REPAYMENT",TENANT_COLLECTIVE,A,"TC_"),
    ("TENANT_OPERATING_EXPENSE",TENANT_COLLECTIVE,A,"TC_"),
)


def lines(scope,tenant,prefix,amount=15000):
    return (
        CandidateLine(scope,tenant,prefix+"ASSET","DR",amount),
        CandidateLine(scope,tenant,prefix+"OFFSET","CR",amount),
    )


def review(event,scope,tenant,prefix,amount=15000):
    return review_journal_candidate(
        event_type=event,scope=scope,tenant_id=tenant,
        evidence_reference="ci-evidence-123456",
        lines=lines(scope,tenant,prefix,amount),
    )


class JournalPreflight(unittest.TestCase):
    def test_all_seven_events_validate_shape_only(self):
        for e,s,t,p in CASES:
            with self.subTest(event=e):
                obj=review(e,s,t,p)
                self.assertEqual(obj.state,"STRUCTURAL_PREVIEW_NO_POSTING")
                self.assertEqual(len(obj.fingerprint),64)
                for field in ("evidence_attested","policy_attested",
                              "provider_reconciled","journal_posted",
                              "payment_enabled","withdrawal_enabled"):
                    self.assertIs(getattr(obj,field),False)
                with self.assertRaises(FrozenInstanceError):
                    obj.journal_posted=True

    def test_fingerprint_stable_when_lines_change_order(self):
        e,s,t,p=CASES[0]
        a=review(e,s,t,p)
        swapped=review_journal_candidate(event_type=e,scope=s,tenant_id=t,
            evidence_reference="ci-evidence-123456",
            lines=tuple(reversed(lines(s,t,p))))
        self.assertEqual(a.fingerprint,swapped.fingerprint)
        different=review_journal_candidate(event_type=e,scope=s,tenant_id=t,
            evidence_reference="ci-evidence-123457",
            lines=lines(s,t,p))
        self.assertNotEqual(a.fingerprint,different.fingerprint)

    def test_refuse_cross_cashbox_accounts_even_when_balanced(self):
        for e,s,t,p in CASES:
            other="PM_" if p!="PM_" else "TA_"
            wrong=(
                CandidateLine(s,t,p+"ASSET","DR",100),
                CandidateLine(s,t,other+"OFFSET","CR",100),
            )
            with self.subTest(event=e):
                with self.assertRaises(ValueError):
                    review_journal_candidate(event_type=e,scope=s,tenant_id=t,
                        evidence_reference="ci-evidence-123456",lines=wrong)

    def test_refuse_cross_tenant_even_with_matching_scope(self):
        for scope,event,prefix in ((TENANT_ADMIN_OWN,"ADMIN_OWN_EXPENSE","TA_"),
                                   (TENANT_COLLECTIVE,"MEMBER_CONTRIBUTION","TC_")):
            bad=(
                CandidateLine(scope,A,prefix+"ASSET","DR",120),
                CandidateLine(scope,B,prefix+"OFFSET","CR",120),
            )
            with self.assertRaises(ValueError):
                review_journal_candidate(event_type=event,scope=scope,tenant_id=A,
                    evidence_reference="ci-evidence-123456",lines=bad)

    def test_refuse_fabricated_master_tenant_or_role_transfer(self):
        e,s,_,p=CASES[0]
        with self.assertRaises(ValueError):
            review(e,s,A,p)
        with self.assertRaises(ValueError):
            review(e,TENANT_ADMIN_OWN,A,"TA_")
        with self.assertRaises(ValueError):
            review("ADMIN_CLOSING_REMUNERATION",TENANT_COLLECTIVE,A,"TC_")
        with self.assertRaises(ValueError):
            review("UNRECOGNIZED",PLATFORM_MASTER,None,"PM_")

    def test_refuse_unbalanced_or_non_integer_or_negative_amount(self):
        e,s,t,p=CASES[0]
        for bad in (0,-1,True,1.25,10**13,"15000",None):
            with self.subTest(amount=bad):
                candidate=(
                    CandidateLine(s,t,p+"ASSET","DR",bad),
                    CandidateLine(s,t,p+"OFFSET","CR",bad),
                )
                with self.assertRaises(ValueError):
                    review_journal_candidate(event_type=e,scope=s,tenant_id=t,
                        evidence_reference="ci-evidence-123456",lines=candidate)
        unbalanced=(
            CandidateLine(s,t,p+"ASSET","DR",150),
            CandidateLine(s,t,p+"OFFSET","CR",149),
        )
        with self.assertRaises(ValueError):
            review_journal_candidate(event_type=e,scope=s,tenant_id=t,
                evidence_reference="ci-evidence-123456",lines=unbalanced)

    def test_refuse_duplicate_or_single_account_or_malformed_reference(self):
        e,s,t,p=CASES[0]
        bad=(
            CandidateLine(s,t,p+"ASSET","DR",100),
            CandidateLine(s,t,p+"ASSET","CR",100),
        )
        with self.assertRaises(ValueError):
            review_journal_candidate(event_type=e,scope=s,tenant_id=t,
                evidence_reference="ci-evidence-123456",lines=bad)
        duplicate=lines(s,t,p)+lines(s,t,p)
        with self.assertRaises(ValueError):
            review_journal_candidate(event_type=e,scope=s,tenant_id=t,
                evidence_reference="ci-evidence-123456",lines=duplicate)
        for ref in ("", "short", "with space", "'; DROP TABLE users; --", "a"*121):
            with self.subTest(reference=ref):
                with self.assertRaises(ValueError):
                    review_journal_candidate(event_type=e,scope=s,tenant_id=t,
                        evidence_reference=ref,lines=lines(s,t,p))

    def test_not_a_posting_or_policy_or_production_adapter(self):
        source=(Path(__file__).resolve().parents[1]/"app/exclusive_cashbox_journal_preflight.py").read_text()
        for forbidden in ("asyncpg", "psycopg", "subprocess", "requests.",
                          "os.kill", "pg_ctl", "INSERT INTO", "UPDATE public.",
                          "DELETE FROM", "COMMIT;", "PIX_REAL=ON"):
            self.assertNotIn(forbidden,source)
        self.assertIn('journal_posted: bool = False',source)
        self.assertIn('provider_reconciled: bool = False',source)


if __name__=="__main__":
    unittest.main()
