"""M40932: Master SQL transaction is READ ONLY before any RLS GUC.

Pure fake pool tests: no original PostgreSQL, no migrations, no services,
no network, no real users/payments and no production trust attestation.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
import os
import unittest
from unittest.mock import patch

from app import database

ROOT = Path(__file__).resolve().parents[2]
FLAGS_OFF = {
    "ENVIRONMENT": "homologation",
    "PIX_REAL": "OFF",
    "PAGAMENTOS_REAIS": "OFF",
    "ATIVACAO_REAL": "OFF",
}


class FakeTransaction:
    def __init__(self, events):
        self.events = events

    async def start(self):
        self.events.append("BEGIN")

    async def commit(self):
        self.events.append("COMMIT")

    async def rollback(self):
        self.events.append("ROLLBACK")


class FakeConnection:
    def __init__(self, *, fail_readonly=False):
        self.events = []
        self.fail_readonly = fail_readonly

    def transaction(self):
        return FakeTransaction(self.events)

    async def execute(self, sql, *params):
        self.events.append((sql, params))
        if sql == "SET TRANSACTION READ ONLY" and self.fail_readonly:
            raise RuntimeError("SYNTHETIC_READONLY_DENIED")


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


class MasterReadOnlyTransaction(unittest.IsolatedAsyncioTestCase):
    async def _drive(self, role, *, fail_readonly=False):
        conn = FakeConnection(fail_readonly=fail_readonly)
        async def fake_pool():
            return FakePool(conn)
        sess = SimpleNamespace(
            role=role, user_id="test-user-synthetic", tenant_id=None
        )
        with (patch.dict(os.environ, FLAGS_OFF, clear=True),
              patch.object(database, "settings",
                           SimpleNamespace(is_database_configured=True)),
              patch.object(database, "get_db_pool", fake_pool),
              patch.object(database, "require_verified_rls_session",
                           lambda session: None)):
            gen = database.get_rls_db_connection(sess)
            if fail_readonly:
                with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_READONLY_DENIED"):
                    await anext(gen)
            else:
                result = await anext(gen)
                self.assertIs(result, conn)
                with self.assertRaises(StopAsyncIteration):
                    await anext(gen)
        return conn.events

    async def test_master_is_readonly_before_any_guc_or_query(self):
        events = await self._drive("MASTER")
        self.assertEqual(events[0], "BEGIN")
        self.assertEqual(events[1], ("SET TRANSACTION READ ONLY", ()))
        self.assertEqual(
            [event[0] for event in events if isinstance(event, tuple)][1:4],
            [
                "SELECT set_config('app.current_user_id', $1, true);",
                "SELECT set_config('app.current_role', $1, true);",
                "SELECT set_config('app.current_tenant_id', $1, true);",
            ],
        )
        self.assertIn("COMMIT", events)
        self.assertEqual(events[-1], ("RESET ALL; DISCARD TEMP;", ()))

    async def test_master_readonly_failure_rolls_back_before_context(self):
        events = await self._drive("MASTER", fail_readonly=True)
        self.assertEqual(events, [
            "BEGIN", ("SET TRANSACTION READ ONLY", ()),
            "ROLLBACK", ("RESET ALL; DISCARD TEMP;", ()),
        ])

    async def test_tenant_role_keeps_original_transaction_flow(self):
        events = await self._drive("TENANT_ADMIN")
        self.assertEqual(events[0], "BEGIN")
        self.assertNotIn(("SET TRANSACTION READ ONLY", ()), events)
        self.assertEqual(events[1][0],
                         "SELECT set_config('app.current_user_id', $1, true);")
        self.assertEqual(events[-2], "COMMIT")

    def test_master_write_guards_and_m40840_still_exist(self):
        main = (ROOT / "backend/app/routers/master.py").read_text()
        promo = (ROOT / "backend/app/routers/saas_promotions.py").read_text()
        sql = (ROOT / "backend/app/database.py").read_text()
        gate = (ROOT / "backend/app/m40840_financial_sql_release_no_go.py").read_text()
        self.assertIn('dependencies=[Depends(require_unreleased_master_write)]', main)
        self.assertEqual(
            promo.count('dependencies=[Depends(require_unreleased_master_write)]'), 2
        )
        self.assertIn('if session.role == "MASTER":\n                await conn.execute("SET TRANSACTION READ ONLY")', sql)
        self.assertIn('require_nonproduction_financial_sql(os.environ)', sql)
        self.assertIn('M40840_FINANCIAL_SQL_NO_GO', gate)


if __name__ == "__main__":
    unittest.main()
