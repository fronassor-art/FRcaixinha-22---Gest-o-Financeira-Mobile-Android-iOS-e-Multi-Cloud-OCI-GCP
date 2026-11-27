"""M41480: synthetic renewal and verified full refund, canonical disposable PG18 only.
No provider transport, real money, new database or runtime dependency override.
"""
from calendar import monthrange
from zoneinfo import ZoneInfo
from uuid import UUID,uuid4
from .account_lifecycle import LifecycleDenied
from .cycle_identity_registration_ci import _guard
from .admin_license_onboarding_ci import _session,COLLECTOR_CI,_audit
from .preliminary_onboarding_ci import _binding
from .onboarding_readback_ci import _document
from .saas_billing_ci import _cents,stage_saas_payment_ci,attach_mp_payment_identifier_ci,revoke_after_verified_refund_ci
from .mercado_pago_safety import ExpectedPayment,matches_approved_payment,matches_full_refund

ZONE=ZoneInfo("America/Belem")
def renewal_term(previous_end,previous_anchor,confirmed_at,period):
    if period not in ("MONTHLY","ANNUAL") or type(previous_anchor) is not int or not 1<=previous_anchor<=31:
        raise LifecycleDenied("Vigência incompatível.")
    if any(x.tzinfo is None or x.utcoffset() is None for x in (previous_end,confirmed_at)):
        raise LifecycleDenied("Data sem fuso.")
    now=confirmed_at.astimezone(ZONE)
    # At the exact boundary there is no gap; preserve the paid anchor.
    start=max(previous_end,confirmed_at).astimezone(ZONE)
    anchor=previous_anchor if confirmed_at<=previous_end else now.day
    months=1 if period=="MONTHLY" else 12
    year=start.year+(start.month-1+months)//12
    month=(start.month-1+months)%12+1
    end=start.replace(year=year,month=month,day=min(anchor,monthrange(year,month)[1]))
    return start,end,anchor

def _lock(conn,tenant):
    _guard(conn)
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),))

def _previous(conn,tenant,actor,predecessor,acceptance):
    row=conn.execute(
        "SELECT e.id,e.plan_tier,e.status,e.valid_from,e.valid_until,s.contract_acceptance_id,p.status,"
        "p.live_mode,p.reconciled_at,p.paid_at FROM public.saas_license_entitlements e "
        "JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id "
        "JOIN public.saas_payment_intents p ON p.id=e.payment_intent_id AND p.preparation_id=s.id "
        "JOIN public.platform_license_price_versions v ON v.id=s.price_version_id AND v.plan_tier=s.plan_tier "
        "WHERE e.id=%s AND e.tenant_id=%s AND s.tenant_id=e.tenant_id AND p.tenant_id=e.tenant_id "
        "AND s.admin_user_id=%s AND p.admin_user_id=s.admin_user_id AND s.contract_acceptance_id=%s "
        "AND e.plan_tier=s.plan_tier AND p.price_version_id=s.price_version_id "
        "AND p.platform_collector_id=%s AND p.provider_payment_id IS NOT NULL "
        "AND p.currency='BRL' AND p.provider='MERCADO_PAGO' AND p.live_mode=false "
        "AND p.expected_amount_cents=(CASE s.billing_period WHEN 'MONTHLY' THEN v.monthly_price ELSE v.annual_price END)*100 "
        "AND s.status='PENDING_PAYMENT' AND p.reconciled_at<=clock_timestamp() FOR SHARE OF e,s,p,v",
        (predecessor,tenant,actor,acceptance,COLLECTOR_CI)).fetchone()
    if not row or row[2] not in ("ACTIVE","EXPIRED") or row[6]!="APPROVED" or not row[8] or not row[9] or row[8]<row[9]:
        raise LifecycleDenied("Período anterior indisponível para renovação.")
    # No skipping a paid future segment or overlapping a different branch.
    if conn.execute("SELECT 1 FROM public.saas_license_entitlements WHERE tenant_id=%s AND id<>%s "
                    "AND valid_until>%s AND status<>'REVOKED'",(tenant,predecessor,row[4])).fetchone():
        raise LifecycleDenied("Existe período posterior.")
    return row

def prepare_renewal_ci(conn,*,token,tenant,request_id,predecessor,price_version,period,cents,document_id,document_hash,accepted):
    _guard(conn)
    if accepted is not True or type(cents) is not int or not 0<cents<=100000000 or period not in ("MONTHLY","ANNUAL"):
        raise LifecycleDenied("Aceite de renovação inválido.")
    if any(type(x) is not UUID or not x.int for x in (tenant,request_id,predecessor,price_version,document_id)):
        raise LifecycleDenied("Identificador inválido.")
    with conn.transaction():
        _lock(conn,tenant)
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant)
        acceptance,status=_binding(conn,actor,tenant)
        if status!="ATIVO":raise LifecycleDenied("Vínculo indisponível.")
        doc=_document(conn,document_id,"PLATFORM_LICENSE")
        if doc["document_hash"]!=document_hash or not conn.execute(
            "SELECT 1 FROM public.contract_acceptances WHERE id=%s AND user_id=%s AND document_id=%s FOR SHARE",
            (acceptance,actor,document_id)).fetchone():
            raise LifecycleDenied("Contrato A incompatível.")
        saved=conn.execute("SELECT tenant_id,actor,predecessor,price_version,period,cents,document_id,document_hash,preparation_id,intent_id "
                           "FROM public.fr_v23_renewals WHERE request_id=%s",(request_id,)).fetchone()
        exact=(tenant,actor,predecessor,price_version,period,cents,document_id,document_hash)
        if saved:
            if saved[:8]!=exact:raise LifecycleDenied("Colisão de renovação.")
            return saved[8],saved[9]
        prev=_previous(conn,tenant,actor,predecessor,acceptance)
        if conn.execute("SELECT 1 FROM public.fr_v23_renewals WHERE predecessor=%s",(predecessor,)).fetchone():
            raise LifecycleDenied("Renovação anterior já registrada.")
        price=conn.execute(
            "SELECT v.id,v.monthly_price,v.annual_price FROM public.platform_license_price_versions v "
            "JOIN public.platform_license_plans p ON p.tier=v.plan_tier "
            "WHERE p.tier=%s AND p.status='ACTIVE' AND p.tier<>'AMPLIADO' ORDER BY v.created_at DESC,v.id DESC LIMIT 1 FOR SHARE OF v,p",
            (prev[1],)).fetchone()
        if not price or price[0]!=price_version or _cents(price[1] if period=="MONTHLY" else price[2])!=cents:
            raise LifecycleDenied("Oferta substituída ou preço incorreto.")
        prep=uuid4()
        conn.execute("INSERT INTO public.saas_subscription_preparations "
                     "(id,tenant_id,admin_user_id,plan_tier,price_version_id,billing_period,contract_acceptance_id,renewal_request_id) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(prep,tenant,actor,prev[1],price_version,period,acceptance,request_id))
        intent=stage_saas_payment_ci(conn,preparation_id=prep,platform_collector_id=COLLECTOR_CI,live_mode=False)
        conn.execute("INSERT INTO public.fr_v23_renewals(request_id,tenant_id,actor,predecessor,price_version,period,cents,"
                     "document_id,document_hash,preparation_id,intent_id,expires_at) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes')", 
                     (request_id,tenant,actor,predecessor,price_version,period,cents,document_id,document_hash,prep,intent))
        _audit(conn,actor,"TENANT_ADMIN",tenant,"CI_RENEWAL_OFFER_ACCEPTED",request_id,intent)
        return prep,intent

def _reviewer(conn,token,reviewer_tenant,tenant,actor):
    reviewer,_=_session(conn,token,"TENANT_ADMIN",reviewer_tenant)
    if reviewer==actor or reviewer_tenant==tenant or not conn.execute(
        "SELECT 1 FROM public.invitations i JOIN public.fr_v23_admin_invite_bindings b ON b.invitation_id=i.id "
        "WHERE i.tenant_id=%s AND i.accepted_user_id=%s AND i.accepted_at IS NOT NULL AND i.revoked_at IS NULL "
        "AND b.reviewer_id=%s FOR SHARE OF i,b",(tenant,actor,reviewer)).fetchone():
        raise LifecycleDenied("Revisão sintética independente indisponível.")
    return reviewer

def reconcile_renewal_ci(conn,*,reviewer_token,reviewer_tenant,tenant,intent,payment,gross,fee,net):
    _guard(conn)
    if type(payment) is not dict or any(type(x) is not int for x in (gross,fee,net)) or not 0<=fee<gross or net!=gross-fee:
        raise LifecycleDenied("Extrato sintético incompatível.")
    if type(payment.get("transaction_amount_refunded")) not in (str,int) or payment["transaction_amount_refunded"] not in ("0","0.00",0):
        raise LifecycleDenied("Pagamento revertido.")
    with conn.transaction():
        _lock(conn,tenant)
        row=conn.execute(
            "SELECT r.actor,r.predecessor,r.preparation_id,r.period,r.cents,r.expires_at,r.entitlement_id,"
            "p.status,p.provider_payment_id,p.external_reference,s.contract_acceptance_id,s.plan_tier "
            "FROM public.fr_v23_renewals r JOIN public.saas_payment_intents p ON p.id=r.intent_id AND p.preparation_id=r.preparation_id "
            "JOIN public.saas_subscription_preparations s ON s.id=r.preparation_id AND s.renewal_request_id=r.request_id "
            "JOIN public.platform_license_plans pl ON pl.tier=s.plan_tier "
            "JOIN public.platform_license_price_versions v ON v.id=r.price_version AND v.plan_tier=s.plan_tier "
            "WHERE r.tenant_id=%s AND r.intent_id=%s AND p.tenant_id=r.tenant_id AND s.tenant_id=r.tenant_id "
            "AND p.admin_user_id=r.actor AND s.admin_user_id=r.actor AND s.price_version_id=r.price_version "
            "AND p.price_version_id=r.price_version AND s.billing_period=r.period AND p.expected_amount_cents=r.cents "
            "AND p.live_mode=false AND p.platform_collector_id=%s AND s.status='PENDING_PAYMENT' "
            "AND pl.status='ACTIVE' AND pl.tier<>'AMPLIADO' "
            "AND r.cents=(CASE r.period WHEN 'MONTHLY' THEN v.monthly_price ELSE v.annual_price END)*100 "
            "FOR UPDATE OF r,p,s FOR SHARE OF pl,v",
            (tenant,intent,COLLECTOR_CI)).fetchone()
        if not row or gross!=row[4] or row[7] not in ("PENDING","APPROVED"):
            raise LifecycleDenied("Renovação fora do escopo.")
        actor,previous,prep,period,cents,expiry,ent,state,stored_id,ref,acceptance,tier=row
        reviewer=_reviewer(conn,reviewer_token,reviewer_tenant,tenant,actor)
        if _binding(conn,actor,tenant)!=(acceptance,"ATIVO"):
            raise LifecycleDenied("Vínculo original indisponível.")
        provider_id=str(payment.get("id",""))
        if not provider_id.isascii() or not provider_id.isdecimal() or len(provider_id)>40 or not matches_approved_payment(
            ExpectedPayment(stored_id or provider_id,COLLECTOR_CI,ref,cents,False),payment):
            raise LifecycleDenied("Pagamento não confere.")
        if state=="APPROVED":
            if not ent:raise LifecycleDenied("Conciliação incompleta.")
            return ent
        now=conn.execute("SELECT clock_timestamp()").fetchone()[0]
        if now>=expiry:raise LifecycleDenied("Oferta expirada; conciliação em revisão.")
        prev=_previous(conn,tenant,actor,previous,acceptance)
        prior_anchor=conn.execute("SELECT anchor_day FROM public.fr_v23_renewals WHERE entitlement_id=%s",(previous,)).fetchone()
        anchor=prior_anchor[0] if prior_anchor else prev[3].astimezone(ZONE).day
        start,end,anchor=renewal_term(prev[4],anchor,now,period)
        if stored_id is None and not attach_mp_payment_identifier_ci(conn,intent_id=intent,provider_payment_id=provider_id):
            raise LifecycleDenied("Vínculo de pagamento indisponível.")
        ent=uuid4()
        conn.execute("INSERT INTO public.saas_license_entitlements(id,preparation_id,payment_intent_id,tenant_id,plan_tier,valid_from,valid_until) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s)",(ent,prep,intent,tenant,tier,start,end))
        conn.execute("UPDATE public.saas_payment_intents SET status='APPROVED',paid_at=%s,reconciled_at=%s WHERE id=%s",(now,now,intent))
        conn.execute("UPDATE public.fr_v23_renewals SET anchor_day=%s,entitlement_id=%s WHERE intent_id=%s",(anchor,ent,intent))
        _audit(conn,reviewer,"SYSTEM",tenant,"CI_RENEWAL_RECONCILED",ent,intent)
        return ent

def reconcile_full_refund_ci(conn,*,reviewer_token,reviewer_tenant,tenant,intent,payment,statement_refunded_cents):
    _guard(conn)
    if type(statement_refunded_cents) is not int or statement_refunded_cents<=0 or type(payment) is not dict:
        raise LifecycleDenied("Estorno sem extrato sintético.")
    with conn.transaction():
        _lock(conn,tenant)
        row=conn.execute("SELECT admin_user_id,provider_payment_id,external_reference,expected_amount_cents,status "
                         "FROM public.saas_payment_intents WHERE id=%s AND tenant_id=%s AND live_mode=false "
                         "AND platform_collector_id=%s FOR UPDATE",(intent,tenant,COLLECTOR_CI)).fetchone()
        if not row or statement_refunded_cents!=row[3] or not matches_full_refund(
            ExpectedPayment(row[1],COLLECTOR_CI,row[2],row[3],False),payment):
            raise LifecycleDenied("Estorno incompatível.")
        _reviewer(conn,reviewer_token,reviewer_tenant,tenant,row[0])
        if row[4]=="REFUNDED":
            return bool(conn.execute("SELECT 1 FROM public.saas_license_entitlements e JOIN public.audit_events a "
                        "ON a.tenant_id=e.tenant_id AND a.object_id=e.payment_intent_id::text "
                        "WHERE e.payment_intent_id=%s AND e.status='REVOKED' AND a.action='CI_SAAS_REFUND_REVOKED' "
                        "AND a.evidence_ref=%s",(intent,row[1])).fetchone())
        if not revoke_after_verified_refund_ci(conn,intent_id=intent,authoritative_payment=payment):
            raise LifecycleDenied("Estorno não registrado.")
        return True
