"""FR Finance M40610: pure source-only RLS session provenance guard."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest

from backend.app.m40610_verified_rls_session import (
    UnverifiedRLSSession, require_verified_rls_session,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 18, 21, 0, tzinfo=timezone.utc)


def principal(role="TENANT_MEMBER", **changes):
    data = dict(
        user_id=str(uuid4()), role=role,
        tenant_id=None if role=="MASTER" else str(uuid4()),
        is_master=(role=="MASTER"),
        verified_session_id=str(uuid4()),
        verified_session_at=NOW - timedelta(seconds=1),
        verified_session_expires_at=NOW + timedelta(minutes=15),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    data.update(changes)
    return SimpleNamespace(**data)


@pytest.mark.parametrize("role", ["MASTER", "TENANT_ADMIN", "TENANT_MEMBER"])
def test_verified_master_and_tenant_principals_accepted(role):
    assert require_verified_rls_session(principal(role), now=NOW) is None


@pytest.mark.parametrize("role", ["TENANT_ADMIN", "TENANT_MEMBER"])
def test_master_account_with_explicit_tenant_membership_accepted(role):
    # is_master is a property of the account, not the active session role.
    # Access stays bound to the verified role and tenant of this session.
    assert require_verified_rls_session(
        principal(role, is_master=True), now=NOW
    ) is None


@pytest.mark.parametrize("bad", [
    {"verification_source":"LEGACY_NO_SESSION_BINDING"},
    {"verified_session_id":None},
    {"verified_session_id":"00000000-0000-0000-0000-000000000000"},
    {"verified_session_id":"malformed"},
    {"user_id":"not-a-uuid"},
    {"verified_session_at":None},
    {"verified_session_at":NOW + timedelta(minutes=10)},
    {"verified_session_at":datetime(2026, 11, 18, 21)},
    {"verified_session_expires_at":NOW},
    {"verified_session_expires_at":NOW - timedelta(seconds=1)},
    {"verified_session_expires_at":datetime(2026, 11, 18, 21, 30)},
])
def test_missing_forged_stale_or_naive_evidence_denied(bad):
    with pytest.raises(UnverifiedRLSSession):
        require_verified_rls_session(principal(**bad), now=NOW)


@pytest.mark.parametrize("role,fields", [
    ("MASTER", {"is_master":False}),
    ("MASTER", {"tenant_id":str(uuid4())}),
    ("TENANT_ADMIN", {"is_master":"true"}),
    ("TENANT_MEMBER", {"is_master":None}),
    ("TENANT_MEMBER", {"tenant_id":None}),
    ("TENANT_MEMBER", {"tenant_id":"not-uuid"}),
    ("TENANT_MEMBER", {"tenant_id":"00000000-0000-0000-0000-000000000000"}),
    ("UNKNOWN", {"tenant_id":None}),
])
def test_role_and_tenant_consistency_denied(role,fields):
    with pytest.raises(UnverifiedRLSSession):
        require_verified_rls_session(principal(role, **fields), now=NOW)


def test_fake_object_and_invalid_clock_denied():
    with pytest.raises(UnverifiedRLSSession):
        require_verified_rls_session(object(), now=NOW)
    with pytest.raises(UnverifiedRLSSession):
        require_verified_rls_session(principal(), now=datetime(2026, 11, 18, 21))


def test_guard_before_pool_or_database_configuration_and_no_sql_rewrite():
    source=(ROOT/"backend/app/database.py").read_text(encoding="utf-8")
    guard=source.index("require_verified_rls_session(session)")
    assert guard < source.index("if not settings.is_database_configured")
    assert guard < source.index("pool = await get_db_pool()")
    assert "except UnverifiedRLSSession:" in source
    assert "status.HTTP_401_UNAUTHORIZED" in source
    for marker in (
        "user_id = str(session.user_id)",
        "role = str(session.role)",
        "tenant_id = str(session.tenant_id)",
        "set_config('app.current_user_id', $1, true)",
        "set_config('app.current_role', $1, true)",
        "set_config('app.current_tenant_id', $1, true)",
        "await tx.rollback()",
        "RESET ALL; DISCARD TEMP;",
    ):
        assert marker in source


def test_guard_has_no_database_or_network_io():
    source=(ROOT/"backend/app/m40610_verified_rls_session.py").read_text(encoding="utf-8")
    assert "def require_verified_rls_session" in source
    for forbidden in ("asyncpg", "psycopg", "connect(", "os.environ",
                      "requests.", "urllib", "subprocess", "print("):
        assert forbidden not in source
