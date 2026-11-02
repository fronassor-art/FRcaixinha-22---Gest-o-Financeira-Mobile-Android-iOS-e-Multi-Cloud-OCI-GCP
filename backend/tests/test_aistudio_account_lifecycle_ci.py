"""Regressão CI do ciclo de vida de convite e recuperação, SEM e-mail ou usuário real."""
import os
from uuid import uuid4
from urllib.parse import urlparse

import psycopg
import pytest

from app.account_lifecycle import (
    LifecycleDenied, prepare_invitation_ci, simulate_invitation_delivery_ci,
    accept_existing_identity_ci, revoke_invitation_ci,
    prepare_password_reset_ci, simulate_reset_delivery_ci, reset_password_ci,
)
from app.security import hash_password_secure, hash_token, verify_password_secure


@pytest.fixture
def synthetic_accounts():
    if os.getenv("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("Somente PostgreSQL descartável do GitHub Actions")
    dsn = os.environ["CI_ADMIN_DATABASE_URL"]
    parsed = urlparse(dsn)
    assert parsed.hostname in ("127.0.0.1", "localhost")
    assert parsed.port == 5432 and parsed.path == "/frcaixinha_ci"
    users = {name: uuid4() for name in ("master", "admin", "member", "outsider")}
    tenant = uuid4()
    with psycopg.connect(dsn, autocommit=True) as db:
        for name, uid in users.items():
            db.execute(
                "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master) "
                "VALUES(%s,%s,%s,%s,'00000000000',%s)",
                (uid, f"{uid}@example.com", f"{name} sintético",
                 uid.hex[:14], name == "master"),
            )
        db.execute(
            "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id) "
            "VALUES(%s,'Caixinha descartável CI',%s,%s)",
            (tenant, str(uuid4()), users["admin"]),
        )
        db.execute(
            "INSERT INTO public.memberships(tenant_id,user_id,role) "
            "VALUES(%s,%s,'TENANT_ADMIN')", (tenant, users["admin"]),
        )
        db.execute(
            "INSERT INTO public.credentials(user_id,password_hash) VALUES(%s,%s)",
            (users["member"], hash_password_secure("senha-sintetica-inicial")),
        )
        try:
            yield db, users, tenant
        finally:
            db.execute(
                "DELETE FROM public.audit_events WHERE tenant_id=%s OR actor_id=ANY(%s::uuid[])",
                (tenant, list(users.values())),
            )
            db.execute(
                "DELETE FROM public.invitations WHERE tenant_id=%s", (tenant,),
            )
            db.execute(
                "DELETE FROM public.password_reset_tokens WHERE user_id=ANY(%s::uuid[])",
                (list(users.values()),),
            )
            db.execute(
                "DELETE FROM public.sessions WHERE user_id=ANY(%s::uuid[])",
                (list(users.values()),),
            )
            db.execute(
                "DELETE FROM public.memberships WHERE tenant_id=%s", (tenant,),
            )
            db.execute("DELETE FROM public.tenants WHERE id=%s", (tenant,))
            db.execute(
                "DELETE FROM public.users WHERE id=ANY(%s::uuid[])", (list(users.values()),),
            )


def test_invitation_requires_delivery_correct_identity_and_single_use(synthetic_accounts):
    db, users, tenant = synthetic_accounts
    invitation_id, token = prepare_invitation_ci(
        db, tenant_id=tenant, inviter_id=users["admin"],
        recipient_email=f"{users['member']}@example.com", target_role="TENANT_MEMBER",
    )
    stored = db.execute(
        "SELECT token_hash,delivery_status FROM public.invitations WHERE id=%s",
        (invitation_id,),
    ).fetchone()
    assert stored == (hash_token(token), "PENDING_DELIVERY")
    assert token not in str(stored)
    assert accept_existing_identity_ci(db, token=token, user_id=users["member"]) is None
    assert simulate_invitation_delivery_ci(db, invitation_id)
    assert not simulate_invitation_delivery_ci(db, invitation_id)
    assert accept_existing_identity_ci(db, token=token, user_id=users["outsider"]) is None
    membership_id = accept_existing_identity_ci(db, token=token, user_id=users["member"])
    assert membership_id is not None
    assert accept_existing_identity_ci(db, token=token, user_id=users["member"]) is None
    assert not revoke_invitation_ci(db, invitation_id)
    membership = db.execute(
        "SELECT user_id,tenant_id,role,status FROM public.memberships WHERE id=%s",
        (membership_id,),
    ).fetchone()
    assert membership == (users["member"], tenant, "TENANT_MEMBER", "ATIVA")
    assert db.execute(
        "SELECT count(*) FROM public.audit_events WHERE action='CI_INVITATION_ACCEPTED' "
        "AND object_id=%s", (str(membership_id),),
    ).fetchone()[0] == 1


def test_invitation_hierarchy_expiration_and_revoke(synthetic_accounts):
    db, users, tenant = synthetic_accounts
    with pytest.raises(LifecycleDenied):
        prepare_invitation_ci(
            db, tenant_id=tenant, inviter_id=users["member"],
            recipient_email=f"{users['outsider']}@example.com",
            target_role="TENANT_MEMBER",
        )
    with pytest.raises(LifecycleDenied):
        prepare_invitation_ci(
            db, tenant_id=tenant, inviter_id=users["admin"],
            recipient_email=f"{users['outsider']}@example.com",
            target_role="TENANT_ADMIN",
        )

    invite, token = prepare_invitation_ci(
        db, tenant_id=tenant, inviter_id=users["master"],
        recipient_email=f"{users['outsider']}@example.com",
        target_role="TENANT_ADMIN",
    )
    assert simulate_invitation_delivery_ci(db, invite)
    assert revoke_invitation_ci(db, invite)
    assert accept_existing_identity_ci(db, token=token, user_id=users["outsider"]) is None

    pending, expiring = prepare_invitation_ci(
        db, tenant_id=tenant, inviter_id=users["admin"],
        recipient_email=f"{users['outsider']}@example.com",
        target_role="TENANT_MEMBER",
    )
    assert simulate_invitation_delivery_ci(db, pending)
    db.execute(
        "UPDATE public.invitations SET expires_at=now()-interval '1 minute' WHERE id=%s",
        (pending,),
    )
    assert accept_existing_identity_ci(db, token=expiring, user_id=users["outsider"]) is None
    assert db.execute(
        "SELECT count(*) FROM public.memberships WHERE user_id=%s",
        (users["outsider"],),
    ).fetchone()[0] == 0


def test_reset_is_hashed_expires_once_and_revokes_every_session(synthetic_accounts):
    db, users, tenant = synthetic_accounts
    session_token = "ci-session-only-never-real"
    db.execute(
        "INSERT INTO public.sessions(id,token_hash,user_id,active_role,active_tenant_id,expires_at) "
        "VALUES(%s,%s,%s,'TENANT_MEMBER',%s,now()+interval '10 minutes')",
        (uuid4(), hash_token(session_token), users["member"], tenant),
    )
    first_id, first_raw = prepare_password_reset_ci(db, users["member"])
    assert not reset_password_ci(db, token=first_raw, new_password="senha-atualizada-ci-1234")
    assert simulate_reset_delivery_ci(db, first_id)
    db.execute(
        "UPDATE public.password_reset_tokens "
        "SET requested_at=now()-interval '30 minutes', "
        "expires_at=now()-interval '15 minutes' WHERE id=%s", (first_id,),
    )
    assert not reset_password_ci(db, token=first_raw, new_password="senha-atualizada-ci-1234")

    second_id, second_raw = prepare_password_reset_ci(db, users["member"])
    assert simulate_reset_delivery_ci(db, second_id)
    other_id, other_raw = prepare_password_reset_ci(db, users["member"])
    assert simulate_reset_delivery_ci(db, other_id)
    assert reset_password_ci(db, token=second_raw, new_password="senha-atualizada-ci-1234")
    assert not reset_password_ci(db, token=second_raw, new_password="outra-senha-ci-1234")
    assert not reset_password_ci(db, token=other_raw, new_password="outra-senha-ci-1234")
    result = db.execute(
        "SELECT password_hash FROM public.credentials WHERE user_id=%s",
        (users["member"],),
    ).fetchone()
    assert result and verify_password_secure("senha-atualizada-ci-1234", result[0])
    assert not verify_password_secure("senha-sintetica-inicial", result[0])
    assert db.execute(
        "SELECT count(*) FROM public.sessions WHERE user_id=%s AND revoked_at IS NULL",
        (users["member"],),
    ).fetchone()[0] == 0
    assert db.execute(
        "SELECT count(*) FROM public.audit_events WHERE actor_id=%s "
        "AND action='CI_PASSWORD_RESET'", (users["member"],),
    ).fetchone()[0] == 1


def test_app_and_auth_have_no_direct_lifecycle_token_access(synthetic_accounts):
    for env_name in ("DATABASE_URL", "CI_AUTH_DATABASE_URL"):
        dsn = os.environ[env_name]
        with psycopg.connect(dsn) as conn:
            for table in ("public.invitations", "public.password_reset_tokens"):
                assert not conn.execute(
                    "SELECT has_table_privilege(current_user,%s,'SELECT')",
                    (table,),
                ).fetchone()[0]
                assert not conn.execute(
                    "SELECT has_table_privilege(current_user,%s,'INSERT')",
                    (table,),
                ).fetchone()[0]


def test_lifecycle_refuses_non_ci_environment(monkeypatch, synthetic_accounts):
    db, users, tenant = synthetic_accounts
    monkeypatch.delenv("FRCAIXINHA_CI_ISOLATED")
    with pytest.raises(LifecycleDenied):
        prepare_password_reset_ci(db, users["member"])
    with pytest.raises(LifecycleDenied):
        prepare_invitation_ci(
            db, tenant_id=tenant, inviter_id=users["admin"],
            recipient_email=f"{users['member']}@example.com",
            target_role="TENANT_MEMBER",
        )
