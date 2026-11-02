"""Ciclo de vida de conta do AI Studio — laboratório CI ISOLADO.

NÃO é API pública. Os fluxos precisam de verificação de e-mail, autorização,
entrega confiável, políticas de rate-limit distribuídas e revisão antes de
qualquer exposição. Nenhum banco do Termux pode ser usado por estas funções.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import os
import secrets

from .security import hash_password_secure, hash_token


class LifecycleDenied(ValueError):
    """Operação de laboratório rejeitada, sem revelar identidade do destinatário."""


def _ci_only(conn) -> None:
    if (os.getenv("FRCAIXINHA_CI_ISOLATED") != "1"
            or os.getenv("ENVIRONMENT", "development") == "production"):
        raise LifecycleDenied("Ciclo de vida disponível apenas no PostgreSQL descartável de CI.")
    identity = conn.execute(
        "SELECT current_database(),current_user,inet_server_port()"
    ).fetchone()
    if identity != ("frcaixinha_ci", "postgres", 5432):
        raise LifecycleDenied("Banco diferente do PostgreSQL descartável autorizado.")


def _email(value: str) -> str:
    result = value.strip().casefold()
    if len(result) > 255 or len(result) < 6 or result.count("@") != 1:
        raise LifecycleDenied("Endereço de convite inválido.")
    local, domain = result.split("@")
    if not local or not domain or "." not in domain:
        raise LifecycleDenied("Endereço de convite inválido.")
    return result


def prepare_invitation_ci(conn, *, tenant_id: UUID, inviter_id: UUID,
                          recipient_email: str, target_role: str) -> tuple[UUID, str]:
    """Token opaco de uso único; hash apenas no PostgreSQL; nenhuma entrega."""
    _ci_only(conn)
    if target_role not in ("TENANT_ADMIN", "TENANT_MEMBER"):
        raise LifecycleDenied("Papel de convite não autorizado.")
    email = _email(recipient_email)
    raw = secrets.token_urlsafe(32)
    invitation_id = uuid4()
    with conn.transaction():
        tenant = conn.execute(
            "SELECT status FROM public.tenants WHERE id=%s FOR SHARE", (tenant_id,)
        ).fetchone()
        inviter = conn.execute(
            "SELECT status,is_master FROM public.users WHERE id=%s", (inviter_id,)
        ).fetchone()
        if not tenant or tenant[0] != "ATIVO" or not inviter or inviter[0] != "ACTIVE":
            raise LifecycleDenied("Caixinha ou responsável indisponível.")
        if target_role == "TENANT_ADMIN":
            if not inviter[1]:
                raise LifecycleDenied("Só o Master pode convidar administradores.")
        else:
            active_admin = conn.execute(
                "SELECT 1 FROM public.memberships WHERE tenant_id=%s AND user_id=%s "
                "AND role='TENANT_ADMIN' AND status='ATIVA'",
                (tenant_id, inviter_id),
            ).fetchone()
            if not active_admin:
                raise LifecycleDenied("Somente administrador ativo pode convidar membro.")
        conn.execute(
            "INSERT INTO public.invitations(id,tenant_id,inviter_user_id,target_email,"
            "target_role,token_hash,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (invitation_id, tenant_id, inviter_id, email, target_role,
             hash_token(raw), datetime.now(timezone.utc) + timedelta(hours=24)),
        )
        conn.execute(
            "INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,"
            "action,object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,%s,%s,'CI_INVITATION_STAGED','INVITATION',%s,%s,'CI_NO_DELIVERY')",
            (inviter_id, "MASTER" if inviter[1] and target_role == "TENANT_ADMIN"
             else "TENANT_ADMIN", tenant_id, str(invitation_id),
             "Convite sintético preparado no CI; nenhum e-mail enviado"),
        )
    return invitation_id, raw


def simulate_invitation_delivery_ci(conn, invitation_id: UUID) -> bool:
    """Marcação apenas sintética; não equivale a confirmação de provedor."""
    _ci_only(conn)
    result = conn.execute(
        "UPDATE public.invitations SET delivery_status='DELIVERED', delivered_at=now() "
        "WHERE id=%s AND accepted_at IS NULL AND revoked_at IS NULL "
        "AND expires_at>now() AND delivery_status='PENDING_DELIVERY'",
        (invitation_id,),
    )
    return result.rowcount == 1


def revoke_invitation_ci(conn, invitation_id: UUID) -> bool:
    _ci_only(conn)
    result = conn.execute(
        "UPDATE public.invitations SET revoked_at=now() WHERE id=%s "
        "AND accepted_at IS NULL AND revoked_at IS NULL",
        (invitation_id,),
    )
    return result.rowcount == 1


def accept_existing_identity_ci(conn, *, token: str, user_id: UUID) -> UUID | None:
    """Aceita para conta EXISTENTE e verificada; sem autocadastro ou e-mail.

    Atualização, membership e auditoria em uma transação.
    """
    _ci_only(conn)
    with conn.transaction():
        invitation = conn.execute(
            "SELECT id,tenant_id,target_email,target_role,expires_at,"
            "accepted_at,revoked_at,delivery_status,inviter_user_id "
            "FROM public.invitations WHERE token_hash=%s FOR UPDATE",
            (hash_token(token),),
        ).fetchone()
        if (not invitation or invitation[5] or invitation[6]
                or invitation[4] <= datetime.now(timezone.utc)
                or invitation[7] != "DELIVERED"):
            return None
        user = conn.execute(
            "SELECT email,status FROM public.users WHERE id=%s FOR UPDATE",
            (user_id,),
        ).fetchone()
        if not user or user[1] != "ACTIVE" or user[0].casefold() != invitation[2]:
            return None
        tenant = conn.execute(
            "SELECT status FROM public.tenants WHERE id=%s", (invitation[1],)
        ).fetchone()
        if not tenant or tenant[0] != "ATIVO":
            return None
        if invitation[3] == "TENANT_MEMBER":
            inviter = conn.execute(
                "SELECT 1 FROM public.memberships WHERE tenant_id=%s AND user_id=%s "
                "AND role='TENANT_ADMIN' AND status='ATIVA'",
                (invitation[1], invitation[8]),
            ).fetchone()
            if not inviter:
                return None
        elif not conn.execute(
            "SELECT is_master FROM public.users WHERE id=%s AND status='ACTIVE'",
            (invitation[8],),
        ).fetchone()[0]:
            return None
        membership_id = uuid4()
        created = conn.execute(
            "INSERT INTO public.memberships(id,tenant_id,user_id,role) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT (tenant_id,user_id,role) "
            "DO NOTHING RETURNING id",
            (membership_id, invitation[1], user_id, invitation[3]),
        ).fetchone()
        if not created:
            return None
        conn.execute(
            "UPDATE public.invitations SET accepted_at=now(),accepted_user_id=%s,"
            "accepted_membership_id=%s WHERE id=%s",
            (user_id, membership_id, invitation[0]),
        )
        conn.execute(
            "INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,"
            "action,object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,%s,%s,'CI_INVITATION_ACCEPTED','MEMBERSHIP',%s,%s,%s)",
            (user_id, invitation[3], invitation[1], str(membership_id),
             "Aceite sintético de convite de uso único no CI", str(invitation[0])),
        )
        return membership_id


def prepare_password_reset_ci(conn, user_id: UUID) -> tuple[UUID, str]:
    """Somente preparativo de laboratório; não envia ou revela token em API."""
    _ci_only(conn)
    record = conn.execute(
        "SELECT status FROM public.users WHERE id=%s", (user_id,)
    ).fetchone()
    if not record or record[0] != "ACTIVE":
        raise LifecycleDenied("Conta indisponível.")
    raw = secrets.token_urlsafe(32)
    reset_id = uuid4()
    conn.execute(
        "INSERT INTO public.password_reset_tokens(id,user_id,token_hash,expires_at) "
        "VALUES(%s,%s,%s,%s)",
        (reset_id, user_id, hash_token(raw),
         datetime.now(timezone.utc) + timedelta(minutes=15)),
    )
    return reset_id, raw


def simulate_reset_delivery_ci(conn, reset_id: UUID) -> bool:
    _ci_only(conn)
    result = conn.execute(
        "UPDATE public.password_reset_tokens SET delivery_status='DELIVERED' "
        "WHERE id=%s AND consumed_at IS NULL AND revoked_at IS NULL "
        "AND expires_at>now() AND delivery_status='PENDING_DELIVERY'",
        (reset_id,),
    )
    return result.rowcount == 1


def reset_password_ci(conn, *, token: str, new_password: str) -> bool:
    """Uso único, hash Argon2, revogação de sessões e outros tokens, em transação."""
    _ci_only(conn)
    if len(new_password) < 12:
        raise LifecycleDenied("A senha de laboratório exige ao menos 12 caracteres.")
    new_hash = hash_password_secure(new_password)
    algorithm = "argon2id" if new_hash.startswith("$argon2id$") else "bcrypt"
    with conn.transaction():
        row = conn.execute(
            "SELECT id,user_id,expires_at,consumed_at,revoked_at,delivery_status "
            "FROM public.password_reset_tokens WHERE token_hash=%s FOR UPDATE",
            (hash_token(token),),
        ).fetchone()
        if (not row or row[3] or row[4] or row[2] <= datetime.now(timezone.utc)
                or row[5] != "DELIVERED"):
            return False
        active = conn.execute(
            "SELECT 1 FROM public.users WHERE id=%s AND status='ACTIVE'", (row[1],)
        ).fetchone()
        if not active:
            return False
        updated = conn.execute(
            "UPDATE public.credentials SET password_hash=%s,algorithm=%s,"
            "password_changed_at=now() WHERE user_id=%s",
            (new_hash, algorithm, row[1]),
        )
        if updated.rowcount != 1:
            raise LifecycleDenied("Credencial inexistente; atualização não concluída.")
        conn.execute(
            "UPDATE public.password_reset_tokens SET consumed_at=now() WHERE id=%s",
            (row[0],),
        )
        conn.execute(
            "UPDATE public.password_reset_tokens SET revoked_at=now() "
            "WHERE user_id=%s AND id<>%s AND consumed_at IS NULL AND revoked_at IS NULL",
            (row[1], row[0]),
        )
        conn.execute(
            "UPDATE public.sessions SET revoked_at=now() "
            "WHERE user_id=%s AND revoked_at IS NULL", (row[1],),
        )
        conn.execute(
            "INSERT INTO public.audit_events(actor_id,actor_role,action,"
            "object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,'SYSTEM','CI_PASSWORD_RESET','USER',%s,%s,'CI_NO_EMAIL')",
            (row[1], str(row[1]),
             "Redefinição sintética com sessões revogadas no CI"),
        )
    return True
