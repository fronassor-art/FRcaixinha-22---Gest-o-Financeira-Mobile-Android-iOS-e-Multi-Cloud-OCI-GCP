"""Sessão em memória falsa: nega expiração, revogação e vínculo inválido.

Nenhuma consulta ao banco, nenhuma migration ou alteração de conta real.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app import dependencies as deps

USER=UUID("00000000-0000-4000-8000-000000000001")
TENANT=UUID("00000000-0000-4000-8000-000000000002")
NOW=lambda:datetime.now(timezone.utc)


class FakeTransaction:
    async def __aenter__(self):
        return self
    async def __aexit__(self,exc_type,exc,tb):
        return False


class FakeConnection:
    def __init__(self,row,links=None,refresh=True):
        self.row=row
        self.links=links or []
        self.refresh=refresh
        self.closed=False
        self.calls=[]
    def transaction(self):
        return FakeTransaction()
    async def fetchrow(self,*args):
        self.calls.append("fetchrow")
        return self.row
    async def fetch(self,*args):
        self.calls.append("fetch")
        return self.links
    async def fetchval(self,*args):
        self.calls.append("refresh")
        return NOW()+timedelta(minutes=10) if self.refresh else None
    async def close(self):
        self.closed=True


def make_row(**changes):
    data={
        "user_id":USER,"active_role":"MASTER",
        "active_tenant_id":None,
        "expires_at":NOW()+timedelta(minutes=10),
        "revoked_at":None,"email":"ci@example.invalid",
        "full_name":"Synthetic Master","is_master":True,"status":"ACTIVE",
    }
    data.update(changes)
    return data


def make_request(token=True):
    headers=[(b"authorization",b"Bearer synthetic-ci-token")] if token else []
    return Request({"type":"http","method":"GET","path":"/ci",
                    "headers":headers,"query_string":b""})


async def evaluate(monkeypatch,conn):
    calls=[]
    async def fake_connect(*args,**kwargs):
        calls.append(("connect",args,kwargs))
        return conn
    monkeypatch.setattr(deps, "auth_database_url", lambda:"ci-fake-dsn")
    monkeypatch.setattr(deps.asyncpg,"connect",fake_connect)
    try:
        return await deps.get_current_session(make_request())
    finally:
        assert conn.closed
        assert len(calls)==1


@pytest.mark.asyncio
@pytest.mark.parametrize("change",[
    {"revoked_at":NOW()},
    {"expires_at":NOW()-timedelta(seconds=1)},
    {"status":"SUSPENDED"},
    {"active_tenant_id":TENANT},
    {"is_master":False},
])
async def test_expired_revoked_suspended_and_invalid_master_are_denied(monkeypatch,change):
    conn=FakeConnection(make_row(**change))
    with pytest.raises(HTTPException) as exc:
        await evaluate(monkeypatch,conn)
    assert exc.value.status_code==401
    assert "refresh" not in conn.calls


@pytest.mark.asyncio
async def test_nonmaster_without_active_membership_is_denied(monkeypatch):
    conn=FakeConnection(make_row(
        active_role="TENANT_MEMBER",active_tenant_id=TENANT,is_master=False,
    ))
    with pytest.raises(HTTPException) as exc:
        await evaluate(monkeypatch,conn)
    assert exc.value.status_code==401
    assert "fetch" in conn.calls
    assert "refresh" not in conn.calls


@pytest.mark.asyncio
async def test_refresh_revoked_between_checks_fails_closed(monkeypatch):
    conn=FakeConnection(make_row(),refresh=False)
    with pytest.raises(HTTPException) as exc:
        await evaluate(monkeypatch,conn)
    assert exc.value.status_code==401
    assert "refresh" in conn.calls


@pytest.mark.asyncio
async def test_valid_master_is_verified_without_tenant(monkeypatch):
    conn=FakeConnection(make_row())
    session=await evaluate(monkeypatch,conn)
    assert session.role=="MASTER"
    assert session.tenant_id is None
    assert session.is_master is True
    assert session.user_id==str(USER)


@pytest.mark.asyncio
async def test_missing_token_never_opens_connection(monkeypatch):
    async def blocked_connect(*args,**kwargs):
        raise AssertionError("No DB when bearer absent")
    monkeypatch.setattr(deps.asyncpg,"connect",blocked_connect)
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_session(make_request(token=False))
    assert exc.value.status_code==401


@pytest.mark.asyncio
async def test_network_unavailable_is_503_without_local_auth(monkeypatch):
    monkeypatch.setattr(deps,"auth_database_url",lambda:"ci-fake-dsn")
    async def fails(*args,**kwargs):
        raise OSError("synthetic offline")
    monkeypatch.setattr(deps.asyncpg,"connect",fails)
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_session(make_request())
    assert exc.value.status_code==503
