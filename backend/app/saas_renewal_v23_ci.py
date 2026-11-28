"""M41480: synthetic renewal and verified full refund, canonical disposable PG18 only.
No provider transport, real money, new database or runtime dependency override.
"""
from calendar import monthrange
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import UUID,uuid4
from hashlib import sha256
import json
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

def _review_exists(conn,tenant,intent):
    return bool(conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND object_id=%s "
                             "AND object_type='SAAS_PAYMENT' AND action IN ('CI_RENEWAL_LATE_PAYMENT_REVIEW','CI_RENEWAL_AMOUNT_REVIEW','CI_RENEWAL_TIER_REVIEW')",
                             (tenant,str(intent))).fetchone())


def _assert_lineage(conn,tenant):
    """One connected chain; refunded intervals are historical, not paid coverage."""
    rows=conn.execute("SELECT id,status,valid_from,valid_until FROM public.saas_license_entitlements "
                      "WHERE tenant_id=%s FOR SHARE",(tenant,)).fetchall()
    edges=conn.execute("SELECT predecessor,entitlement_id FROM public.fr_v23_renewals WHERE tenant_id=%s "
                       "AND entitlement_id IS NOT NULL AND canceled_at IS NULL FOR SHARE",(tenant,)).fetchall()
    ids={r[0] for r in rows}
    parent={child:prev for prev,child in edges}
    roots=ids-parent.keys()
    if not ids or len(ids)>50 or len(edges)!=len(ids)-1 or len(parent)!=len(edges) or len(set(parent.values()))!=len(edges) or len(roots)!=1:
        raise LifecycleDenied("Cadeia de vigência incompatível.")
    if any(child not in ids or prev not in ids for child,prev in parent.items()):
        raise LifecycleDenied("Cadeia fora do escopo.")
    root=next(iter(roots))
    for eid in ids:
        seen=set()
        while eid in parent:
            if eid in seen:raise LifecycleDenied("Cadeia circular.")
            seen.add(eid)
            eid=parent[eid]
        if eid!=root:raise LifecycleDenied("Cadeia desconectada.")
    paid=sorted((start,end) for _,state,start,end in rows if state!="REVOKED")
    if any(start>=end for start,end in paid) or any(left[1]>right[0] for left,right in zip(paid,paid[1:])):
        raise LifecycleDenied("Períodos pagos sobrepostos.")


def _previous(conn,tenant,actor,predecessor,acceptance,*,ancestor=False):
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
    if not row or not row[8] or not row[9] or row[8]<row[9]:
        raise LifecycleDenied("Período anterior indisponível para renovação.")
    if row[2]=="REVOKED" and row[6]=="REFUNDED":
        if not conn.execute("SELECT 1 FROM public.saas_license_entitlements e JOIN public.saas_payment_intents p ON p.id=e.payment_intent_id "
                            "JOIN public.audit_events a ON a.tenant_id=e.tenant_id AND a.object_id=p.id::text "
                            "WHERE e.id=%s AND e.tenant_id=%s AND a.action='CI_SAAS_REFUND_REVOKED' "
                            "AND a.evidence_ref=p.provider_payment_id",(predecessor,tenant)).fetchone():
            raise LifecycleDenied("Estorno sem prova.")
    elif row[2] not in ("ACTIVE","EXPIRED") or row[6]!="APPROVED":
        raise LifecycleDenied("Período anterior indisponível para renovação.")
    if not ancestor:
        _assert_lineage(conn,tenant)
        leaves=conn.execute("SELECT e.id FROM public.saas_license_entitlements e WHERE e.tenant_id=%s "
                            "AND NOT EXISTS(SELECT 1 FROM public.fr_v23_renewals r WHERE r.tenant_id=e.tenant_id "
                            "AND r.predecessor=e.id AND r.entitlement_id IS NOT NULL AND r.canceled_at IS NULL)",(tenant,)).fetchall()
        if leaves!=[(predecessor,)]:raise LifecycleDenied("Predecessor não é a ponta única da cadeia.")
        if conn.execute("SELECT 1 FROM public.fr_v23_renewals r JOIN public.saas_payment_intents p ON p.id=r.intent_id "
                        "WHERE r.tenant_id=%s AND r.predecessor=%s AND r.canceled_at IS NOT NULL "
                        "AND (p.status<>'CANCELED' OR p.paid_at IS NOT NULL OR p.reconciled_at IS NOT NULL "
                        "OR NOT EXISTS(SELECT 1 FROM public.audit_events a WHERE a.tenant_id=r.tenant_id "
                        "AND a.action='CI_RENEWAL_EXPIRED_CANCELED' AND a.object_id=r.request_id::text "
                        "AND a.evidence_ref=p.provider_payment_id))",(tenant,predecessor)).fetchone():
            raise LifecycleDenied("Cancelamento anterior sem prova.")
        if conn.execute("SELECT 1 FROM public.saas_license_entitlements WHERE tenant_id=%s AND status='SUSPENDED'",(tenant,)).fetchone():
            raise LifecycleDenied("Suspensão exige revisão própria.")
    return row

def _term_base(conn,tenant,actor,prev,acceptance,now):
    """Follow only verified predecessors. Refunded time is never paid time."""
    visited=set()
    while prev[2]=="REVOKED":
        if prev[0] in visited or len(visited)>=50:raise LifecycleDenied("Histórico circular ou extenso.")
        visited.add(prev[0])
        parent=conn.execute("SELECT predecessor FROM public.fr_v23_renewals WHERE tenant_id=%s AND actor=%s "
                            "AND entitlement_id=%s AND canceled_at IS NULL",(tenant,actor,prev[0])).fetchone()
        if not parent:
            # Only an original checkout may lack a predecessor.
            if not conn.execute("SELECT 1 FROM public.saas_license_entitlements e JOIN public.saas_subscription_preparations s "
                                "ON s.id=e.preparation_id WHERE e.id=%s AND s.renewal_request_id IS NULL",(prev[0],)).fetchone():
                raise LifecycleDenied("Histórico sem predecessor.")
            if conn.execute("SELECT 1 FROM public.saas_license_entitlements WHERE tenant_id=%s AND status<>'REVOKED' AND valid_until>%s",
                            (tenant,now)).fetchone():raise LifecycleDenied("Existe período pago posterior.")
            return now,now.astimezone(ZONE).day
        prev=_previous(conn,tenant,actor,parent[0],acceptance,ancestor=True)
    if conn.execute("SELECT 1 FROM public.saas_license_entitlements WHERE tenant_id=%s AND id<>%s "
                    "AND valid_until>%s AND status<>'REVOKED'",(tenant,prev[0],prev[4])).fetchone():
        raise LifecycleDenied("Existe período posterior.")
    prior=conn.execute("SELECT anchor_day FROM public.fr_v23_renewals WHERE entitlement_id=%s",(prev[0],)).fetchone()
    return prev[4],prior[0] if prior else prev[3].astimezone(ZONE).day

def _renewal_tier(conn,tenant,actor,prev):
    """Resolve the next paid term from the verified lineage and immutable upgrade proof.

    Never rewrite the base tier. A refunded upgrade cannot change the tier of
    an independently paid successor. Unresolved evidence denies new billing.
    Caller holds the tenant transaction lock and verified predecessor.
    """
    row=conn.execute("SELECT r.request_id,r.actor,r.reviewer,r.evidence,r.evidence_hash,r.gross_cents,r.provider_payment_id,r.recorded_at,"
                     "q.snapshot,q.snapshot_hash,q.accepted_at,q.expires_at "
                     "FROM public.fr_v23_upgrade_settlement_reviews r JOIN public.fr_v23_plan_change_quotes q ON q.request_id=r.request_id "
                     "WHERE r.tenant_id=%s AND q.tenant_id=r.tenant_id AND q.actor=r.actor FOR SHARE OF r,q",(tenant,)).fetchone()
    if not row:
        if conn.execute("SELECT 1 FROM public.fr_v23_upgrade_settlement_reviews WHERE tenant_id=%s",(tenant,)).fetchone():
            raise LifecycleDenied("Histórico de upgrade incompatível.")
        return prev[1]
    req,payer,reviewer,evidence,settlement,gross,provider,recorded,snap,offer,accepted,expiry=row
    def digest(v):
        return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    def audit(action,by,proof):
        return bool(conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s "
                                 "AND action=%s AND object_id=%s AND evidence_ref=%s",(tenant,by,action,str(req),proof)).fetchone())
    if (payer!=actor or reviewer==actor or digest(evidence)!=settlement or digest(snap)!=offer
        or not accepted or not accepted<=recorded<expiry or snap.get("tenant_id")!=str(tenant) or snap.get("user_id")!=str(actor)
        or snap.get("current_tier")!="ESSENCIAL" or snap.get("target_tier")!="INTERMEDIARIO"
        or snap.get("decision")!="UPGRADE_REVIEW" or snap.get("total_cents")!=gross
        or evidence.get("gross")!=gross or evidence.get("provider_id")!=provider or evidence.get("offer_hash")!=offer
        or not audit("CI_PLAN_CHANGE_REVIEW_ACCEPTED",actor,offer) or not audit("CI_UPGRADE_SETTLEMENT_REVIEW",reviewer,settlement)):
        raise LifecycleDenied("Prova de upgrade incompatível.")
    app=conn.execute("SELECT tenant_id,actor,reviewer,offer_hash,settlement_hash,target_price_version,members_limit,quotas_limit,applied_at "
                     "FROM public.fr_v23_upgrade_applications WHERE request_id=%s FOR SHARE",(req,)).fetchone()
    lines=conn.execute("SELECT entitlement_id,period,period_start,period_end,base_price_version,paid_cents,target_cents,difference_cents "
                       "FROM public.fr_v23_upgrade_segments WHERE request_id=%s ORDER BY entitlement_id FOR SHARE",(req,)).fetchall()
    if app:
        expected=sorted((UUID(v["entitlement_id"]),v["period"],datetime.fromisoformat(v["period_start"]),
                         datetime.fromisoformat(v["period_end"]),UUID(v["price_version"]),v["paid_cents"],v["target_cents"],v["difference_cents"])
                        for v in snap["segments"])
        if (app[:5]!=(tenant,actor,reviewer,offer,settlement) or str(app[5])!=snap["target_price_version"]
            or app[6:8]!=(snap["members_limit"],snap["quotas_limit"]) or not recorded<=app[8]<expiry
            or not lines or lines!=expected or sum(v[-1] for v in lines)!=gross
            or not audit("CI_UPGRADE_APPLIED",reviewer,settlement)):
            raise LifecycleDenied("Aplicação de upgrade incompatível.")
    elif lines:
        raise LifecycleDenied("Segmentos sem aplicação.")
    refund=conn.execute("SELECT tenant_id,reviewer,settlement_hash,refunded_cents,evidence,evidence_hash,recorded_at "
                        "FROM public.fr_v23_upgrade_refunds WHERE request_id=%s FOR SHARE",(req,)).fetchone()
    if refund:
        expected=dict(settlement_hash=settlement,provider_id=provider,refunded_cents=gross,
                      reference=f"saas-upgrade-review:{req}",collector=COLLECTOR_CI,currency="BRL",live_mode=False,had_application=bool(app))
        if (refund[:4]!=(tenant,reviewer,settlement,gross) or refund[4]!=expected or digest(expected)!=refund[5]
            or refund[6]<(app[8] if app else recorded) or not audit("CI_UPGRADE_REFUNDED",reviewer,refund[5])):
            raise LifecycleDenied("Estorno de upgrade incompatível.")
        return prev[1]
    if not app:
        raise LifecycleDenied("Alteração de plano em revisão de liquidação.")
    covered=next((v for v in lines if v[0]==prev[0]),None)
    if covered:
        if prev[1]!="ESSENCIAL" or prev[2]=="REVOKED" or covered[2:4]!=prev[3:5]:
            raise LifecycleDenied("Período base do upgrade exige revisão.")
        # Bind the selected historical segment to its original paid price.
        original=conn.execute("SELECT s.billing_period,s.price_version_id,p.expected_amount_cents "
                              "FROM public.saas_license_entitlements e JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id "
                              "JOIN public.saas_payment_intents p ON p.id=e.payment_intent_id WHERE e.id=%s AND e.tenant_id=%s",
                              (prev[0],tenant)).fetchone()
        if original!=(covered[1],covered[4],covered[5]):
            raise LifecycleDenied("Preço base incompatível.")
        return "INTERMEDIARIO"
    if prev[1]!="INTERMEDIARIO":
        raise LifecycleDenied("Sucessor do upgrade exige revisão.")
    return prev[1]


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
        tier=_renewal_tier(conn,tenant,actor,prev)
        _term_base(conn,tenant,actor,prev,acceptance,conn.execute("SELECT clock_timestamp()").fetchone()[0])
        if conn.execute("SELECT 1 FROM public.fr_v23_renewals WHERE predecessor=%s AND canceled_at IS NULL",(predecessor,)).fetchone():
            raise LifecycleDenied("Renovação anterior já registrada.")
        price=conn.execute(
            "SELECT v.id,v.monthly_price,v.annual_price FROM public.platform_license_price_versions v "
            "JOIN public.platform_license_plans p ON p.tier=v.plan_tier "
            "WHERE p.tier=%s AND p.status='ACTIVE' AND p.tier<>'AMPLIADO' ORDER BY v.created_at DESC,v.id DESC LIMIT 1 FOR SHARE OF v,p",
            (tier,)).fetchone()
        if not price or price[0]!=price_version or _cents(price[1] if period=="MONTHLY" else price[2])!=cents:
            raise LifecycleDenied("Oferta substituída ou preço incorreto.")
        prep=uuid4()
        conn.execute("INSERT INTO public.saas_subscription_preparations "
                     "(id,tenant_id,admin_user_id,plan_tier,price_version_id,billing_period,contract_acceptance_id,renewal_request_id) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(prep,tenant,actor,tier,price_version,period,acceptance,request_id))
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
        if _review_exists(conn,tenant,intent):raise LifecycleDenied("Pagamento em revisão independente.")
        now=conn.execute("SELECT clock_timestamp()").fetchone()[0]
        if now>=expiry:raise LifecycleDenied("Oferta expirada; conciliação em revisão.")
        prev=_previous(conn,tenant,actor,previous,acceptance)
        if _renewal_tier(conn,tenant,actor,prev)!=tier:
            raise LifecycleDenied("Plano alterado após aceite: pagamento exige revisão independente.")
        base,anchor=_term_base(conn,tenant,actor,prev,acceptance,now)
        start,end,anchor=renewal_term(base,anchor,now,period)
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


def cancel_expired_renewal_ci(conn,*,reviewer_token,reviewer_tenant,tenant,intent,payment,statement_settled_cents):
    """CI only: a terminal canceled PSP record plus independent zero settlement.
    An expired or missing response alone never authorizes a new charge.
    """
    _guard(conn)
    if type(statement_settled_cents) is not int or statement_settled_cents!=0 or type(payment) is not dict or payment.get("status")!="cancelled":
        raise LifecycleDenied("Cancelamento sem prova de não liquidação.")
    if payment.get("transaction_amount_refunded") not in ("0","0.00",0) or type(payment.get("transaction_amount_refunded")) not in (str,int):
        raise LifecycleDenied("Cancelamento incompatível.")
    with conn.transaction():
        _lock(conn,tenant)
        row=conn.execute(
            "SELECT r.actor,r.request_id,r.expires_at,r.canceled_at,r.entitlement_id,r.cents,p.status,p.provider_payment_id,"
            "p.external_reference,p.paid_at,p.reconciled_at,s.contract_acceptance_id "
            "FROM public.fr_v23_renewals r JOIN public.saas_payment_intents p ON p.id=r.intent_id AND p.preparation_id=r.preparation_id "
            "JOIN public.saas_subscription_preparations s ON s.id=r.preparation_id AND s.renewal_request_id=r.request_id "
            "WHERE r.tenant_id=%s AND r.intent_id=%s AND p.tenant_id=r.tenant_id AND s.tenant_id=r.tenant_id "
            "AND p.admin_user_id=r.actor AND s.admin_user_id=r.actor AND p.price_version_id=r.price_version "
            "AND s.price_version_id=r.price_version AND s.billing_period=r.period AND p.expected_amount_cents=r.cents "
            "AND p.live_mode=false AND p.platform_collector_id=%s AND p.provider='MERCADO_PAGO' AND p.currency='BRL' "
            "AND s.status='PENDING_PAYMENT' FOR UPDATE OF r,p,s",(tenant,intent,COLLECTOR_CI)).fetchone()
        if not row:raise LifecycleDenied("Renovação fora do escopo.")
        actor,request,expiry,canceled,ent,cents,state,stored,ref,paid,reconciled,acceptance=row
        reviewer=_reviewer(conn,reviewer_token,reviewer_tenant,tenant,actor)
        if _binding(conn,actor,tenant)!=(acceptance,"ATIVO") or ent is not None or paid is not None or reconciled is not None:
            raise LifecycleDenied("Pagamento já constituído ou vínculo inválido.")
        now=conn.execute("SELECT clock_timestamp()").fetchone()[0]
        provider_id=str(payment.get("id",""))
        if (now<expiry or not provider_id.isascii() or not provider_id.isdecimal() or len(provider_id)>40
            or not matches_approved_payment(ExpectedPayment(stored or provider_id,COLLECTOR_CI,ref,cents,False),{**payment,"status":"approved"})):
            raise LifecycleDenied("Prova de cancelamento incompatível.")
        if state=="CANCELED" and canceled and stored==provider_id:
            if conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND action='CI_RENEWAL_EXPIRED_CANCELED' "
                            "AND object_id=%s AND evidence_ref=%s",(tenant,str(request),provider_id)).fetchone():return request
            raise LifecycleDenied("Cancelamento sem trilha.")
        if state!="PENDING" or canceled or _review_exists(conn,tenant,intent):raise LifecycleDenied("Estado incompatível ou pagamento em revisão.")
        if stored is None and not attach_mp_payment_identifier_ci(conn,intent_id=intent,provider_payment_id=provider_id):
            raise LifecycleDenied("Vínculo de pagamento indisponível.")
        conn.execute("UPDATE public.saas_payment_intents SET status='CANCELED' WHERE id=%s",(intent,))
        conn.execute("UPDATE public.fr_v23_renewals SET canceled_at=%s WHERE request_id=%s",(now,request))
        _audit(conn,reviewer,"SYSTEM",tenant,"CI_RENEWAL_EXPIRED_CANCELED",request,provider_id)
        return request



def record_renewal_payment_review_ci(conn,*,reviewer_token,reviewer_tenant,tenant,intent,payment,gross,fee,net):
    """Persist verified synthetic receipt anomalies without granting or moving money.

    Only a pending, scoped offer may enter this review. Exact replays return the
    same classification. A contradictory later observation cannot clear it.
    """
    _guard(conn)
    if (type(payment) is not dict or any(type(x) is not int for x in (gross,fee,net))
        or not 0<=fee<gross<=100000000 or net!=gross-fee
        or type(payment.get("transaction_amount_refunded")) not in (str,int)
        or payment["transaction_amount_refunded"] not in ("0","0.00",0)):
        raise LifecycleDenied("Extrato de revisão incompatível.")
    with conn.transaction():
        _lock(conn,tenant)
        row=conn.execute(
            "SELECT r.actor,r.request_id,r.cents,r.expires_at,r.entitlement_id,r.canceled_at,"
            "p.status,p.provider_payment_id,p.external_reference,p.paid_at,p.reconciled_at,s.contract_acceptance_id,r.predecessor,s.plan_tier "
            "FROM public.fr_v23_renewals r JOIN public.saas_payment_intents p ON p.id=r.intent_id AND p.preparation_id=r.preparation_id "
            "JOIN public.saas_subscription_preparations s ON s.id=r.preparation_id AND s.renewal_request_id=r.request_id "
            "JOIN public.platform_license_price_versions v ON v.id=r.price_version AND v.plan_tier=s.plan_tier "
            "WHERE r.tenant_id=%s AND r.intent_id=%s AND p.tenant_id=r.tenant_id AND s.tenant_id=r.tenant_id "
            "AND p.admin_user_id=r.actor AND s.admin_user_id=r.actor AND p.price_version_id=r.price_version "
            "AND s.price_version_id=r.price_version AND s.billing_period=r.period AND p.expected_amount_cents=r.cents "
            "AND r.cents=(CASE r.period WHEN 'MONTHLY' THEN v.monthly_price ELSE v.annual_price END)*100 "
            "AND p.live_mode=false AND p.platform_collector_id=%s AND p.provider='MERCADO_PAGO' AND p.currency='BRL' "
            "AND s.status='PENDING_PAYMENT' FOR UPDATE OF r,p,s FOR SHARE OF v",(tenant,intent,COLLECTOR_CI)).fetchone()
        if not row:raise LifecycleDenied("Pagamento fora do escopo.")
        actor,request,cents,expiry,ent,canceled,state,stored,ref,paid,reconciled,acceptance,previous,tier=row
        reviewer=_reviewer(conn,reviewer_token,reviewer_tenant,tenant,actor)
        if (_binding(conn,actor,tenant)!=(acceptance,"ATIVO") or state!="PENDING"
            or any(x is not None for x in (ent,canceled,paid,reconciled))):
            raise LifecycleDenied("Pagamento já decidido ou vínculo inválido.")
        provider_id=str(payment.get("id",""))
        if (not provider_id.isascii() or not provider_id.isdecimal() or len(provider_id)>40
            or not matches_approved_payment(ExpectedPayment(stored or provider_id,COLLECTOR_CI,ref,gross,False),payment)):
            raise LifecycleDenied("Recebimento sem prova independente compatível.")
        # No raw PSP payload, personal data, credentials or client-supplied audit.
        evidence=f"{provider_id}:{gross}:{fee}:{net}:{cents}"
        saved=conn.execute("SELECT action,evidence_ref FROM public.audit_events WHERE tenant_id=%s AND object_id=%s "
                           "AND object_type='SAAS_PAYMENT' AND action IN ('CI_RENEWAL_LATE_PAYMENT_REVIEW','CI_RENEWAL_AMOUNT_REVIEW','CI_RENEWAL_TIER_REVIEW')",
                           (tenant,str(intent))).fetchall()
        if saved:
            if len(saved)==1 and stored==provider_id and saved[0][1]==evidence:return saved[0][0]
            raise LifecycleDenied("Evidência divergente da revisão registrada.")
        now=conn.execute("SELECT clock_timestamp()").fetchone()[0]
        if gross!=cents:action="CI_RENEWAL_AMOUNT_REVIEW"
        elif now>=expiry:action="CI_RENEWAL_LATE_PAYMENT_REVIEW"
        else:
            prev=_previous(conn,tenant,actor,previous,acceptance)
            if _renewal_tier(conn,tenant,actor,prev)==tier:
                raise LifecycleDenied("Recebimento regular deve seguir conciliação própria.")
            action="CI_RENEWAL_TIER_REVIEW"
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s::text,41510))",(provider_id,))
        if conn.execute("SELECT 1 FROM public.saas_payment_intents WHERE provider_payment_id=%s AND id<>%s",
                        (provider_id,intent)).fetchone():
            raise LifecycleDenied("Identificador de pagamento já vinculado.")
        if stored is None and not attach_mp_payment_identifier_ci(conn,intent_id=intent,provider_payment_id=provider_id):
            raise LifecycleDenied("Vínculo de pagamento indisponível.")
        conn.execute("INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref) "
                     "VALUES(%s,'SYSTEM',%s,%s,'SAAS_PAYMENT',%s,'Recebimento sintético M41510; revisão sem licença ou cobrança',%s)",
                     (reviewer,tenant,action,str(intent),evidence))
        return action
