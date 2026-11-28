"""Canonical disposable PG18 renewal/reversal integration after real CI onboarding."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import UUID,uuid4
from app.saas_renewal_v23_ci import prepare_renewal_ci,reconcile_renewal_ci,reconcile_full_refund_ci,renewal_term,cancel_expired_renewal_ci,record_renewal_payment_review_ci,cancel_subscription_ci,resolve_reviewed_renewal_refund_ci,_lock
from app.administrator_reauthentication_ci import _license_access
from app.saas_billing_ci import reconcile_approved_saas_payment_ci
from app.saas_plan_change_v23_ci import prorata_cents,_decision,_hash,_stamp,freeze_plan_change_ci,accept_plan_change_ci,record_upgrade_settlement_review_ci,plan_change_preview_ci,apply_reviewed_upgrade_ci,reconcile_upgrade_refund_ci
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
        cancel_args={k:args[k] for k in ("token","tenant","request_id","predecessor","document_id","document_hash","accepted")}
        with db.transaction(force_rollback=True):
            reject(cancel_subscription_ci,db,**{**cancel_args,"token":reviewer_token})
            reject(cancel_subscription_ci,db,**{**cancel_args,"accepted":False})
            stop=cancel_subscription_ci(db,**cancel_args)
            assert stop==cancel_subscription_ci(db,**cancel_args)
            stopped=renewal_overview_ci(db,token=token,tenant=tenant)
            assert stopped["offer"] is None and stopped["cancellation"]==stop
            assert stopped["access"]==snapshot["access"]
            reject(prepare_renewal_ci,db,**args)
            reject(cancel_subscription_ci,db,**{**cancel_args,"request_id":uuid4()})
            with db.transaction(force_rollback=True):
                reject(db.execute,"DELETE FROM public.fr_v23_subscription_cancellations WHERE tenant_id=%s",(tenant,))
        def stage(index):
            if index==0:
                http,_=client_for()
                result=post(http,path,http_body,token)
                assert result["renewals"][0]["state"]=="PENDING"
                with connection() as c:
                    return c.execute("SELECT preparation_id,intent_id FROM public.fr_v23_renewals WHERE request_id=%s",(args["request_id"],)).fetchone()
            with connection() as c:return prepare_renewal_ci(c,**args)
        # A committed renewal and a competing cancellation cannot both win.
        # Hold the same tenant lock until a second connection proves contention.
        locked,contending=Event(),Event()
        def winning_stage():
            with connection() as c,c.transaction():
                _lock(c,tenant)
                result=prepare_renewal_ci(c,**args)
                locked.set()
                assert contending.wait(10)
                return result
        def losing_cancel():
            assert locked.wait(10)
            with connection() as c,c.transaction():
                assert c.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),)).fetchone()==(False,)
                contending.set()
                reject(cancel_subscription_ci,c,**cancel_args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            winner=pool.submit(winning_stage)
            loser=pool.submit(losing_cancel)
            a=winner.result(timeout=20)
            loser.result(timeout=20)
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(stage,range(2)))==[a,a]
        assert db.execute("SELECT count(*) FROM public.fr_v23_subscription_cancellations WHERE tenant_id=%s",(tenant,)).fetchone()[0]==0
        print("M41580_RENEWAL_CANCEL_CONTENTION=PASS")
        prep,intent=a
        reject(cancel_subscription_ci,db,**cancel_args)
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
        reject(reconcile_renewal_ci,db,**{**review,"fee":11,"net":cents-11})
        assert reconcile_renewal_ci(db,**review)==ent
        assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action='CI_RENEWAL_SETTLEMENT_EVIDENCE'",(tenant,str(intent))).fetchone()[0]==1
        print("M41580_SETTLEMENT_EXACT_REPLAY=PASS")
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
        base_limits=db.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
        existing_provider=db.execute("SELECT provider_payment_id FROM public.saas_payment_intents WHERE id=%s",(old_intent,)).fetchone()[0]
        reject(record_upgrade_settlement_review_ci,db,**{**upgrade,"payment":{**upgrade_payment,"id":existing_provider}})
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
            assert renewal_overview_ci(db,token=token,tenant=tenant)["upgrade"]["state"]=="SETTLEMENT_REVIEW"
            apply_args={k:upgrade[k] for k in ("token","reviewer_token","reviewer_tenant","tenant","request_id","offer_hash")}
            apply_args["evidence_hash"]=receipt["evidence_hash"]
            refund_payment={**upgrade_payment,"status":"refunded","transaction_amount_refunded":upgrade_payment["transaction_amount"]}
            refund_args=dict(reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,request_id=request,
                             payment=refund_payment,statement_refunded_cents=gross)
            # Before application: full refund never creates any new coverage.
            with db.transaction(force_rollback=True):
                before=reconcile_upgrade_refund_ci(db,**refund_args)
                assert before==reconcile_upgrade_refund_ci(db,**refund_args)
                reject(apply_reviewed_upgrade_ci,db,**apply_args)
                before_view=renewal_overview_ci(db,token=token,tenant=tenant)
                assert before_view["upgrade"]["state"]=="REFUNDED" and before_view["offer"]["tier"]=="ESSENCIAL"
                assert db.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()==base_limits
            with db.transaction(force_rollback=True):
                reject(db.execute,"UPDATE public.saas_payment_intents SET provider_payment_id=%s WHERE id=%s",(upgrade_payment["id"],old_intent))
            assert db.execute("SELECT source_kind,object_id,tenant_id FROM public.fr_v23_saas_provider_claims WHERE provider_payment_id=%s",(upgrade_payment["id"],)).fetchone()==("UPGRADE",request,tenant)
            anchor_before=db.execute("SELECT request_id,anchor_day FROM public.fr_v23_renewals WHERE tenant_id=%s ORDER BY request_id",(tenant,)).fetchall()
            for bad in (dict(evidence_hash="f"*64),dict(offer_hash="f"*64),dict(request_id=uuid4()),
                        dict(tenant=uuid4()),dict(reviewer_token=token,reviewer_tenant=tenant)):
                reject(apply_reviewed_upgrade_ci,db,**{**apply_args,**bad})
            applied=apply_reviewed_upgrade_ci(db,**apply_args)
            assert applied==apply_reviewed_upgrade_ci(db,**apply_args)
            assert applied["state"]=="CI_APPLIED" and applied["difference_cents"]==gross and applied["real_payment_authorized"] is False
            assert db.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()==(snap["members_limit"],snap["quotas_limit"])
            assert db.execute("SELECT request_id,anchor_day FROM public.fr_v23_renewals WHERE tenant_id=%s ORDER BY request_id",(tenant,)).fetchall()==anchor_before
            read=renewal_overview_ci(db,token=token,tenant=tenant)
            assert read["offer"]["tier"]=="INTERMEDIARIO" and read["upgrade"]["state"]=="CI_APPLIED"
            assert read["offer"]["predecessor"]==future and read["offer"]["price_version"]==UUID(quote["snapshot"]["target_price_version"])
            assert set(map(str,read["upgrade"]["entitlement_ids"]))=={v["entitlement_id"] for v in snap["segments"]}
            assert db.execute("SELECT sum(difference_cents),count(*) FROM public.fr_v23_upgrade_segments WHERE request_id=%s",(request,)).fetchone()==(gross,len(snap["segments"]))
            assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action='CI_UPGRADE_APPLIED'",(tenant,str(request))).fetchone()[0]==1
            with db.transaction(force_rollback=True):
                reject(db.execute,"DELETE FROM public.fr_v23_upgrade_segments WHERE request_id=%s",(request,))
            print("M41540_UPGRADE_CAPACITY_"+("ANNUAL" if late else "MIXED")+"=PASS")
            # Reuse the authoritative offer, not the upgrade difference, for
            # the separately paid future term. Old price must be rejected.
            next_args={**future_args,"request_id":uuid4(),"predecessor":future,
                       "price_version":read["offer"]["price_version"],"cents":read["offer"]["annual_cents"]}
            reject(prepare_renewal_ci,db,**{**next_args,"price_version":price,"cents":70033})
            with db.transaction(force_rollback=True):
                _,ni=prepare_renewal_ci(db,**next_args)
                assert prepare_renewal_ci(db,**next_args)[1]==ni
                np={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{ni}",
                    "transaction_amount":str(Decimal(next_args["cents"])/100)}
                nr={**review,"intent":ni,"payment":np,"gross":next_args["cents"],"net":next_args["cents"]-10}
                successor=reconcile_renewal_ci(db,**nr)
                assert successor==reconcile_renewal_ci(db,**nr)
                assert db.execute("SELECT plan_tier,valid_from FROM public.saas_license_entitlements WHERE id=%s",(successor,)).fetchone()==("INTERMEDIARIO",future_before[1])
                assert db.execute("SELECT valid_from,valid_until,status FROM public.saas_license_entitlements WHERE id=%s",(future,)).fetchone()==future_before
                assert renewal_overview_ci(db,token=token,tenant=tenant)["offer"]["predecessor"]==successor
                reconcile_upgrade_refund_ci(db,**refund_args)
                after_paid=renewal_overview_ci(db,token=token,tenant=tenant)
                assert after_paid["upgrade"]["state"]=="REFUNDED" and after_paid["offer"]["tier"]=="INTERMEDIARIO"
                assert db.execute("SELECT plan_tier,status FROM public.saas_license_entitlements WHERE id=%s",(successor,)).fetchone()==("INTERMEDIARIO","ACTIVE")
                down_args={**future_args,"request_id":uuid4(),"predecessor":successor}
                reject(prepare_renewal_ci,db,**down_args)
                assert "downgrade_offer" not in after_paid
                # Move the fixture's paid periods into the past without overlap.
                # All historical upgrade proofs stay immutable; the overlay has
                # already been refunded. No production time is modified.
                shift=db.execute("SELECT max(valid_until)-clock_timestamp()+interval '1 day' FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()[0]
                db.execute("UPDATE public.saas_license_entitlements SET valid_from=valid_from-%s,valid_until=valid_until-%s,status='EXPIRED' WHERE tenant_id=%s AND status<>'REVOKED'",(shift,shift,tenant))
                boundary=renewal_overview_ci(db,token=token,tenant=tenant)
                assert boundary["access"]=="CONTINUITY_ONLY" and boundary["downgrade_offer"]["tier"]=="ESSENCIAL"
                down=boundary["downgrade_offer"]
                down_args={**down_args,"price_version":down["price_version"],"cents":down["annual_cents"]}
                with db.transaction(force_rollback=True):
                    db.execute("UPDATE public.platform_license_plans SET members_limit=1,quotas_limit=1 WHERE tier='ESSENCIAL'")
                    # The fixture created two open quotas before this exercise.
                    from app.saas_plan_change_v23_ci import _capacity
                    assert _capacity(db,tenant)[1]>=2
                    reject(prepare_renewal_ci,db,**down_args)
                    assert "downgrade_offer" not in renewal_overview_ci(db,token=token,tenant=tenant)
                _,di=prepare_renewal_ci(db,**down_args)
                dp={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{di}","transaction_amount":str(Decimal(down_args["cents"])/100)}
                dproof={**review,"intent":di,"payment":dp,"gross":down_args["cents"],"net":down_args["cents"]-10}
                with db.transaction(force_rollback=True):
                    db.execute("UPDATE public.platform_license_plans SET quotas_limit=1 WHERE tier='ESSENCIAL'")
                    reject(reconcile_renewal_ci,db,**dproof)
                    assert record_renewal_payment_review_ci(db,**dproof)=="CI_RENEWAL_TIER_REVIEW"
                    assert db.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE payment_intent_id=%s",(di,)).fetchone()[0]==0
                decreased=reconcile_renewal_ci(db,**dproof)
                assert decreased==reconcile_renewal_ci(db,**dproof)
                assert db.execute("SELECT plan_tier,status FROM public.saas_license_entitlements WHERE id=%s",(decreased,)).fetchone()==("ESSENCIAL","ACTIVE")
                # The fixture is inside a rollback-only transaction; access
                # checks use now() and cannot attest a new clock_timestamp()
                # settlement until commit. Test the actual successor resolver.
                from app.saas_renewal_v23_ci import _previous,_renewal_tier
                from app.preliminary_onboarding_ci import _binding
                acceptance,_=_binding(db,actor,tenant)
                assert _renewal_tier(db,tenant,actor,_previous(db,tenant,actor,decreased,acceptance))=="ESSENCIAL"
                assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND action='CI_RENEWAL_DOWNGRADE' AND object_id=%s",(tenant,str(decreased))).fetchone()[0]==1
                print("M41570_DOWNGRADE_BOUNDARY_"+("ANNUAL" if late else "MIXED")+"=PASS")
            with db.transaction(force_rollback=True):
                _,ni=prepare_renewal_ci(db,**next_args)
                np={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{ni}",
                    "transaction_amount":str(Decimal(next_args["cents"])/100)}
                reconcile_upgrade_refund_ci(db,**refund_args)
                reject(reconcile_renewal_ci,db,**{**review,"intent":ni,"payment":np,"gross":next_args["cents"],"net":next_args["cents"]-10})
                assert db.execute("SELECT status,paid_at FROM public.saas_payment_intents WHERE id=%s",(ni,)).fetchone()==("PENDING",None)
                stale_review={**review,"intent":ni,"payment":np,"gross":next_args["cents"],"net":next_args["cents"]-10}
                assert record_renewal_payment_review_ci(db,**stale_review)=="CI_RENEWAL_TIER_REVIEW"
                assert record_renewal_payment_review_ci(db,**stale_review)=="CI_RENEWAL_TIER_REVIEW"
                blocked=renewal_overview_ci(db,token=token,tenant=tenant)
                assert blocked["offer"] is None
                assert next(x for x in blocked["renewals"] if x["intent_id"]==ni)["state"]=="PAYMENT_REVIEW"
                assert db.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE payment_intent_id=%s",(ni,)).fetchone()[0]==0
            print("M41560_UPGRADE_RENEWAL_"+("ANNUAL" if late else "MIXED")+"=PASS")
            for bad in (dict(statement_refunded_cents=1),dict(tenant=uuid4()),dict(request_id=uuid4()),
                        dict(reviewer_token=token,reviewer_tenant=tenant),
                        dict(payment={**refund_payment,"live_mode":True}),dict(payment={**refund_payment,"collector_id":"999"}),
                        dict(payment={**refund_payment,"transaction_amount_refunded":"0.01"}),
                        dict(payment={**refund_payment,"external_reference":"other"})):
                reject(reconcile_upgrade_refund_ci,db,**{**refund_args,**bad})
            reversed_upgrade=reconcile_upgrade_refund_ci(db,**refund_args)
            assert reversed_upgrade==reconcile_upgrade_refund_ci(db,**refund_args)
            assert reversed_upgrade["state"]=="REFUNDED" and reversed_upgrade["refunded_cents"]==gross
            reject(record_upgrade_settlement_review_ci,db,**upgrade)
            reject(apply_reviewed_upgrade_ci,db,**apply_args)
            assert db.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()==base_limits
            assert _license_access(db,actor,tenant)=="CURRENT"
            reversed_read=renewal_overview_ci(db,token=token,tenant=tenant)
            assert reversed_read["offer"]["tier"]=="ESSENCIAL" and reversed_read["upgrade"]["state"]=="REFUNDED"
            assert reversed_read["offer"]["predecessor"]==future and reversed_read["offer"]["price_version"]==price
            assert reversed_read["upgrade"]["members_limit"] is None and reversed_read["upgrade"]["quotas_limit"] is None
            assert reversed_read["upgrade"]["entitlement_ids"]==read["upgrade"]["entitlement_ids"]
            assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action='CI_UPGRADE_REFUNDED'",(tenant,str(request))).fetchone()[0]==1
            with db.transaction(force_rollback=True):
                reject(db.execute,"DELETE FROM public.fr_v23_upgrade_refunds WHERE request_id=%s",(request,))
            print("M41550_UPGRADE_FULL_REFUND_"+("ANNUAL" if late else "MIXED")+"=PASS")
            reject(plan_change_preview_ci,db,token=token,tenant=tenant,target=target)
            reject(prepare_renewal_ci,db,**next_args)
            with db.transaction(force_rollback=True):
                base_args={**future_args,"request_id":uuid4(),"predecessor":future}
                _,ni=prepare_renewal_ci(db,**base_args)
                np={**payment,"id":str(uuid4().int)[:38],"external_reference":f"saas:{ni}","transaction_amount":"700.33"}
                successor=reconcile_renewal_ci(db,**{**review,"intent":ni,"payment":np,"gross":70033,"net":70023})
                assert db.execute("SELECT plan_tier,valid_from FROM public.saas_license_entitlements WHERE id=%s",(successor,)).fetchone()==("ESSENCIAL",future_before[1])
                assert renewal_overview_ci(db,token=token,tenant=tenant)["upgrade"]["state"]=="REFUNDED"
            print("M41560_REFUNDED_UPGRADE_RENEWAL_"+("ANNUAL" if late else "MIXED")+"=PASS")
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
        # M41590: real committed contention, not savepoint-only simulation.
        # Annual: apply wins then refund; mixed: refund wins then apply is denied.
        receipt=record_upgrade_settlement_review_ci(db,**upgrade)
        apply_args["evidence_hash"]=receipt["evidence_hash"]
        locked,contending=Event(),Event()
        def first():
            with connection() as c,c.transaction():
                _lock(c,tenant)
                result=(apply_reviewed_upgrade_ci(c,**apply_args) if late else reconcile_upgrade_refund_ci(c,**refund_args))
                locked.set()
                assert contending.wait(10)
                return result
        def second():
            assert locked.wait(10)
            with connection() as c,c.transaction():
                assert c.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s::text,41320))",(str(tenant),)).fetchone()==(False,)
                contending.set()
                if late:return reconcile_upgrade_refund_ci(c,**refund_args)
                reject(apply_reviewed_upgrade_ci,c,**apply_args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            winner,loser=pool.submit(first),pool.submit(second)
            first_result=winner.result(timeout=20)
            second_result=loser.result(timeout=20)
        assert first_result["state"]==("CI_APPLIED" if late else "REFUNDED")
        assert (second_result["state"] if late else second_result)==("REFUNDED" if late else None)
        assert reconcile_upgrade_refund_ci(db,**refund_args)==(second_result if late else first_result)
        reject(apply_reviewed_upgrade_ci,db,**apply_args)
        reject(record_upgrade_settlement_review_ci,db,**upgrade)
        assert db.execute("SELECT count(*) FROM public.fr_v23_upgrade_applications WHERE request_id=%s",(request,)).fetchone()[0]==int(late)
        assert db.execute("SELECT count(*) FROM public.fr_v23_upgrade_segments WHERE request_id=%s",(request,)).fetchone()[0]==(len(snap["segments"]) if late else 0)
        assert db.execute("SELECT evidence->>'had_application' FROM public.fr_v23_upgrade_refunds WHERE request_id=%s",(request,)).fetchone()==("true" if late else "false",)
        assert db.execute("SELECT action,count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action IN ('CI_UPGRADE_APPLIED','CI_UPGRADE_REFUNDED') GROUP BY action ORDER BY action",(tenant,str(request))).fetchall()==([("CI_UPGRADE_APPLIED",1),("CI_UPGRADE_REFUNDED",1)] if late else [("CI_UPGRADE_REFUNDED",1)])
        assert db.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()==base_limits
        assert db.execute("SELECT id,plan_tier,valid_from,valid_until,status FROM public.saas_license_entitlements WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==original_terms
        assert db.execute("SELECT count(*) FROM public.saas_payment_intents WHERE tenant_id=%s",(tenant,)).fetchone()[0]==counts
        assert db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==ledger
        assert db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==cycles
        final_upgrade=renewal_overview_ci(db,token=token,tenant=tenant)
        assert final_upgrade["upgrade"]["state"]=="REFUNDED" and final_upgrade["offer"]["tier"]=="ESSENCIAL"
        assert final_upgrade["upgrade"]["members_limit"] is None and final_upgrade["upgrade"]["quotas_limit"] is None
        print("M41590_UPGRADE_REFUND_CONTENTION_"+("APPLY_FIRST" if late else "REFUND_FIRST")+"=PASS")
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
        with db.transaction(force_rollback=True):
            if not late:db.execute("UPDATE public.fr_v23_renewals SET accepted_at=now()-interval '2 hours',expires_at=now()-interval '1 hour' WHERE request_id=%s",(review_args["request_id"],))
            reject(cancel_expired_renewal_ci,db,**{**proof,"intent":qi,"payment":{**exact["payment"],"status":"cancelled"}})
        quarantined=get(client,path,token)
        assert quarantined["offer"] is None and next(x for x in quarantined["renewals"] if x["intent_id"]==str(qi))["state"]=="PAYMENT_REVIEW"
        assert quarantined["access"]==gap["access"]
        assert db.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE payment_intent_id=%s",(qi,)).fetchone()[0]==0
        assert db.execute("SELECT valid_from,valid_until,status FROM public.saas_license_entitlements WHERE id=%s",(future,)).fetchone()==future_before
        assert db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==ledger
        assert db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==cycles
        # Full refund of the actual receipt, not the expected offer amount.
        refunded_payment={**qp,"status":"refunded","transaction_amount_refunded":qp["transaction_amount"]}
        resolution=dict(reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,intent=qi,
                        payment=refunded_payment,statement_refunded_cents=amount)
        for bad in (dict(statement_refunded_cents=amount-1),dict(payment={**refunded_payment,"transaction_amount_refunded":"0.01"}),
                    dict(payment={**refunded_payment,"id":str(uuid4().int)[:38]}),dict(payment={**refunded_payment,"live_mode":True}),
                    dict(tenant=reviewer_tenant),dict(reviewer_token=token,reviewer_tenant=tenant)):
            reject(resolve_reviewed_renewal_refund_ci,db,**{**resolution,**bad})
        def resolve(_):
            with connection() as c:return resolve_reviewed_renewal_refund_ci(c,**resolution)
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(resolve,range(2)))==[review_args["request_id"]]*2
        assert db.execute("SELECT count(*) FROM public.audit_events WHERE tenant_id=%s AND object_id=%s AND action='CI_RENEWAL_REVIEW_REFUNDED'",(tenant,str(qi))).fetchone()[0]==1
        assert db.execute("SELECT status,paid_at,reconciled_at FROM public.saas_payment_intents WHERE id=%s",(qi,)).fetchone()==("CANCELED",None,None)
        reject(reconcile_renewal_ci,db,**exact)
        reject(record_renewal_payment_review_ci,db,**qr)
        assert db.execute("SELECT review_refunded,canceled_at>=expires_at FROM public.fr_v23_renewals WHERE intent_id=%s",(qi,)).fetchone()==(True,late)
        with db.transaction(force_rollback=True):
            db.execute("UPDATE public.fr_v23_renewals SET review_refunded=false,canceled_at=GREATEST(canceled_at,expires_at) WHERE intent_id=%s",(qi,))
            reject(renewal_overview_ci,db,token=token,tenant=tenant)
        resolved=get(client,path,token)
        assert resolved["offer"]["predecessor"]==str(future)
        assert next(x for x in resolved["renewals"] if x["intent_id"]==str(qi))["state"]=="REVIEW_REFUNDED"
        assert resolved["segments"]==quarantined["segments"] and resolved["access"]==quarantined["access"]
        assert db.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE payment_intent_id=%s",(qi,)).fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==ledger
        assert db.execute("SELECT id,start_date,settlement_date FROM public.cycles WHERE tenant_id=%s ORDER BY id",(tenant,)).fetchall()==cycles
        with db.transaction(force_rollback=True):
            fresh={**review_args,"request_id":uuid4()}
            assert prepare_renewal_ci(db,**fresh)[1]!=qi
        print("M41580_REVIEW_FULL_REFUND_"+("LATE" if late else "DIVERGENT")+"=PASS")
        print("M41570_SUBSCRIPTION_CANCEL_"+("ANNUAL" if late else "MIXED")+"=PASS")
        print("M41510_PAYMENT_REVIEW_GAP_"+("LATE" if late else "DIVERGENT")+"=PASS")
        print("M41500_RECOVERY_EXPIRED_REFUND_"+("LATE" if late else "EARLY")+"=PASS")
        assert refunded["access"]==("CONTINUITY_ONLY" if late else "CURRENT")
        print("M41490_SCOPED_RENEWAL_HTTP_"+("LATE" if late else "EARLY")+"=PASS")
        print("M41480_RENEWAL_"+("LATE_ANNUAL" if late else "EARLY_MONTHLY")+"_REFUND_REPLAY_ISOLATION=PASS")
    # Two independent committed transactions compete in the same registry used
    # by both actual table triggers. One wins; the other cannot claim the ID.
    import psycopg
    from threading import Barrier
    provider=str(uuid4().int)[:38]
    barrier=Barrier(2)
    claim_objects=(uuid4(),uuid4())
    def claim(i):
        with connection() as c:
            barrier.wait(timeout=10)
            try:
                with c.transaction():
                    c.execute("SELECT public.fr_v23_claim_saas_provider(%s,%s,%s,%s)",
                              ("0"*i+provider,("INTENT","UPGRADE")[i],claim_objects[i],(tenant,reviewer_tenant)[i]))
                return i
            except psycopg.errors.UniqueViolation:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        winners=[i for i in pool.map(claim,range(2)) if i is not None]
    assert len(winners)==1
    with connection() as db:
        winner=winners[0]
        assert db.execute("SELECT source_kind,object_id,tenant_id FROM public.fr_v23_saas_provider_claims WHERE provider_payment_id=%s",(provider,)).fetchone()==(("INTENT","UPGRADE")[winner],claim_objects[winner],(tenant,reviewer_tenant)[winner])
    print("M41550_PROVIDER_REGISTRY_CONCURRENT=PASS")
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
