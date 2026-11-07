"""O Master exige escolha explícita; nenhuma troca automática de papel."""
import uuid
import pytest
from fastapi import HTTPException
from app.login_role_policy import select_login_role

TENANT = uuid.UUID("00000000-0000-4000-8000-000000000002")
LINKS = [
    {"role": "TENANT_ADMIN", "tenant_id": TENANT},
    {"role": "TENANT_MEMBER", "tenant_id": TENANT},
]


def test_master_is_never_implicit_even_if_user_has_multiple_roles():
    assert select_login_role(
        requested_role="MASTER", is_master=True, links=LINKS
    ) == ("MASTER", None)
    for role in (None, "", "OUTRO"):
        with pytest.raises(HTTPException) as exc:
            select_login_role(requested_role=role, is_master=True, links=LINKS)
        assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        select_login_role(requested_role="MASTER", is_master=False, links=LINKS)


def test_explicit_tenant_roles_do_not_promote_to_master():
    for role in ("TENANT_ADMIN", "TENANT_MEMBER"):
        assert select_login_role(
            requested_role=role, is_master=True, links=LINKS
        ) == (role, TENANT)
    with pytest.raises(HTTPException):
        select_login_role(
            requested_role="TENANT_ADMIN", is_master=True, links=[]
        )


def test_nonmaster_legacy_fallback_never_grants_platform_access():
    assert select_login_role(
        requested_role=None, is_master=False, links=LINKS
    ) == ("TENANT_ADMIN", TENANT)
    for role, links in [
        (None, []), ("MASTER", LINKS), ("TENANT_MEMBER", []),
        ("INVALID", LINKS), (None, [{"role": "MASTER", "tenant_id": TENANT}])
    ]:
        with pytest.raises(HTTPException):
            select_login_role(
                requested_role=role, is_master=False, links=links
            )


def test_explicit_tenant_choice_requires_matching_active_link():
    other_tenant = uuid.UUID("00000000-0000-4000-8000-000000000003")
    multi = LINKS + [
        {"role": "TENANT_ADMIN", "tenant_id": other_tenant},
        {"role": "TENANT_MEMBER", "tenant_id": other_tenant},
    ]
    for role in ("TENANT_ADMIN", "TENANT_MEMBER"):
        with pytest.raises(HTTPException) as ambiguous:
            select_login_role(requested_role=role, is_master=False, links=multi)
        assert ambiguous.value.status_code == 409
        assert select_login_role(
            requested_role=role, is_master=False, links=multi,
            requested_tenant_id=other_tenant,
        ) == (role, other_tenant)
        with pytest.raises(HTTPException) as exc:
            select_login_role(
                requested_role=role, is_master=False, links=LINKS,
                requested_tenant_id=other_tenant,
            )
        assert exc.value.status_code == 401
    for role, master in ((None, False), ("MASTER", True)):
        with pytest.raises(HTTPException) as exc:
            select_login_role(
                requested_role=role, is_master=master, links=multi,
                requested_tenant_id=other_tenant,
            )
        assert exc.value.status_code == 401
