"""M17000: strict in-memory recipient scope and MAC-authenticated keyset cursors."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID
import pytest
from app.notification_inbox_page_boundary import (
    CONTRACT, RecipientScope, decode_cursor, encode_cursor,
    preview_notification_page,
)
from app.notifications_policy import NoticeRole
from app.pix_automation_contract import FinancialOperationBlocked

T=UUID("ffffffff-0000-4000-8000-000000000011")
B=UUID("ffffffff-0000-4000-8000-000000000012")
U=UUID("ffffffff-0000-4000-8000-000000000001")
V=UUID("ffffffff-0000-4000-8000-000000000002")
NOW=datetime(2026,11,5,13,tzinfo=timezone.utc)
KEY=b"CI-inbox-cursor-secret-more-than-32-bytes-only"
S=RecipientScope(U,NoticeRole.TENANT_MEMBER,T)

def row(n,scope=S):
    return {
        "id":UUID(f"eeeeeeee-0000-4000-8000-{n:012d}"),
        "tenant_id":scope.tenant_id,"recipient_user_id":scope.user_id,
        "recipient_role":scope.role.value,"kind":"CONTRIBUTION_DUE_INFO",
        "title":"Contribuição a conferir",
        "message":"Confira a informação no painel.",
        "created_at":NOW-timedelta(seconds=n),
        "read_at":None,
    }

def page(rows,scope=S,limit=2,after=None):
    return preview_notification_page(tuple(rows),scope,secret=KEY,
                                      now=NOW,limit=limit,after=after)

def test_sorted_cursor_progress_and_never_invents_unread_total():
    p=page([row(1),row(2),row(3)])
    assert p.contract==CONTRACT
    assert len(p.items)==2 and p.has_more and p.next_cursor
    assert p.unread_count is None
    assert not p.inbox_api_connected and not p.production_auth_verified
    assert not p.external_send_authorized
    assert not p.bank_reconciled
    second=page([row(3),row(4)],after=p.next_cursor)
    assert not second.has_more and second.next_cursor is None
    assert [x["id"] for x in second.items] == [str(row(3)["id"]),str(row(4)["id"])]
    assert len({x["id"] for x in p.items+second.items})==4

@pytest.mark.parametrize("s",[
    RecipientScope(V,NoticeRole.TENANT_MEMBER,T),
    RecipientScope(U,NoticeRole.TENANT_MEMBER,B),
    RecipientScope(U,NoticeRole.TENANT_ADMIN,T),
    RecipientScope(U,NoticeRole.MASTER,None),
])
def test_cross_recipient_role_tenant_cursor_rejected(s):
    token=encode_cursor(S,row(2)["created_at"],row(2)["id"],secret=KEY,now=NOW)
    with pytest.raises(FinancialOperationBlocked):
        decode_cursor(token,s,secret=KEY,now=NOW)

@pytest.mark.parametrize("raw",[
    "","garbage","x.y.z","a."+"0"*64,None,"!"*2000,7,
])
def test_malformed_cursor_rejected(raw):
    with pytest.raises(FinancialOperationBlocked):
        decode_cursor(raw,S,secret=KEY,now=NOW)

def test_cursor_expired_future_and_tampered():
    token=encode_cursor(S,row(2)["created_at"],row(2)["id"],secret=KEY,now=NOW)
    with pytest.raises(FinancialOperationBlocked):
        decode_cursor(token,S,secret=KEY,now=NOW+timedelta(seconds=901))
    with pytest.raises(FinancialOperationBlocked):
        decode_cursor(token,S,secret=KEY,now=NOW-timedelta(seconds=31))
    with pytest.raises(FinancialOperationBlocked):
        decode_cursor(token[:-1]+("a" if token[-1]!="a" else "b"),
                      S,secret=KEY,now=NOW)

@pytest.mark.parametrize("bad",[
    RecipientScope(U,NoticeRole.MASTER,T),
    RecipientScope(U,NoticeRole.TENANT_MEMBER,None),
    RecipientScope(UUID(int=0),NoticeRole.TENANT_MEMBER,T),
    RecipientScope(U,"TENANT_MEMBER",T),
])
def test_bad_role_scope_fails_closed(bad):
    with pytest.raises(FinancialOperationBlocked):
        page([],scope=bad)

@pytest.mark.parametrize("bad",[
    {"recipient_user_id":V}, {"tenant_id":B},
    {"recipient_role":"TENANT_ADMIN"},{"kind":"UNKNOWN"},
    {"read_at":NOW-timedelta(days=3)}, {"title":""},
    {"message":"this has\nnewline"}, {"id":UUID(int=0)},
    {"created_at":NOW.replace(tzinfo=None)},
])
def test_bad_row_always_rejected(bad):
    x=row(1)
    x.update(bad)
    with pytest.raises(FinancialOperationBlocked):
        page([x])

def test_no_duplicate_or_unordered_records():
    with pytest.raises(FinancialOperationBlocked):
        page([row(1),row(1)])
    with pytest.raises(FinancialOperationBlocked):
        page([row(2),row(1)])

def test_replay_prior_cursor_not_accepted_in_new_page():
    cur=encode_cursor(S,row(2)["created_at"],row(2)["id"],secret=KEY,now=NOW)
    with pytest.raises(FinancialOperationBlocked):
        page([row(2)],after=cur)

@pytest.mark.parametrize("limit",[0,-1,51,True,1.5])
def test_page_size_requires_one_to_fifty_integer(limit):
    with pytest.raises(FinancialOperationBlocked):
        page([],limit=limit)

def test_limit_one_extra_and_truncation_detected():
    assert len(page([row(1),row(2)],limit=1).items)==1
    with pytest.raises(FinancialOperationBlocked):
        page([row(1),row(2),row(3),row(4)],limit=2)

def test_empty_page_not_authoritative_zero_unread():
    p=page([])
    assert not p.has_more and p.items==()
    assert p.unread_count is None and not p.inbox_api_connected

def test_secret_must_be_at_least_32_bytes():
    with pytest.raises(FinancialOperationBlocked):
        preview_notification_page(tuple(),S,secret=b"abc",now=NOW)
