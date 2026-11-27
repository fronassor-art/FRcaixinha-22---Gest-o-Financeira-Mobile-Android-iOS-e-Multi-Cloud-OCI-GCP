"""Canonical disposable PG18 renewal/reversal integration after real CI onboarding."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
from app.saas_renewal_v23_ci import prepare_renewal_ci,reconcile_renewal_ci,reconcile_full_refund_ci,renewal_term
from app.administrator_reauthentication_ci import _license_access
from app.admin_license_onboarding_ci import reconcile_admin_checkout_ci
from m41400_cycle_identity_ci import connection,reject

def exercise(tenant,actor,token,reviewer_tenant,reviewer_token,price,doc,digest,late):
    with connection() as db:
        prev,old_intent,old_from,old_end=db.execute(
            "SELECT id,payment_intent_id,valid_from,valid_until FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()
        if late:
            db.execute("UPDATE public.saas_license_entitlements SET status='EXPIRED',valid_from=now()-interval '2 days',valid_until=now()-interval '1 day' WHERE id=%s",(prev,))
            with db.transaction():assert _license_access(db,actor,tenant)=="CONTINUITY_ONLY"
        ledger=db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]
        cycles=db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()
        args=dict(token=token,tenant=tenant,request_id=uuid4(),predecessor=prev,price_version=price,
                  period="ANNUAL" if late else "MONTHLY",cents=70033 if late else 8990,document_id=doc,document_hash=digest,accepted=True)
        for change in (dict(accepted=False),dict(cents=1),dict(document_hash="f"*64),dict(token=reviewer_token),dict(predecessor=uuid4())):
            reject(prepare_renewal_ci,db,**{**args,**change})
        def stage(_):
            with connection() as c:return prepare_renewal_ci(c,**args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a,b=list(pool.map(stage,range(2)))
        assert a==b
        prep,intent=a
        reject(prepare_renewal_ci,db,**{**args,"request_id":uuid4()})
        reject(prepare_renewal_ci,db,**{**args,"cents":1})
        assert db.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()[0]==1
        cents=args["cents"]
        payment=dict(id=str(uuid4().int)[:38],collector_id="12345",external_reference=f"saas:{intent}",
                     transaction_amount=str(Decimal(cents)/100),transaction_amount_refunded="0.00",currency_id="BRL",status="approved",live_mode=False)
        review=dict(reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,intent=intent,payment=payment,gross=cents,fee=10,net=cents-10)
        reject(reconcile_admin_checkout_ci,db,reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,intent=intent,
               payment=payment,statement_gross_cents=cents,statement_fee_cents=10,statement_net_cents=cents-10)
        for change in (dict(payment={**payment,"live_mode":True}),dict(payment={**payment,"transaction_amount_refunded":"1.00"}),
                       dict(net=cents),dict(reviewer_token=token,reviewer_tenant=tenant),dict(tenant=uuid4())):
            reject(reconcile_renewal_ci,db,**{**review,**change})
        def reconcile(_):
            with connection() as c:return reconcile_renewal_ci(c,**review)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a,b=list(pool.map(reconcile,range(2)))
        assert a==b
        ent=a
        start,end,paid=db.execute("SELECT e.valid_from,e.valid_until,p.paid_at FROM public.saas_license_entitlements e "
                                 "JOIN public.saas_payment_intents p ON p.id=e.payment_intent_id WHERE e.id=%s",(ent,)).fetchone()
        if late:assert start==paid and start>old_from
        else:assert start==old_end and paid<start
        assert end>start
        assert db.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()==(20,40)
        refund={**payment,"status":"refunded","transaction_amount_refunded":payment["transaction_amount"]}
        rev=dict(reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,intent=intent,payment=refund,statement_refunded_cents=cents)
        reject(reconcile_full_refund_ci,db,**{**rev,"statement_refunded_cents":1})
        reject(reconcile_full_refund_ci,db,**{**rev,"payment":{**refund,"transaction_amount_refunded":"0.01"}})
        assert reconcile_full_refund_ci(db,**rev) and reconcile_full_refund_ci(db,**rev)
        reject(reconcile_renewal_ci,db,**review)
        assert db.execute("SELECT status FROM public.saas_license_entitlements WHERE id=%s",(ent,)).fetchone()[0]=="REVOKED"
        with db.transaction():
            assert _license_access(db,actor,tenant)==("CONTINUITY_ONLY" if late else "CURRENT")
        assert db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==ledger
        assert db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==cycles
        assert db.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()[0]==2
        print("M41480_RENEWAL_"+("LATE_ANNUAL" if late else "EARLY_MONTHLY")+"_REFUND_REPLAY_ISOLATION=PASS")
    from zoneinfo import ZoneInfo
    tz=ZoneInfo("America/Belem")
    feb=datetime(2027,2,28,10,tzinfo=tz)
    start,end,anchor=renewal_term(feb,31,feb-timedelta(days=1),"MONTHLY")
    assert (start,end.day,end.month,anchor)==(feb,31,3,31)
    _,end,anchor=renewal_term(feb,31,feb+timedelta(days=2),"ANNUAL")
    assert (end.year,end.month,end.day,anchor)==(2028,3,2,2)
