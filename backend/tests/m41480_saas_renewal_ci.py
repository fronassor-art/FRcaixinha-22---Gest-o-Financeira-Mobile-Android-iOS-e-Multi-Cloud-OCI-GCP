"""Canonical disposable PG18 renewal/reversal integration after real CI onboarding."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import UUID,uuid4
from app.saas_renewal_v23_ci import prepare_renewal_ci,reconcile_renewal_ci,reconcile_full_refund_ci,renewal_term,cancel_expired_renewal_ci,record_renewal_payment_review_ci
from app.administrator_reauthentication_ci import _license_access
from app.saas_billing_ci import reconcile_approved_saas_payment_ci
from app.saas_plan_change_v23_ci import prorata_cents,_decision,_hash,_stamp,freeze_plan_change_ci,accept_plan_change_ci,record_upgrade_settlement_review_ci,plan_change_preview_ci
from app.saas_renewal_readback_ci import renewal_overview_ci
from psycopg.types.json import Jsonb
from app.admin_license_onboarding_ci import reconcile_admin_checkout_ci
from m41400_cycle_identity_ci import connection,reject
from m41420_onboarding_http_ci import client_for,post,get

def exercise(tenant,actor,token,reviewer_tenant,reviewer_token,price,doc,digest,late):
    assert all(type(x) is UUID for x in (tenant,actor,reviewer_tenant,price,doc))
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
        client,_=client_for()
        path=f"/tenants/{tenant}/renewal"
        snapshot=get(client,path,token)
        assert snapshot["access"]==("CONTINUITY_ONLY" if late else "CURRENT")
        assert snapshot["offer"]["predecessor"]==str(prev) and snapshot["offer"]["price_version"]==str(price)
        assert snapshot["document"]["document_hash"]==digest and snapshot["renewals"]==[]
        assert snapshot["production_authorized"] is False and snapshot["real_payment_authorized"] is False
        get(client,path,reviewer_token,403)
        http_body={k:v for k,v in args.items() if k not in ("tenant","token")}
        post(client,path,{**http_body,"cents":1},token,403)
        post(client,path,http_body,reviewer_token,403)
        for change in (dict(accepted=False),dict(cents=1),dict(document_hash="f"*64),dict(token=reviewer_token),dict(predecessor=uuid4()),dict(price_version=str(price)),dict(document_id=str(doc)),dict(request_id=UUID(int=0))):
            reject(prepare_renewal_ci,db,**{**args,**change})
        def stage(index):
            if index==0:
                http,_=client_for()
                result=post(http,path,http_body,token)
                assert result["renewals"][0]["state"]=="PENDING"
                with connection() as c:
                    return c.execute("SELECT preparation_id,intent_id FROM public.fr_v23_renewals WHERE request_id=%s",(args["request_id"],)).fetchone()
            with connection() as c:return prepare_renewal_ci(c,**args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a,b=list(pool.map(stage,range(2)))
        assert a==b
        prep,intent=a
        pending=post(client,path,http_body,token)
        assert pending["offer"] is None and len(pending["renewals"])==1
        assert pending["renewals"][0]["state"]=="PENDING" and pending["renewals"][0]["intent_id"]==str(intent)
        post(client,path,{**http_body,"request_id":uuid4()},token,403)
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
        paid_snapshot=get(client,path,token)
        assert paid_snapshot["renewals"][0]["state"]=="CI_RECONCILED"
        assert [x["state"] for x in paid_snapshot["segments"]]==(["EXPIRED","CURRENT"] if late else ["CURRENT","SCHEDULED"])
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
        refunded=get(client,path,token)
        assert refunded["renewals"][0]["state"]=="REFUNDED"
        assert refunded["offer"]["predecessor"]==str(ent)
        # Expired replacement cannot be paid or superseded until terminal
        # provider cancellation and independent zero settlement are verified.
        recover={**args,"request_id":uuid4(),"predecessor":ent}
        rp,ri=prepare_renewal_ci(db,**recover)
        premature={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{ri}","status":"cancelled"}
        reject(cancel_expired_renewal_ci,db,reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,
               intent=ri,payment=premature,statement_settled_cents=0)
        db.execute("UPDATE public.fr_v23_renewals SET accepted_at=now()-interval '2 hours',expires_at=now()-interval '1 hour' WHERE request_id=%s",(recover["request_id"],))
        pending_recovery=get(client,path,token)
        assert pending_recovery["offer"] is None and next(x for x in pending_recovery["renewals"] if x["request_id"]==str(recover["request_id"]))["state"]=="REVIEW_REQUIRED"
        again={**recover,"request_id":uuid4()}
        reject(prepare_renewal_ci,db,**again)
        canceled={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{ri}","status":"cancelled"}
        proof=dict(reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,intent=ri,payment=canceled,statement_settled_cents=0)
        reject(cancel_expired_renewal_ci,db,**{**proof,"statement_settled_cents":1})
        reject(cancel_expired_renewal_ci,db,**{**proof,"payment":{**canceled,"external_reference":"other"}})
        reject(cancel_expired_renewal_ci,db,**{**proof,"tenant":uuid4()})
        reject(cancel_expired_renewal_ci,db,**{**proof,"payment":{**canceled,"status":"pending"}})
        reject(cancel_expired_renewal_ci,db,**{**proof,"reviewer_token":token,"reviewer_tenant":tenant})
        reject(reconcile_renewal_ci,db,**{**review,"intent":ri,"payment":{**canceled,"status":"approved"}})
        def cancel(_):
            with connection() as c:return cancel_expired_renewal_ci(c,**proof)
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(cancel,range(2)))==[recover["request_id"]]*2
        reject(reconcile_renewal_ci,db,**{**review,"intent":ri,"payment":{**canceled,"status":"approved"}})
        reopened=get(client,path,token)
        assert reopened["offer"]["predecessor"]==str(ent) and next(x for x in reopened["renewals"] if x["request_id"]==str(recover["request_id"]))["state"]=="CANCELED"
        def retry(_):
            with connection() as c:return prepare_renewal_ci(c,**again)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a,b=list(pool.map(retry,range(2)))
        assert a==b and a[1]!=ri
        reject(prepare_renewal_ci,db,**{**again,"request_id":uuid4()})
        replacement={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{a[1]}"}
        new=reconcile_renewal_ci(db,**{**review,"intent":a[1],"payment":replacement})
        nstart,npaid=db.execute("SELECT e.valid_from,p.paid_at FROM public.saas_license_entitlements e JOIN public.saas_payment_intents p "
                                "ON p.id=e.payment_intent_id WHERE e.id=%s",(new,)).fetchone()
        assert nstart==(npaid if late else old_end)
        assert db.execute("SELECT status FROM public.saas_license_entitlements WHERE id=%s",(ent,)).fetchone()[0]=="REVOKED"
        assert db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==ledger
        assert db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==cycles
        restored=get(client,path,token)
        assert restored["access"]=="CURRENT" and restored["offer"]["predecessor"]==str(new)
        assert {x["request_id"]:x["state"] for x in restored["renewals"]}=={str(args["request_id"]):"REFUNDED",str(recover["request_id"]):"CANCELED",str(again["request_id"]):"CI_RECONCILED"}
        # Pay a future segment, then refund the non-terminal predecessor.
        # Early monthly tenant also prepays one annual segment; each keeps its period.
        future_args={**args,"request_id":uuid4(),"predecessor":new,"period":"ANNUAL","cents":70033}
        _,fi=prepare_renewal_ci(db,**future_args)
        fp={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{fi}","transaction_amount":"700.33"}
        future=reconcile_renewal_ci(db,**{**review,"intent":fi,"payment":fp,"gross":70033,"net":70023})
        future_before=db.execute("SELECT valid_from,valid_until,status FROM public.saas_license_entitlements WHERE id=%s",(future,)).fetchone()
        # The same current and future paid intervals are priced separately.
        target="INTERMEDIARIO"
        quote_path=f"/tenants/{tenant}/plan-change"
        preview=get(client,quote_path+"/"+target,token)
        get(client,quote_path+"/"+target,reviewer_token,403)
        get(client,quote_path+"/ESSENCIAL",token,403)
        snap=preview["snapshot"]
        assert snap["current_tier"]=="ESSENCIAL" and snap["target_tier"]==target
        assert snap["decision"]=="UPGRADE_REVIEW" and snap["real_payment_authorized"] is False
        assert len(snap["segments"])== (2 if late else 3)
        assert {x["period"] for x in snap["segments"]}==({"ANNUAL"} if late else {"MONTHLY","ANNUAL"})
        assert snap["total_cents"]==sum(x["difference_cents"] for x in snap["segments"])
        assert snap["segments"][-1]["difference_cents"]==max(0,snap["segments"][-1]["target_cents"]-snap["segments"][-1]["paid_cents"])
        counts=db.execute("SELECT count(*) FROM public.saas_payment_intents WHERE tenant_id=%s",(tenant,)).fetchone()[0]
        request=uuid4()
        quote_args=dict(token=token,tenant=tenant,target=target,request_id=request)
        def freeze(_):
            with connection() as c:return freeze_plan_change_ci(c,**quote_args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            q1,q2=list(pool.map(freeze,range(2)))
        assert q1==q2 and q1["accepted"] is False
        quote=post(client,quote_path+"/quotes",dict(request_id=request,target=target),token)
        assert quote==q1
        body=dict(request_id=request,offer_hash=quote["offer_hash"],document_id=doc,document_hash=digest,accepted=True)
        post(client,quote_path+"/accept",{**body,"offer_hash":"f"*64},token,403)
        post(client,quote_path+"/accept",body,reviewer_token,403)
        def accept(_):
            with connection() as c:return accept_plan_change_ci(c,token=token,tenant=tenant,**body)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a1,a2=list(pool.map(accept,range(2)))
        assert a1==a2 and a1["accepted"] is True and a1["real_payment_authorized"] is False
        assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action='CI_PLAN_CHANGE_REVIEW_ACCEPTED'",(tenant,str(request))).fetchone()[0]==1
        # Synthetic stale quote: preserve a new snapshot, then change only its
        # deadline in the disposable fixture to demonstrate fail-closed expiry.
        expired=uuid4()
        at=db.execute("SELECT clock_timestamp()-interval '1 hour'").fetchone()[0]
        expiry=at+timedelta(minutes=15)
        past={**quote["snapshot"],"calculated_at":_stamp(at),"expires_at":_stamp(expiry)}
        past_hash=_hash(past)
        db.execute("INSERT INTO public.fr_v23_plan_change_quotes(request_id,tenant_id,actor,snapshot,snapshot_hash,calculated_at,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                   (expired,tenant,actor,Jsonb(past),past_hash,at,expiry))
        reject(accept_plan_change_ci,db,token=token,tenant=tenant,**{**body,"request_id":expired,"offer_hash":past_hash})
        reject(db.execute,"UPDATE public.fr_v23_plan_change_quotes SET snapshot_hash=%s WHERE request_id=%s",("f"*64,request))
        reject(db.execute,"DELETE FROM public.fr_v23_plan_change_quotes WHERE request_id=%s",(request,))
        assert db.execute("SELECT count(*) FROM public.saas_payment_intents WHERE tenant_id=%s",(tenant,)).fetchone()[0]==counts
        assert db.execute("SELECT valid_from,valid_until,status FROM public.saas_license_entitlements WHERE id=%s",(future,)).fetchone()==future_before
        assert _decision("INTERMEDIARIO","ESSENCIAL",20,40,20,40,0)=="DOWNGRADE_NEXT_RENEWAL"
        assert _decision("INTERMEDIARIO","ESSENCIAL",21,40,20,40,0)=="CAPACITY_REVIEW"
        assert _decision("INTERMEDIARIO","ESSENCIAL",20,41,20,40,0)=="CAPACITY_REVIEW"
        assert _decision("ESSENCIAL","INTERMEDIARIO",20,40,50,50,0)=="ZERO_DIFFERENCE_REVIEW"
        # Exercise the new review in a rollback-only subscenario so the existing
        # independent refund/gap/recovery tests below still run unchanged.
        gross=quote["snapshot"]["total_cents"]
        upgrade_payment={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas-upgrade-review:{request}",
                         "transaction_amount":str(Decimal(gross)/100)}
        upgrade=dict(token=token,reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,
                     request_id=request,offer_hash=quote["offer_hash"],payment=upgrade_payment,gross=gross,fee=0,net=gross)
        original_terms=db.execute("SELECT id,plan_tier,valid_from,valid_until,status FROM public.saas_license_entitlements WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()
        for change in (dict(offer_hash="f"*64),dict(request_id=expired),dict(tenant=uuid4()),dict(reviewer_token=token,reviewer_tenant=tenant),
                       dict(payment={**upgrade_payment,"live_mode":True}),dict(payment={**upgrade_payment,"collector_id":"999"}),
                       dict(payment={**upgrade_payment,"transaction_amount_refunded":"0.01"}),dict(payment={**upgrade_payment,"external_reference":"other"}),
                       dict(payment={**upgrade_payment,"transaction_amount":"0.01"}),dict(net=gross-1)):
            reject(record_upgrade_settlement_review_ci,db,**{**upgrade,**change})
        with db.transaction(force_rollback=True):
            receipt=record_upgrade_settlement_review_ci(db,**upgrade)
            assert receipt==record_upgrade_settlement_review_ci(db,**upgrade)
            assert receipt["state"]=="SETTLEMENT_REVIEW" and receipt["entitlement_applied"] is False and receipt["real_payment_authorized"] is False
            reject(record_upgrade_settlement_review_ci,db,**{**upgrade,"fee":1,"net":gross-1})
            reject(record_upgrade_settlement_review_ci,db,**{**upgrade,"payment":{**upgrade_payment,"id":str(uuid4().int)[:38]}})
            assert db.execute("SELECT count(*) FROM public.fr_v23_upgrade_settlement_reviews WHERE tenant_id=%s",(tenant,)).fetchone()[0]==1
            assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action='CI_UPGRADE_SETTLEMENT_REVIEW'",(tenant,str(request))).fetchone()[0]==1
            assert renewal_overview_ci(db,token=token,tenant=tenant)["offer"] is None
            reject(plan_change_preview_ci,db,token=token,tenant=tenant,target=target)
            reject(prepare_renewal_ci,db,**{**future_args,"request_id":uuid4(),"predecessor":future})
            for sql in ("UPDATE public.fr_v23_upgrade_settlement_reviews SET fee_cents=1 WHERE tenant_id=%s",
                        "DELETE FROM public.fr_v23_upgrade_settlement_reviews WHERE tenant_id=%s"):
                with db.transaction(force_rollback=True):reject(db.execute,sql,(tenant,))
            assert db.execute("SELECT id,plan_tier,valid_from,valid_until,status FROM public.saas_license_entitlements WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==original_terms
            assert db.execute("SELECT count(*) FROM public.saas_payment_intents WHERE tenant_id=%s",(tenant,)).fetchone()[0]==counts
            assert db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==ledger
            assert db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==cycles
        assert db.execute("SELECT count(*) FROM public.fr_v23_upgrade_settlement_reviews WHERE tenant_id=%s",(tenant,)).fetchone()[0]==0
        print("M41530_UPGRADE_SETTLEMENT_REVIEW_"+("ANNUAL" if late else "MIXED")+"=PASS")
        print("M41520_FROZEN_PLAN_CHANGE_"+("ANNUAL" if late else "MIXED")+"=PASS")
        assert reconcile_full_refund_ci(db,**{**rev,"intent":a[1],"payment":{**replacement,"status":"refunded","transaction_amount_refunded":replacement["transaction_amount"]}})
        gap=get(client,path,token)
        assert gap["access"]==("CONTINUITY_ONLY" if late else "CURRENT")
        assert next(x for x in gap["segments"] if x["entitlement_id"]==str(future))["state"]=="SCHEDULED"
        assert gap["offer"]["predecessor"]==str(future)
        assert db.execute("SELECT valid_from,valid_until,status FROM public.saas_license_entitlements WHERE id=%s",(future,)).fetchone()==future_before
        # A late or divergent received amount is evidence, not a license.
        review_args={**args,"request_id":uuid4(),"predecessor":future}
        _,qi=prepare_renewal_ci(db,**review_args)
        amount=cents if late else cents+100
        qp={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{qi}","transaction_amount":str(Decimal(amount)/100)}
        qr={**review,"intent":qi,"payment":qp,"gross":amount,"fee":10,"net":amount-10}
        exact={**qr,"gross":cents,"net":cents-10,"payment":{**qp,"transaction_amount":payment["transaction_amount"]}}
        reject(record_renewal_payment_review_ci,db,**exact)
        if late:db.execute("UPDATE public.fr_v23_renewals SET accepted_at=now()-interval '2 hours',expires_at=now()-interval '1 hour' WHERE request_id=%s",(review_args["request_id"],))
        for change in (dict(payment={**qp,"collector_id":"999"}),dict(payment={**qp,"live_mode":True}),
                       dict(payment={**qp,"external_reference":"other"}),dict(payment={**qp,"transaction_amount_refunded":"0.01"}),
                       dict(net=amount),dict(tenant=uuid4()),dict(reviewer_token=token,reviewer_tenant=tenant)):
            reject(record_renewal_payment_review_ci,db,**{**qr,**change})
        def quarantine(_):
            with connection() as c:return record_renewal_payment_review_ci(c,**qr)
        action="CI_RENEWAL_LATE_PAYMENT_REVIEW" if late else "CI_RENEWAL_AMOUNT_REVIEW"
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(quarantine,range(2)))==[action,action]
        assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action=%s",(tenant,str(qi),action)).fetchone()[0]==1
        assert db.execute("SELECT status,paid_at,reconciled_at FROM public.saas_payment_intents WHERE id=%s",(qi,)).fetchone()==("PENDING",None,None)
        reject(record_renewal_payment_review_ci,db,**{**qr,"fee":11,"net":amount-11})
        reject(reconcile_renewal_ci,db,**exact)
        assert reconcile_approved_saas_payment_ci(db,intent_id=qi,authoritative_payment=exact["payment"]) is None
        reject(prepare_renewal_ci,db,**{**review_args,"request_id":uuid4()})
        if not late:db.execute("UPDATE public.fr_v23_renewals SET accepted_at=now()-interval '2 hours',expires_at=now()-interval '1 hour' WHERE request_id=%s",(review_args["request_id"],))
        reject(cancel_expired_renewal_ci,db,**{**proof,"intent":qi,"payment":{**exact["payment"],"status":"cancelled"}})
        quarantined=get(client,path,token)
        assert quarantined["offer"] is None and next(x for x in quarantined["renewals"] if x["intent_id"]==str(qi))["state"]=="PAYMENT_REVIEW"
        assert quarantined["access"]==gap["access"]
        assert db.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE payment_intent_id=%s",(qi,)).fetchone()[0]==0
        assert db.execute("SELECT valid_from,valid_until,status FROM public.saas_license_entitlements WHERE id=%s",(future,)).fetchone()==future_before
        assert db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==ledger
        assert db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==cycles
        print("M41510_PAYMENT_REVIEW_GAP_"+("LATE" if late else "DIVERGENT")+"=PASS")
        print("M41500_RECOVERY_EXPIRED_REFUND_"+("LATE" if late else "EARLY")+"=PASS")
        assert refunded["access"]==("CONTINUITY_ONLY" if late else "CURRENT")
        print("M41490_SCOPED_RENEWAL_HTTP_"+("LATE" if late else "EARLY")+"=PASS")
        print("M41480_RENEWAL_"+("LATE_ANNUAL" if late else "EARLY_MONTHLY")+"_REFUND_REPLAY_ISOLATION=PASS")
    from zoneinfo import ZoneInfo
    tz=ZoneInfo("America/Belem")
    feb=datetime(2027,2,28,10,tzinfo=tz)
    assert prorata_cents(100,101,feb,feb+timedelta(seconds=2),feb+timedelta(seconds=1))==1
    assert prorata_cents(100,101,feb,feb+timedelta(seconds=2),feb+timedelta(seconds=1,microseconds=1))==0
    assert prorata_cents(100,200,feb,feb+timedelta(days=1),feb-timedelta(days=1))==100
    assert prorata_cents(100,200,feb,feb+timedelta(days=1),feb+timedelta(days=1))==0
    assert prorata_cents(200,100,feb,feb+timedelta(days=1),feb)==0
    start,end,anchor=renewal_term(feb,31,feb-timedelta(days=1),"MONTHLY")
    assert (start,end.day,end.month,anchor)==(feb,31,3,31)
    _,end,anchor=renewal_term(feb,31,feb+timedelta(days=2),"ANNUAL")
    assert (end.year,end.month,end.day,anchor)==(2028,3,2,2)
