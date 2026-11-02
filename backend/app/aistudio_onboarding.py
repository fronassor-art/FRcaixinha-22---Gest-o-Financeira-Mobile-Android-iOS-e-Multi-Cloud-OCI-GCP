"""Provisionamento local de homologacao: identidade unica, tenant, Admin e Membro.

NAO eh cadastro publico, entrega de convite ou verificacao de titularidade de e-mail.
Apenas cluster AI Studio do Termux ou PostgreSQL descartavel isolado do CI.
O Master autoriza com a propria senha; o operador usa credencial SQL local.
"""
import os
import re
from uuid import uuid4

from .security import hash_password_secure, verify_password_secure


class OnboardingDenied(ValueError):
    """Recusa segura: transacao sera revertida integralmente."""


LOCAL_IDENTITY = (
    "frc_ai_owner", "frcaixinha_aistudio_dev", 5433,
    "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18",
)
CI_IDENTITY = ("postgres", "frcaixinha_ci", 5432)


def _guard_database(conn):
    if not conn.autocommit:
        raise OnboardingDenied("Conexao exige autocommit e transacao explicita")
    ident = conn.execute(
        "SELECT current_user,current_database(),inet_server_port(),"
        "current_setting('data_directory')"
    ).fetchone()
    if ident == LOCAL_IDENTITY:
        if (os.getenv("AI_STUDIO_ALLOW_ROLE_ONBOARDING") != "YES"
                or os.getenv("ENVIRONMENT", "homologation") == "production"):
            raise OnboardingDenied("Provisionamento local nao autorizado")
    elif ident[:3] == CI_IDENTITY and os.getenv("FRCAIXINHA_CI_ISOLATED") == "1":
        pass
    else:
        raise OnboardingDenied("Banco/role nao pertencem ao AI Studio autorizado")


def _email(value):
    normalized = str(value).strip().lower()
    if len(normalized) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise OnboardingDenied("E-mail invalido")
    return normalized


def _account(conn, details):
    """Nunca faz update em usuarios existentes; exige prova da senha original."""
    mode = details.get("mode")
    email = _email(details.get("email", ""))
    if mode == "existing":
        row = conn.execute(
            "SELECT u.id,u.status,c.password_hash "
            "FROM public.users u JOIN public.credentials c ON c.user_id=u.id "
            "WHERE lower(u.email)=%s FOR UPDATE OF u",
            (email,),
        ).fetchone()
        if (row is None or row[1] != "ACTIVE"
                or not verify_password_secure(details.get("password", ""), row[2])):
            raise OnboardingDenied("Identidade existente nao comprovada")
        return row[0]

    if mode != "new":
        raise OnboardingDenied("Modo de conta invalido")
    name = " ".join(str(details.get("full_name", "")).strip().split())
    cpf = re.sub(r"\D", "", str(details.get("cpf", "")))
    phone = re.sub(r"\D", "", str(details.get("phone", "")))
    password = details.get("password", "")
    if (not name or len(name) > 255 or any(c in name for c in "[]{}<>")
            or any(ord(c) < 32 for c in name)):
        raise OnboardingDenied("Nome invalido ou com caracteres indevidos")
    if len(cpf) != 11 or not 10 <= len(phone) <= 13:
        raise OnboardingDenied("CPF ou telefone com formato invalido")
    if not isinstance(password, str) or len(password) < 12:
        raise OnboardingDenied("Senha deve conter ao menos 12 caracteres")
    # Evita duplicidade mesmo se conta anterior gravou CPF com pontuacao.
    found = conn.execute(
        "SELECT 1 FROM public.users WHERE lower(email)=%s "
        "OR regexp_replace(cpf,'[^0-9]','','g')=%s",
        (email, cpf),
    ).fetchone()
    if found:
        raise OnboardingDenied("E-mail ou CPF ja cadastrado; use modo existente")
    digest = hash_password_secure(password)
    user_id = uuid4()
    conn.execute(
        "INSERT INTO public.users(id,email,full_name,cpf,phone,status,is_master) "
        "VALUES(%s,%s,%s,%s,%s,'ACTIVE',FALSE)",
        (user_id, email, name, cpf, phone),
    )
    conn.execute(
        "INSERT INTO public.credentials(user_id,password_hash,algorithm) "
        "VALUES(%s,%s,%s)",
        (user_id, digest, "argon2id" if digest.startswith("$argon2id$") else "bcrypt"),
    )
    return user_id


def onboard_tenant_with_roles(conn, *, master_email, master_password,
                             tenant_name, contracting_party_id, admin, member):
    """Tudo ou nada: valida Master, vincula identidades e registra auditoria."""
    _guard_database(conn)
    tenant_name = " ".join(str(tenant_name).split())
    party = str(contracting_party_id).strip()
    if (not 3 <= len(tenant_name) <= 255
            or any(ord(c) < 32 for c in tenant_name)
            or not 5 <= len(party) <= 100
            or any(ord(c) < 32 for c in party)):
        raise OnboardingDenied("Identificacao da caixinha/contratante invalida")

    with conn.transaction():
        # Compartilha o mesmo lock transacional com bootstrap de Master.
        conn.execute("SELECT pg_advisory_xact_lock(706719221346)")
        if conn.execute(
            "SELECT count(*) FROM public.users WHERE is_master=TRUE"
        ).fetchone()[0] != 1:
            raise OnboardingDenied("Exige exatamente um Master cadastrado")
        actor = conn.execute(
            "SELECT u.id,u.status,c.password_hash FROM public.users u "
            "JOIN public.credentials c ON c.user_id=u.id "
            "WHERE u.is_master=TRUE AND lower(u.email)=%s FOR UPDATE OF u",
            (_email(master_email),),
        ).fetchone()
        if (actor is None or actor[1] != "ACTIVE"
                or not verify_password_secure(master_password, actor[2])):
            raise OnboardingDenied("Autorizacao do Master recusada")
        actor_id = actor[0]
        admin_id = _account(conn, admin)
        member_id = _account(conn, member)

        tenant_id = uuid4()
        conn.execute(
            "INSERT INTO public.tenants(id,display_name,contracting_party_id,"
            "admin_user_id,status,is_owner_box) "
            "VALUES(%s,%s,%s,%s,'ATIVO',FALSE)",
            (tenant_id, tenant_name, party, admin_id),
        )
        members = []
        for user_id, role in ((admin_id, "TENANT_ADMIN"),
                              (member_id, "TENANT_MEMBER")):
            membership_id = uuid4()
            conn.execute(
                "INSERT INTO public.memberships(id,tenant_id,user_id,role,status) "
                "VALUES(%s,%s,%s,%s,'ATIVA')",
                (membership_id, tenant_id, user_id, role),
            )
            conn.execute(
                "INSERT INTO public.audit_events"
                "(actor_id,actor_role,tenant_id,action,object_type,object_id,"
                "reason,evidence_ref) "
                "VALUES(%s,'MASTER',%s,'AI_STUDIO_LOCAL_ROLE_ENROLLED',"
                "'MEMBERSHIP',%s,%s,'LOCAL_HOMOLOGATION_OPERATOR_APPROVED')",
                (actor_id, tenant_id, str(membership_id),
                 "Vinculo local de homologacao " + role),
            )
            members.append(membership_id)
        conn.execute(
            "INSERT INTO public.audit_events"
            "(actor_id,actor_role,tenant_id,action,object_type,object_id,"
            "reason,evidence_ref) "
            "VALUES(%s,'MASTER',%s,'AI_STUDIO_LOCAL_TENANT_CREATED',"
            "'TENANT',%s,%s,'LOCAL_HOMOLOGATION_OPERATOR_APPROVED')",
            (actor_id, tenant_id, str(tenant_id),
             "Caixinha criada para homologar 3 perfis com Master"),
        )
    return {"tenant_id": tenant_id, "admin_id": admin_id,
            "member_id": member_id, "admin_membership_id": members[0],
            "member_membership_id": members[1]}
