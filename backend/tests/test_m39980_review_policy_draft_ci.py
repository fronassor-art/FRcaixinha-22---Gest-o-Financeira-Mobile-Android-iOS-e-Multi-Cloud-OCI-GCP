"""M39980: authorizations remain missing even with a well-formed draft.

These fixtures are untrusted and synthetic; NEVER a real two-person signature.
"""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from pathlib import Path
from uuid import UUID
import ast
import unittest

from backend.app.exclusive_cashbox_provenance import (
    PLATFORM_MASTER,TENANT_ADMIN_OWN,TENANT_COLLECTIVE,
)
from backend.app.exclusive_cashbox_review_policy_draft import (
    DraftReviewPolicyDenied, ReviewPolicyDraft, ReviewerGrantDraft,
    assess_unapproved_review_policy,
)
from backend.tests.test_m39970_review_session_pair_ci import (
    fixture, fake_session, T, OBSERVED, TENANT_A, TENANT_B,
    PREPARER, REVIEWER_A, REVIEWER_B, SID_A, SID_B,
)
from backend.tests.test_m39950_documentary_review_chain_ci import sample
from backend.app.exclusive_cashbox_documentary_review import DocumentaryReviewClaim
from backend.app.exclusive_cashbox_review_session_pair import (
    correlate_unverified_review_sessions,
)

AUTHOR=UUID("99999999-9999-4999-8999-999999999999")
POLICY=UUID("44444444-4444-4444-8444-444444444444")
EVENTS={
    PLATFORM_MASTER:"SAAS_SETTLEMENT",
    TENANT_ADMIN_OWN:"ADMIN_CLOSING_REMUNERATION",
}

def setup(scope=PLATFORM_MASTER):
    j,e,claims,sessions=fixture(scope)
    role="MASTER" if scope==PLATFORM_MASTER else "TENANT_ADMIN"
    grants=tuple(ReviewerGrantDraft(
        reviewer_id=uid,scope=scope,tenant_id=j.tenant_id,role=role)
        for uid in (REVIEWER_A,REVIEWER_B))
    policy=ReviewPolicyDraft(
        policy_id=POLICY,policy_document_digest="a"*64,
        scope=scope,tenant_id=j.tenant_id,event_type=EVENTS[scope],
        created_by=AUTHOR,created_by_role=role,
        valid_from=T-timedelta(minutes=2),
        valid_until=T+timedelta(minutes=15),
        reviewer_grants=grants,
    )
    return j,e,claims,sessions,policy

class TestM39980PolicyDraft(unittest.TestCase):
    def check_rejected(self,j,e,c,s,p,now=OBSERVED):
        with self.assertRaises(DraftReviewPolicyDenied):
            assess_unapproved_review_policy(
                j,e,c,s,p,observed_at=now)

    def test_master_and_admin_scoped_drafts_remain_unapproved(self):
        for scope in (PLATFORM_MASTER,TENANT_ADMIN_OWN):
            with self.subTest(scope=scope):
                j,e,c,s,p=setup(scope)
                result=assess_unapproved_review_policy(
                    j,e,c,s,p,observed_at=OBSERVED)
                self.assertEqual(result.state,"POLICY_DRAFT_NO_AUTHORITY")
                self.assertEqual(result.scope,scope)
                self.assertEqual(result.tenant_id,j.tenant_id)
                self.assertEqual(result.journal_fingerprint,j.fingerprint)
                self.assertEqual(len(result.policy_draft_fingerprint),64)
                self.assertGreaterEqual(len(result.outstanding_gates),8)
                self.assertTrue(result.reviewer_grant_shapes_aligned)
                for prop in (
                    "policy_approved","policy_source_authenticated",
                    "roles_and_tenant_authorized",
                    "independent_reviewer_appointment_verified",
                    "two_person_approval_verified","event_evidence_reconciled",
                    "journal_posted","payment_enabled","payout_enabled",
                ):
                    self.assertIs(getattr(result,prop),False)
                self.assertIn("JOURNAL_POSTING_AND_PAYOUT_DISABLED",
                              result.outstanding_gates)
                with self.assertRaises(FrozenInstanceError):
                    result.policy_approved=True

    def test_distinct_policy_gap_by_financial_patrimony(self):
        j,e,c,s,p=setup(PLATFORM_MASTER)
        report=assess_unapproved_review_policy(j,e,c,s,p,observed_at=OBSERVED)
        self.assertIn("MASTER_INDEPENDENT_REVIEWER_MANDATE_UNRATIFIED",
                      report.outstanding_gates)
        self.assertIn("PROVIDER_SETTLEMENT_AND_SAAS_ENTITLEMENT_UNVERIFIED",
                      report.outstanding_gates)
        j,e,c,s,p=setup(TENANT_ADMIN_OWN)
        report=assess_unapproved_review_policy(j,e,c,s,p,observed_at=OBSERVED)
        self.assertIn(
            "TENANT_ADMIN_OWN_SECOND_REVIEWER_DESIGNATION_UNRATIFIED",
            report.outstanding_gates)
        self.assertIn("ANNUAL_CLOSING_AND_15_85_ENTITLEMENTS_UNVERIFIED",
                      report.outstanding_gates)

    def test_deterministic_fingerprint_not_legal_signature(self):
        j,e,c,s,p=setup()
        a=assess_unapproved_review_policy(j,e,c,s,p,observed_at=OBSERVED)
        b=assess_unapproved_review_policy(j,e,c,s,p,observed_at=OBSERVED)
        self.assertEqual(a.policy_draft_fingerprint,b.policy_draft_fingerprint)
        alt=assess_unapproved_review_policy(j,e,c,s,replace(
            p,policy_document_digest="b"*64),observed_at=OBSERVED)
        self.assertNotEqual(a.policy_draft_fingerprint,
                            alt.policy_draft_fingerprint)
        self.assertFalse(a.policy_source_authenticated)
        self.assertFalse(alt.policy_approved)

    def test_cross_tenant_scope_and_event_fail_closed(self):
        j,e,c,s,p=setup(TENANT_ADMIN_OWN)
        for change in (
            dict(tenant_id=TENANT_B),
            dict(tenant_id=None),
            dict(scope=PLATFORM_MASTER),
            dict(scope=TENANT_COLLECTIVE),
            dict(event_type="SAAS_SETTLEMENT"),
            dict(event_type="TENANT_OPERATING_EXPENSE"),
            dict(event_type="UNKNOWN"),
            dict(event_type=0),
        ):
            with self.subTest(change=change):
                self.check_rejected(j,e,c,s,replace(p,**change))
        jm,em,cm,sm,pm=setup(PLATFORM_MASTER)
        self.check_rejected(jm,em,cm,sm,replace(pm,tenant_id=TENANT_A))

    def test_unsigned_or_approved_claim_from_client_is_denied(self):
        j,e,c,s,p=setup()
        for status in ("APPROVED","SIGNED","ACTIVE","RATIFIED",None,False):
            with self.subTest(status=status):
                self.check_rejected(j,e,c,s,replace(p,status=status))
        for digest in ("",None,"A"*64,"x"*64,123,"0"*63):
            with self.subTest(digest=digest):
                self.check_rejected(j,e,c,s,replace(p,policy_document_digest=digest))
        for invalid in (None,"abc",UUID(int=0),True):
            with self.subTest(id=invalid):
                self.check_rejected(j,e,c,s,replace(p,policy_id=invalid))

    def test_reviewer_role_delegation_or_cross_tenant_denied(self):
        j,e,c,s,p=setup(TENANT_ADMIN_OWN)
        for bad in (
            replace(p.reviewer_grants[1],tenant_id=TENANT_B),
            replace(p.reviewer_grants[1],scope=PLATFORM_MASTER),
            replace(p.reviewer_grants[1],role="MASTER"),
            replace(p.reviewer_grants[1],role="TENANT_MEMBER"),
            replace(p.reviewer_grants[1],grant_origin="SERVER_VERIFIED"),
            replace(p.reviewer_grants[1],grant_origin="APPROVED"),
            replace(p.reviewer_grants[1],reviewer_id=REVIEWER_A),
            replace(p.reviewer_grants[1],reviewer_id=AUTHOR),
            replace(p.reviewer_grants[1],reviewer_id=PREPARER),
        ):
            with self.subTest(bad=bad):
                self.check_rejected(j,e,c,s,replace(
                    p,reviewer_grants=(p.reviewer_grants[0],bad)))

    def test_no_creator_or_preparer_as_reviewer(self):
        j,e,c,s,p=setup()
        self.check_rejected(j,e,c,s,replace(p,created_by=PREPARER))
        self.check_rejected(j,e,c,s,replace(p,created_by=REVIEWER_A))
        self.check_rejected(j,e,c,s,replace(p,created_by=REVIEWER_B))
        self.check_rejected(j,e,c,s,replace(p,created_by=UUID(int=0)))
        self.check_rejected(j,e,c,s,replace(p,created_by="not-uuid"))
        self.check_rejected(j,e,c,s,replace(p,created_by_role="TENANT_ADMIN"))

    def test_windows_and_alleged_claim_times_are_not_attestations(self):
        j,e,c,s,p=setup()
        bad_windows=(
            dict(valid_from=OBSERVED+timedelta(minutes=1)),
            dict(valid_until=OBSERVED),
            dict(valid_from=p.valid_until),
            dict(valid_until=p.valid_from),
            dict(valid_from=p.valid_from.replace(tzinfo=None)),
            dict(valid_until=p.valid_until.replace(tzinfo=None)),
            dict(valid_from="2026-11-15"),
        )
        for change in bad_windows:
            with self.subTest(change=change):
                self.check_rejected(j,e,c,s,replace(p,**change))
        self.check_rejected(j,e,c,s,p,now=OBSERVED.replace(tzinfo=None))
        # Despite valid sessions, their alleged review dates do not belong
        # to the policy's proposed effective interval.
        later=replace(p,valid_from=T+timedelta(seconds=30))
        self.check_rejected(j,e,c,s,later)

    def test_distinct_sessions_still_do_not_attest_grants(self):
        j,e,c,s,p=setup()
        self.check_rejected(j,e,c,(s[0],s[0]),p)
        self.check_rejected(j,e,c,(s[1],s[0]),p)
        self.check_rejected(j,e,c,(s[0],fake_session(
            REVIEWER_B,SID_B,PLATFORM_MASTER,
            role_override="TENANT_ADMIN")),p)
        self.check_rejected(j,e,c,s,replace(
            p,reviewer_grants=(p.reviewer_grants[0],)))
        self.check_rejected(j,e,c,s,replace(
            p,reviewer_grants=list(p.reviewer_grants)))
        self.check_rejected(j,e,c,s,replace(
            p,reviewer_grants=(p.reviewer_grants[0],"not-a-grant")))

    def test_collective_scope_unratified_even_with_two_claims(self):
        j,e,c,s=fixture(TENANT_COLLECTIVE)
        grants=(
            ReviewerGrantDraft(REVIEWER_A,TENANT_COLLECTIVE,TENANT_A,"TENANT_ADMIN"),
            ReviewerGrantDraft(REVIEWER_B,TENANT_COLLECTIVE,TENANT_A,"TENANT_ADMIN"),
        )
        draft=ReviewPolicyDraft(
            POLICY,"a"*64,TENANT_COLLECTIVE,TENANT_A,
            "MEMBER_CONTRIBUTION",AUTHOR,"TENANT_ADMIN",
            T-timedelta(minutes=2),T+timedelta(minutes=15),grants,
        )
        self.check_rejected(j,e,c,s,draft)

    def test_source_stays_pure_and_all_money_flags_false(self):
        src=(Path(__file__).resolve().parents[1]/
             "app/exclusive_cashbox_review_policy_draft.py").read_text()
        self.assertIn("policy_approved: bool = False",src)
        self.assertIn("payout_enabled: bool = False",src)
        self.assertIn("status: str = \"PROPOSED_ONLY\"",src)
        self.assertIn("DRAFT_NOT_ATTESTED",src)
        tree=ast.parse(src)
        bad_imports={"asyncpg","psycopg","requests","httpx","urllib",
                     "subprocess","socket"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for item in node.names:
                    self.assertNotIn(item.name.split(".")[0],bad_imports)
            if isinstance(node,ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0],bad_imports)
        for token in ("INSERT INTO","UPDATE public.","DELETE FROM",
                      "os.kill","@router.post","create_payment"):
            self.assertNotIn(token,src)

if __name__=="__main__":
    unittest.main()
