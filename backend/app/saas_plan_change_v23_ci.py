"""M41520: frozen synthetic plan-change review; never a charge or entitlement."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP,localcontext
from hashlib import sha256
import json
from uuid import UUID
from psycopg.types.json import Jsonb
from .account_lifecycle import LifecycleDenied
from .saas_renewal_readback_ci import renewal_overview_ci
from .saas_renewal_v23_ci import _lock
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

def _snapshot(conn,token,tenant,target,at=None):
    _lock(conn,tenant)
    if target not in RANK:raise LifecycleDenied("Plano comercial indisponível.")
    view=renewal_overview_ci(conn,token=token,tenant=tenant)
    now=_instant(view["observed_at"])
    at=now if at is None else _instant(at)
    if at>now or view["access"]!="CURRENT" or view["offer"] is None:
        raise LifecycleDenied("Vigência ou ação pendente exige revisão.")
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
