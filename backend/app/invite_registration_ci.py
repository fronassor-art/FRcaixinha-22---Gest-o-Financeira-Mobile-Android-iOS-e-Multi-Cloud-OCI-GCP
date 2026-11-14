"""Cadastro por convite com identidade única — somente laboratório CI.

Token recebido pelo e-mail + contrato na versão correta + identidade e CPF
válido. O Master nunca é criado por convite. Nenhuma rota pública usa
este módulo sem revisão jurídica, e-mail validado e serviço segregado.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID, uuid4
import re
import secrets

from .account_lifecycle import _ci_only, LifecycleDenied
from .invite_challenge_guard_ci import check_challenge_budget, ChallengeGuardError
from .security import hash_password_secure, hash_token


def _valid_cpf(value: str) -> bool:
    if not re.fullmatch(r"[0-9]{11}",value) or len(set(value))==1:
        return False
    digits=[int(x) for x in value]
    for length in (9,10):
        remainder=(sum(digits[i]*(length+1-i) for i in range(length))*10)%11
        if remainder==10: remainder=0
        if digits[length]!=remainder:
            return False
    return True


def prepare_invite_email_verification_ci(conn, *, invitation_id: UUID) -> str:
    """Gera segundo token independente; NÃO marca a entrega como real."""
    _ci_only(conn)
    with conn.transaction():
        inv=conn.execute(
            "SELECT target_email,expires_at,revoked_at,accepted_at,delivery_status "
            "FROM public.invitations WHERE id=%s FOR UPDATE", (invitation_id,),
        ).fetchone()
        now=datetime.now(timezone.utc)
        if (not inv or inv[1]<=now or inv[2] or inv[3]
                or inv[4]!='DELIVERED'):
            raise LifecycleDenied("Convite indisponível para verificação do e-mail.")
        # The locked invitation serializes issuers. Historical challenges
        # count even if revoked or consumed. Refusal must not revoke the
        # currently active challenge.
        history=conn.execute(
            "SELECT count(*)::int,max(created_at) "
            "FROM public.invite_email_verification WHERE invitation_id=%s",
            (invitation_id,),
        ).fetchone()
        try:
            check_challenge_budget(
                issued_count=history[0] if history else -1,
                last_created_at=history[1] if history else None,
                now=now,
            )
        except ChallengeGuardError as exc:
            raise LifecycleDenied("Verificação indisponível para nova emissão.") from exc
        conn.execute(
            "UPDATE public.invite_email_verification SET revoked_at=now() "
            "WHERE invitation_id=%s AND consumed_at IS NULL AND revoked_at IS NULL",
            (invitation_id,),
        )
        token=secrets.token_urlsafe(36)
        conn.execute(
            "INSERT INTO public.invite_email_verification"
            "(invitation_id,recipient_email,token_hash,expires_at)"
            "VALUES(%s,%s,%s,%s)",
            (invitation_id,inv[0].casefold(),hash_token(token),
             min(inv[1],datetime.now(timezone.utc)+timedelta(minutes=30))),
        )
        return token


def register_new_invited_identity_ci(
    conn, *, verification_token: str, name: str, cpf: str, phone: str,
    password: str, document_id: UUID,
    consent: bool = False, accepted_document_sha256: str | None = None,
) -> UUID:
    """Cria SOMENTE membro/admin convidado, com aceite documental atômico.

    Respeita o convite existente e entregue, titularidade do link, CPF único,
    versão do documento e autorização atual do convidante.
    """
    _ci_only(conn)
    # A verification link is not affirmative agreement to contract terms.
    # No password hashing or database mutation occurs without a fresh,
    # explicit yes and a hash identifying the exact document displayed.
    if (consent is not True or type(accepted_document_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", accepted_document_sha256) is None):
        raise LifecycleDenied("Aceite expresso da versão contratual obrigatório.")
    if (not 3<=len(name.strip())<=255 or not _valid_cpf(cpf)
            or not re.fullmatch(r"[0-9+() -]{8,20}",phone)
            or len(password)<12):
        raise LifecycleDenied("Dados de cadastro ou senha inválidos.")
    pwd_hash=hash_password_secure(password)
    with conn.transaction():
        rec=conn.execute(
            "SELECT v.id,v.invitation_id,v.recipient_email,v.expires_at,"
            "v.consumed_at,v.revoked_at,"
            "i.tenant_id,i.inviter_user_id,i.target_role,i.target_email,"
            "i.expires_at,i.accepted_at,i.revoked_at,i.delivery_status "
            "FROM public.invite_email_verification v JOIN public.invitations i "
            "ON i.id=v.invitation_id WHERE v.token_hash=%s FOR UPDATE OF v,i",
            (hash_token(verification_token),),
        ).fetchone()
        now=datetime.now(timezone.utc)
        if (not rec or rec[3]<=now or rec[4] or rec[5] or rec[10]<=now
                or rec[11] or rec[12] or rec[13]!='DELIVERED'
                or rec[2].casefold()!=rec[9].casefold()):
            raise LifecycleDenied("Convite inválido, expirado ou já utilizado.")
        if rec[6] is None:
            raise LifecycleDenied("Convite de administrador preliminar requer criação segura do tenant.")
        if not conn.execute(
            "SELECT 1 FROM public.tenants WHERE id=%s AND status='ATIVO'",(rec[6],),
        ).fetchone():
            raise LifecycleDenied("Caixinha ainda não está ativa.")
        if rec[8]=='TENANT_MEMBER':
            inviter_ok=conn.execute(
                "SELECT 1 FROM public.memberships WHERE tenant_id=%s AND user_id=%s "
                "AND role='TENANT_ADMIN' AND status='ATIVA'",(rec[6],rec[7]),
            ).fetchone()
        elif rec[8]=='TENANT_ADMIN':
            inviter_ok=conn.execute(
                "SELECT 1 FROM public.users WHERE id=%s AND is_master AND status='ACTIVE'",
                (rec[7],),
            ).fetchone()
        else:
            inviter_ok=None
        if not inviter_ok:
            raise LifecycleDenied("Convite perdeu a autorização do remetente.")
        if conn.execute(
            "SELECT 1 FROM public.users WHERE lower(email)=lower(%s) OR cpf=%s",
            (rec[2],cpf),
        ).fetchone():
            raise LifecycleDenied("Identidade já cadastrada. Use o fluxo de vínculo existente.")
        doc=conn.execute(
            "SELECT sha256 FROM public.contract_documents "
            "WHERE id=%s AND document_kind='TENANT_MEMBERSHIP' AND published_at IS NOT NULL",
            (document_id,),
        ).fetchone()
        if not doc or doc[0] != accepted_document_sha256:
            raise LifecycleDenied("Versão de contrato não publicada ou incompatível.")
        expected=conn.execute(
            "SELECT required_document_id FROM public.invitations WHERE id=%s",
            (rec[1],),
        ).fetchone()
        if not expected or expected[0] != document_id:
            raise LifecycleDenied("Versão contratual não vinculada ao convite.")
        person=uuid4()
        membership=uuid4()
        evidence=sha256((str(person)+str(document_id)+accepted_document_sha256+
                         secrets.token_hex(32)).encode()).hexdigest()
        conn.execute(
            "INSERT INTO public.users"
            "(id,email,full_name,cpf,phone,status,is_master,email_verified_at)"
            "VALUES(%s,%s,%s,%s,%s,'ACTIVE',false,now())",
            (person,rec[2],name.strip(),cpf,phone),
        )
        conn.execute(
            "INSERT INTO public.credentials(user_id,password_hash,algorithm)"
            "VALUES(%s,%s,%s)",
            (person,pwd_hash,'argon2id' if pwd_hash.startswith('$argon2id$') else 'bcrypt'),
        )
        acceptance=uuid4()
        conn.execute(
            "INSERT INTO public.contract_acceptances"
            "(id,document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method)"
            "VALUES(%s,%s,'TENANT_MEMBERSHIP',%s,%s,%s,'CI_VERIFIED_IDENTITY')",
            (acceptance,document_id,person,rec[6],evidence),
        )
        conn.execute(
            "INSERT INTO public.memberships(id,tenant_id,user_id,role,status)"
            "VALUES(%s,%s,%s,%s,'ATIVA')",(membership,rec[6],person,rec[8]),
        )
        conn.execute(
            "UPDATE public.invite_email_verification SET consumed_at=now() WHERE id=%s",(rec[0],),
        )
        conn.execute(
            "UPDATE public.invitations "
            "SET accepted_at=now(),accepted_user_id=%s,accepted_membership_id=%s WHERE id=%s",
            (person,membership,rec[1]),
        )
        conn.execute(
            "INSERT INTO public.audit_events"
            "(actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,%s,%s,'CI_INVITED_IDENTITY_REGISTERED','USER',%s,%s,%s)",
            (person,rec[8],rec[6],str(person),
             "Cadastro CI após confirmação afirmativa da versão e posse sintética do link",str(acceptance)),
        )
        return person
