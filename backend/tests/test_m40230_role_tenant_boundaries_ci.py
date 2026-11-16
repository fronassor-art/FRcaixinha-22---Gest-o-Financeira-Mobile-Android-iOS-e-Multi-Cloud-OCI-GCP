"""M40230: role/tenant deny-first matrix with synthetic identities only.

Isolated FastAPI router assembly and dependency overrides. Never calls the
real auth DB or original PostgreSQL, never requests production endpoints.
Mutating attempts here are in-memory TestClient and must be rejected BEFORE
any fake DB call. No real credentials or member data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.dependencies import AuthenticatedSession, get_current_session
from app.database import get_rls_db_connection
from app.routers import (
    exclusive_cashboxes, exclusive_cashbox_review_gaps, special_credit, tenants,
)
from backend.scripts import frfinance_m40230_role_rls_source_readonly as static

A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ADMIN = UUID("11111111-1111-4111-8111-111111111111")
MASTER = UUID("22222222-2222-4222-8222-222222222222")
MEMBER = UUID("33333333-3333-4333-8333-333333333333")
NONOWNER = UUID("44444444-4444-4444-8444-444444444444")
SESSION = UUID("55555555-5555-4555-8555-555555555555")
CAMPAIGN = UUID("66666666-6666-4666-8666-666666666666")

TENANT_ROOT = f"/api/v1/tenants/{A}"
MASTER_ROOT = "/api/v1/master"
CREDIT = TENANT_ROOT + "/special-credit"


class NeverDB:
    def __init__(self):
        self.calls = []
    async def fetchval(self, *args, **kwargs):
        self.calls.append("fetchval")
        pytest.fail("Unauthorized role tried SQL before denying access")
    async def fetch(self, *args, **kwargs):
        self.calls.append("fetch")
        pytest.fail("Unauthorized role tried SQL before denying access")
    async def fetchrow(self, *args, **kwargs):
        self.calls.append("fetchrow")
        pytest.fail("Unauthorized role tried SQL before denying access")
    async def execute(self, *args, **kwargs):
        self.calls.append("execute")
        pytest.fail("Unauthorized role tried SQL before denying access")


class NonOwnerDB(NeverDB):
    async def fetchval(self, query, *args):
        self.calls.append("fetchval")
        assert query == (
            "SELECT admin_user_id FROM public.tenants "
            "WHERE id=$1 AND status='ATIVO'"
        )
        assert args == (A,)
        return NONOWNER


def synthetic_session(role, tenant, actor=None):
    now = datetime.now(timezone.utc)
    if actor is None:
        actor = MASTER if role == "MASTER" else (
            MEMBER if role == "TENANT_MEMBER" else ADMIN)
    return AuthenticatedSession(
        str(actor), role, str(tenant) if tenant is not None else None,
        "synthetic@example.invalid", "Synthetic CI", role == "MASTER",
        verified_session_id=str(SESSION), verified_session_at=now,
        verified_session_expires_at=now + timedelta(minutes=15),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )


def synthetic_app(role, tenant, db=None):
    target = FastAPI()
    target.include_router(tenants.router, prefix="/api/v1")
    target.include_router(special_credit.router, prefix="/api/v1")
    target.include_router(exclusive_cashboxes.master_router, prefix="/api/v1")
    target.include_router(exclusive_cashboxes.tenant_router, prefix="/api/v1")
    target.include_router(exclusive_cashbox_review_gaps.master_router,
                          prefix="/api/v1")
    target.include_router(exclusive_cashbox_review_gaps.tenant_router,
                          prefix="/api/v1")
    principal = synthetic_session(role, tenant)
    store = db or NeverDB()
    target.dependency_overrides[get_current_session] = lambda: principal
    target.dependency_overrides[get_rls_db_connection] = lambda: store
    return TestClient(target), store


@pytest.fixture(autouse=True)
def no_external_connections(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("No real DB connection allowed in M40230 synthetic CI")
    monkeypatch.setattr("app.dependencies.asyncpg.connect", forbidden)
    monkeypatch.setattr("app.database.get_db_pool", forbidden)


TENANT_READS = (
    TENANT_ROOT + "/dashboard",
    TENANT_ROOT + "/members",
    TENANT_ROOT + "/admin-exclusive-cashbox",
    TENANT_ROOT + "/admin-exclusive-cashbox/history",
    TENANT_ROOT + "/admin-exclusive-cashbox/review-readiness",
    TENANT_ROOT + "/admin-exclusive-cashbox/review-policy-gaps",
    CREDIT + "/members",
    CREDIT + "/cycle-readiness",
    CREDIT + "/grants",
    CREDIT + "/campaigns",
    CREDIT + "/opportunities",
    CREDIT + "/preferences",
    TENANT_ROOT + "/my-contracts",
)
MASTER_READS = (
    MASTER_ROOT + "/exclusive-cashbox",
    MASTER_ROOT + "/exclusive-cashbox/history",
    MASTER_ROOT + "/exclusive-cashbox/review-readiness",
    MASTER_ROOT + "/exclusive-cashbox/review-policy-gaps",
)
ADMIN_ONLY = (
    TENANT_ROOT + "/members",
    TENANT_ROOT + "/admin-exclusive-cashbox",
    TENANT_ROOT + "/admin-exclusive-cashbox/history",
    TENANT_ROOT + "/admin-exclusive-cashbox/review-readiness",
    TENANT_ROOT + "/admin-exclusive-cashbox/review-policy-gaps",
    CREDIT + "/members",
    CREDIT + "/cycle-readiness",
    CREDIT + "/campaigns",
)
MEMBER_ONLY = (
    CREDIT + "/opportunities",
    CREDIT + "/preferences",
)


@pytest.mark.parametrize("url", TENANT_READS)
def test_master_cannot_read_any_tenant_area(url):
    client, db = synthetic_app("MASTER", None)
    with client:
        response = client.get(url)
    assert response.status_code == 403, url
    assert db.calls == []


@pytest.mark.parametrize("url", TENANT_READS)
@pytest.mark.parametrize("role", ("TENANT_ADMIN", "TENANT_MEMBER"))
def test_wrong_tenant_does_not_reach_rls(role, url):
    client, db = synthetic_app(role, B)
    with client:
        response = client.get(url)
    assert response.status_code == 403, (role, url)
    assert db.calls == []


@pytest.mark.parametrize("url", MASTER_READS)
@pytest.mark.parametrize("role", ("TENANT_ADMIN", "TENANT_MEMBER"))
def test_tenant_role_cannot_access_master_cashbox(role, url):
    client, db = synthetic_app(role, A)
    with client:
        response = client.get(url)
    assert response.status_code == 403, (role, url)
    assert db.calls == []


@pytest.mark.parametrize("url", ADMIN_ONLY)
def test_member_cannot_read_admin_only_areas(url):
    client, db = synthetic_app("TENANT_MEMBER", A)
    with client:
        response = client.get(url)
    assert response.status_code == 403, url
    assert db.calls == []


@pytest.mark.parametrize("url", MEMBER_ONLY)
def test_admin_cannot_read_private_member_opportunities(url):
    client, db = synthetic_app("TENANT_ADMIN", A)
    with client:
        response = client.get(url)
    assert response.status_code == 403, url
    assert db.calls == []


@pytest.mark.parametrize("url", (
    TENANT_ROOT + "/admin-exclusive-cashbox",
    TENANT_ROOT + "/admin-exclusive-cashbox/history",
    TENANT_ROOT + "/admin-exclusive-cashbox/review-readiness",
    TENANT_ROOT + "/admin-exclusive-cashbox/review-policy-gaps",
))
def test_admin_is_not_automatically_proven_owner(url):
    db = NonOwnerDB()
    client, db = synthetic_app("TENANT_ADMIN", A, db)
    with client:
        response = client.get(url)
    assert response.status_code == 403, url
    assert db.calls == ["fetchval"]


@pytest.mark.parametrize("role,tenant,path,payload", (
    ("TENANT_MEMBER", A, f"{CREDIT}/campaigns/{CAMPAIGN}/publish", None),
    ("TENANT_MEMBER", A, f"{CREDIT}/campaigns/{CAMPAIGN}/cancel", None),
    ("TENANT_MEMBER", A, f"{CREDIT}/grants/{CAMPAIGN}/revoke", None),
    ("TENANT_ADMIN", B, f"{CREDIT}/campaigns/{CAMPAIGN}/publish", None),
    ("MASTER", None, f"{CREDIT}/campaigns/{CAMPAIGN}/publish", None),
    ("TENANT_ADMIN", A, f"{CREDIT}/opportunities/{CAMPAIGN}/reply",
     {"status": "INTERESTED"}),
    ("TENANT_MEMBER", B, f"{CREDIT}/opportunities/{CAMPAIGN}/reply",
     {"status": "DECLINED"}),
))
def test_disallowed_credit_action_denied_before_synthetic_db(
    role, tenant, path, payload
):
    client, db = synthetic_app(role, tenant)
    with client:
        response = client.post(path, json=payload)
    assert response.status_code == 403, (role, path, response.status_code)
    assert db.calls == []


def test_credit_sandbox_is_closed_even_to_own_admin(monkeypatch):
    monkeypatch.setenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", "OFF")
    client, db = synthetic_app("TENANT_ADMIN", A)
    with client:
        response = client.get(CREDIT + "/campaigns")
    assert response.status_code == 503
    assert db.calls == []


def test_rbac_rls_source_is_present_not_live_attested():
    assert static.evaluate() == "PASS_SOURCE_BOUNDARIES_ONLY_NOT_RUNTIME_RLS"


def test_static_gate_rejects_removed_session_tenant_check(tmp_path):
    source = static.FILES["dependencies"].read_text(encoding="utf-8")
    source = source.replace(
        "session.tenant_id != target_tenant_id",
        "session.tenant_id == target_tenant_id",
    )
    changed = tmp_path / "dependencies.py"
    changed.write_text(source, encoding="utf-8")
    sources = dict(static.FILES)
    sources["dependencies"] = changed
    assert static.evaluate(sources).startswith("BLOCKED_")


def test_static_source_only_has_no_live_db(monkeypatch, capsys):
    assert static.main(["--source-only"]) == 0
    output = capsys.readouterr().out
    assert "M40230_LIVE_POSTGRESQL=NOT_QUERIED" in output
    assert "M40230_ACTUAL_AUTHENTICATED_RLS=NOT_TESTED" in output
