"""M41400: compose existing identity registration and V2.3 consent in disposable PG18.
Never wired to public HTTP, provider delivery, or the authoritative database.
"""
from datetime import date, datetime, timezone
from uuid import UUID
import os
import re

from .account_lifecycle import _ci_only, _email, LifecycleDenied, prepare_invitation_ci
from .invite_registration_ci import register_new_invited_identity_ci
from .security import hash_token


def _guard(conn):
    flags = {"GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
             "PIX_REAL":"OFF","PAGAMENTOS_REAIS":"OFF","ATIVACAO_REAL":"OFF"}
    if any(os.getenv(k)!=v for k,v in flags.items()):
        raise LifecycleDenied("M41400: somente CI isolado.")
    _ci_only(conn)
    if not conn.execute("SELECT current_setting('server_version_num')::int BETWEEN 180000 AND 189999").fetchone()[0]:
        raise LifecycleDenied("M41400: PG18 obrigatório.")


def _policy(conn, tenant, cycle, actor, joined, quotas):
    row=conn.execute(
        "SELECT p.document_id,p.policy_hash,p.quota_cents,d.sha256 "
        "FROM public.fr_v23_policy p JOIN public.cycles c ON c.id=p.cycle_id AND c.tenant_id=p.tenant_id "
        "JOIN public.tenants t ON t.id=p.tenant_id JOIN public.users u ON u.id=t.admin_user_id "
        "JOIN public.memberships m ON m.tenant_id=t.id AND m.user_id=u.id "
        "JOIN public.contract_documents d ON d.id=p.document_id "
        "WHERE p.tenant_id=%s AND p.cycle_id=%s AND t.admin_user_id=%s "
        "AND t.status='ATIVO' AND u.status='ACTIVE' AND m.role='TENANT_ADMIN' AND m.status='ATIVA' "
        "AND c.status='ABERTO' AND %s BETWEEN c.start_date AND p.last_due "
        "AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL "
        "FOR SHARE OF c,t,u,m,d",(tenant,cycle,actor,joined)).fetchone()
    if not row or type(quotas) is not int or not 1<=quotas<=400 or quotas*row[2]>100000000:
        raise LifecycleDenied("Política ou escopo incompatível.")
    conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
    return row


def stage_cycle_identity_invite_ci(conn, *, admin_token: str, tenant: UUID, cycle: UUID,
                                  email: str, joined: date, quotas: int,
                                  previous_id: UUID | None = None):
    """Existing 24h laboratory invitation, fresh token, explicit predecessor for reissue."""
    _guard(conn)
    email=_email(email)
    if not email.endswith("@example.invalid") or type(joined) is not date:
        raise LifecycleDenied("Somente identidade sintética e data civil.")
    with conn.transaction():
        actor=conn.execute("SELECT public.fr_v23_actor(%s,%s,true)",(admin_token,tenant)).fetchone()[0]
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),))
        doc,policy_hash,_,_=_policy(conn,tenant,cycle,actor,joined,quotas)
        if conn.execute("SELECT 1 FROM public.users WHERE lower(email)=%s",(email,)).fetchone():
            raise LifecycleDenied("Identidade existente: usar vínculo autenticado.")
        prior=conn.execute(
            "SELECT i.id,i.accepted_at,i.revoked_at,i.expires_at,b.cycle_id "
            "FROM public.invitations i JOIN public.fr_v23_identity_invite_bindings b ON b.invitation_id=i.id "
            "WHERE b.tenant_id=%s AND lower(i.target_email)=%s "
            "ORDER BY b.created_at DESC,i.id DESC LIMIT 1 FOR UPDATE OF i",(tenant,email)).fetchone()
        if prior:
            if (previous_id!=prior[0] or prior[1] is not None or prior[4]!=cycle
                or (prior[2] is None and prior[3]>datetime.now(timezone.utc))):
                raise LifecycleDenied("Convite anterior não elegível para reemissão.")
            # Expiration alone is insufficient for an old proof to remain active.
            conn.execute("UPDATE public.invitations SET revoked_at=coalesce(revoked_at,now()) WHERE id=%s",(prior[0],))
            conn.execute("UPDATE public.invite_email_verification SET revoked_at=now() "
                         "WHERE invitation_id=%s AND consumed_at IS NULL AND revoked_at IS NULL",(prior[0],))
        elif previous_id is not None:
            raise LifecycleDenied("Predecessor incompatível.")
        invitation,raw=prepare_invitation_ci(conn,tenant_id=tenant,inviter_id=actor,
            recipient_email=email,target_role="TENANT_MEMBER",required_document_id=doc)
        conn.execute("INSERT INTO public.fr_v23_identity_invite_bindings "
                     "(invitation_id,tenant_id,cycle_id,document_id,policy_hash,joined,quotas,previous_id) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                     (invitation,tenant,cycle,doc,policy_hash,joined,quotas,previous_id))
        return invitation,raw


def register_cycle_identity_ci(conn, *, invitation_token: str, verification_token: str,
                               cycle: UUID, policy_hash: str, document_id: UUID,
                               document_hash: str, joined: date, quotas: int,
                               accepted: bool, name: str, cpf: str, phone: str, password: str):
    """Both proofs, exact document and policy; registration + consent commit together.
    No session is issued here; admission and capacity enforcement remain separate.
    """
    _guard(conn)
    if (accepted is not True or type(joined) is not date or type(quotas) is not int
        or type(policy_hash) is not str or re.fullmatch(r"[0-9a-f]{64}",policy_hash) is None
        or type(document_hash) is not str or re.fullmatch(r"[0-9a-f]{64}",document_hash) is None
        or any(type(x) is not str or not 32<=len(x)<=512 for x in (invitation_token,verification_token))
        or invitation_token==verification_token):
        raise LifecycleDenied("Provas ou consentimento inválidos.")
    with conn.transaction():
        identity=conn.execute("SELECT tenant_id FROM public.invitations WHERE token_hash=%s",
                              (hash_token(invitation_token),)).fetchone()
        if not identity or identity[0] is None:
            raise LifecycleDenied("Convite indisponível.")
        tenant=identity[0]
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),))
        row=conn.execute(
            "SELECT i.id,i.inviter_user_id,i.expires_at,b.cycle_id,b.document_id,b.policy_hash,b.joined,b.quotas "
            "FROM public.invitations i JOIN public.fr_v23_identity_invite_bindings b ON b.invitation_id=i.id "
            "JOIN public.invite_email_verification v ON v.invitation_id=i.id "
            "WHERE i.token_hash=%s AND v.token_hash=%s AND i.tenant_id=b.tenant_id AND i.tenant_id=%s "
            "AND i.target_role='TENANT_MEMBER' AND i.required_document_id=b.document_id "
            "AND i.accepted_at IS NULL AND i.revoked_at IS NULL AND i.expires_at>clock_timestamp() "
            "AND i.delivery_status='DELIVERED' AND v.consumed_at IS NULL AND v.revoked_at IS NULL "
            "AND v.expires_at>clock_timestamp() AND lower(v.recipient_email)=lower(i.target_email) "
            "FOR UPDATE OF i,v",
            (hash_token(invitation_token),hash_token(verification_token),tenant)).fetchone()
        if not row or tuple(row[3:])!=(cycle,document_id,policy_hash,joined,quotas):
            raise LifecycleDenied("Convite ou termos incompatíveis.")
        doc,digest,_,sha=_policy(conn,tenant,cycle,row[1],joined,quotas)
        if (doc,digest,sha)!=(document_id,policy_hash,document_hash):
            raise LifecycleDenied("Versão contratual incompatível.")
        # Creating an active identity consumes a seat, even before financial admission.
        seat_limit=conn.execute("SELECT members_limit FROM public.fr_v23_license(%s,%s)",(tenant,row[1])).fetchone()[0]
        seats=conn.execute(
            "SELECT count(*) FROM (SELECT m.id FROM public.memberships m WHERE m.tenant_id=%s "
            "AND m.role='TENANT_MEMBER' AND m.status='ATIVA' UNION "
            "SELECT a.membership_id FROM public.fr_v23_admission a JOIN public.cycles c ON c.id=a.cycle_id "
            "WHERE c.tenant_id=%s AND c.status<>'LIQUIDADO') used",(tenant,tenant)).fetchone()[0]
        if seats>=seat_limit:
            raise LifecycleDenied("Capacidade de identidade indisponível.")
        person=register_new_invited_identity_ci(conn,verification_token=verification_token,
            name=name,cpf=cpf,phone=phone,password=password,document_id=document_id,
            consent=True,accepted_document_sha256=document_hash)
        member,acc=conn.execute(
            "SELECT m.id,a.id FROM public.memberships m JOIN public.contract_acceptances a "
            "ON a.user_id=m.user_id AND a.tenant_id=m.tenant_id "
            "WHERE m.user_id=%s AND m.tenant_id=%s AND m.role='TENANT_MEMBER' "
            "AND m.status='ATIVA' AND m.joined_at<=%s AND a.document_id=%s",
            (person,tenant,joined,document_id)).fetchone() or (None,None)
        if not member or not acc:
            raise LifecycleDenied("Vínculo ou ingresso incompatível.")
        conn.execute("INSERT INTO public.fr_v23_cycle_invites "
                     "(tenant_id,cycle_id,membership_id,actor,policy_hash,joined,quotas,expires_at) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                     (tenant,cycle,member,row[1],policy_hash,joined,quotas,row[2]))
        consent=conn.execute("INSERT INTO public.fr_v23_member_consent "
                     "(cycle_id,membership_id,acceptance_id,actor,policy_hash,joined,quotas) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                     (cycle,member,acc,person,policy_hash,joined,quotas)).fetchone()[0]
        # Force the deferred fence while still inside the outer atomic operation.
        conn.execute("SET CONSTRAINTS fr_v23_identity_binding_acceptance IMMEDIATE")
        conn.execute("SET CONSTRAINTS fr_v23_identity_binding_acceptance DEFERRED")
        return person,member,consent
