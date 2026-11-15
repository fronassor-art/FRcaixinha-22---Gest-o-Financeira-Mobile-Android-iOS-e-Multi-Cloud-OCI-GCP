"""M40030: CI-only interrupted transaction and replay safety source contract."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql"
WF=ROOT/".github/workflows/frfinance-m40030-crash-recovery-ci.yml"
SOURCES={
 "guard":SQL/"m40030_disposable_guard.psql",
 "prepare":SQL/"m40030_disposable_prepare_pg18_ci.sql",
 "receipt_crash":SQL/"m40030_disposable_receipt_crash_pg18_ci.sql",
 "receipt_recover":SQL/"m40030_disposable_receipt_recover_pg18_ci.sql",
 "replay":SQL/"m40030_disposable_replay_after_commit_pg18_ci.sql",
 "stop_crash":SQL/"m40030_disposable_stop_crash_pg18_ci.sql",
 "stop_recover":SQL/"m40030_disposable_stop_recover_pg18_ci.sql",
 "audit":SQL/"m40030_disposable_final_audit_pg18_ci.sql",
}


class TestM40030CrashRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src={k:v.read_text(encoding="utf-8") for k,v in SOURCES.items()}
        cls.workflow=WF.read_text(encoding="utf-8")

    def test_gate_before_every_sql_and_disposable_identity(self):
        guard=self.src["guard"]
        for value in (
            r"\ir m40020_disposable_guard.psql",
            r"\if :{?CI_M40030_DISPOSABLE}",
            "frcaixinha_ci","inet_server_port()=5432",
            "session_user='postgres'",
            "frfinance.m40030_ci",
            "DISPOSABLE_ONLY",
            "M40030_BLOCKED_WRONG_CLUSTER",
        ):
            self.assertIn(value,guard)
        for kind,src in self.src.items():
            if kind!="guard":
                self.assertIn(r"\ir m40030_disposable_guard.psql",src)
            for bad in (
                "frcaixinha_aistudio_dev",
                "DROP DATABASE",
                "CREATE TABLE public.",
                "ALTER TABLE public.",
                "dblink(",
                "GRANT UPDATE ON m40010_ci",
                "GRANT INSERT ON m40020_ci",
            ):
                self.assertNotIn(bad,src,kind)

    def test_crash_scripts_have_marker_before_commit_and_bounded_pause(self):
        expected={
            "receipt_crash":"M40030_RECEIPT_PENDING_COMMIT_WITH_ROW_LOCK",
            "stop_crash":"M40030_STOP_PENDING_COMMIT_WITH_ROW_LOCK",
        }
        for kind,mark in expected.items():
            with self.subTest(script=kind):
                src=self.src[kind]
                self.assertIn("BEGIN;",src)
                self.assertIn("SELECT pg_sleep(8);",src)
                self.assertIn("COMMIT;",src)
                self.assertLess(src.index(mark),src.index("SELECT pg_sleep(8);"))
                self.assertLess(src.index("SELECT pg_sleep(8);"),src.index("\nCOMMIT;"))
                self.assertIn("M40030_UNEXPECTED_",src)

    def test_retry_after_crash_and_named_unique_replay_rejections(self):
        for mark in (
            "M40030_CRASHED_RECEIPT_WAS_NOT_ROLLED_BACK",
            "M40030_RECOVERED_RECEIPT_NOT_COMMITTED",
            "M40030_CRASHED_RECEIPT_ROLLBACK_AND_IDENTICAL_RETRY=PASS",
        ):
            self.assertIn(mark,self.src["receipt_recover"])
        for mark in (
            "m40010_unique_nonce",
            "m40010_unique_idem",
            "M40030_NONCE_REPLAY_UNEXPECTED_CONSTRAINT_",
            "M40030_IDEMPOTENCY_REPLAY_UNEXPECTED_CONSTRAINT_",
            "GET STACKED DIAGNOSTICS name=CONSTRAINT_NAME",
            "M40030_COMMITTED_NONCE_AND_IDEMPOTENCY_REPLAY=DENIED",
        ):
            self.assertIn(mark,self.src["replay"])

    def test_stopped_proposal_crash_does_not_authenticate_real_revocation(self):
        for mark in (
            "M40030_CRASHED_STOP_PARTIALLY_COMMITTED",
            "M40030_STOP_RECOVERY_NOT_ATOMIC",
            "M40030_CRASHED_STOP_ROLLBACK_AND_IDENTICAL_RETRY=PASS",
        ):
            self.assertIn(mark,self.src["stop_recover"])
        for mark in (
            "M40030_FAILURE_RECOVERY_COUNTS_INVALID",
            "M40030_RETRY_NOT_SAME_EVENT_ID",
            "M40030_REAL_APPROVAL_WAS_FABRICATED",
            "M40030_ACTOR_A_RLS_FAILED",
            "M40030_ACTOR_B_RLS_FAILED",
            "M40030_REAL_REVOCATION=NOT_ATTESTED",
            "M40030_REAL_APPROVAL=FALSE",
            "M40030_ORIGINAL_DB_WRITES=NONE",
            "M40030_PRODUCTION=BLOCKED",
        ):
            self.assertIn(mark,self.src["audit"])

    def test_workflow_kills_only_ephemeral_psql_and_never_termux(self):
        w=self.workflow
        for mark in (
            "image: postgres:18",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "GITHUB_ACTIONS",
            "CI_M40030_DISPOSABLE=1",
            "frfinance.m40030_ci=DISPOSABLE_ONLY",
            "stdbuf -oL -eL psql",
            'kill -KILL "$holder"',
            'test "$exit_code" -eq 137',
            'trap - EXIT',
            "M40030_RECEIPT_PENDING_COMMIT_WITH_ROW_LOCK",
            "M40030_STOP_PENDING_COMMIT_WITH_ROW_LOCK",
            "m40030_disposable_receipt_recover_pg18_ci.sql",
            "m40030_disposable_replay_after_commit_pg18_ci.sql",
            "m40030_disposable_stop_recover_pg18_ci.sql",
            "m40020_disposable_stopped_writer_pg18_ci.sql",
            "m40030_disposable_final_audit_pg18_ci.sql",
            "M40030_TERMUX_ACCESS=NONE",
            "M40030_ORIGINAL_DB_WRITES=NONE",
            "M40030_LOCAL_MIGRATIONS=NONE",
            "M40030_PRODUCTION=BLOCKED",
        ):
            with self.subTest(expected=mark):
                self.assertIn(mark,w)
        for forbidden in ("frcaixinha_aistudio_dev","pg_ctl","ssh ","systemctl",
                          "postgresql://","PIX_REAL=ON"):
            self.assertNotIn(forbidden,w)
        self.assertEqual(w.count('kill -KILL "$holder"'),4)

if __name__=="__main__":
    unittest.main()
