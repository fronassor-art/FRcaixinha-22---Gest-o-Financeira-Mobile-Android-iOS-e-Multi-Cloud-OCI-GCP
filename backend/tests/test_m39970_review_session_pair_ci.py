"""M39970 — two untrusted review claims correlated to session shapes only."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
import unittest

from backend.app.dependencies import AuthenticatedSession
from backend.app.exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE,
)
from backend.app.exclusive_cashbox_review_session_pair import (
    ReviewSessionPairDenied, correlate_unverified_review_sessions,
)
from backend.tests.test_m39950_documentary_review_chain_ci import (
    sample, T, TENANT_A, TENANT_B, PREPARER, REVIEWER_A, REVIEWER_B,
)

SID_A=UUID("77777777-7777-4777-8777-777777777777")
SID_B=UUID("88888888-8888-4888-8888-888888888888")
OBSERVED=T+timedelta(minutes=1,seconds=20)


def fake_session(actor,session_id,scope,*,tenant_override=None,source=None,
                 at=None,expires_at=None,role_override=None,master_override=None):
    role="MASTER" if scope==PLATFORM_MASTER else "TENANT_ADMIN"
    if role_override is not None:
        role=role_override
    master=scope==PLATFORM_MASTER
    if master_override is not None:
        master=master_override
    tenant=TENANT_A if scope==TENANT_ADMIN_OWN else None
    if tenant_override is not None:
        tenant=tenant_override
    now=T-timedelta(seconds=20) if actor==REVIEWER_A else T+timedelta(seconds=20)
    if at is not None:
        now=at
    end=T+timedelta(minutes=12) if expires_at is None else expires_at
    return AuthenticatedSession(
        str(actor),role,str(tenant) if tenant is not None else None,
        "fake@example.invalid","synthetic",master,
        verified_session_id=str(session_id) if session_id is not None else None,
        verified_session_at=now,verified_session_expires_at=end,
        verification_source=source or "POSTGRES_TOKEN_HASH_REFRESH",
    )


def fixture(scope=PLATFORM_MASTER):
    journal,evidence,claims=sample(scope)
    sessions=(
        fake_session(REVIEWER_A,SID_A,scope),
        fake_session(REVIEWER_B,SID_B,scope),
    )
    return journal,evidence,claims,sessions


class M39970ReviewSessionPair(unittest.TestCase):
    def assert_denied(self,journal,evidence,claims,sessions,observed_at=OBSERVED):
        with self.assertRaises(ReviewSessionPairDenied):
            correlate_unverified_review_sessions(
                journal,evidence,claims,sessions,observed_at=observed_at)

    def test_master_and_admin_two_session_shapes_never_authorize(self):
        for scope in (PLATFORM_MASTER,TENANT_ADMIN_OWN):
            with self.subTest(scope=scope):
                j,e,c,s=fixture(scope)
                r=correlate_unverified_review_sessions(
                    j,e,c,s,observed_at=OBSERVED)
                self.assertEqual(r.state,"REVIEW_SESSION_PAIR_STRUCTURAL_ONLY")
                self.assertTrue(r.session_claim_alignment)
                self.assertEqual(r.scope,scope)
                self.assertEqual(r.tenant_id,j.tenant_id)
                self.assertEqual(r.journal_fingerprint,j.fingerprint)
                self.assertEqual(len(r.documentary_chain_fingerprint),64)
                self.assertGreaterEqual(len(r.outstanding_gates),6)
                for flag in (
                    "claims_cryptographically_signed",
                    "verified_independent_reviewers",
                    "reviewer_roles_authorized","tenant_owner_attested",
                    "documentary_review_authorized",
                    "source_document_authenticated","provider_reconciled",
                    "journal_posted","payout_enabled",
                ):
                    self.assertFalse(getattr(r,flag))
                with self.assertRaises(FrozenInstanceError):
                    r.payout_enabled=True

    def test_repeated_actor_and_session_rejected(self):
        j,e,c,s=fixture()
        self.assert_denied(j,e,c,(s[0],replace_user(s[1],REVIEWER_A)))
        self.assert_denied(j,e,c,(s[0],fake_session(REVIEWER_B,SID_A,PLATFORM_MASTER)))
        self.assert_denied(j,e,c,(s[1],s[0]))
        self.assert_denied(j,e,c,(s[0],fake_session(PREPARER,SID_B,PLATFORM_MASTER)))

    def test_other_tenant_wrong_role_and_master_mix_rejected(self):
        j,e,c,s=fixture(TENANT_ADMIN_OWN)
        self.assert_denied(j,e,c,(s[0],fake_session(
            REVIEWER_B,SID_B,TENANT_ADMIN_OWN,tenant_override=TENANT_B)))
        self.assert_denied(j,e,c,(s[0],fake_session(
            REVIEWER_B,SID_B,TENANT_ADMIN_OWN,role_override="TENANT_MEMBER")))
        self.assert_denied(j,e,c,(s[0],fake_session(
            REVIEWER_B,SID_B,TENANT_ADMIN_OWN,master_override=True)))
        jm,em,cm,sm=fixture(PLATFORM_MASTER)
        self.assert_denied(jm,em,cm,(sm[0],fake_session(
            REVIEWER_B,SID_B,PLATFORM_MASTER,role_override="TENANT_ADMIN")))

    def test_legacy_expired_future_unbound_session_fail_closed(self):
        j,e,c,s=fixture()
        wrong=[
            fake_session(REVIEWER_B,SID_B,PLATFORM_MASTER,source="LEGACY_NO_SESSION_BINDING"),
            fake_session(REVIEWER_B,None,PLATFORM_MASTER),
            fake_session(REVIEWER_B,UUID(int=0),PLATFORM_MASTER),
            fake_session(REVIEWER_B,SID_B,PLATFORM_MASTER,
                         at=T-timedelta(minutes=10)),
            fake_session(REVIEWER_B,SID_B,PLATFORM_MASTER,
                         at=T+timedelta(minutes=4)),
            fake_session(REVIEWER_B,SID_B,PLATFORM_MASTER,
                         expires_at=T+timedelta(minutes=1)),
            fake_session(REVIEWER_B,SID_B,PLATFORM_MASTER,
                         expires_at=T+timedelta(minutes=50)),
        ]
        for session in wrong:
            with self.subTest(verified_id=session.verified_session_id,
                              verified_at=session.verified_session_at):
                self.assert_denied(j,e,c,(s[0],session))

    def test_claim_time_alone_never_signs_and_outside_session_fails(self):
        j,e,c,s=fixture()
        bad_claims=(c[0],replace(c[1],claimed_at=T+timedelta(seconds=5)))
        self.assert_denied(j,e,bad_claims,s)
        # Earlier than session verification, but still monotonic with a second claim:
        claimed_past=(
            replace(c[0],claimed_at=T-timedelta(minutes=1)),
            c[1],
        )
        self.assert_denied(j,e,claimed_past,s)
        self.assert_denied(j,e,c,s,observed_at=T+timedelta(seconds=30))

    def test_document_and_claim_mismatch_denied(self):
        j,e,c,s=fixture()
        self.assert_denied(j,replace(e,document_digest="b"*64),c,s)
        self.assert_denied(j,e,(replace(c[0],reviewer_id=PREPARER),c[1]),s)
        self.assert_denied(j,e,(replace(c[0],decision="APPROVED"),c[1]),s)
        self.assert_denied(replace(j,journal_posted=True),e,c,s)

    def test_no_collective_reviewer_policy_yet(self):
        j,e,c,_=fixture(TENANT_COLLECTIVE)
        a=fake_session(REVIEWER_A,SID_A,TENANT_ADMIN_OWN)
        b=fake_session(REVIEWER_B,SID_B,TENANT_ADMIN_OWN)
        self.assert_denied(j,e,c,(a,b))

    def test_reject_non_pair_and_unverified_clock(self):
        j,e,c,s=fixture()
        for value in ((s[0],),[s[0],s[1]],(),None,(s[0],s[1],s[1])):
            self.assert_denied(j,e,c,value)
        self.assert_denied(j,e,c,s,observed_at=OBSERVED.replace(tzinfo=None))
        self.assert_denied(j,e,c,s,observed_at="2026-11-15T12:01:20Z")

    def test_pure_no_io_and_no_public_endpoint(self):
        src=(Path(__file__).resolve().parents[1]/
             "app/exclusive_cashbox_review_session_pair.py").read_text()
        for forbidden in (
            "asyncpg.connect(","psycopg.connect(","httpx.","requests.get(",
            "requests.post(","INSERT INTO","UPDATE public.","DELETE FROM",
            "create_payment","approve_payout","subprocess.","os.kill",
            "@router.post",
        ):
            self.assertNotIn(forbidden,src)
        parsed=ast.parse(src)
        prohibited_roots={"asyncpg","psycopg","httpx","requests","urllib",
                          "socket","subprocess"}
        for node in ast.walk(parsed):
            if isinstance(node,ast.Import):
                self.assertFalse(any(
                    item.name.split(".")[0] in prohibited_roots
                    for item in node.names))
            if isinstance(node,ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0],prohibited_roots)
        self.assertIn("verified_independent_reviewers: bool = False",src)
        self.assertIn("payout_enabled: bool = False",src)
        self.assertIn("SERVER_MUST_OBTAIN_EACH_SESSION",src)


def replace_user(s: AuthenticatedSession, actor: UUID):
    return AuthenticatedSession(
        str(actor),s.role,s.tenant_id,s.email,s.name,s.is_master,
        verified_session_id=s.verified_session_id,
        verified_session_at=s.verified_session_at,
        verified_session_expires_at=s.verified_session_expires_at,
        verification_source=s.verification_source,
    )


if __name__=="__main__":
    unittest.main()
