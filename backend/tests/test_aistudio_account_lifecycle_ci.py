"""Regressão CI do ciclo de vida de convite e recuperação, SEM e-mail ou usuário real."""
import os
from hashlib import sha256
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
from app.account_governance_ci import publish_document_ci


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
    with psycopg.connect(dsn) as db:
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
            db.rollback()


def create_contract_ci(db):
    label="ci-invitation-"+str(uuid4())
    return publish_document_ci(
        db,kind="TENANT_MEMBERSHIP",version=label,
        sha256_hex=sha256(label.encode()).hexdigest(),
        reference="Termos sintéticos de convite para CI descartável"
    )


def test_invitation_requires_delivery_correct_identity_and_single_use(synthetic_accounts):
    db, users, tenant = synthetic_accounts
    doc=create_contract_ci(db)
    invitation_id, token = prepare_invitation_ci(
        db, tenant_id=tenant, inviter_id=users["admin"],
        recipient_email=f"{users['member']}@example.com", target_role="TENANT_MEMBER",
    )
    db.execute("UPDATE public.invitations SET required_document_id=%s WHERE id=%s",
               (doc,invitation_id))
    stored = db.execute(
        "SELECT token_hash,delivery_status FROM public.invitations WHERE id=%s",
        (invitation_id,),
    ).fetchone()
    assert stored == (hash_token(token), "PENDING_DELIVERY")
    assert token not in str(stored)
    assert accept_existing_identity_ci(db, token=token, user_id=users["member"], document_id=doc, consent=True) is None
    assert simulate_invitation_delivery_ci(db, invitation_id)
    assert not simulate_invitation_delivery_ci(db, invitation_id)
    assert accept_existing_identity_ci(
        db,token=token,user_id=users["member"],document_id=doc,
        consent=False
    ) is None
    assert accept_existing_identity_ci(
        db,token=token,user_id=users["member"],document_id=uuid4(),
        consent=True
    ) is None
    assert accept_existing_identity_ci(db, token=token, user_id=users["outsider"], document_id=doc, consent=True) is None
    membership_id = accept_existing_identity_ci(db, token=token, user_id=users["member"], document_id=doc, consent=True)
    assert membership_id is not None
    assert accept_existing_identity_ci(db, token=token, user_id=users["member"], document_id=doc, consent=True) is None
    assert not revoke_invitation_ci(db, invitation_id)
    membership = db.execute(
        "SELECT user_id,tenant_id,role,status FROM public.memberships WHERE id=%s",
        (membership_id,),
    ).fetchone()
    assert membership == (users["member"], tenant, "TENANT_MEMBER", "ATIVA")
    assert db.execute(
        "SELECT count(*) FROM public.contract_acceptances "
        "WHERE user_id=%s AND document_id=%s AND tenant_id=%s",
        (users["member"],doc,tenant),
    ).fetchone()[0]==1
    # Mesmo destinatário, segundo convite e mesmo papel: não duplica vínculo
    # nem cria um aceite órfão para o segundo convite.
    second_id, second_token = prepare_invitation_ci(
        db,tenant_id=tenant,inviter_id=users["admin"],
        recipient_email=f"{users['member']}@example.com",
        target_role="TENANT_MEMBER",
    )
    db.execute(
        "UPDATE public.invitations SET required_document_id=%s WHERE id=%s",
        (doc,second_id),
    )
    assert simulate_invitation_delivery_ci(db,second_id)
    assert accept_existing_identity_ci(
        db,token=second_token,user_id=users["member"],
        document_id=doc,consent=True,
    ) is None
    assert db.execute(
        "SELECT count(*) FROM public.contract_acceptances "
        "WHERE user_id=%s AND document_id=%s AND tenant_id=%s",
        (users["member"],doc,tenant),
    ).fetchone()[0]==1

    assert db.execute(
        "SELECT count(*) FROM public.audit_events WHERE action='CI_INVITATION_ACCEPTED' "
        "AND object_id=%s", (str(membership_id),),
    ).fetchone()[0] == 1


def test_invitation_hierarchy_expiration_and_revoke(synthetic_accounts):
    db, users, tenant = synthetic_accounts
    doc=create_contract_ci(db)
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
    db.execute("UPDATE public.invitations SET required_document_id=%s WHERE id=%s",
               (doc,invite))
    assert simulate_invitation_delivery_ci(db, invite)
    assert revoke_invitation_ci(db, invite)
    assert accept_existing_identity_ci(db, token=token, user_id=users["outsider"], document_id=doc, consent=True) is None

    pending, expiring = prepare_invitation_ci(
        db, tenant_id=tenant, inviter_id=users["admin"],
        recipient_email=f"{users['outsider']}@example.com",
        target_role="TENANT_MEMBER",
    )
    db.execute("UPDATE public.invitations SET required_document_id=%s WHERE id=%s",
               (doc,pending))
    assert simulate_invitation_delivery_ci(db, pending)
    db.execute(
        "UPDATE public.invitations SET expires_at=now()-interval '1 minute' WHERE id=%s",
        (pending,),
    )
    assert accept_existing_identity_ci(db, token=expiring, user_id=users["outsider"], document_id=doc, consent=True) is None
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


def test_preliminary_admin_invitation_schema_allows_no_tenant_but_member_requires_one(synthetic_accounts):
    """Contrato 3.1: convite MASTER preliminar pode anteceder tenant existente."""
    db, users, _ = synthetic_accounts
    preliminary_id = uuid4()
    db.execute(
        "INSERT INTO public.invitations(id,tenant_id,inviter_user_id,target_email,"
        "target_role,token_hash,expires_at) "
        "VALUES(%s,NULL,%s,'admin.preliminar@example.com','TENANT_ADMIN',%s,"
        "now()+interval '1 day')",
        (preliminary_id, users["master"], hash_token("ci-preliminary-admin")),
    )
    try:
        row = db.execute(
            "SELECT tenant_id,target_role FROM public.invitations WHERE id=%s",
            (preliminary_id,),
        ).fetchone()
        assert row == (None, "TENANT_ADMIN")
    finally:
        db.execute("DELETE FROM public.invitations WHERE id=%s", (preliminary_id,))
    with pytest.raises(psycopg.errors.CheckViolation):
        with db.transaction():
            db.execute(
                "INSERT INTO public.invitations(id,tenant_id,inviter_user_id,"
                "target_email,target_role,token_hash,expires_at) "
                "VALUES(%s,NULL,%s,'member.invalid@example.com','TENANT_MEMBER',%s,"
                "now()+interval '1 day')",
                (uuid4(), users["admin"], hash_token("ci-invalid-member")),
            )


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


def test_new_invited_identity_requires_affirmative_versioned_acceptance(synthetic_accounts):
    """M24400: no user/membership/acceptance without explicit version proof."""
    from app.invite_registration_ci import (
        prepare_invite_email_verification_ci,
        register_new_invited_identity_ci,
    )
    db, users, tenant = synthetic_accounts
    doc = create_contract_ci(db)
    digest = db.execute(
        "SELECT sha256 FROM public.contract_documents WHERE id=%s", (doc,)
    ).fetchone()[0]
    recipient = f"new-{uuid4()}@example.invalid"
    inv, _ = prepare_invitation_ci(
        db, tenant_id=tenant, inviter_id=users["admin"],
        recipient_email=recipient, target_role="TENANT_MEMBER",
    )
    assert simulate_invitation_delivery_ci(db, inv)
    proof = prepare_invite_email_verification_ci(db, invitation_id=inv)

    def attempt(**changes):
        kw=dict(verification_token=proof,name="Membro sintético",
                cpf="12345678909",phone="11999990000",
                password="Somente-Teste-Seguro-2026!",document_id=doc)
        kw.update(changes)
        return register_new_invited_identity_ci(db,**kw)

    for opts in (
        {},   # no consent or hash
        {"consent":False,"accepted_document_sha256":digest},
        {"consent":"true","accepted_document_sha256":digest},
        {"consent":True,"accepted_document_sha256":None},
        {"consent":True,"accepted_document_sha256":"f"*64},
        {"consent":True,"accepted_document_sha256":digest}, # no bound doc yet
    ):
        with pytest.raises(LifecycleDenied):
            attempt(**opts)
        assert db.execute(
            "SELECT count(*) FROM public.users WHERE email=%s",(recipient,)
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT accepted_at FROM public.invitations WHERE id=%s",(inv,)
        ).fetchone()[0] is None

    db.execute(
        "UPDATE public.invitations SET required_document_id=%s WHERE id=%s",
        (doc,inv),
    )
    person = attempt(consent=True, accepted_document_sha256=digest)
    row=db.execute(
        "SELECT email,status,is_master,email_verified_at FROM public.users WHERE id=%s",
        (person,),
    ).fetchone()
    assert row[0]==recipient and row[1]=="ACTIVE" and row[2] is False
    assert row[3] is not None
    membership=db.execute(
        "SELECT tenant_id,role,status FROM public.memberships WHERE user_id=%s",
        (person,),
    ).fetchone()
    assert membership==(tenant,"TENANT_MEMBER","ATIVA")
    acceptance=db.execute(
        "SELECT document_id,document_kind,tenant_id,evidence_hash "
        "FROM public.contract_acceptances WHERE user_id=%s", (person,)
    ).fetchone()
    assert acceptance[:3]==(doc,"TENANT_MEMBERSHIP",tenant)
    assert len(acceptance[3])==64
    assert db.execute(
        "SELECT count(*) FROM public.invite_email_verification "
        "WHERE invitation_id=%s AND consumed_at IS NOT NULL", (inv,)
    ).fetchone()[0]==1
    with pytest.raises(LifecycleDenied):
        attempt(consent=True, accepted_document_sha256=digest)
    assert db.execute(
        "SELECT count(*) FROM public.contract_acceptances WHERE user_id=%s",
        (person,),
    ).fetchone()[0]==1


def test_new_invited_identity_never_runs_outside_ci(monkeypatch, synthetic_accounts):
    from app.invite_registration_ci import register_new_invited_identity_ci
    db, users, tenant=synthetic_accounts
    monkeypatch.delenv("FRCAIXINHA_CI_ISOLATED")
    with pytest.raises(LifecycleDenied):
        register_new_invited_identity_ci(
            db,verification_token="synthetic",name="Membro sintético",
            cpf="12345678909",phone="11999990000",password="SomenteTeste-2026!",
            document_id=uuid4(),consent=True,
            accepted_document_sha256="a"*64,
        )


def test_public_invitation_endpoint_keeps_production_disabled():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    router=(root/"app/routers/invitations.py").read_text()
    registration=(root/"app/invite_registration_ci.py").read_text()
    assert 'status.HTTP_503_SERVICE_UNAVAILABLE' in router
    assert "Convites ainda não implementados" in router
    assert "register_new_invited_identity_ci" not in router
    assert "consent is not True" in registration
    assert "expected[0] != document_id" in registration
