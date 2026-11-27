"""M41490: exact scoped SaaS overview, disposable PG18 only."""
from .account_lifecycle import LifecycleDenied
from .cycle_identity_registration_ci import _guard
from .admin_license_onboarding_ci import _session,COLLECTOR_CI
from .preliminary_onboarding_ci import _binding
from .administrator_reauthentication_ci import _license_access
from .saas_renewal_v23_ci import _lock,_previous,_term_base,_review_exists,_assert_lineage,prepare_renewal_ci
from .onboarding_readback_ci import _document
from .saas_billing_ci import _cents

def renewal_overview_ci(conn,*,token,tenant):
    _guard(conn)
    with conn.transaction():
        _lock(conn,tenant)
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant)
        acceptance,status=_binding(conn,actor,tenant)
        if status!="ATIVO":raise LifecycleDenied("Vínculo indisponível.")
        _assert_lineage(conn,tenant)
        access=_license_access(conn,actor,tenant)
        docid=conn.execute("SELECT document_id FROM public.contract_acceptances WHERE id=%s",(acceptance,)).fetchone()[0]
        doc=_document(conn,docid,"PLATFORM_LICENSE")
        now=conn.execute("SELECT clock_timestamp()").fetchone()[0]
        rows=conn.execute(
            "SELECT e.id,e.plan_tier,e.valid_from,e.valid_until,e.status,s.billing_period,p.expected_amount_cents,p.status,p.id "
            "FROM public.saas_license_entitlements e JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id "
            "JOIN public.saas_payment_intents p ON p.id=e.payment_intent_id AND p.preparation_id=s.id "
            "JOIN public.platform_license_price_versions v ON v.id=s.price_version_id AND v.plan_tier=s.plan_tier "
            "WHERE e.tenant_id=%s AND s.tenant_id=e.tenant_id AND p.tenant_id=e.tenant_id AND s.admin_user_id=%s "
            "AND p.admin_user_id=s.admin_user_id AND s.contract_acceptance_id=%s AND e.plan_tier=s.plan_tier "
            "AND p.price_version_id=s.price_version_id AND p.platform_collector_id=%s AND p.live_mode=false "
            "AND p.provider='MERCADO_PAGO' AND p.currency='BRL' AND p.provider_payment_id IS NOT NULL "
            "AND p.paid_at IS NOT NULL AND p.reconciled_at>=p.paid_at AND p.reconciled_at<=%s "
            "AND p.expected_amount_cents=(CASE s.billing_period WHEN 'MONTHLY' THEN v.monthly_price ELSE v.annual_price END)*100 "
            "AND ((p.status='APPROVED' AND e.status IN ('ACTIVE','SUSPENDED','EXPIRED')) OR (p.status='REFUNDED' AND e.status='REVOKED' "
            "AND EXISTS(SELECT 1 FROM public.audit_events a WHERE a.tenant_id=e.tenant_id AND a.object_id=p.id::text "
            "AND a.action='CI_SAAS_REFUND_REVOKED' AND a.evidence_ref=p.provider_payment_id))) "
            "ORDER BY e.valid_from,e.id LIMIT 51 FOR SHARE OF e,s,p,v",
            (tenant,actor,acceptance,COLLECTOR_CI,now)).fetchall()
        count=conn.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()[0]
        if not rows or len(rows)>50 or count!=len(rows):
            raise LifecycleDenied("Histórico indisponível ou exige paginação.")
        segments=[]
        for eid,tier,start,end,state,period,cents,pay,intent in rows:
            if state=="REVOKED":label="REFUNDED"
            elif state=="SUSPENDED":label="SUSPENDED"
            elif end<=now:label="EXPIRED"
            elif state=="ACTIVE":label="SCHEDULED" if start>now else "CURRENT"
            else:raise LifecycleDenied("Vigência incompatível.")
            segments.append(dict(entitlement_id=eid,tier=tier,period=period,cents=cents,
                                 valid_from=start,valid_until=end,state=label,intent_id=intent))
        if sum(x["state"]=="CURRENT" for x in segments)!=(1 if access=="CURRENT" else 0):
            raise LifecycleDenied("Vigência inconsistente.")
        renewals=conn.execute(
            "SELECT r.request_id,r.predecessor,r.intent_id,r.price_version,r.period,r.cents,r.expires_at,r.entitlement_id,p.status,r.canceled_at,p.provider_payment_id,p.paid_at,p.reconciled_at "
            "FROM public.fr_v23_renewals r JOIN public.saas_payment_intents p ON p.id=r.intent_id AND p.preparation_id=r.preparation_id "
            "JOIN public.saas_subscription_preparations s ON s.id=r.preparation_id AND s.renewal_request_id=r.request_id "
            "WHERE r.tenant_id=%s AND r.actor=%s AND p.tenant_id=r.tenant_id AND s.tenant_id=r.tenant_id "
            "AND p.admin_user_id=r.actor AND s.admin_user_id=r.actor AND s.contract_acceptance_id=%s "
            "AND r.document_id=%s AND r.document_hash=%s AND p.live_mode=false AND p.platform_collector_id=%s "
            "AND p.price_version_id=r.price_version AND s.price_version_id=r.price_version AND s.billing_period=r.period "
            "AND p.expected_amount_cents=r.cents ORDER BY r.accepted_at,r.request_id LIMIT 51 FOR SHARE OF r,p,s",
            (tenant,actor,acceptance,docid,doc["document_hash"],COLLECTOR_CI)).fetchall()
        if len(renewals)>50 or len(renewals)!=conn.execute("SELECT count(*) FROM public.fr_v23_renewals WHERE tenant_id=%s",(tenant,)).fetchone()[0]:
            raise LifecycleDenied("Histórico de renovação inconsistente.")
        items=[]
        by_id={x["entitlement_id"]:x for x in segments}
        for req,prev,intent,price,period,cents,expiry,ent,pay,canceled,provider_id,paid,reconciled in renewals:
            if prev not in by_id:raise LifecycleDenied("Predecessor indisponível.")
            if pay=="CANCELED" and ent is None and canceled and expiry<=canceled<=now and provider_id and paid is None and reconciled is None:
                if not conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND action='CI_RENEWAL_EXPIRED_CANCELED' "
                                    "AND object_id=%s AND evidence_ref=%s",(tenant,str(req),provider_id)).fetchone():
                    raise LifecycleDenied("Cancelamento sem prova.")
                label="CANCELED"
            elif pay=="PENDING" and ent is None and canceled is None and paid is None and reconciled is None:
                if _review_exists(conn,tenant,intent):
                    if not provider_id:raise LifecycleDenied("Revisão sem vínculo de pagamento.")
                    label="PAYMENT_REVIEW"
                else:label="PENDING" if now<expiry else "REVIEW_REQUIRED"
            elif pay in ("APPROVED","REFUNDED") and canceled is None and ent in by_id and by_id[ent]["intent_id"]==intent and by_id[ent]["cents"]==cents and by_id[ent]["period"]==period:
                label="REFUNDED" if pay=="REFUNDED" else "CI_RECONCILED"
                if (label=="REFUNDED")!=(by_id[ent]["state"]=="REFUNDED"):raise LifecycleDenied("Estorno inconsistente.")
            else:raise LifecycleDenied("Pagamento incompatível.")
            items.append(dict(request_id=req,predecessor=prev,intent_id=intent,price_version=price,period=period,cents=cents,
                              expires_at=expiry,entitlement_id=ent,state=label))
        offer=None
        # History is a lineage, not a maximum date (a refunded annual period
        # can extend beyond a replacement monthly period).
        used={x["predecessor"] for x in items if x["entitlement_id"] is not None}
        leaves=[x for x in segments if x["entitlement_id"] not in used]
        if len(leaves)!=1:raise LifecycleDenied("Histórico de vigência ambíguo.")
        last=leaves[0]
        if last["state"] in ("CURRENT","EXPIRED","SCHEDULED","REFUNDED") and not any(x["predecessor"]==last["entitlement_id"] and x["state"]!="CANCELED" for x in items):
            try:
                prev=_previous(conn,tenant,actor,last["entitlement_id"],acceptance)
                _term_base(conn,tenant,actor,prev,acceptance,now)
            except LifecycleDenied:prev=None
            if prev:
                price=conn.execute(
                    "SELECT v.id,p.tier,p.members_limit,p.quotas_limit,v.monthly_price,v.annual_price "
                    "FROM public.platform_license_plans p JOIN public.platform_license_price_versions v ON v.plan_tier=p.tier "
                    "WHERE p.tier=%s AND p.status='ACTIVE' AND p.tier IN ('ESSENCIAL','INTERMEDIARIO') "
                    "ORDER BY v.created_at DESC,v.id DESC LIMIT 1 FOR SHARE OF p,v",(prev[1],)).fetchone()
                if price:
                    offer=dict(predecessor=last["entitlement_id"],price_version=price[0],tier=price[1],members_limit=price[2],
                               quotas_limit=price[3],monthly_cents=_cents(price[4]),annual_cents=_cents(price[5]))
        # No further commercial offer while the synthetic upgrade is unresolved.
        if conn.execute("SELECT 1 FROM public.fr_v23_upgrade_settlement_reviews WHERE tenant_id=%s",(tenant,)).fetchone():
            offer=None
        return dict(user_id=actor,tenant_id=tenant,role="TENANT_ADMIN",ci_only=True,production_authorized=False,
                    real_payment_authorized=False,observed_at=now,access=access,document=doc,segments=segments,renewals=items,offer=offer)

def renewal_prepare_http_ci(conn,*,token,tenant,**body):
    _guard(conn)
    with conn.transaction():
        prepare_renewal_ci(conn,token=token,tenant=tenant,**body)
        return renewal_overview_ci(conn,token=token,tenant=tenant)
