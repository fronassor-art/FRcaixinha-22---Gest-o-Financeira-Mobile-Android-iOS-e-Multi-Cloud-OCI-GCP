"""M40020 CI-only PostgreSQL concurrency source/permission contract."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql"
FILES={
    "guard":SQL/"m40020_disposable_guard.psql",
    "init":SQL/"m40020_disposable_lock_init_pg18_ci.sql",
    "first":SQL/"m40020_disposable_race_first_pg18_ci.sql",
    "second":SQL/"m40020_disposable_race_duplicate_pg18_ci.sql",
    "stop":SQL/"m40020_disposable_stop_proposal_pg18_ci.sql",
    "late":SQL/"m40020_disposable_stopped_writer_pg18_ci.sql",
    "audit":SQL/"m40020_disposable_final_audit_pg18_ci.sql",
}
WORKFLOW=ROOT/".github/workflows/frfinance-m40020-concurrent-stop-ci.yml"


class TestM40020ConcurrencySource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source={k:path.read_text(encoding="utf-8") for k,path in FILES.items()}
        cls.wf=WORKFLOW.read_text(encoding="utf-8")

    def test_all_scripts_guard_disposable_database_and_ci_flag(self):
        g=self.source["guard"]
        for marker in (
            r"\ir m40010_disposable_guard.psql",
            r"\if :{?CI_M40020_DISPOSABLE}",
            "frcaixinha_ci",
            "inet_server_port()=5432",
            "session_user='postgres'",
            "frfinance.m40020_ci",
            "DISPOSABLE_ONLY",
            "M40020_BLOCKED_WRONG_CLUSTER",
        ):
            self.assertIn(marker,g)
        for kind in ("init","first","second","stop","late","audit"):
            self.assertIn(r"\ir m40020_disposable_guard.psql",self.source[kind])
        for kind,body in self.source.items():
            self.assertNotIn("frcaixinha_aistudio_dev",body,kind)
            self.assertNotIn("DROP DATABASE",body,kind)
            self.assertNotIn("ALTER TABLE public.",body,kind)
            self.assertNotIn("dblink(",body,kind)

    def test_trigger_serializes_receipts_with_proposed_stop_row(self):
        s=self.source["init"]
        for term in (
            "CREATE SCHEMA m40020_ci",
            "CREATE TABLE m40020_ci.proposed_grant_state",
            "CREATE TABLE m40020_ci.proposed_stop_events",
            "CHECK(state='PROPOSED_ONLY_NOT_EFFECTIVE')",
            "CHECK(authentic_revocation=false)",
            "CHECK(approved=false)",
            "CHECK(payments_enabled=false)",
            "reviewer_identity_authenticated=false",
            "effective_revocation_verified=false",
            "SECURITY DEFINER SET search_path=pg_catalog,pg_temp",
            "FOR UPDATE",
            "m40020_lock_before_receipt",
            "M40020_PROPOSED_STOP_BLOCKS_FUTURE_CI_RECEIPT",
            "M40020_STOP_ONLY_ONCE_NO_REACTIVATION",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "m40020_grant_read",
            "m40020_stop_read",
            "BEFORE UPDATE OR DELETE",
            "GRANT SELECT",
            "GRANT USAGE",
        ):
            with self.subTest(term=term):
                self.assertIn(term,s)
        self.assertNotIn("GRANT UPDATE ON m40020_ci",s)
        self.assertNotIn("GRANT DELETE ON m40020_ci",s)
        self.assertNotIn("GRANT INSERT ON m40020_ci",s)

    def test_two_real_postgresql_processes_compete_under_lock(self):
        for script,role in (("first","m40010_a_a"),("second","m40010_a_a"),
                            ("late","m40010_a_b")):
            self.assertIn("SET LOCAL ROLE "+role,self.source[script])
        self.assertIn("M40020_FIRST_WRITER_LOCK_HELD",self.source["first"])
        self.assertIn("M40020_CONCURRENT_DUPLICATE_REJECTED=",self.source["second"])
        self.assertIn("M40020_STOP_PROPOSAL_LOCK_HELD",self.source["stop"])
        self.assertIn("M40020_CONCURRENT_RECEIPT_AFTER_STOP=DENIED",self.source["late"])
        self.assertIn("GET STACKED DIAGNOSTICS constraint_hit",self.source["second"])
        self.assertIn("EXCEPTION WHEN SQLSTATE 'P0001'",self.source["late"])
        self.assertIn("SELECT pg_sleep(3)",self.source["first"])
        self.assertIn("SELECT pg_sleep(3)",self.source["stop"])

    def test_audit_detects_false_grants_and_payment_state(self):
        s=self.source["audit"]
        for term in (
            "M40020_ATOMIC_ONE_RECEIPT_EXPECTED",
            "M40020_STOP_EVENT_NOT_ATOMICALLY_PERSISTED",
            "M40020_LATE_WRITER_BYPASSED_STOP",
            "M40020_ANY_REAL_FINANCIAL_OR_IDENTITY_CLAIM",
            "M40020_UNEXPECTED_APPLICATION_WRITE_GRANT",
            "M40020_REACTIVATION_ACCEPTED",
            "M40020_AUDIT_DELETE_ACCEPTED",
            "M40020_FIRST_ACTOR_RLS_LEAK",
            "M40020_SECOND_ACTOR_RLS_LEAK",
            "M40020_REAL_AUTHENTICATION=NOT_ATTESTED",
            "M40020_REAL_REVOCATION=NOT_ATTESTED",
            "M40020_REAL_PAYMENTS=OFF",
            "\nROLLBACK;",
        ):
            with self.subTest(term=term):
                self.assertIn(term,s)

    def test_workflow_no_local_database_and_overlapping_psql_processes(self):
        w=self.wf
        for term in (
            "image: postgres:18",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "frfinance.m40020_ci=DISPOSABLE_ONLY",
            "CI_M40020_DISPOSABLE=1",
            "m40010_disposable_init_pg18_ci.sql",
            "m40020_disposable_lock_init_pg18_ci.sql",
            "m40020_disposable_race_first_pg18_ci.sql",
            "m40020_disposable_race_duplicate_pg18_ci.sql",
            "m40020_disposable_stop_proposal_pg18_ci.sql",
            "m40020_disposable_stopped_writer_pg18_ci.sql",
            "m40020_disposable_final_audit_pg18_ci.sql",
            "stdbuf -oL -eL psql",
            'holder=$!',
            'kill -0 "$holder"',
            'wait "$holder"',
            'grep -q "M40020_FIRST_WRITER_LOCK_HELD"',
            'grep -q "M40020_STOP_PROPOSAL_LOCK_HELD"',
            "M40020_ORIGINAL_DB_ACCESS=NONE",
            "M40020_TERMUX_ACCESS=NONE",
            "M40020_LOCAL_MIGRATIONS=NONE",
            "M40020_PRODUCTION=BLOCKED",
        ):
            with self.subTest(term=term):
                self.assertIn(term,w)
        self.assertNotIn("ssh ",w)
        self.assertNotIn("frcaixinha_aistudio_dev",w)
        self.assertNotIn("pg_ctl",w)


if __name__=="__main__":
    unittest.main()
