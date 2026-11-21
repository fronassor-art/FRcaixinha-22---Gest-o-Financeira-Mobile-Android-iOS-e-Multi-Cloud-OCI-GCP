"""M38998: M048 attestation must work as frc_ai_auth, not the superuser.

No real Termux Postgres connection, schema migration, token, SMTP or Pix.
"""
from __future__ import annotations

import pytest
import asyncpg

from app import access_delivery_pg18 as delivery


BASE = {
    "db": "frcaixinha_aistudio_dev",
    "login_role": "frc_ai_auth",
    "active_role": "frc_ai_auth",
    "port": 5433,
    "ver": 180006,
    "invite": True,
    "reset": True,
    "auth_invite": True,
    "auth_reset": True,
    "app_invite": False,
    "app_reset": False,
}


class ReadOnlyFake:
    def __init__(self, values: dict, *, fails=False):
        self.values = values
        self.fails = fails
        self.statements: list[str] = []
        self.closed = False

    async def fetchrow(self, statement: str):
        self.statements.append(statement)
        if self.fails:
            raise asyncpg.PostgresError("SYNTHETIC_PROVIDER_INTERNAL_SECRET")
        return dict(self.values)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_auth_role_can_attest_m048_without_restricted_pgdata(monkeypatch):
    fake = ReadOnlyFake(BASE)
    async def fake_connect(_):
        return fake
    monkeypatch.setattr(delivery, "_connect", fake_connect)
    await delivery.verify_existing_redemption_schema(object())
    assert fake.closed is True
    assert len(fake.statements) == 1
    sql = fake.statements[0]
    assert "current_setting('data_directory')" not in sql
    assert "pg_read_all_settings" not in sql
    assert "ALTER ROLE" not in sql
    assert "CREATE " not in sql
    assert "session_user AS login_role" in sql
    assert "current_user AS active_role" in sql
    assert "current_setting('server_version_num')" in sql
    assert "frfinance_verify_invite_email(character)" in sql
    assert "frfinance_redeem_reset_token(" in sql
    assert "has_function_privilege('frc_ai_auth'" in sql
    assert "has_function_privilege('frc_ai_app'" in sql


@pytest.mark.parametrize("changed", [
    {"db": "frcaixinha_2_2_dev"},
    {"db": "postgres"},
    {"login_role": "frc_ai_owner"},
    {"login_role": "frc_ai_app"},
    {"active_role": "frc_ai_owner"},
    {"port": 5432},
    {"port": None},
    {"ver": 170009},
    {"ver": 190000},
    {"invite": False},
    {"reset": False},
    {"auth_invite": False},
    {"auth_reset": False},
    {"app_invite": True},
    {"app_reset": True},
    {"app_reset": None},
])
@pytest.mark.asyncio
async def test_any_schema_role_version_or_privilege_mismatch_still_blocks(
    monkeypatch, changed
):
    fake = ReadOnlyFake({**BASE, **changed})
    async def fake_connect(_):
        return fake
    monkeypatch.setattr(delivery, "_connect", fake_connect)
    with pytest.raises(delivery.AccessQueueBlocked, match="^M048_REDEMPTION_NOT_ATTESTED$"):
        await delivery.verify_existing_redemption_schema(object())
    assert fake.closed is True


@pytest.mark.asyncio
async def test_db_read_error_is_sanitized_no_secret_in_exception(monkeypatch):
    fake = ReadOnlyFake(BASE, fails=True)
    async def fake_connect(_):
        return fake
    monkeypatch.setattr(delivery, "_connect", fake_connect)
    with pytest.raises(delivery.AccessQueueBlocked) as exc:
        await delivery.verify_existing_redemption_schema(object())
    assert str(exc.value) == "M048_REDEMPTION_NOT_ATTESTED"
    assert exc.value.__cause__ is None
    assert fake.closed is True


def test_same_m047_m048_sql_and_migrations_are_untouched_by_readiness_fix():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    code = (root / "backend/app/access_delivery_pg18.py").read_text()
    assert "async def verify_existing_schema" in code
    assert "async def verify_existing_redemption_schema" in code
    assert "_ORIGINAL_DB = \"frcaixinha_aistudio_dev\"" in code
    assert "_ORIGINAL_PORT = 5433" in code
    assert "M048_REDEMPTION_NOT_ATTESTED" in code
