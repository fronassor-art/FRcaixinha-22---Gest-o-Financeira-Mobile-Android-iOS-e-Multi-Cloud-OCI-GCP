"""M38001-M38012: scope uniqueness before issuing a user context."""
from itertools import permutations
from uuid import UUID
import pytest
from fastapi import HTTPException
from app.login_role_policy import select_login_role

A=UUID("00000000-0000-4000-8000-0000000000a1")
B=UUID("00000000-0000-4000-8000-0000000000b2")
C=UUID("00000000-0000-4000-8000-0000000000c3")
AD="TENANT_ADMIN"
MB="TENANT_MEMBER"
ADMIN1={"tenant_id":A,"role":AD}
MEMBER1={"tenant_id":A,"role":MB}
MEMBER2={"tenant_id":B,"role":MB}
ADMIN3={"tenant_id":C,"role":AD}
ROWS=[ADMIN1,MEMBER1,MEMBER2,ADMIN3]


def choose(links,role=None,tenant=None,master=False):
    return select_login_role(requested_role=role,
        requested_tenant_id=tenant,is_master=master,links=links)


def reject(links,role=None,tenant=None,master=False,status=401):
    with pytest.raises(HTTPException) as exc:
        choose(links,role,tenant,master)
    assert exc.value.status_code==status
    detail=str(exc.value.detail)
    assert all(str(item) not in detail for item in (A,B,C))


@pytest.mark.parametrize("row",ROWS)
def test_single_link_legacy_compatibility(row):
    assert choose([row])==(row["role"],row["tenant_id"])


@pytest.mark.parametrize("links",[[ADMIN1,MEMBER1],[MEMBER1,MEMBER2],
    [ADMIN1,MEMBER2],[ADMIN1,ADMIN3],[ADMIN1,ADMIN1],
    [MEMBER1,MEMBER1],ROWS])
def test_multiple_roles_tenants_duplicate_rows_require_selection(links):
    reject(links,status=409)


@pytest.mark.parametrize("order",list(permutations(ROWS,4)))
def test_query_order_cannot_choose_implicit_context(order):
    reject(order,status=409)
    for role,tenant in [(AD,A),(MB,A),(MB,B),(AD,C)]:
        assert choose(order,role,tenant)==(role,tenant)


def test_explicit_role_same_tenant_is_not_ambiguous():
    assert choose([ADMIN1,MEMBER1],AD)==(AD,A)
    assert choose([ADMIN1,MEMBER1],MB)==(MB,A)


def test_explicit_role_two_tenants_requires_tenant():
    reject([MEMBER1,MEMBER2],MB,status=409)
    reject([ADMIN1,ADMIN3],AD,status=409)
    reject([MEMBER1,MEMBER1],MB,A,status=409)


def test_master_explicit_only_and_no_implicit_tenant():
    assert choose(ROWS,"MASTER",master=True)==("MASTER",None)
    reject([ADMIN1],"MASTER")
    reject([ADMIN1],"MASTER",A,True)
    reject([ADMIN1],master=True)
    assert choose([ADMIN1],AD,master=True)==(AD,A)


@pytest.mark.parametrize("role",["INVALID","",False,0])
def test_invalid_roles_never_fallback(role):
    reject([MEMBER1],role)


def test_absent_or_null_tenant_never_authorized():
    reject([])
    reject([],MB)
    reject([{"role":MB,"tenant_id":None}])
    reject([{"role":AD,"tenant_id":None}],AD)


def test_unknown_requested_tenant_denied():
    reject([ADMIN1],AD,B)
    reject([ADMIN1],tenant=A)


def test_policy_does_not_write_database_or_allow_public_registration():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/"app/login_role_policy.py").read_text()
    assert "len(links) != 1" in src and "len(eligible) > 1" in src
    assert "if requested_role is None and not is_master and links" in src
    for snippet in ("INSERT INTO","UPDATE public.","DELETE FROM","asyncpg.connect",
                    "requests.","httpx.","app.include_router"):
        assert snippet not in src
