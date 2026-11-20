"""Offline, nonfinancial M40929 regression for a Linux SO_PEERCRED limitation."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().with_name("m40929_same_uid_peercred_no_go.py")


class SameUidPeerCredNoGo(unittest.TestCase):
    def test_fail_closed_when_not_in_offline_ci(self):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--proof"],
            env={"PATH": os.environ.get("PATH", "")},
            capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("M40929_CI_OFFLINE_ONLY=BLOCKED", result.stdout)

    def test_different_process_same_uid_connects_unix_socket(self):
        if os.environ.get("CI_M40929_OFFLINE") != "1":
            self.skipTest("Only GitHub isolated offline test")
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--proof"],
            env={
                "PATH": os.environ.get("PATH", ""),
                "GITHUB_ACTIONS": "true",
                "CI_M40929_OFFLINE": "1",
                "PIX_REAL": "OFF",
                "PAGAMENTOS_REAIS": "OFF",
                "ATIVACAO_REAL": "OFF",
            },
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("M40929_DISTINCT_PROCESS_SAME_GATEWAY_UID=SO_PEERCRED_ACCEPTS_UID", result.stdout)
        self.assertIn("M40929_ED25519_OR_SQL_BYPASS=NOT_TESTED", result.stdout)
        self.assertIn("M40929_PRODUCTION=BLOCKED", result.stdout)

    def test_no_financial_runtime_imports_or_externals(self):
        body = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("psycopg", "requests", "urllib", "asyncpg", "git push",
                          "DATABASE_URL", "127.0.0.1:5433", "migrations/114",
                          "PIX_REAL=ON", "PAGAMENTOS_REAIS=ON", "ATIVACAO_REAL=ON"):
            self.assertNotIn(forbidden, body)
        self.assertIn("M40929_ED25519_OR_SQL_BYPASS=NOT_TESTED", body)


if __name__ == "__main__":
    unittest.main()
