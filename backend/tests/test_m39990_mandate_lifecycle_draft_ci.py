"""M39990 — synthetic mandate event stream; none of its entries is authentic."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from pathlib import Path
from uuid import UUID
import unittest

from backend.app.exclusive_cashbox_mandate_lifecycle_draft import (
    MandateLifecycleDraftDenied, MandateEventDraft,
    inspect_untrusted_mandate_lifecycle,
)
from backend.app.exclusive_cashbox_review_policy_draft import (
    assess_unapproved_review_policy,
)
from backend.app.exclusive_cashbox_provenance import PLATFORM_MASTER, TENANT_ADMIN_OWN
from backend.tests.test_m39980_review_policy_draft_ci import (
    setup, AUTHOR, OBSERVED, T, REVIEWER_A, REVIEWER_B, TENANT_A, TENANT_B,
)

EVENT_A = UUID("10101010-1010-4010-8010-101010101010")
EVENT_B = UUID("20202020-2020-4020-8020-202020202020")
EVENT_C = UUID("30303030-3030-4030-8030-303030303030")
EVENT_D = UUID("40404040-4040-4040-8040-404040404040")


def fixture(scope=PLATFORM_MASTER):
    j,e,c,s,p=setup(scope)
    report=assess_unapproved_review_policy(j,e,c,s,p,observed_at=OBSERVED)
    first=MandateEventDraft(
        EVENT_A,report.policy_draft_fingerprint,scope,j.tenant_id,
        REVIEWER_A,"APPOINTMENT_PROPOSED",T-timedelta(minutes=1),
        AUTHOR,"1"*64)
    second=MandateEventDraft(
        EVENT_B,report.policy_draft_fingerprint,scope,j.tenant_id,
        REVIEWER_B,"APPOINTMENT_PROPOSED",T-timedelta(seconds=30),
        AUTHOR,"2"*64)
    withdrawal=MandateEventDraft(
        EVENT_C,report.policy_draft_fingerprint,scope,j.tenant_id,
        REVIEWER_A,"WITHDRAWAL_PROPOSED",T+timedelta(seconds=65),
        REVIEWER_A,"3"*64)
    revocation=MandateEventDraft(
        EVENT_D,report.policy_draft_fingerprint,scope,j.tenant_id,
        REVIEWER_B,"REVOCATION_PROPOSED",T+timedelta(seconds=70),
        AUTHOR,"4"*64)
    return j,e,c,s,p,(first,second,withdrawal,revocation)


class M39990MandateEventChain(unittest.TestCase):
    def assert_denied(self,j,e,c,s,p,events,at=OBSERVED):
        with self.assertRaises(MandateLifecycleDraftDenied):
            inspect_untrusted_mandate_lifecycle(
                j,e,c,s,p,events,observed_at=at)

    def test_two_apppointment_proposals_for_master_and_admin_still_unverified(self):
        for scope in (PLATFORM_MASTER,TENANT_ADMIN_OWN):
            with self.subTest(scope=scope):
                j,e,c,s,p,events=fixture(scope)
                r=inspect_untrusted_mandate_lifecycle(
                    j,e,c,s,p,events[:2],observed_at=OBSERVED)
                self.assertEqual(r.state,"MANDATE_LIFECYCLE_DRAFT_ONLY")
                self.assertEqual(r.proposal_event_count,2)
                self.assertEqual(r.nonterminal_proposal_count,2)
                self.assertEqual(r.terminal_proposal_count,0)
                self.assertEqual(r.scope,scope)
                self.assertEqual(r.tenant_id,j.tenant_id)
                self.assertEqual(len(r.policy_draft_fingerprint),64)
                self.assertEqual(len(r.chain_fingerprint),64)
                self.assertGreaterEqual(len(r.outstanding_gates),8)
                for name in (
                    "source_events_authenticated","durable_audit_events_recorded",
                    "reviewer_appointment_verified","consent_signatures_verified",
                    "effective_revocation_recorded","reviewer_grants_authorized",
                    "independent_review_approved","journal_posted",
                    "payment_enabled","payout_enabled",
                ):
                    self.assertIs(getattr(r,name),False)
                with self.assertRaises(FrozenInstanceError):
                    r.payout_enabled=True

    def test_withdrawal_and_revocation_only_change_unverified_proposal_counts(self):
        j,e,c,s,p,items=fixture(TENANT_ADMIN_OWN)
        r3=inspect_untrusted_mandate_lifecycle(
            j,e,c,s,p,items[:3],observed_at=OBSERVED)
        self.assertEqual((r3.proposal_event_count,r3.nonterminal_proposal_count,
                          r3.terminal_proposal_count),(3,1,1))
        self.assertFalse(r3.effective_revocation_recorded)
        self.assertFalse(r3.reviewer_grants_authorized)
        r4=inspect_untrusted_mandate_lifecycle(
            j,e,c,s,p,items,observed_at=OBSERVED)
        self.assertEqual((r4.proposal_event_count,r4.nonterminal_proposal_count,
                          r4.terminal_proposal_count),(4,0,2))
        self.assertFalse(r4.independent_review_approved)
        self.assertFalse(r4.journal_posted)
        self.assertFalse(r4.payout_enabled)
        self.assertNotEqual(r3.chain_fingerprint,r4.chain_fingerprint)

    def test_deterministic_chain_changes_with_event_and_utc_equivalence(self):
        j,e,c,s,p,items=fixture()
        left=inspect_untrusted_mandate_lifecycle(
            j,e,c,s,p,items,observed_at=OBSERVED)
        again=inspect_untrusted_mandate_lifecycle(
            j,e,c,s,p,items,observed_at=OBSERVED)
        self.assertEqual(left.chain_fingerprint,again.chain_fingerprint)
        altered=items[:2]+(replace(items[2],claimed_document_digest="5"*64),items[3])
        changed=inspect_untrusted_mandate_lifecycle(
            j,e,c,s,p,altered,observed_at=OBSERVED)
        self.assertNotEqual(left.chain_fingerprint,changed.chain_fingerprint)
        tz=timezone(timedelta(hours=-3))
        converted=(replace(items[0],claimed_at=items[0].claimed_at.astimezone(tz)),)+items[1:]
        same=inspect_untrusted_mandate_lifecycle(
            j,e,c,s,p,converted,observed_at=OBSERVED)
        self.assertEqual(left.chain_fingerprint,same.chain_fingerprint)

    def test_missing_first_event_and_replay_rejected(self):
        j,e,c,s,p,items=fixture()
        for candidate in (
            None,[],(),(items[0],),(items[0],items[1],items[2],items[3],items[3]),
            (items[0],items[0]),(items[0],items[2]),
            (items[2],items[1]),(items[1],items[2]),
            (items[0],items[1],items[0]),
            (items[0],items[1],items[2],items[2]),
        ):
            with self.subTest(event_count=(len(candidate) if candidate is not None else -1)):
                self.assert_denied(j,e,c,s,p,candidate)
        self.assert_denied(j,e,c,s,p,(items[0],"forged"))

    def test_rejected_false_approved_state_and_unauthorized_event_actor(self):
        j,e,c,s,p,items=fixture()
        for action in ("APPROVED","REVOKED","ACTIVE","PAID","SIGN","",None,True):
            with self.subTest(action=action):
                self.assert_denied(j,e,c,s,p,(replace(items[0],action=action),items[1]))
        self.assert_denied(j,e,c,s,p,(replace(items[0],claimed_actor_id=REVIEWER_A),items[1]))
        self.assert_denied(j,e,c,s,p,(items[0],replace(items[1],claimed_actor_id=REVIEWER_B)))
        self.assert_denied(j,e,c,s,p,items[:2]+(
            replace(items[2],claimed_actor_id=AUTHOR),))
        self.assert_denied(j,e,c,s,p,items[:3]+(
            replace(items[3],claimed_actor_id=REVIEWER_B),))
        self.assert_denied(j,e,c,s,p,items[:2]+(
            replace(items[2],action="APPOINTMENT_PROPOSED"),))

    def test_scope_tenant_and_policy_fingerprint_replay_rejected(self):
        j,e,c,s,p,items=fixture(TENANT_ADMIN_OWN)
        for mutation in (
            dict(tenant_id=TENANT_B),
            dict(scope=PLATFORM_MASTER),
            dict(policy_draft_fingerprint="f"*64),
            dict(reviewer_id=UUID("55555555-5555-4555-8555-555555555555")),
            dict(reviewer_id=UUID(int=0)),
            dict(event_id=UUID(int=0)),
        ):
            with self.subTest(mutation=mutation):
                self.assert_denied(j,e,c,s,p,
                    (items[0],replace(items[1],**mutation)))
        self.assert_denied(j,e,c,s,replace(p,policy_document_digest="e"*64),items[:2])

    def test_event_ids_digests_and_temporal_sequence(self):
        j,e,c,s,p,items=fixture()
        for mutation in (
            dict(event_id=items[0].event_id),
            dict(claimed_document_digest=items[0].claimed_document_digest),
            dict(claimed_document_digest="f"*63),
            dict(claimed_document_digest="F"*64),
            dict(claimed_document_digest=None),
            dict(claimed_document_digest=1),
            dict(claimed_at=items[0].claimed_at),
            dict(claimed_at=items[0].claimed_at-timedelta(seconds=1)),
            dict(claimed_at=p.valid_until),
            dict(claimed_at=p.valid_until+timedelta(seconds=1)),
            dict(claimed_at=OBSERVED+timedelta(seconds=1)),
            dict(claimed_at=items[1].claimed_at.replace(tzinfo=None)),
        ):
            with self.subTest(mutation=mutation):
                self.assert_denied(j,e,c,s,p,
                    (items[0],replace(items[1],**mutation)))
        self.assert_denied(j,e,c,s,p,items[:2],at=OBSERVED.replace(tzinfo=None))

    def test_no_reactivation_after_proposed_terminal_event(self):
        j,e,c,s,p,items=fixture()
        reappoint=replace(items[3],action="APPOINTMENT_PROPOSED",
                          reviewer_id=REVIEWER_A,claimed_actor_id=AUTHOR)
        self.assert_denied(j,e,c,s,p,items[:3]+(reappoint,))
        repeated_termination=replace(items[3],reviewer_id=REVIEWER_A)
        self.assert_denied(j,e,c,s,p,items[:3]+(repeated_termination,))
        no_first=items[:2]+(replace(items[2],reviewer_id=REVIEWER_B,
                                    claimed_actor_id=REVIEWER_B),items[3])
        self.assert_denied(j,e,c,s,p,no_first)

    def test_no_io_no_http_no_database_and_all_authorities_false(self):
        src=(Path(__file__).resolve().parents[1]/
             "app/exclusive_cashbox_mandate_lifecycle_draft.py").read_text()
        parsed=ast.parse(src)
        prohibited={"asyncpg","psycopg","httpx","requests","urllib",
                    "socket","subprocess"}
        for node in ast.walk(parsed):
            if isinstance(node,ast.Import):
                self.assertFalse(any(n.name.split(".")[0] in prohibited
                                     for n in node.names))
            if isinstance(node,ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0],prohibited)
        for snippet in ("INSERT INTO","UPDATE public.","DELETE FROM","os.kill(",
                        "@router.post","create_payment","enable_payout"):
            self.assertNotIn(snippet,src)
        self.assertIn("effective_revocation_recorded: bool = False",src)
        self.assertIn("reviewer_grants_authorized: bool = False",src)
        self.assertIn("payout_enabled: bool = False",src)


if __name__=="__main__":
    unittest.main()
