"""M41520: frozen synthetic plan-change review; never a charge or entitlement."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP,localcontext
from hashlib import sha256
import json
from uuid import UUID
from psycopg.types.json import Jsonb
from .account_lifecycle import LifecycleDenied
from .saas_renewal_readback_ci import renewal_overview_ci
from .saas_renewal_v23_ci import _lock,_reviewer
from .mercado_pago_safety import ExpectedPayment,matches_approved_payment,matches_full_refund
from .admin_license_onboarding_ci import COLLECTOR_CI
from .saas_billing_ci import _cents
from .admin_license_onboarding_ci import _audit

RANK={"ESSENCIAL":1,"INTERMEDIARIO":2}
MAX_CENTS=100000000

def _instant(v):
    if type(v) is not datetime or v.tzinfo is None or v.utcoffset() is None:
        raise LifecycleDenied("Instante sem fuso.")
    return v.astimezone(timezone.utc)

def _micros(delta):
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds

def prorata_cents(old,new,start,end,calculated_at):
    """Round each disclosed segment once, half up; never charge elapsed time."""
    if any(type(v) is not int or not 0<v<=MAX_CENTS for v in (old,new)):
        raise LifecycleDenied("Preço inválido.")
    start,end,at=map(_instant,(start,end,calculated_at))
    total=_micros(end-start)
    if total<=0:raise LifecycleDenied("Período inválido.")
    remaining=max(0,_micros(end-max(start,at)))
    with localcontext() as ctx:
        ctx.prec=80
        return int((Decimal(max(0,new-old))*Decimal(remaining)/Decimal(total)).quantize(Decimal("1"),rounding=ROUND_HALF_UP))

def _hash(snapshot):
    return sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

def _stamp(t):
    return _instant(t).isoformat(timespec="microseconds")

def _capacity(conn,tenant):
    # Same conservative active/open-obligation fence as fr_v23_admit; pending
    # invitations alone never consume a place under V2.3 3.4.
    members=conn.execute(
        "SELECT count(*) FROM (SELECT m.id FROM public.memberships m WHERE m.tenant_id=%s "
        "AND m.role='TENANT_MEMBER' AND m.status='ATIVA' UNION SELECT a.membership_id "
        "FROM public.fr_v23_admission a JOIN public.cycles c ON c.id=a.cycle_id "
        "WHERE c.tenant_id=%s AND c.status<>'LIQUIDADO') u",(tenant,tenant)).fetchone()[0]
    quotas=conn.execute("SELECT (SELECT count(*) FROM public.quotas WHERE tenant_id=%s AND status='ATIVA') "
                       "+(SELECT coalesce(sum(a.quotas),0) FROM public.fr_v23_admission a "
                       "JOIN public.cycles c ON c.id=a.cycle_id WHERE c.tenant_id=%s AND c.status<>'LIQUIDADO')",
                       (tenant,tenant)).fetchone()[0]
    return members,quotas

def _decision(current,target,members,quotas,ml,ql,total):
    if current not in RANK or target not in RANK or current==target:
        raise LifecycleDenied("Plano indisponível.")
    if members>ml or quotas>ql:return "CAPACITY_REVIEW"
    if RANK[target]<RANK[current]:return "DOWNGRADE_NEXT_RENEWAL"
    return "UPGRADE_REVIEW" if total>0 else "ZERO_DIFFERENCE_REVIEW"

def _snapshot(conn,token,tenant,target,at=None,*,settlement_review=False):
    _lock(conn,tenant)
    if target not in RANK:raise LifecycleDenied("Plano comercial indisponível.")
    view=renewal_overview_ci(conn,token=token,tenant=tenant)
    now=_instant(view["observed_at"])
    at=now if at is None else _instant(at)
    if at>now or view["access"]!="CURRENT" or (view["offer"] is None and not settlement_review):
        raise LifecycleDenied("Vigência ou ação pendente exige revisão.")
    if settlement_review and view.get("upgrade",{}).get("state")!="SETTLEMENT_REVIEW":
        raise LifecycleDenied("Revisão de liquidação indisponível.")
    if any(x["state"] in ("PENDING","REVIEW_REQUIRED","PAYMENT_REVIEW") for x in view["renewals"]):
        raise LifecycleDenied("Pagamento pendente.")
    current=next(x for x in view["segments"] if x["state"]=="CURRENT")
    old=current["tier"]
    if old==target or old not in RANK:raise LifecycleDenied("Plano incompatível.")
    plan=conn.execute("SELECT v.id,p.members_limit,p.quotas_limit,v.monthly_price,v.annual_price "
                      "FROM public.platform_license_plans p JOIN public.platform_license_price_versions v ON v.plan_tier=p.tier "
                      "WHERE p.tier=%s AND p.status='ACTIVE' ORDER BY v.created_at DESC,v.id DESC LIMIT 1 FOR SHARE OF p,v",
                      (target,)).fetchone()
    if not plan or any(type(n) is not int or not 0<n<=400 for n in plan[1:3]):
        raise LifecycleDenied("Catálogo incompatível.")
    members,quotas=_capacity(conn,tenant)
    lines=[]
    eligible=[x for x in view["segments"] if x["state"] in ("CURRENT","SCHEDULED")]
    if any(x["tier"]!=old for x in eligible):
        raise LifecycleDenied("Mudanças históricas de capacidade exigem revisão.")
    for x in sorted(eligible,key=lambda x:(x["valid_from"],str(x["entitlement_id"]))):
        if x["valid_until"]<=at:raise LifecycleDenied("Fotografia fora da vigência.")
        old_price=conn.execute("SELECT price_version_id FROM public.saas_subscription_preparations s "
                               "JOIN public.saas_license_entitlements e ON e.preparation_id=s.id "
                               "WHERE e.id=%s AND e.tenant_id=%s AND s.tenant_id=e.tenant_id FOR SHARE OF s",
                               (x["entitlement_id"],tenant)).fetchone()
        if not old_price:raise LifecycleDenied("Preço histórico indisponível.")
        target_cents=_cents(plan[3] if x["period"]=="MONTHLY" else plan[4])
        amount=prorata_cents(x["cents"],target_cents,x["valid_from"],x["valid_until"],at) if RANK[target]>RANK[old] else 0
        lines.append(dict(entitlement_id=str(x["entitlement_id"]),price_version=str(old_price[0]),period=x["period"],
                          period_start=_stamp(x["valid_from"]),period_end=_stamp(x["valid_until"]),
                          paid_cents=x["cents"],target_cents=target_cents,difference_cents=amount))
    total=sum(x["difference_cents"] for x in lines)
    if total>MAX_CENTS:raise LifecycleDenied("Valor exige revisão.")
    doc=view["document"]
    return dict(user_id=str(view["user_id"]),tenant_id=str(tenant),role="TENANT_ADMIN",ci_only=True,
                production_authorized=False,real_payment_authorized=False,
                current_tier=old,target_tier=target,target_price_version=str(plan[0]),
                document_id=str(doc["document_id"]),document_hash=doc["document_hash"],
                calculated_at=_stamp(at),expires_at=_stamp(at+timedelta(minutes=15)),
                members_in_use=members,quotas_in_use=quotas,members_limit=plan[1],quotas_limit=plan[2],
                decision=_decision(old,target,members,quotas,plan[1],plan[2],total),
                total_cents=total,segments=lines)

def plan_change_preview_ci(conn,*,token,tenant,target):
    with conn.transaction():
        snapshot=_snapshot(conn,token,tenant,target)
        return dict(snapshot=snapshot,offer_hash=_hash(snapshot))

def freeze_plan_change_ci(conn,*,token,tenant,target,request_id):
    if type(request_id) is not UUID or not request_id.int:raise LifecycleDenied("Pedido inválido.")
    with conn.transaction():
        _lock(conn,tenant)
        from .admin_license_onboarding_ci import _session
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant)
        row=conn.execute("SELECT tenant_id,actor,snapshot,snapshot_hash,accepted_at FROM public.fr_v23_plan_change_quotes "
                         "WHERE request_id=%s FOR UPDATE",(request_id,)).fetchone()
        if row:
            if row[:2]!=(tenant,actor) or row[2]["target_tier"]!=target or _hash(row[2])!=row[3]:
                raise LifecycleDenied("Colisão de oferta.")
            return dict(request_id=str(request_id),snapshot=row[2],offer_hash=row[3],accepted=row[4] is not None)
        snap=_snapshot(conn,token,tenant,target)
        digest=_hash(snap)
        conn.execute("INSERT INTO public.fr_v23_plan_change_quotes(request_id,tenant_id,actor,snapshot,snapshot_hash,calculated_at,expires_at) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s)",(request_id,tenant,actor,Jsonb(snap),digest,
                     datetime.fromisoformat(snap["calculated_at"]),datetime.fromisoformat(snap["expires_at"])))
        return dict(request_id=str(request_id),snapshot=snap,offer_hash=digest,accepted=False)

def accept_plan_change_ci(conn,*,token,tenant,request_id,offer_hash,document_id,document_hash,accepted):
    if accepted is not True or type(request_id) is not UUID or type(document_id) is not UUID:
        raise LifecycleDenied("Aceite inválido.")
    with conn.transaction():
        _lock(conn,tenant)
        from .admin_license_onboarding_ci import _session
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant)
        row=conn.execute("SELECT snapshot,snapshot_hash,calculated_at,expires_at,accepted_at FROM public.fr_v23_plan_change_quotes "
                         "WHERE request_id=%s AND tenant_id=%s AND actor=%s FOR UPDATE",(request_id,tenant,actor)).fetchone()
        if not row:raise LifecycleDenied("Oferta indisponível.")
        snap,digest,at,expiry,saved=row
        if (_hash(snap)!=digest or offer_hash!=digest or snap["document_id"]!=str(document_id)
            or snap["calculated_at"]!=_stamp(at) or snap["expires_at"]!=_stamp(expiry)
            or snap["user_id"]!=str(actor) or snap["tenant_id"]!=str(tenant)
            or snap["document_hash"]!=document_hash or snap["decision"] not in ("UPGRADE_REVIEW","DOWNGRADE_NEXT_RENEWAL")):
            raise LifecycleDenied("Oferta ou instrumento incompatível.")
        if saved is not None:
            if not conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s "
                                "AND action='CI_PLAN_CHANGE_REVIEW_ACCEPTED' AND object_id=%s AND evidence_ref=%s",
                                (tenant,actor,str(request_id),digest)).fetchone():raise LifecycleDenied("Aceite sem trilha.")
            return dict(request_id=str(request_id),offer_hash=digest,accepted=True,real_payment_authorized=False)
        if conn.execute("SELECT clock_timestamp()").fetchone()[0]>=expiry:
            raise LifecycleDenied("Oferta expirada: recalcular e aceitar novamente.")
        if _snapshot(conn,token,tenant,snap["target_tier"],at)!=snap:
            raise LifecycleDenied("Oferta alterada: recalcular e aceitar novamente.")
        conn.execute("UPDATE public.fr_v23_plan_change_quotes SET accepted_at=clock_timestamp() WHERE request_id=%s",(request_id,))
        _audit(conn,actor,"TENANT_ADMIN",tenant,"CI_PLAN_CHANGE_REVIEW_ACCEPTED",request_id,digest)
        return dict(request_id=str(request_id),offer_hash=digest,accepted=True,real_payment_authorized=False)


# M41530: a synthetic settlement evidence receipt, NOT a paid upgrade.
def record_upgrade_settlement_review_ci(conn,*,token,reviewer_token,reviewer_tenant,tenant,request_id,offer_hash,payment,gross,fee,net):
    if any(type(x) is not UUID or not x.int for x in (tenant,reviewer_tenant,request_id)):
        raise LifecycleDenied("Escopo inválido.")
    if type(payment) is not dict or any(type(x) is not int for x in (gross,fee,net)) or not 0<=fee<gross<=MAX_CENTS or net!=gross-fee:
        raise LifecycleDenied("Extrato sintético incompatível.")
    if type(payment.get("transaction_amount_refunded")) not in (str,int) or payment["transaction_amount_refunded"] not in ("0","0.00",0):
        raise LifecycleDenied("Pagamento revertido.")
    provider_id=str(payment.get("id",""))
    if not provider_id.isascii() or not provider_id.isdecimal() or len(provider_id)>40:
        raise LifecycleDenied("Identificador inválido.")
    with conn.transaction():
        _lock(conn,tenant)
        from .admin_license_onboarding_ci import _session
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant)
        reviewer=_reviewer(conn,reviewer_token,reviewer_tenant,tenant,actor)
        row=conn.execute("SELECT snapshot,snapshot_hash,calculated_at,expires_at,accepted_at FROM public.fr_v23_plan_change_quotes "
                         "WHERE request_id=%s AND tenant_id=%s AND actor=%s FOR UPDATE",(request_id,tenant,actor)).fetchone()
        if not row:raise LifecycleDenied("Oferta indisponível.")
        snap,digest,at,expiry,accepted_at=row
        if (accepted_at is None or _hash(snap)!=digest or offer_hash!=digest or snap["decision"]!="UPGRADE_REVIEW"
            or snap["tenant_id"]!=str(tenant) or snap["user_id"]!=str(actor) or snap["calculated_at"]!=_stamp(at)
            or snap["expires_at"]!=_stamp(expiry) or not at<=accepted_at<expiry or snap["total_cents"]!=gross
            or not conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s "
                                "AND action='CI_PLAN_CHANGE_REVIEW_ACCEPTED' AND object_id=%s AND evidence_ref=%s",
                                (tenant,actor,str(request_id),digest)).fetchone()):
            raise LifecycleDenied("Oferta ou aceite incompatível.")
        # Separate reference namespace; no generic renewal/checkout can consume it.
        reference=f"saas-upgrade-review:{request_id}"
        if not matches_approved_payment(ExpectedPayment(provider_id,COLLECTOR_CI,reference,gross,False),payment):
            raise LifecycleDenied("Pagamento não confere.")
        evidence=dict(offer_hash=digest,provider_id=provider_id,collector=COLLECTOR_CI,reference=reference,
                      gross=gross,fee=fee,net=net,currency="BRL",live_mode=False)
        proof=_hash(evidence)
        saved=conn.execute("SELECT request_id,actor,reviewer,provider_payment_id,evidence_hash FROM public.fr_v23_upgrade_settlement_reviews "
                           "WHERE tenant_id=%s FOR UPDATE",(tenant,)).fetchone()
        if saved:
            if conn.execute("SELECT 1 FROM public.fr_v23_upgrade_refunds WHERE request_id=%s",(request_id,)).fetchone():
                raise LifecycleDenied("Upgrade estornado.")
            if saved!=(request_id,actor,reviewer,provider_id,proof) or not conn.execute(
                "SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s "
                "AND action='CI_UPGRADE_SETTLEMENT_REVIEW' AND object_id=%s AND evidence_ref=%s",
                (tenant,reviewer,str(request_id),proof)).fetchone():
                raise LifecycleDenied("Liquidação em revisão ou colisão.")
        else:
            now=conn.execute("SELECT clock_timestamp()").fetchone()[0]
            if now>=expiry or _snapshot(conn,token,tenant,snap["target_tier"],at)!=snap:
                raise LifecycleDenied("Oferta expirada ou alterada; revisão separada necessária.")
            if conn.execute("SELECT 1 FROM public.saas_payment_intents WHERE provider_payment_id=%s",(provider_id,)).fetchone():
                raise LifecycleDenied("Identificador já usado em outra cobrança.")
            conn.execute("INSERT INTO public.fr_v23_upgrade_settlement_reviews "
                         "(request_id,tenant_id,actor,reviewer,provider_payment_id,evidence,evidence_hash,gross_cents,fee_cents,net_cents) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                         (request_id,tenant,actor,reviewer,provider_id,Jsonb(evidence),proof,gross,fee,net))
            _audit(conn,reviewer,"SYSTEM",tenant,"CI_UPGRADE_SETTLEMENT_REVIEW",request_id,proof)
        return dict(request_id=str(request_id),evidence_hash=proof,state="SETTLEMENT_REVIEW",
                    entitlement_applied=False,real_payment_authorized=False)


def apply_reviewed_upgrade_ci(conn,*,token,reviewer_token,reviewer_tenant,tenant,request_id,offer_hash,evidence_hash):
    """M41540: atomic synthetic capacity overlay, never a new paid term or payment."""
    if any(type(x) is not UUID or not x.int for x in (tenant,reviewer_tenant,request_id)):
        raise LifecycleDenied("Escopo inválido.")
    with conn.transaction():
        _lock(conn,tenant)
        from .admin_license_onboarding_ci import _session
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant)
        reviewer=_reviewer(conn,reviewer_token,reviewer_tenant,tenant,actor)
        row=conn.execute("SELECT q.snapshot,q.snapshot_hash,q.calculated_at,q.expires_at,q.accepted_at,"
                         "r.evidence,r.evidence_hash,r.gross_cents,r.reviewer,r.provider_payment_id,r.recorded_at "
                         "FROM public.fr_v23_plan_change_quotes q JOIN public.fr_v23_upgrade_settlement_reviews r ON r.request_id=q.request_id "
                         "WHERE q.request_id=%s AND q.tenant_id=%s AND r.tenant_id=q.tenant_id AND q.actor=%s AND r.actor=q.actor FOR UPDATE OF q,r",
                         (request_id,tenant,actor)).fetchone()
        if not row:raise LifecycleDenied("Liquidação em revisão indisponível.")
        snap,digest,at,expiry,accepted,evidence,proof,gross,original_reviewer,provider_id,recorded=row
        if (digest!=offer_hash or proof!=evidence_hash or _hash(snap)!=digest or _hash(evidence)!=proof
            or evidence.get("offer_hash")!=digest or evidence.get("provider_id")!=provider_id or evidence.get("gross")!=gross
            or snap.get("total_cents")!=gross or not 0<gross<=MAX_CENTS or original_reviewer!=reviewer
            or snap.get("current_tier")!="ESSENCIAL" or snap.get("target_tier")!="INTERMEDIARIO" or snap.get("decision")!="UPGRADE_REVIEW"
            or accepted is None or not at<=accepted<=recorded<expiry
            or not conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s "
                                "AND action='CI_UPGRADE_SETTLEMENT_REVIEW' AND object_id=%s AND evidence_ref=%s",
                                (tenant,reviewer,str(request_id),proof)).fetchone()
            or not conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s "
                                "AND action='CI_PLAN_CHANGE_REVIEW_ACCEPTED' AND object_id=%s AND evidence_ref=%s",
                                (tenant,actor,str(request_id),digest)).fetchone()):
            raise LifecycleDenied("Prova de liquidação incompatível.")
        if conn.execute("SELECT 1 FROM public.fr_v23_upgrade_refunds WHERE request_id=%s",(request_id,)).fetchone():
            raise LifecycleDenied("Upgrade estornado.")
        lines=snap["segments"]
        if not 1<=len(lines)<=50 or len({v["entitlement_id"] for v in lines})!=len(lines) or sum(v["difference_cents"] for v in lines)!=gross:
            raise LifecycleDenied("Segmentos incompatíveis.")
        expected=sorted((UUID(v["entitlement_id"]),v["period"],datetime.fromisoformat(v["period_start"]),
                         datetime.fromisoformat(v["period_end"]),UUID(v["price_version"]),v["paid_cents"],
                         v["target_cents"],v["difference_cents"]) for v in lines)
        existing=conn.execute("SELECT entitlement_id,period,period_start,period_end,base_price_version,paid_cents,target_cents,difference_cents "
                              "FROM public.fr_v23_upgrade_segments WHERE request_id=%s ORDER BY entitlement_id",(request_id,)).fetchall()
        applied=conn.execute("SELECT offer_hash,settlement_hash,reviewer FROM public.fr_v23_upgrade_applications WHERE request_id=%s AND tenant_id=%s",
                             (request_id,tenant)).fetchone()
        if applied:
            if applied!=(digest,proof,reviewer) or existing!=expected or not conn.execute(
                "SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s AND action='CI_UPGRADE_APPLIED' AND object_id=%s AND evidence_ref=%s",
                (tenant,reviewer,str(request_id),proof)).fetchone():
                raise LifecycleDenied("Histórico de upgrade incompleto.")
        else:
            # The review receipt suppresses new offers. Recompute the frozen
            # inputs under the same tenant lock, not a new commercial offer.
            if existing or conn.execute("SELECT clock_timestamp()").fetchone()[0]>=expiry or _snapshot(
                conn,token,tenant,snap["target_tier"],at,settlement_review=True)!=snap:
                raise LifecycleDenied("Alteração ou prazo exige nova revisão.")
            old_limits=conn.execute("SELECT members_limit,quotas_limit FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
            if snap["members_limit"]<old_limits[0] or snap["quotas_limit"]<old_limits[1]:
                raise LifecycleDenied("Upgrade não pode reduzir capacidade adquirida.")
            conn.execute("INSERT INTO public.fr_v23_upgrade_applications(request_id,tenant_id,actor,reviewer,offer_hash,settlement_hash,target_price_version,members_limit,quotas_limit) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                         (request_id,tenant,actor,reviewer,digest,proof,UUID(snap["target_price_version"]),snap["members_limit"],snap["quotas_limit"]))
            for line in expected:
                conn.execute("INSERT INTO public.fr_v23_upgrade_segments(request_id,entitlement_id,period,period_start,period_end,base_price_version,paid_cents,target_cents,difference_cents) "
                             "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(request_id,*line))
            _audit(conn,reviewer,"SYSTEM",tenant,"CI_UPGRADE_APPLIED",request_id,proof)
            if conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()!=(snap["members_limit"],snap["quotas_limit"]):
                raise LifecycleDenied("Capacidade efetiva incompatível.")
        return dict(request_id=str(request_id),state="CI_APPLIED",segments=len(expected),difference_cents=gross,
                    real_payment_authorized=False,production_authorized=False)


def reconcile_upgrade_refund_ci(conn,*,reviewer_token,reviewer_tenant,tenant,request_id,payment,statement_refunded_cents):
    """M41550: verified full synthetic refund, before or after application.
    Preserve the paid base and obligations. Partial refunds need separate policy.
    """
    if any(type(x) is not UUID or not x.int for x in (tenant,reviewer_tenant,request_id)):
        raise LifecycleDenied("Escopo inválido.")
    if type(payment) is not dict or type(statement_refunded_cents) is not int or not 0<statement_refunded_cents<=MAX_CENTS:
        raise LifecycleDenied("Extrato de estorno incompatível.")
    with conn.transaction():
        _lock(conn,tenant)
        row=conn.execute("SELECT r.actor,r.reviewer,r.provider_payment_id,r.gross_cents,r.evidence,r.evidence_hash,q.snapshot,q.snapshot_hash "
                         "FROM public.fr_v23_upgrade_settlement_reviews r JOIN public.fr_v23_plan_change_quotes q ON q.request_id=r.request_id "
                         "WHERE r.request_id=%s AND r.tenant_id=%s AND q.tenant_id=r.tenant_id AND q.actor=r.actor AND q.accepted_at IS NOT NULL "
                         "FOR UPDATE OF q,r",(request_id,tenant)).fetchone()
        if not row:raise LifecycleDenied("Revisão de liquidação indisponível.")
        actor,original_reviewer,provider_id,gross,evidence,settlement_hash,snapshot,offer_hash=row
        reviewer=_reviewer(conn,reviewer_token,reviewer_tenant,tenant,actor)
        if (reviewer!=original_reviewer or gross!=statement_refunded_cents or _hash(evidence)!=settlement_hash
            or _hash(snapshot)!=offer_hash or evidence.get("offer_hash")!=offer_hash or evidence.get("provider_id")!=provider_id
            or evidence.get("gross")!=gross or snapshot.get("total_cents")!=gross
            or not matches_full_refund(ExpectedPayment(provider_id,COLLECTOR_CI,f"saas-upgrade-review:{request_id}",gross,False),payment)
            or not conn.execute("SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s "
                                "AND action='CI_UPGRADE_SETTLEMENT_REVIEW' AND object_id=%s AND evidence_ref=%s",
                                (tenant,reviewer,str(request_id),settlement_hash)).fetchone()):
            raise LifecycleDenied("Estorno não confere.")
        applied=conn.execute("SELECT 1 FROM public.fr_v23_upgrade_applications WHERE request_id=%s AND tenant_id=%s",(request_id,tenant)).fetchone()
        refund=dict(settlement_hash=settlement_hash,provider_id=provider_id,refunded_cents=gross,
                    reference=f"saas-upgrade-review:{request_id}",collector=COLLECTOR_CI,currency="BRL",live_mode=False,
                    had_application=bool(applied))
        proof=_hash(refund)
        saved=conn.execute("SELECT reviewer,evidence_hash,evidence FROM public.fr_v23_upgrade_refunds WHERE request_id=%s AND tenant_id=%s",
                           (request_id,tenant)).fetchone()
        if saved:
            if saved!=(reviewer,proof,refund) or not conn.execute(
                "SELECT 1 FROM public.audit_events WHERE tenant_id=%s AND actor_id=%s AND action='CI_UPGRADE_REFUNDED' AND object_id=%s AND evidence_ref=%s",
                (tenant,reviewer,str(request_id),proof)).fetchone():
                raise LifecycleDenied("Histórico de estorno incompatível.")
        else:
            conn.execute("INSERT INTO public.fr_v23_upgrade_refunds(request_id,tenant_id,reviewer,settlement_hash,refunded_cents,evidence,evidence_hash) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s)",(request_id,tenant,reviewer,settlement_hash,gross,Jsonb(refund),proof))
            _audit(conn,reviewer,"SYSTEM",tenant,"CI_UPGRADE_REFUNDED",request_id,proof)
        return dict(request_id=str(request_id),state="REFUNDED",refunded_cents=gross,evidence_hash=proof,
                    production_authorized=False,real_payment_authorized=False)
