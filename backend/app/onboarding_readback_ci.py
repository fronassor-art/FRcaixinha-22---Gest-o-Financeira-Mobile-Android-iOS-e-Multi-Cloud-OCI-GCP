"""M41430 readback in the existing disposable CI only.
Text is resolved from a fixed synthetic fixture, NEVER from client paths or URLs.
The canonical legal document store is not implemented by this module.
"""
from hashlib import sha256
from .cycle_identity_registration_ci import _guard,_policy
from .admin_license_onboarding_ci import _session
from .account_lifecycle import LifecycleDenied
from .security import hash_token
from .saas_billing_ci import _cents

TEXTS={
 "CI_M41430_A":"INSTRUMENTO SINTÉTICO A — somente CI. Assinatura de software; preço mensal e anual independentes. Sem contratação jurídica ou pagamento real.",
 "CI_M41430_B":"INSTRUMENTO SINTÉTICO B — somente CI. Política, calendário, cotas e aceite do ciclo vinculados ao convite. Sem adesão jurídica ou operação real.",
}

def _document(conn,doc,kind):
    row=conn.execute("SELECT version_label,sha256,source_reference FROM public.contract_documents "
                     "WHERE id=%s AND document_kind=%s AND published_at IS NOT NULL",(doc,kind)).fetchone()
    text=TEXTS.get(row[2]) if row else None
    if not text or sha256(text.encode("utf-8")).hexdigest()!=row[1]:
        raise LifecycleDenied("Texto integral não comprovado.")
    return dict(document_id=doc,kind=kind,version=row[0],document_hash=row[1],text=text,ci_only=True)

def master_document_ci(conn,token,doc):
    _guard(conn)
    with conn.transaction():
        actor,_=_session(conn,token,"MASTER")
        return dict(user_id=actor,tenant_id=None,role="MASTER",document=_document(conn,doc,"PLATFORM_LICENSE"))

def admin_document_ci(conn,token,tenant,doc):
    _guard(conn)
    with conn.transaction():
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant)
        conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
        return dict(user_id=actor,tenant_id=tenant,role="TENANT_ADMIN",document=_document(conn,doc,"TENANT_MEMBERSHIP"))

def invitation_terms_ci(conn,invitation_token,verification_token):
    _guard(conn)
    if invitation_token==verification_token:
        raise LifecycleDenied("Provas incompatíveis.")
    with conn.transaction():
        row=conn.execute(
            "SELECT i.id,i.target_role,i.tenant_id,i.inviter_user_id,i.required_document_id,"
            "a.document_hash,a.document_id,m.cycle_id,m.policy_hash,m.joined,m.quotas,m.document_id "
            "FROM public.invitations i JOIN public.invite_email_verification v ON v.invitation_id=i.id "
            "LEFT JOIN public.fr_v23_admin_invite_bindings a ON a.invitation_id=i.id "
            "LEFT JOIN public.fr_v23_identity_invite_bindings m ON m.invitation_id=i.id AND m.tenant_id=i.tenant_id "
            "WHERE i.token_hash=%s AND v.token_hash=%s AND i.accepted_at IS NULL AND i.revoked_at IS NULL "
            "AND i.expires_at>clock_timestamp() AND i.delivery_status='DELIVERED' "
            "AND v.consumed_at IS NULL AND v.revoked_at IS NULL AND v.expires_at>clock_timestamp() "
            "AND lower(v.recipient_email)=lower(i.target_email) AND i.target_email LIKE '%%@example.invalid' "
            "FOR SHARE OF i,v",(hash_token(invitation_token),hash_token(verification_token))).fetchone()
        if not row:
            raise LifecycleDenied("Convite indisponível.")
        inv,role,tenant,actor,doc,ah,ad,cycle,policy,joined,quotas,md=row
        if role=="TENANT_ADMIN" and tenant is None and ad==doc and cycle is None:
            document=_document(conn,doc,"PLATFORM_LICENSE")
            if document["document_hash"]!=ah:
                raise LifecycleDenied("Documento incompatível.")
            terms=None
        elif role=="TENANT_MEMBER" and tenant is not None and md==doc and ad is None:
            document=_document(conn,doc,"TENANT_MEMBERSHIP")
            if _policy(conn,tenant,cycle,actor,joined,quotas)[0:2]!=(doc,policy):
                raise LifecycleDenied("Política incompatível.")
            terms=dict(cycle=cycle,policy_hash=policy,joined=joined,quotas=quotas)
        else:
            raise LifecycleDenied("Convite incompatível.")
        return dict(invitation_id=inv,role=role,document=document,terms=terms)

def offers_ci(conn,token,tenant):
    _guard(conn)
    with conn.transaction():
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant,draft=True)
        if not conn.execute("SELECT 1 FROM public.tenants WHERE id=%s AND status='RASCUNHO_INATIVO'",(tenant,)).fetchone():
            raise LifecycleDenied("Contratação inicial encerrada.")
        bound=conn.execute("SELECT a.id FROM public.invitations i JOIN public.fr_v23_admin_invite_bindings b ON b.invitation_id=i.id "
                           "JOIN public.contract_acceptances a ON a.document_id=b.document_id AND a.user_id=i.accepted_user_id "
                           "AND a.document_kind='PLATFORM_LICENSE' AND a.tenant_id IS NULL "
                           "WHERE i.tenant_id=%s AND i.accepted_user_id=%s AND i.accepted_at IS NOT NULL",(tenant,actor)).fetchone()
        if not bound:
            raise LifecycleDenied("Aceite A indisponível.")
        saved=conn.execute("SELECT 1 FROM public.saas_subscription_preparations WHERE tenant_id=%s AND admin_user_id=%s AND contract_acceptance_id=%s",
                           (tenant,actor,bound[0])).fetchone()
        rows=[] if saved else conn.execute(
            "SELECT DISTINCT ON (p.tier) v.id,p.tier,p.members_limit,p.quotas_limit,v.monthly_price,v.annual_price "
            "FROM public.platform_license_plans p JOIN public.platform_license_price_versions v ON v.plan_tier=p.tier "
            "WHERE p.status='ACTIVE' AND p.tier IN ('ESSENCIAL','INTERMEDIARIO') "
            "ORDER BY p.tier,v.created_at DESC,v.id DESC").fetchall()
        return dict(user_id=actor,tenant_id=tenant,role="TENANT_ADMIN",ci_only=True,
                    offers=[dict(price_version=x[0],tier=x[1],members_limit=x[2],quotas_limit=x[3],
                                 monthly_cents=_cents(x[4]),annual_cents=_cents(x[5])) for x in rows])

def checkout_status_ci(conn,token,tenant,intent):
    _guard(conn)
    with conn.transaction():
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant,draft=True)
        row=conn.execute("SELECT p.id,p.status,p.expected_amount_cents,s.billing_period,e.id,t.status "
                         "FROM public.saas_payment_intents p JOIN public.saas_subscription_preparations s ON s.id=p.preparation_id "
                         "JOIN public.tenants t ON t.id=p.tenant_id AND t.admin_user_id=p.admin_user_id "
                         "LEFT JOIN public.saas_license_entitlements e ON e.payment_intent_id=p.id AND e.tenant_id=t.id "
                         "WHERE p.id=%s AND p.tenant_id=%s AND p.admin_user_id=%s AND p.live_mode=false "
                         "AND s.tenant_id=p.tenant_id AND s.admin_user_id=p.admin_user_id AND s.price_version_id=p.price_version_id",
                         (intent,tenant,actor)).fetchone()
        if not row:
            raise LifecycleDenied("Pagamento indisponível.")
        if row[1]=="APPROVED" and row[4] and row[5]=="ATIVO":
            conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
            state="CI_RECONCILED"
        elif row[1]=="PENDING" and row[4] is None and row[5]=="RASCUNHO_INATIVO":
            state="PENDING"
        else:
            raise LifecycleDenied("Estado de pagamento incompatível.")
        return dict(user_id=actor,tenant_id=tenant,role="TENANT_ADMIN",intent_id=intent,state=state,
                    cents=row[2],period=row[3],ci_only=True,real_payment_authorized=False)
