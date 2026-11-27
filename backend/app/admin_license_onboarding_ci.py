"""M41410 preliminary administrator and initial SaaS checkout; disposable CI only."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4
import re
import secrets
from .account_lifecycle import LifecycleDenied, _email
from .cycle_identity_registration_ci import _guard
from .invite_registration_ci import _valid_cpf
from .security import hash_password_secure, hash_token, verify_password_secure
from .account_governance_ci import prepare_saas_license_ci
from .saas_billing_ci import (stage_saas_payment_ci, attach_mp_payment_identifier_ci,
                             reconcile_approved_saas_payment_ci, _cents)
from .mercado_pago_safety import ExpectedPayment, matches_approved_payment

COLLECTOR_CI="12345"

def _session(conn, token, role, tenant=None, draft=False):
    if type(token) is not str or not 32<=len(token)<=512:
        raise LifecycleDenied("Sessão inválida.")
    row=conn.execute(
        "SELECT u.id,u.email FROM public.sessions s JOIN public.users u ON u.id=s.user_id "
        "WHERE s.token_hash=%s AND s.active_role=%s AND s.active_tenant_id IS NOT DISTINCT FROM %s::uuid "
        "AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.status='ACTIVE' "
        "AND u.email_verified_at IS NOT NULL AND (u.is_master OR %s<>'MASTER') FOR SHARE OF s,u",
        (hash_token(token),role,tenant,role)).fetchone()
    if not row or not row[1].endswith("@example.invalid"):
        raise LifecycleDenied("Sessão sintética indisponível.")
    if role=="TENANT_ADMIN" and not conn.execute(
        "SELECT 1 FROM public.tenants t JOIN public.memberships m ON m.tenant_id=t.id "
        "WHERE t.id=%s AND t.admin_user_id=%s AND m.user_id=%s AND m.role='TENANT_ADMIN' "
        "AND m.status='ATIVA' AND t.status=ANY(%s) FOR SHARE OF t,m",
        (tenant,row[0],row[0],["RASCUNHO_INATIVO","ATIVO"] if draft else ["ATIVO"])).fetchone():
        raise LifecycleDenied("Vínculo administrativo indisponível.")
    return row

def _audit(conn, actor, role, tenant, action, obj, evidence):
    conn.execute("INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref) "
                 "VALUES(%s,%s,%s,%s,'ADMIN_ONBOARDING_CI',%s,'Evidência exclusivamente sintética M41410',%s)",
                 (actor,role,tenant,action,str(obj),str(evidence)))

def stage_admin_invite_ci(conn, *, master_token, master_password, reviewer_token, reviewer_tenant,
                          email, document_id, document_hash):
    """Distinct reviewer is only a synthetic test actor, never a real approval role."""
    _guard(conn)
    email=_email(email)
    if not email.endswith("@example.invalid") or type(document_hash) is not str or not re.fullmatch(r"[0-9a-f]{64}",document_hash):
        raise LifecycleDenied("Destinatário ou documento inválido.")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(706719221346)")
        master,master_email=_session(conn,master_token,"MASTER")
        reviewer,reviewer_email=_session(conn,reviewer_token,"TENANT_ADMIN",reviewer_tenant)
        cred=conn.execute("SELECT password_hash,locked_until FROM public.credentials WHERE user_id=%s FOR SHARE",(master,)).fetchone()
        if (master==reviewer or email in (master_email,reviewer_email) or not cred
            or (cred[1] is not None and cred[1]>datetime.now(timezone.utc))
            or type(master_password) is not str or not verify_password_secure(master_password,cred[0])):
            raise LifecycleDenied("Controle sintético de emissão recusado.")
        if not conn.execute("SELECT 1 FROM public.contract_documents WHERE id=%s AND document_kind='PLATFORM_LICENSE' "
                            "AND sha256=%s AND published_at IS NOT NULL FOR SHARE",(document_id,document_hash)).fetchone():
            raise LifecycleDenied("Contrato A incompatível.")
        if conn.execute("SELECT 1 FROM public.users WHERE lower(email)=%s",(email,)).fetchone() or conn.execute(
            "SELECT 1 FROM public.invitations WHERE lower(target_email)=%s AND target_role='TENANT_ADMIN' "
            "AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at>clock_timestamp()",(email,)).fetchone():
            raise LifecycleDenied("Identidade ou convite existente.")
        inv,raw=uuid4(),secrets.token_urlsafe(32)
        conn.execute("INSERT INTO public.invitations(id,tenant_id,inviter_user_id,target_email,target_role,token_hash,expires_at,required_document_id) "
                     "VALUES(%s,NULL,%s,%s,'TENANT_ADMIN',%s,%s,%s)",
                     (inv,master,email,hash_token(raw),datetime.now(timezone.utc)+timedelta(hours=24),document_id))
        conn.execute("INSERT INTO public.fr_v23_admin_invite_bindings(invitation_id,master_id,reviewer_id,document_id,document_hash) "
                     "VALUES(%s,%s,%s,%s,%s)",(inv,master,reviewer,document_id,document_hash))
        _audit(conn,master,"MASTER",None,"CI_ADMIN_INVITE_STAGED",inv,reviewer)
        return inv,raw

def register_admin_ci(conn, *, invitation_token, verification_token, document_id, document_hash,
                      accepted, name, cpf, phone, password, tenant_name):
    _guard(conn)
    if (accepted is not True or type(document_hash) is not str or not re.fullmatch(r"[0-9a-f]{64}",document_hash)
        or any(type(x) is not str or not 32<=len(x)<=512 for x in (invitation_token,verification_token))
        or invitation_token==verification_token or type(name) is not str or not 3<=len(name.strip())<=255
        or type(cpf) is not str or not _valid_cpf(cpf) or type(phone) is not str or not re.fullmatch(r"[0-9+() -]{8,20}",phone)
        or type(password) is not str or not 12<=len(password)<=256 or type(tenant_name) is not str
        or not 3<=len(tenant_name.strip())<=255 or any(ord(c)<32 for c in name+tenant_name)):
        raise LifecycleDenied("Cadastro ou aceite A inválido.")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(706719221346)")
        row=conn.execute(
            "SELECT i.id,i.target_email,v.id,b.master_id,b.reviewer_id FROM public.invitations i "
            "JOIN public.fr_v23_admin_invite_bindings b ON b.invitation_id=i.id "
            "JOIN public.invite_email_verification v ON v.invitation_id=i.id "
            "JOIN public.contract_documents d ON d.id=b.document_id "
            "JOIN public.users master ON master.id=b.master_id JOIN public.users reviewer ON reviewer.id=b.reviewer_id "
            "WHERE i.token_hash=%s AND v.token_hash=%s AND i.tenant_id IS NULL AND i.target_role='TENANT_ADMIN' "
            "AND i.inviter_user_id=b.master_id AND i.required_document_id=b.document_id AND b.document_id=%s "
            "AND b.document_hash=%s AND d.sha256=b.document_hash AND d.document_kind='PLATFORM_LICENSE' "
            "AND d.published_at IS NOT NULL AND i.delivery_status='DELIVERED' AND i.expires_at>clock_timestamp() "
            "AND i.accepted_at IS NULL AND i.revoked_at IS NULL AND v.expires_at>clock_timestamp() "
            "AND v.consumed_at IS NULL AND v.revoked_at IS NULL AND lower(v.recipient_email)=lower(i.target_email) "
            "AND master.is_master AND master.status='ACTIVE' AND reviewer.status='ACTIVE' "
            "AND master.email_verified_at IS NOT NULL AND reviewer.email_verified_at IS NOT NULL "
            "FOR UPDATE OF i,v",(hash_token(invitation_token),hash_token(verification_token),document_id,document_hash)).fetchone()
        if not row or not row[1].endswith("@example.invalid"):
            raise LifecycleDenied("Convite ou prova incompatível.")
        if conn.execute("SELECT 1 FROM public.users WHERE lower(email)=lower(%s) OR regexp_replace(cpf,'[^0-9]','','g')=%s",(row[1],cpf)).fetchone():
            raise LifecycleDenied("Identidade já existente.")
        actor,tenant,member,acc=uuid4(),uuid4(),uuid4(),uuid4()
        pwd=hash_password_secure(password)
        conn.execute("INSERT INTO public.users(id,email,full_name,cpf,phone,status,is_master,email_verified_at) "
                     "VALUES(%s,%s,%s,%s,%s,'ACTIVE',false,now())",(actor,row[1],name.strip(),cpf,phone))
        conn.execute("INSERT INTO public.credentials(user_id,password_hash,algorithm) VALUES(%s,%s,%s)",
                     (actor,pwd,'argon2id' if pwd.startswith('$argon2id$') else 'bcrypt'))
        evidence=sha256((str(row[0])+str(actor)+str(document_id)+document_hash+secrets.token_hex(32)).encode()).hexdigest()
        conn.execute("INSERT INTO public.contract_acceptances(id,document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method) "
                     "VALUES(%s,%s,'PLATFORM_LICENSE',%s,NULL,%s,'CI_VERIFIED_IDENTITY')",(acc,document_id,actor,evidence))
        conn.execute("INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status,is_owner_box) "
                     "VALUES(%s,%s,%s,%s,'RASCUNHO_INATIVO',false)",(tenant,tenant_name.strip(),str(actor),actor))
        conn.execute("INSERT INTO public.memberships(id,tenant_id,user_id,role,status) VALUES(%s,%s,%s,'TENANT_ADMIN','ATIVA')",(member,tenant,actor))
        conn.execute("UPDATE public.invite_email_verification SET consumed_at=now() WHERE id=%s",(row[2],))
        conn.execute("UPDATE public.invitations SET tenant_id=%s,accepted_at=now(),accepted_user_id=%s,accepted_membership_id=%s WHERE id=%s",
                     (tenant,actor,member,row[0]))
        _audit(conn,actor,"TENANT_ADMIN",tenant,"CI_ADMIN_A_ACCEPTED",row[0],acc)
        conn.execute("SET CONSTRAINTS fr_v23_admin_binding_acceptance IMMEDIATE")
        conn.execute("SET CONSTRAINTS fr_v23_admin_binding_acceptance DEFERRED")
        return actor,tenant,acc

def prepare_admin_checkout_ci(conn, *, admin_token, tenant, price_version, period, accepted_cents, accepted):
    _guard(conn)
    if accepted is not True or period not in ("MONTHLY","ANNUAL") or type(accepted_cents) is not int or accepted_cents<=0:
        raise LifecycleDenied("Oferta exige confirmação explícita.")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),))
        actor,_=_session(conn,admin_token,"TENANT_ADMIN",tenant,draft=True)
        bound=conn.execute("SELECT a.id FROM public.invitations i JOIN public.fr_v23_admin_invite_bindings b ON b.invitation_id=i.id "
                           "JOIN public.contract_acceptances a ON a.document_id=b.document_id AND a.user_id=i.accepted_user_id "
                           "AND a.document_kind='PLATFORM_LICENSE' AND a.tenant_id IS NULL "
                           "WHERE i.tenant_id=%s AND i.accepted_user_id=%s AND i.accepted_at IS NOT NULL",(tenant,actor)).fetchone()
        price=conn.execute("SELECT v.monthly_price,v.annual_price FROM public.platform_license_price_versions v "
                           "JOIN public.platform_license_plans p ON p.tier=v.plan_tier "
                           "WHERE v.id=%s AND p.status='ACTIVE' AND p.tier<>'AMPLIADO' FOR SHARE OF v,p",(price_version,)).fetchone()
        if not bound or not price or _cents(price[0] if period=="MONTHLY" else price[1])!=accepted_cents:
            raise LifecycleDenied("Preço ou aceite A incompatível.")
        saved=conn.execute("SELECT s.id,s.price_version_id,s.billing_period,p.id,p.expected_amount_cents,p.status "
                           "FROM public.saas_subscription_preparations s JOIN public.saas_payment_intents p ON p.preparation_id=s.id "
                           "WHERE s.tenant_id=%s AND s.admin_user_id=%s AND s.contract_acceptance_id=%s FOR UPDATE OF s,p",
                           (tenant,actor,bound[0])).fetchone()
        if saved:
            if tuple(saved[1:3])!=(price_version,period) or saved[4]!=accepted_cents or saved[5] not in ("PENDING","APPROVED"):
                raise LifecycleDenied("Oferta já vinculada; alteração exige fluxo próprio.")
            return saved[0],saved[3]
        if not conn.execute("SELECT 1 FROM public.tenants WHERE id=%s AND status='RASCUNHO_INATIVO'",(tenant,)).fetchone():
            raise LifecycleDenied("Cadastro inicial já encerrado.")
        prep=prepare_saas_license_ci(conn,tenant_id=tenant,admin_id=actor,price_version_id=price_version,
                                     billing_period=period,acceptance_id=bound[0])
        intent=stage_saas_payment_ci(conn,preparation_id=prep,platform_collector_id=COLLECTOR_CI,live_mode=False)
        return prep,intent

def reconcile_admin_checkout_ci(conn, *, reviewer_token, reviewer_tenant, tenant, intent,
                                payment, statement_gross_cents, statement_fee_cents, statement_net_cents):
    """Synthetic provider, statement and distinct session, not external proof."""
    _guard(conn)
    if (type(payment) is not dict or any(type(x) is not int for x in (statement_gross_cents,statement_fee_cents,statement_net_cents))
        or not 0<=statement_fee_cents<statement_gross_cents or statement_net_cents<=0
        or statement_fee_cents+statement_net_cents!=statement_gross_cents
        or type(payment.get("transaction_amount_refunded")) not in (int,str)
        or payment.get("transaction_amount_refunded") not in (0,"0","0.00")):
        raise LifecycleDenied("Conciliação sintética inconsistente.")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),))
        reviewer,_=_session(conn,reviewer_token,"TENANT_ADMIN",reviewer_tenant)
        row=conn.execute("SELECT p.admin_user_id,p.provider_payment_id,p.external_reference,p.expected_amount_cents,p.status,t.status,b.reviewer_id "
                         "FROM public.saas_payment_intents p JOIN public.saas_subscription_preparations s ON s.id=p.preparation_id "
                         "JOIN public.tenants t ON t.id=p.tenant_id AND t.admin_user_id=p.admin_user_id "
                         "JOIN public.invitations i ON i.tenant_id=t.id AND i.accepted_user_id=p.admin_user_id "
                         "JOIN public.fr_v23_admin_invite_bindings b ON b.invitation_id=i.id "
                         "JOIN public.contract_acceptances a ON a.id=s.contract_acceptance_id AND a.document_id=b.document_id AND a.user_id=p.admin_user_id "
                         "WHERE p.id=%s AND p.tenant_id=%s AND s.tenant_id=p.tenant_id AND s.admin_user_id=p.admin_user_id "
                         "AND p.platform_collector_id=%s AND p.live_mode=false FOR UPDATE OF p,t",
                         (intent,tenant,COLLECTOR_CI)).fetchone()
        if (not row or reviewer!=row[6] or reviewer==row[0] or row[3]!=statement_gross_cents
            or row[4] not in ("PENDING","APPROVED") or row[5] not in ("RASCUNHO_INATIVO","ATIVO")):
            raise LifecycleDenied("Pagamento fora do escopo.")
        provider_id=str(payment.get("id",""))
        if not provider_id.isascii() or not provider_id.isdecimal() or len(provider_id)>40:
            raise LifecycleDenied("Identificador sintético inválido.")
        expected=ExpectedPayment(row[1] or provider_id,COLLECTOR_CI,row[2],row[3],False)
        if not matches_approved_payment(expected,payment):
            raise LifecycleDenied("Pagamento não confere.")
        if row[1] is None and not attach_mp_payment_identifier_ci(conn,intent_id=intent,provider_payment_id=provider_id):
            raise LifecycleDenied("Identificador não vinculado.")
        ent=reconcile_approved_saas_payment_ci(conn,intent_id=intent,authoritative_payment=payment,now=conn.execute("SELECT now()").fetchone()[0])
        if not ent:
            raise LifecycleDenied("Licença não conciliada.")
        conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,row[0])).fetchone()
        if row[5]=="RASCUNHO_INATIVO":
            conn.execute("UPDATE public.tenants SET status='ATIVO' WHERE id=%s",(tenant,))
            _audit(conn,reviewer,"SYSTEM",tenant,"CI_ADMIN_LICENSE_DRAFT_RELEASED",ent,intent)
        return ent

def accept_admin_b_ci(conn, *, admin_token, tenant, document_id, document_hash, accepted):
    """Separate exact B acceptance after license; no policy or cycle opened here."""
    _guard(conn)
    if accepted is not True or type(document_hash) is not str or not re.fullmatch(r"[0-9a-f]{64}",document_hash):
        raise LifecycleDenied("Aceite B explícito obrigatório.")
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),))
        actor,_=_session(conn,admin_token,"TENANT_ADMIN",tenant)
        conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
        doc=conn.execute("SELECT sha256 FROM public.contract_documents WHERE id=%s AND document_kind='TENANT_MEMBERSHIP' "
                         "AND published_at IS NOT NULL FOR SHARE",(document_id,)).fetchone()
        if not doc or doc[0]!=document_hash:
            raise LifecycleDenied("Documento B incompatível.")
        old=conn.execute("SELECT id FROM public.contract_acceptances WHERE document_id=%s AND user_id=%s "
                         "AND tenant_id=%s AND document_kind='TENANT_MEMBERSHIP'",(document_id,actor,tenant)).fetchone()
        if old:
            return old[0]
        from app.account_governance_ci import record_contract_acceptance_ci
        return record_contract_acceptance_ci(conn,user_id=actor,document_id=document_id,tenant_id=tenant)
