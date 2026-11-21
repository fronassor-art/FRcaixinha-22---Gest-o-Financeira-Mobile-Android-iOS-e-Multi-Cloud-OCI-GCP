"""M39950: synthetic two-reviewer chain is still NOT a financial approval."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from uuid import UUID

from backend.app.exclusive_cashbox_documentary_review import (
    DocumentaryReviewClaim, inspect_documentary_review_claims,
)
from backend.app.exclusive_cashbox_evidence_preflight import EvidenceDraft
from backend.app.exclusive_cashbox_journal_preflight import (
    CandidateLine, review_journal_candidate,
)
from backend.app.exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE,
)

TENANT_A=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
PREPARER=UUID("11111111-1111-4111-8111-111111111111")
REVIEWER_A=UUID("22222222-2222-4222-8222-222222222222")
REVIEWER_B=UUID("33333333-3333-4333-8333-333333333333")
CYCLE=UUID("44444444-4444-4444-8444-444444444444")
POLICY=UUID("55555555-5555-4555-8555-555555555555")
T=datetime(2026,11,15,12,0,tzinfo=timezone.utc)


def sample(scope=PLATFORM_MASTER):
    if scope==PLATFORM_MASTER:
        event,prefix,tenant,amount,kind="SAAS_SETTLEMENT","PM_",None,1200,"PROVIDER_SETTLEMENT"
        extra=dict(provider_payment_id="123456",provider_collector_id="654321",
                   provider_observed_at=T)
    elif scope==TENANT_ADMIN_OWN:
        event,prefix,tenant,amount,kind="ADMIN_CLOSING_REMUNERATION","TA_",TENANT_A,1500,"ANNUAL_CLOSING"
        extra=dict(cycle_id=CYCLE,policy_id=POLICY,closing_year=2026,
                   net_profit_cents=10000,proposed_members_pool_cents=8500)
    else:
        event,prefix,tenant,amount,kind="MEMBER_CONTRIBUTION","TC_",TENANT_A,900,"PROVIDER_SETTLEMENT"
        extra=dict(provider_payment_id="123456",provider_collector_id="654321",
                   provider_observed_at=T)
    journal=review_journal_candidate(
        event_type=event,scope=scope,tenant_id=tenant,
        evidence_reference="ci-review-evidence-001",
        lines=(CandidateLine(scope,tenant,prefix+"RECEIVABLE","DR",amount),
               CandidateLine(scope,tenant,prefix+"OFFSET","CR",amount)),
    )
    evidence=EvidenceDraft(
        scope=scope,tenant_id=tenant,event_type=event,
        journal_fingerprint=journal.fingerprint,evidence_reference=journal.evidence_reference,
        document_kind=kind,document_digest="c"*64,obligation_amount_cents=amount,
        preparer_id=PREPARER,proposed_reviewer_id=REVIEWER_A,
        **extra,
    )
    a=DocumentaryReviewClaim(
        scope=scope,tenant_id=tenant,journal_fingerprint=journal.fingerprint,
        document_digest=evidence.document_digest,reviewer_id=REVIEWER_A,
        claimed_at=T,decision="DOCUMENTARY_CHECK_PROPOSED",
        note_code="SHAPE_REVIEW_PENDING",
    )
    b=replace(a,reviewer_id=REVIEWER_B,
              claimed_at=T+timedelta(minutes=1),
              decision="REQUEST_MORE_EVIDENCE",
              note_code="PROVIDER_AUTHENTICITY_PENDING")
    return journal,evidence,(a,b)


class TestM39950ReviewChain(unittest.TestCase):
    def test_each_scope_only_unverified_review_claims(self):
        for scope in (PLATFORM_MASTER,TENANT_ADMIN_OWN,TENANT_COLLECTIVE):
            with self.subTest(scope=scope):
                journal,evidence,claims=sample(scope)
                r=inspect_documentary_review_claims(journal,evidence,claims)
                self.assertEqual(r.state,"DOCUMENTARY_REVIEW_CLAIMS_UNVERIFIED")
                self.assertEqual(r.claimed_review_count,2)
                self.assertEqual(r.scope,scope)
                self.assertEqual(r.tenant_id,journal.tenant_id)
                self.assertEqual(len(r.chain_fingerprint),64)
                self.assertTrue(r.outstanding_gates)
                for field in (
                    "document_authenticated","reviewer_identities_verified",
                    "two_person_approval_verified","independent_authorization_verified",
                    "provider_reconciled","journal_posted","payout_enabled",
                ):
                    self.assertIs(getattr(r,field),False)
                with self.assertRaises(FrozenInstanceError):
                    r.payout_enabled=True

    def test_fingerprint_repeatable_but_not_signature(self):
        journal,evidence,claims=sample()
        one=inspect_documentary_review_claims(journal,evidence,claims)
        again=inspect_documentary_review_claims(journal,evidence,claims)
        self.assertEqual(one.chain_fingerprint,again.chain_fingerprint)
        changed=inspect_documentary_review_claims(journal,evidence,
            (claims[0],replace(claims[1],note_code="POLICY_AND_CYCLE_PENDING")))
        self.assertNotEqual(one.chain_fingerprint,changed.chain_fingerprint)
        self.assertIn("INDEPENDENT_SIGNATURES_OR_SERVER_ATTESTATION_REQUIRED",one.outstanding_gates)

    def test_two_independent_claims_required(self):
        journal,evidence,claims=sample()
        for bad in (None,[],(),(claims[0],),(claims[0],claims[1],claims[1])):
            with self.subTest(count=type(bad).__name__):
                with self.assertRaises(ValueError):
                    inspect_documentary_review_claims(journal,evidence,bad)
        with self.assertRaises(ValueError):
            inspect_documentary_review_claims(journal,evidence,
                (claims[0],replace(claims[1],reviewer_id=REVIEWER_A)))
        with self.assertRaises(ValueError):
            inspect_documentary_review_claims(journal,evidence,
                (replace(claims[0],reviewer_id=PREPARER),claims[1]))
        with self.assertRaises(ValueError):
            inspect_documentary_review_claims(journal,evidence,
                (replace(claims[0],reviewer_id=REVIEWER_B),
                 replace(claims[1],reviewer_id=UUID("66666666-6666-4666-8666-666666666666"))))

    def test_cross_tenant_and_hash_replay_denied(self):
        journal,evidence,claims=sample(TENANT_COLLECTIVE)
        for alter in (
            dict(tenant_id=TENANT_B),
            dict(scope=TENANT_ADMIN_OWN),
            dict(journal_fingerprint="d"*64),
            dict(document_digest="e"*64),
        ):
            with self.subTest(alter=alter):
                with self.assertRaises(ValueError):
                    inspect_documentary_review_claims(journal,evidence,
                        (replace(claims[0],**alter),claims[1]))
        with self.assertRaises(ValueError):
            inspect_documentary_review_claims(journal,replace(evidence,document_digest="e"*64),claims)

    def test_disallow_payment_or_approval_decisions(self):
        journal,evidence,claims=sample()
        for decision in ("APPROVED","PAY","SETTLED","TRANSFER","SIGN",None,True,""):
            with self.subTest(decision=decision):
                with self.assertRaises(ValueError):
                    inspect_documentary_review_claims(journal,evidence,
                        (replace(claims[0],decision=decision),claims[1]))
        for code in ("PRODUCTION",None,1,""):
            with self.subTest(note=code):
                with self.assertRaises(ValueError):
                    inspect_documentary_review_claims(journal,evidence,
                        (replace(claims[0],note_code=code),claims[1]))

    def test_timezone_aware_and_monotonic(self):
        journal,evidence,claims=sample()
        for bad in (None,"2026-11-15T12:00Z",datetime(2026,11,15,12,0)):
            with self.subTest(date=bad):
                with self.assertRaises(ValueError):
                    inspect_documentary_review_claims(journal,evidence,
                        (replace(claims[0],claimed_at=bad),claims[1]))
        with self.assertRaises(ValueError):
            inspect_documentary_review_claims(journal,evidence,
                (claims[0],replace(claims[1],claimed_at=T-timedelta(seconds=1))))
        offset=timezone(timedelta(hours=-3))
        altered=replace(claims[0],claimed_at=T.astimezone(offset))
        a=inspect_documentary_review_claims(journal,evidence,claims)
        b=inspect_documentary_review_claims(journal,evidence,(altered,claims[1]))
        self.assertEqual(a.chain_fingerprint,b.chain_fingerprint)

    def test_never_trust_forged_financial_evidence(self):
        journal,evidence,claims=sample()
        for flagged in (
            replace(journal,journal_posted=True),
            replace(journal,evidence_attested=True),
            replace(journal,withdrawal_enabled=True),
        ):
            with self.assertRaises(ValueError):
                inspect_documentary_review_claims(flagged,evidence,claims)
        with self.assertRaises(ValueError):
            inspect_documentary_review_claims(journal,
                replace(evidence,obligation_amount_cents=1199),claims)

    def test_no_io_or_database_mutation(self):
        source=(Path(__file__).resolve().parents[1]/
                "app/exclusive_cashbox_documentary_review.py").read_text()
        for term in ("asyncpg","psycopg","requests.","httpx",
                     "INSERT INTO","UPDATE public.","DELETE FROM",
                     "subprocess","os.kill","create_payment"):
            self.assertNotIn(term,source)
        self.assertIn("payout_enabled: bool = False",source)
        self.assertIn("journal_posted: bool = False",source)


if __name__=="__main__":
    unittest.main()
