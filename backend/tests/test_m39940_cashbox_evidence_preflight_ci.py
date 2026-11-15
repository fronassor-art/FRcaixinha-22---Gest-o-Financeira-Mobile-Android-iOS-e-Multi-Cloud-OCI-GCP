"""FR Finance M39940 — evidence preflight is not settlement approval.

All fixtures are synthetic and pure; no PostgreSQL, cloud or provider calls.
"""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
import unittest
from uuid import UUID

from backend.app.exclusive_cashbox_evidence_preflight import (
    EvidenceDraft, preflight_cashbox_evidence,
)
from backend.app.exclusive_cashbox_journal_preflight import (
    CandidateLine, review_journal_candidate,
)
from backend.app.exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE,
)

TENANT_A=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
PREPARER=UUID("11111111-1111-4111-8111-111111111111")
REVIEWER=UUID("22222222-2222-4222-8222-222222222222")
CYCLE=UUID("33333333-3333-4333-8333-333333333333")
POLICY=UUID("44444444-4444-4444-8444-444444444444")
WHEN=datetime(2026,11,14,15,0,tzinfo=timezone.utc)

EVENTS=(
    ("SAAS_SETTLEMENT",PLATFORM_MASTER,None,"PM_","PROVIDER_SETTLEMENT",1200),
    ("PLATFORM_OPERATING_EXPENSE",PLATFORM_MASTER,None,"PM_","FISCAL_EXPENSE",450),
    ("ADMIN_CLOSING_REMUNERATION",TENANT_ADMIN_OWN,TENANT_A,"TA_","ANNUAL_CLOSING",1500),
    ("ADMIN_OWN_EXPENSE",TENANT_ADMIN_OWN,TENANT_A,"TA_","FISCAL_EXPENSE",125),
    ("MEMBER_CONTRIBUTION",TENANT_COLLECTIVE,TENANT_A,"TC_","PROVIDER_SETTLEMENT",15000),
    ("TENANT_LOAN_REPAYMENT",TENANT_COLLECTIVE,TENANT_A,"TC_","PROVIDER_SETTLEMENT",600),
    ("TENANT_OPERATING_EXPENSE",TENANT_COLLECTIVE,TENANT_A,"TC_","FISCAL_EXPENSE",90),
)


def sample(case=EVENTS[0]):
    event,scope,tenant,prefix,kind,amount=case
    journal=review_journal_candidate(
        event_type=event,scope=scope,tenant_id=tenant,
        evidence_reference="ci-document-00001",
        lines=(
            CandidateLine(scope,tenant,prefix+"RECEIVABLE","DR",amount),
            CandidateLine(scope,tenant,prefix+"OFFSET","CR",amount),
        ),
    )
    extra={}
    if kind=="PROVIDER_SETTLEMENT":
        extra=dict(provider_payment_id="123456789",
                   provider_collector_id="987654321",
                   provider_observed_at=WHEN)
    if kind=="FISCAL_EXPENSE":
        extra=dict(expense_reference="invoice:2026:0001")
    if kind=="ANNUAL_CLOSING":
        extra=dict(cycle_id=CYCLE,policy_id=POLICY,
                   net_profit_cents=10000,
                   proposed_members_pool_cents=8500,closing_year=2026)
    evidence=EvidenceDraft(
        scope=scope,tenant_id=tenant,event_type=event,
        journal_fingerprint=journal.fingerprint,
        evidence_reference=journal.evidence_reference,
        document_kind=kind,document_digest="a"*64,
        obligation_amount_cents=amount,preparer_id=PREPARER,
        proposed_reviewer_id=REVIEWER,**extra,
    )
    return journal,evidence


class M39940EvidencePreflight(unittest.TestCase):
    def assert_blocked(self,journal,evidence):
        with self.assertRaises(ValueError):
            preflight_cashbox_evidence(journal,evidence)

    def test_all_seven_event_types_are_preview_only(self):
        for case in EVENTS:
            with self.subTest(event=case[0]):
                journal,evidence=sample(case)
                proof=preflight_cashbox_evidence(journal,evidence)
                self.assertEqual(proof.state,"DOCUMENTARY_CANDIDATE_NOT_AUTHENTICATED")
                self.assertEqual(proof.scope,case[1])
                self.assertEqual(proof.tenant_id,case[2])
                self.assertEqual(proof.journal_fingerprint,journal.fingerprint)
                self.assertGreaterEqual(len(proof.outstanding_gates),6)
                for flag in (
                    "document_authenticated","amount_reconciled","actor_authorized",
                    "independent_review_verified","original_db_posted",
                    "payout_authorized",
                ):
                    self.assertIs(getattr(proof,flag),False)
                with self.assertRaises(FrozenInstanceError):
                    proof.payout_authorized=True

    def test_no_external_evidence_claim_can_reconcile_money(self):
        journal,evidence=sample()
        out=preflight_cashbox_evidence(journal,evidence)
        self.assertIn("SOURCE_AUTHENTICITY_UNATTESTED",out.outstanding_gates)
        self.assertIn("TRANSACTIONAL_IDEMPOTENCY_UNATTESTED",out.outstanding_gates)
        self.assertIn("POSTING_AND_WITHDRAWAL_DISABLED",out.outstanding_gates)
        self.assertFalse(out.amount_reconciled)
        self.assertFalse(out.original_db_posted)

    def test_reject_fingerprint_and_source_mismatch(self):
        journal,evidence=sample()
        for change in (
            dict(journal_fingerprint="0"*64),
            dict(evidence_reference="ci-document-OTHER"),
            dict(scope=TENANT_COLLECTIVE),
            dict(tenant_id=TENANT_A),
            dict(event_type="MEMBER_CONTRIBUTION"),
            dict(document_kind="FISCAL_EXPENSE"),
        ):
            with self.subTest(change=change):
                self.assert_blocked(journal,replace(evidence,**change))

    def test_reject_wrong_cashbox_and_cross_tenant_journals(self):
        journal,evidence=sample(EVENTS[4])
        self.assert_blocked(journal,replace(evidence,tenant_id=TENANT_B))
        self.assert_blocked(journal,replace(evidence,scope=TENANT_ADMIN_OWN))
        self.assert_blocked(journal,replace(evidence,document_kind="ANNUAL_CLOSING"))
        fake=replace(journal,tenant_id=TENANT_B)
        self.assert_blocked(fake,evidence)

    def test_reject_bad_digest_and_non_independent_review(self):
        journal,evidence=sample()
        for invalid in ("", "z"*64, "A"*64, "a"*63, 1, None):
            with self.subTest(digest=invalid):
                self.assert_blocked(journal,replace(evidence,document_digest=invalid))
        self.assert_blocked(journal,replace(evidence,proposed_reviewer_id=PREPARER))
        self.assert_blocked(journal,replace(evidence,preparer_id="not-a-uuid"))

    def test_reject_amount_mismatch_and_boolean_dollars(self):
        journal,evidence=sample()
        for invalid in (0,True,-1,1.5,1201,10**13,None):
            with self.subTest(amount=invalid):
                self.assert_blocked(journal,replace(evidence,obligation_amount_cents=invalid))

    def test_provider_receipt_requires_shape_but_not_reconciliation(self):
        journal,evidence=sample(EVENTS[0])
        for change in (
            dict(provider_payment_id=None),
            dict(provider_payment_id="not-verified"),
            dict(provider_collector_id=None),
            dict(provider_collector_id="123;DROP TABLE"),
            dict(provider_observed_at=None),
            dict(provider_observed_at=datetime(2026,11,14,15,0)),
            dict(expense_reference="invoice:0001"),
            dict(cycle_id=CYCLE),
        ):
            with self.subTest(change=change):
                self.assert_blocked(journal,replace(evidence,**change))

    def test_fiscal_expense_must_not_be_payment_or_closing(self):
        journal,evidence=sample(EVENTS[1])
        for change in (
            dict(expense_reference=""),
            dict(expense_reference="too short"),
            dict(expense_reference=None),
            dict(provider_payment_id="101"),
            dict(provider_observed_at=WHEN),
            dict(policy_id=POLICY),
        ):
            with self.subTest(change=change):
                self.assert_blocked(journal,replace(evidence,**change))

    def test_annual_admin_share_matches_only_synthetic_15_percent(self):
        journal,evidence=sample(EVENTS[2])
        self.assertFalse(preflight_cashbox_evidence(journal,evidence).payout_authorized)
        for change in (
            dict(net_profit_cents=9999),
            dict(proposed_members_pool_cents=8499),
            dict(proposed_members_pool_cents=None),
            dict(proposed_members_pool_cents=True),
            dict(net_profit_cents=0),
            dict(net_profit_cents=True),
            dict(net_profit_cents=10**13),
            dict(cycle_id=None),
            dict(policy_id=None),
            dict(closing_year=0),
            dict(closing_year="2026"),
            dict(provider_payment_id="1"),
            dict(expense_reference="invoice:2026"),
        ):
            with self.subTest(change=change):
                self.assert_blocked(journal,replace(evidence,**change))
        # 15% of 10001 cents rounds to 1500, while 10004 gives 1501.
        self.assertFalse(preflight_cashbox_evidence(
            journal,replace(evidence,net_profit_cents=10001,
                            proposed_members_pool_cents=8501)).payout_authorized)
        self.assert_blocked(journal,replace(evidence,net_profit_cents=10004))

    def test_forged_journal_flags_and_unbalanced_lines_rejected(self):
        journal,evidence=sample()
        self.assert_blocked(replace(journal,provider_reconciled=True),evidence)
        self.assert_blocked(replace(journal,journal_posted=True),evidence)
        self.assert_blocked(replace(journal,payment_enabled=True),evidence)
        self.assert_blocked(replace(journal,withdrawal_enabled=True),evidence)
        self.assert_blocked(replace(journal,policy_attested=True),evidence)
        first,second=journal.lines
        fake=replace(journal,lines=(first,replace(second,amount_cents=1199)))
        self.assert_blocked(fake,evidence)

    def test_not_an_api_database_or_provider_integration(self):
        path=(Path(__file__).resolve().parents[1]/
              "app/exclusive_cashbox_evidence_preflight.py")
        code=path.read_text()
        for forbidden in (
            "asyncpg", "psycopg", "requests.", "httpx",
            "INSERT INTO", "UPDATE public.", "DELETE FROM",
            "os.kill", "subprocess.", "create_payment", "approve_payout",
        ):
            self.assertNotIn(forbidden,code)
        self.assertIn("payout_authorized: bool = False",code)
        self.assertIn("original_db_posted: bool = False",code)


if __name__=="__main__":
    unittest.main()
