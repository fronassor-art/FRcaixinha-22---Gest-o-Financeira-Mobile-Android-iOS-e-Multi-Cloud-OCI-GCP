"""M40010 source contract for CI-only synthetic audit persistence."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/tests/sql"
WORKFLOW=ROOT/".github/workflows/frfinance-m40010-ephemeral-audit-ci.yml"
FILES={
    "guard":SQL/"m40010_disposable_guard.psql",
    "init":SQL/"m40010_disposable_init_pg18_ci.sql",
    "first":SQL/"m40010_disposable_writer_first_pg18_ci.sql",
    "second":SQL/"m40010_disposable_writer_second_pg18_ci.sql",
    "audit":SQL/"m40010_disposable_audit_pg18_ci.sql",
}

class M40010GuardContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src={k:v.read_text(encoding="utf-8") for k,v in FILES.items()}
        cls.workflow=WORKFLOW.read_text(encoding="utf-8")

    def test_every_script_rejects_non_ci_postgres(self):
        guard=self.src["guard"]
        for marker in (
            r"\if :{?CI_M40010_DISPOSABLE}",
            "current_database()='frcaixinha_ci'",
            "inet_server_port()=5432",
            "session_user='postgres'",
            "frfinance.m40010_ci",
            "DISPOSABLE_ONLY",
            "M40010_BLOCKED_WRONG_CLUSTER",
        ):
            self.assertIn(marker,guard)
        for name in ("init","first","second","audit"):
            self.assertIn(r"\ir m40010_disposable_guard.psql",self.src[name])
        for name,src in self.src.items():
            self.assertNotIn("frcaixinha_aistudio_dev",src,name)
            self.assertNotIn("DROP DATABASE",src,name)
            self.assertNotIn("pg_ctl",src,name)
            self.assertNotIn("CREATE TABLE public.",src,name)

    def test_disposable_committed_only_within_github_service(self):
        s=self.src["init"]
        for item in (
            "CREATE SCHEMA m40010_ci",
            "CREATE ROLE m40010_m_a NOLOGIN NOBYPASSRLS",
            "CREATE TABLE m40010_ci.review_packets",
            "CREATE TABLE m40010_ci.synthetic_role_bindings",
            "CREATE TABLE m40010_ci.review_receipts",
            "CONSTRAINT m40010_packet_fk",
            "CONSTRAINT m40010_bound_actor_fk",
            "CONSTRAINT m40010_unique_slot",
            "CONSTRAINT m40010_unique_reviewer",
            "CONSTRAINT m40010_unique_session",
            "CONSTRAINT m40010_unique_nonce",
            "CONSTRAINT m40010_unique_idem",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "CREATE POLICY m40010_receipts_insert",
            "actor_db_role=current_user",
            "GRANT INSERT(receipt_id",
            "BEFORE UPDATE OR DELETE",
            "CHECK(approved=false)",
            "CHECK(payout_enabled=false)",
            "CHECK(available_balance_cents IS NULL)",
            "\nCOMMIT;",
        ):
            self.assertIn(item,s)

    def test_role_provenance_across_independent_processes(self):
        first=self.src["first"]
        second=self.src["second"]
        self.assertIn("SET LOCAL ROLE m40010_m_a",first)
        self.assertIn("SET LOCAL ROLE m40010_m_b",second)
        self.assertIn("SET LOCAL ROLE m40010_a_a",first)
        self.assertIn("SET LOCAL ROLE m40010_b_b",second)
        self.assertIn("current_user",first)
        self.assertIn("current_user",second)
        self.assertEqual(first.count("INSERT INTO m40010_ci.review_receipts"),3)
        self.assertEqual(second.count("INSERT INTO m40010_ci.review_receipts"),3)
        self.assertEqual(first.count("\nCOMMIT;"),3)
        self.assertEqual(second.count("\nCOMMIT;"),3)

    def test_audit_rejects_replay_and_leaks(self):
        s=self.src["audit"]
        for item in (
            "M40010 separate-session data not durable in CI",
            "M40010 tenant A reviewer RLS view leak",
            "M40010 idempotency key replay not rejected",
            "M40010 nonce replay not rejected",
            "M40010 cross tenant writer accepted",
            "M40010 actor DB role spoof accepted",
            "M40010 writer may update approval",
            "M40010_SYNTHETIC_ROLES_NOT_HUMAN_IDENTITY=TRUE",
            "M40010_REAL_APPROVAL=FALSE",
            "\nROLLBACK;",
        ):
            self.assertIn(item,s)

    def test_workflow_guards_separate_psql_sessions(self):
        s=self.workflow
        for item in (
            "image: postgres:18",
            "POSTGRES_PASSWORD: postgres",
            "PGDATABASE: frcaixinha_ci",
            "PGPORT: '5432'",
            "frfinance.m40010_ci=DISPOSABLE_ONLY",
            "CI_M40010_DISPOSABLE=1",
            "GITHUB_ACTIONS",
            "m40010_disposable_init_pg18_ci.sql",
            "m40010_disposable_writer_first_pg18_ci.sql",
            "m40010_disposable_writer_second_pg18_ci.sql",
            "m40010_disposable_audit_pg18_ci.sql",
            "M40010_TERMUX_ACCESS=NONE",
            "M40010_ORIGINAL_DB_ACCESS=NONE",
            "M40010_PRODUCTION=BLOCKED",
        ):
            self.assertIn(item,s)
        self.assertEqual(s.count("psql -X -v ON_ERROR_STOP=1 -v CI_M40010_DISPOSABLE=1"),4)
        self.assertNotIn("ssh ",s)
        self.assertNotIn("frcaixinha_aistudio_dev",s)
        self.assertNotIn("db migrate",s)

if __name__=="__main__":
    unittest.main()
