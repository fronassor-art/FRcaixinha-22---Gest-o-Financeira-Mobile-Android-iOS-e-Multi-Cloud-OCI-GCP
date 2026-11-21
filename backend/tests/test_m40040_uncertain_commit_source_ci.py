"""M40040: source guard against accidental real use and false ACK authority."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql"
WF=ROOT/".github/workflows/frfinance-m40040-uncertain-commit-ci.yml"
NAMES={
 "guard":"m40040_disposable_guard.psql",
 "init":"m40040_disposable_ack_init_pg18_ci.sql",
 "broken":"m40040_disposable_atomic_failure_pg18_ci.sql",
 "rollback":"m40040_disposable_verify_atomic_rollback_pg18_ci.sql",
 "commit":"m40040_disposable_commit_without_ack_pg18_ci.sql",
 "resolve":"m40040_disposable_retry_resolution_pg18_ci.sql",
 "visible":"m40040_disposable_visibility_pg18_ci.sql",
 "stop":"m40040_disposable_stop_after_ack_pg18_ci.sql",
 "final":"m40040_disposable_final_audit_pg18_ci.sql",
}

class TestM40040UncertainCommitSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src={k:(SQL/path).read_text(encoding="utf-8") for k,path in NAMES.items()}
        cls.wf=WF.read_text(encoding="utf-8")

    def test_multi_layer_only_disposable_database_guard(self):
        guard=self.src["guard"]
        for term in (
            r"\ir m40030_disposable_guard.psql",
            r"\if :{?CI_M40040_DISPOSABLE}",
            "current_database()='frcaixinha_ci'",
            "inet_server_port()=5432",
            "session_user='postgres'",
            "frfinance.m40040_ci",
            "DISPOSABLE_ONLY",
            "M40040_BLOCKED_WRONG_CLUSTER",
        ):
            self.assertIn(term,guard)
        for name,body in self.src.items():
            if name!="guard":
                self.assertIn(r"\ir m40040_disposable_guard.psql",body)
            for forbidden in (
                "frcaixinha_aistudio_dev","DROP DATABASE","CREATE TABLE public.",
                "ALTER TABLE public.","GRANT UPDATE ON m40010_ci","PIX_REAL=ON",
                "pg_ctl","systemctl","dblink(",
            ):
                self.assertNotIn(forbidden,body,name)

    def test_atomic_append_only_receipt_ack_and_no_approvals(self):
        s=self.src["init"]
        for term in (
            "CREATE SCHEMA m40040_ci",
            "CREATE TABLE m40040_ci.receipt_ack",
            "m40040_ack_unique_idem",
            "M40040_ACK_NOT_MATCHED_TO_COMMITTED_RECEIPT",
            "SECURITY DEFINER SET search_path=pg_catalog,pg_temp",
            "FOR KEY SHARE",
            "CREATE TRIGGER m40040_ack_binding BEFORE INSERT",
            "BEFORE UPDATE OR DELETE",
            "M40040_APPEND_ONLY_ACK",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "actor_db_role=current_user",
            "SECURITY INVOKER",
            "REVOKE ALL ON FUNCTION",
            "GRANT INSERT(receipt_id",
            "CHECK(session_authenticated=false)",
            "CHECK(signed_human_consent=false)",
            "CHECK(policy_approved=false)",
            "CHECK(payout_enabled=false)",
            "CHECK(available_balance_cents IS NULL)",
            "EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE",
            "CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE",
            "NOT_FOUND_OR_NOT_VISIBLE",
            "INVALID_REQUEST_NO_EFFECT",
        ):
            with self.subTest(term=term):
                self.assertIn(term,s)
        self.assertNotIn("GRANT UPDATE ON m40040_ci",s)
        self.assertNotIn("GRANT DELETE ON m40040_ci",s)

    def test_rollback_and_uncertain_response_are_independent(self):
        self.assertIn("M40040_UNEXPECTED_MISMATCH_ACCEPTED",self.src["broken"])
        self.assertIn("M40040_BROKEN_ACK_TRANSACTION_LEFT_ORPHAN_RECEIPT",self.src["rollback"])
        self.assertIn("M40040_ATOMIC_RECEIPT_AND_ACK_ROLLBACK=PASS",self.src["rollback"])
        s=self.src["commit"]
        self.assertEqual(s.count("INSERT INTO m40010_ci.review_receipts"),1)
        self.assertEqual(s.count("INSERT INTO m40040_ci.receipt_ack"),1)
        self.assertIn("\nCOMMIT;",s)
        self.assertIn("M40040_TRANSACTION_COMMITTED_RESPONSE_BODY_NOT_DELIVERED_IN_CI",s)
        self.assertNotIn("CREATE PAYMENT",s)

    def test_retry_conflicts_visibility_and_proposed_stop(self):
        for term in (
            "EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE",
            "CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE",
            "NOT_FOUND_OR_NOT_VISIBLE",
            "INVALID_REQUEST_NO_EFFECT",
            "M40040_RETRY_INSERTED_DUPLICATE",
            "M40040_COMMIT_WITHOUT_RESPONSE_RECONCILED=PASS",
        ):
            self.assertIn(term,self.src["resolve"])
        for term in (
            "M40040_SECOND_REVIEWER_SAW_FIRST_ACK",
            "M40040_TENANT_B_RLS_LEAK",
            "M40040_PLATFORM_MASTER_RLS_LEAK",
        ):
            self.assertIn(term,self.src["visible"])
        for term in (
            "REVOCATION_PROPOSED",
            "M40020_PROPOSED_STOP_BLOCKS_FUTURE_CI_RECEIPT",
            "M40040_PREEXISTING_RECEIPT_READABLE_AFTER_STOP=PASS",
            "M40040_NEW_RECEIPT_POST_STOP=BLOCKED",
        ):
            self.assertIn(term,self.src["stop"])

    def test_audit_and_workflow_have_no_real_authority(self):
        audit=self.src["final"]
        for term in (
            "M40040_ACK_RECOVERY_COUNTERS_INVALID",
            "M40040_FINANCIAL_OR_IDENTITY_AUTHORITY_FABRICATED",
            "M40040_ACK_WAS_MUTABLE",
            "M40040_ACK_WAS_DELETABLE",
            "M40040_REAL_REVOCATION=NOT_ATTESTED",
            "M40040_ORIGINAL_DB_ACCESS=NONE",
            "M40040_PRODUCTION=BLOCKED",
        ):
            self.assertIn(term,audit)
        w=self.wf
        for term in (
            "image: postgres:18",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "frfinance.m40040_ci=DISPOSABLE_ONLY",
            "CI_M40040_DISPOSABLE=1",
            "m40010_disposable_init_pg18_ci.sql",
            "m40020_disposable_lock_init_pg18_ci.sql",
            "m40040_disposable_ack_init_pg18_ci.sql",
            "m40040_disposable_atomic_failure_pg18_ci.sql",
            "m40040_disposable_verify_atomic_rollback_pg18_ci.sql",
            "m40040_disposable_commit_without_ack_pg18_ci.sql",
            "m40040_disposable_retry_resolution_pg18_ci.sql",
            "m40040_disposable_visibility_pg18_ci.sql",
            "m40040_disposable_stop_after_ack_pg18_ci.sql",
            "m40040_disposable_final_audit_pg18_ci.sql",
            "M40040_TERMUX_ACCESS=NONE",
            "M40040_ORIGINAL_DB_ACCESS=NONE",
            "M40040_LOCAL_MIGRATIONS=NONE",
            "M40040_PRODUCTION=BLOCKED",
        ):
            with self.subTest(term=term):
                self.assertIn(term,w)
        for forbidden in ("ssh ","pg_ctl","frcaixinha_aistudio_dev","migrate upgrade"):
            self.assertNotIn(forbidden,w)

if __name__=="__main__":
    unittest.main()
