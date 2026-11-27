"""Real FastAPI route and SQL transactions; canonical schema in disposable PG18."""
import asyncio,os
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
import asyncpg
import httpx
from fastapi import FastAPI
from app.routers import product_v23

async def main():
    expected={"GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1","PGHOST":"127.0.0.1","PGPORT":"5432","PGUSER":"postgres","PGPASSWORD":"ci-test-only","PGDATABASE":"frcaixinha_ci","PIX_REAL":"OFF","PAGAMENTOS_REAIS":"OFF","ATIVACAO_REAL":"OFF"}
    if any(os.getenv(k)!=v for k,v in expected.items()): raise RuntimeError("M41320_DISPOSABLE_ONLY")
    owner=await asyncpg.connect(host="127.0.0.1",port=5432,database="frcaixinha_ci",user="postgres",password="ci-test-only")
    assert await owner.fetchval("SELECT current_setting('server_version_num')::int BETWEEN 180000 AND 189999")
    pool=await asyncpg.create_pool(host="127.0.0.1",port=5432,database="frcaixinha_ci",user="frcaixinha_pg18_app",password="ci-test-only",min_size=1,max_size=4)
    app=FastAPI()
    app.include_router(product_v23.router)
    async def transaction():
        async with pool.acquire() as conn:
            async with conn.transaction(): yield conn
    app.dependency_overrides[product_v23.unreleased_transaction]=transaction
    async def user():
        u=uuid4()
        await owner.execute("INSERT INTO public.users(id,email,full_name,cpf,phone,status) VALUES($1,$2,'CI V23',$3,'+550000000000','ACTIVE')",u,f"ci-v23-{u}@example.invalid",u.hex[:14])
        return u
    async def tenant(admin):
        t=uuid4()
        await owner.execute("INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status) VALUES($1,'CI V23',$2,$3,'ATIVO')",t,str(t),admin)
        await owner.execute("INSERT INTO public.memberships(tenant_id,user_id,role,status,joined_at) VALUES($1,$2,'TENANT_ADMIN','ATIVA','2026-12-10')",t,admin)
        return t
    async def member(t,u):
        return await owner.fetchval("INSERT INTO public.memberships(tenant_id,user_id,role,status,joined_at) VALUES($1,$2,'TENANT_MEMBER','ATIVA','2026-12-10') RETURNING id",t,u)
    async def token(t,u,role):
        raw=uuid4().hex+uuid4().hex
        await owner.execute("INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at) VALUES(encode(public.digest($1,'sha256'),'hex'),$2,$3,$4,now()+interval '30 minutes')",raw,u,role,t)
        return {"Authorization":"Bearer "+raw}
    try:
        admin,member_a,member_b,other_admin=await user(),await user(),await user(),await user()
        t,other=await tenant(admin),await tenant(other_admin)
        ma,mb=await member(t,member_a),await member(t,member_b)
        h,ha,hb,ho=await token(t,admin,"TENANT_ADMIN"),await token(t,member_a,"TENANT_MEMBER"),await token(t,member_b,"TENANT_MEMBER"),await token(other,other_admin,"TENANT_ADMIN")
        doc=await owner.fetchval("INSERT INTO public.contract_documents(document_kind,version_label,sha256,source_reference,published_at) VALUES('TENANT_MEMBERSHIP',$1,$2,'CI_ONLY_V23',now()) RETURNING id","CI-"+uuid4().hex,"a"*64)
        for u in (admin,member_a):
            await owner.execute("INSERT INTO public.contract_acceptances(document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method) VALUES($1,'TENANT_MEMBERSHIP',$2,$3,$4,'CI_VERIFIED_IDENTITY')",doc,u,t,"b"*64)
        # Synthetic Contract A, price and payment in the SAME disposable canonical schema.
        contract_a=await owner.fetchval("INSERT INTO public.contract_documents(document_kind,version_label,sha256,source_reference,published_at) VALUES('PLATFORM_LICENSE',$1,$2,'CI_ONLY_V23_A',now()) RETURNING id","CI-"+uuid4().hex,"c"*64)
        price=await owner.fetchval("INSERT INTO public.platform_license_price_versions(plan_tier,monthly_price,annual_price,reason) VALUES('ESSENCIAL',89.90,700.33,'CI independent pricing only') RETURNING id")
        async def seed_license(tenant_id,actor,period,amount):
            acc=await owner.fetchval("INSERT INTO public.contract_acceptances(document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method) VALUES($1,'PLATFORM_LICENSE',$2,NULL,$3,'CI_VERIFIED_IDENTITY') RETURNING id",contract_a,actor,"d"*64)
            prep=await owner.fetchval("INSERT INTO public.saas_subscription_preparations(tenant_id,admin_user_id,plan_tier,price_version_id,billing_period,contract_acceptance_id) VALUES($1,$2,'ESSENCIAL',$3,$4,$5) RETURNING id",tenant_id,actor,price,period,acc)
            pay=await owner.fetchval("INSERT INTO public.saas_payment_intents(preparation_id,tenant_id,admin_user_id,price_version_id,expected_amount_cents,external_reference,idempotency_key,provider_payment_id,platform_collector_id,live_mode,status,paid_at,reconciled_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,'123',false,'APPROVED',now(),now()) RETURNING id",prep,tenant_id,actor,price,amount,"CI-"+uuid4().hex,uuid4().hex,str(uuid4().int)[:38])
            ent=await owner.fetchval("INSERT INTO public.saas_license_entitlements(preparation_id,payment_intent_id,tenant_id,plan_tier,valid_from,valid_until) VALUES($1,$2,$3,'ESSENCIAL',now()-interval '1 day',now()+interval '30 days') RETURNING id",prep,pay,tenant_id)
            return ent,pay
        prefix=f"/tenants/{t}/v23"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://ci.invalid") as client:
            cycle=dict(request_id=str(uuid4()),start="2026-12-10",first_due="2026-12-10",last_due="2027-11-10",closing="2027-12-20",quota_cents=5000,admin_bps=1300,late_days=75,late_competences=2,mode="MANUAL",document_id=str(doc))
            async def post(path,body,headers=h,status=200):
                res=await client.post(prefix+path,json=body,headers=headers)
                assert res.status_code==status,(path,status,res.status_code,res.text)
                return res.json()
            async def accepted(policy):
                digest=(await post("/policies/preview",policy))["policy_hash"]
                return {**policy,"policy_hash":digest,"accepted":True}
            await post("/policies/preview",cycle,ha,403)
            await post("/policies/preview",cycle,ho,403)
            payload=await accepted(cycle)
            await post("/cycles",payload,h,403)
            ent,pay=await seed_license(t,admin,"MONTHLY",8990)
            other_ent,other_pay=await seed_license(other,other_admin,"ANNUAL",70033)
            assert await owner.fetchval("SELECT quotas_limit FROM public.fr_v23_license($1,$2)",other,other_admin)==40
            await owner.execute("UPDATE public.saas_payment_intents SET expected_amount_cents=70034 WHERE id=$1",other_pay)
            try:
                await owner.fetchval("SELECT quotas_limit FROM public.fr_v23_license($1,$2)",other,other_admin)
            except asyncpg.InsufficientPrivilegeError: pass
            else: raise AssertionError("incorrect annual price accepted")
            await owner.execute("UPDATE public.saas_payment_intents SET expected_amount_cents=70033 WHERE id=$1",other_pay)
            await post("/cycles",{**payload,"policy_hash":"0"*64},h,409)
            await post("/cycles",payload,ha,403)
            await post("/cycles",payload,ho,403)
            c=(await post("/cycles",payload))["cycle_id"]
            assert (await post("/cycles",payload))["cycle_id"]==c
            await post("/cycles",{**payload,"quota_cents":5001},h,409)
            payload2=await accepted({**cycle,"request_id":str(uuid4()),"mode":"HYBRID"})
            c2=(await post("/cycles",payload2))["cycle_id"]
            assert c!=c2 and payload["policy_hash"]!=payload2["policy_hash"]
            try:
                await owner.execute("UPDATE public.cycles SET settlement_date=settlement_date+1 WHERE id=$1",UUID(c))
            except asyncpg.CheckViolationError: pass
            else: raise AssertionError("accepted dates editable")
            # M41390: no policy discovery without a scoped cycle invitation.
            assert (await client.get(prefix+f"/cycles/{c}/policy",headers=ha)).status_code==403
            assert (await client.get(prefix+"/cycles",headers=ha)).json()["items"]==[]
            expires=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
            async def bind_invite(cid,quotas=2,member_id=ma,headers=h,status=200,expiry=expires):
                return await post(f"/cycles/{cid}/invitations",dict(membership_id=str(member_id),joined="2027-01-10",quotas=quotas,expires_at=expiry),headers,status)
            await bind_invite(c,status=403)
            await owner.execute("UPDATE public.users SET email_verified_at=now() WHERE id=$1",member_a)
            await bind_invite(c,headers=ha,status=403)
            await bind_invite(c,headers=ho,status=403)
            await bind_invite(c,member_id=mb,status=403)
            await bind_invite(c,expiry=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),status=422)
            i1,i2=await asyncio.gather(bind_invite(c),bind_invite(c))
            assert i1==i2
            await bind_invite(c,quotas=3,status=409)
            await bind_invite(c2)
            await owner.execute("UPDATE public.users SET email_verified_at=now() WHERE id=$1",member_b)
            ib=(await bind_invite(c2,member_id=mb))["invitation_id"]
            await post(f"/cycles/{c}/invitations/{ib}/revoke",{},h,403)
            await post(f"/cycles/{c2}/invitations/{ib}/revoke",{},hb,403)
            assert (await post(f"/cycles/{c2}/invitations/{ib}/revoke",{}))["state"]=="REVOKED"
            assert (await post(f"/cycles/{c2}/invitations/{ib}/revoke",{}))["state"]=="REVOKED"
            assert (await client.get(prefix+f"/cycles/{c2}/workspace",headers=hb)).status_code==403
            discovered=(await client.get(prefix+"/cycles",headers=ha)).json()
            assert {x["cycle_id"] for x in discovered["items"]}=={c,c2}
            assert all(x["membership_state"]=="INVITED" for x in discovered["items"])
            pending=(await client.get(prefix+f"/cycles/{c}/workspace",headers=ha)).json()
            assert pending["invitation"]["id"]==i1["invitation_id"] and pending["invitation"]["quotas"]==2
            assert pending["summary"] is None and pending["reserves"] is None and pending["items"]==[]
            assert (await client.get(prefix+f"/cycles/{c}/my-contributions",headers=ha)).status_code==403
            policy=await client.get(prefix+f"/cycles/{c}/policy",headers=ha)
            assert policy.status_code==200 and policy.json()["policy_hash"]==payload["policy_hash"] and policy.json()["quota_cents"]==5000
            assert (await client.get(prefix+f"/cycles/{c}/policy",headers=ho)).status_code==403
            admission=dict(membership_id=str(ma),joined="2027-01-10",quotas=2)
            consent=dict(policy_hash=payload["policy_hash"],joined=admission["joined"],quotas=2,accepted=True)
            await post(f"/cycles/{c}/admissions",admission,h,403)
            await post(f"/cycles/{c}/policy-acceptance",consent,h,403)
            await post(f"/cycles/{c}/policy-acceptance",consent,hb,403)
            await post(f"/cycles/{c}/policy-acceptance",consent,ho,403)
            await post(f"/cycles/{c2}/policy-acceptance",consent,ha,409)
            await post(f"/cycles/{c}/policy-acceptance",{**consent,"quotas":3},ha,409)
            consent_id=(await post(f"/cycles/{c}/policy-acceptance",consent,ha))["consent_id"]
            await post(f"/cycles/{c}/invitations/{i1['invitation_id']}/revoke",{},h,409)
            assert (await post(f"/cycles/{c}/policy-acceptance",consent,ha))["consent_id"]==consent_id
            await post(f"/cycles/{c}/policy-acceptance",{**consent,"quotas":3},ha,409)
            assert (await post(f"/cycles/{c}/admissions",admission))["obligations"]==11
            await post(f"/cycles/{c2}/admissions",admission,h,403)
            await post(f"/cycles/{c2}/policy-acceptance",{**consent,"policy_hash":payload2["policy_hash"]},ha)
            assert (await post(f"/cycles/{c2}/admissions",admission))["obligations"]==11
            await post(f"/cycles/{c}/admissions",{**admission,"membership_id":str(mb)},h,403)
            await post(f"/cycles/{c}/admissions",{**admission,"quotas":3},h,409)
            # Capacity race: 4 existing quotas; two separate 36-quota admissions compete.
            extras=[]
            for _ in range(2):
                ex=await accepted({**cycle,"request_id":str(uuid4())})
                ec=(await post("/cycles",ex))["cycle_id"]
                await bind_invite(ec,quotas=36)
                await post(f"/cycles/{ec}/policy-acceptance",{**consent,"policy_hash":ex["policy_hash"],"quotas":36},ha)
                extras.append(ec)
            await owner.execute("UPDATE public.saas_license_entitlements SET status='SUSPENDED' WHERE id=$1",ent)
            await post(f"/cycles/{extras[0]}/admissions",{**admission,"quotas":36},h,403)
            assert (await post(f"/cycles/{c}/admissions",admission))["obligations"]==11
            blocked_cycle=await accepted({**cycle,"request_id":str(uuid4())})
            await post("/cycles",blocked_cycle,h,403)
            await bind_invite(extras[0],member_id=mb,status=403)
            assert (await post("/cycles",payload))["cycle_id"]==c
            await owner.execute("UPDATE public.saas_license_entitlements SET status='ACTIVE' WHERE id=$1",ent)
            outcomes=await asyncio.gather(*[client.post(prefix+f"/cycles/{ec}/admissions",json={**admission,"quotas":36},headers=h) for ec in extras])
            assert sorted(x.status_code for x in outcomes)==[200,409],[(x.status_code,x.text) for x in outcomes]
            assert await owner.fetchval("SELECT sum(ad.quotas) FROM public.fr_v23_admission ad JOIN public.cycles c ON c.id=ad.cycle_id WHERE c.tenant_id=$1",t)==40
            assert await owner.fetchval("SELECT count(*) FROM public.platform_license_plans WHERE tier='AMPLIADO' AND members_limit=200 AND quotas_limit=400 AND status='BLOCKED_PENDING_CEILING'")==1
            assert await owner.fetchval("SELECT count(*) FROM public.fr_v23_member_consent WHERE cycle_id=$1 AND id=$2",UUID(c),UUID(consent_id))==1
            obligation=await owner.fetchval("SELECT id FROM public.contributions WHERE cycle_id=$1 AND membership_id=$2 ORDER BY due_date LIMIT 1",UUID(c),ma)
            row=dict(request_id=str(uuid4()),contribution_id=str(obligation),cents=6000,method="DINHEIRO",occurred="2027-01-10",reference="CI-"+uuid4().hex,evidence_ref="CI-RECIBO-001")
            await post("/manual-receipts",row,ha,403)
            await post("/manual-receipts",row,ho,403)
            row2={**row,"request_id":str(uuid4()),"reference":"CI-"+uuid4().hex}
            responses=await asyncio.gather(client.post(prefix+"/manual-receipts",json=row,headers=h),client.post(prefix+"/manual-receipts",json=row2,headers=h))
            assert sorted(x.status_code for x in responses)==[200,409],[(x.status_code,x.text) for x in responses]
            winner=next(i for i,x in enumerate(responses) if x.status_code==200)
            selected=(row,row2)[winner];rid=responses[winner].json()["receipt_id"]
            assert (await post("/manual-receipts",selected))["receipt_id"]==rid
            assert await owner.fetchval("SELECT amount_paid FROM public.contributions WHERE id=$1",obligation)==0
            assert await owner.fetchval("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=$1",t)==0
            review=dict(request_id=str(uuid4()),occurred="2027-01-10",evidence_ref="CI-CONFERENCIA")
            assert (await post(f"/manual-receipts/{rid}/CONFIRM",review))["state"]=="CONFIRMED"
            assert (await post(f"/manual-receipts/{rid}/CONFIRM",review))["state"]=="CONFIRMED"
            assert await owner.fetchval("SELECT amount_paid FROM public.contributions WHERE id=$1",obligation)==60
            assert await owner.fetchval("SELECT payment_status FROM public.contributions WHERE id=$1",obligation)=="PARCIAL"
            receipt=await client.get(prefix+f"/manual-receipts/{rid}",headers=ha)
            assert receipt.status_code==200 and receipt.json()["bank_reconciled"] is False
            assert (await client.get(prefix+f"/manual-receipts/{rid}",headers=hb)).status_code==403
            await post(f"/manual-receipts/{rid}/CONTEST",{**review,"request_id":str(uuid4())},hb,403)
            assert (await post(f"/manual-receipts/{rid}/CONTEST",{**review,"request_id":str(uuid4())},ha))["state"]=="CONTESTED"
            rev={**review,"request_id":str(uuid4()),"occurred":"2027-01-11"}
            assert (await post(f"/manual-receipts/{rid}/REVERSE",rev))["state"]=="REVERSED"
            assert await owner.fetchval("SELECT amount_paid FROM public.contributions WHERE id=$1",obligation)==0
            assert await owner.fetchval("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=$1",t)==2
            assert await owner.fetchval("SELECT count(*) FROM public.ledger_entries WHERE tenant_id=$1",t)==4
            assert await owner.fetchval("SELECT balance_cents FROM public.ledger_accounts WHERE tenant_id=$1 AND cycle_id=$2 AND cycle_account_kind='MANUAL_DOCUMENTED'",t,UUID(c))==0
            assert await owner.fetchval("SELECT count(*) FROM public.ledger_accounts WHERE tenant_id=$1 AND cycle_id IS NULL AND balance_cents<>0",t)==0
            assert await owner.fetchval("SELECT coalesce(sum(CASE WHEN entry_type='DR' THEN amount_cents ELSE -amount_cents END),0) FROM public.ledger_entries WHERE tenant_id=$1",t)==0
            # M41330: two active cycles; another member and tenant cannot read.
            async def get(path,headers=h,status=200):
                res=await client.get(prefix+path,headers=headers)
                assert res.status_code==status,(path,status,res.status_code,res.text)
                return res.json()
            first=f"/cycles/{c}/financial-summary"
            second=f"/cycles/{c2}/financial-summary"
            assert (await get(first))["manual_documented_cents"]==0
            assert (await get(second))["manual_documented_cents"]==0
            await get(first,ha,403)
            await get(first,ho,403)
            await get(f"/cycles/{uuid4()}/financial-summary",h,403)
            mine=f"/cycles/{c}/my-contributions"
            await get(mine,h,403)
            await get(mine,hb,403)
            await get(mine,ho,403)
            assert (await get(mine,ha))["membership_id"]==str(ma)
            obligation2=await owner.fetchval("SELECT id FROM public.contributions WHERE cycle_id=$1 AND membership_id=$2 ORDER BY due_date LIMIT 1",UUID(c2),ma)
            def new_receipt(ob,cents):
                return {**row,"request_id":str(uuid4()),"reference":"CI-"+uuid4().hex,"contribution_id":str(ob),"cents":cents}
            rid1=(await post("/manual-receipts",new_receipt(obligation,3000)))["receipt_id"]
            rid2=(await post("/manual-receipts",new_receipt(obligation2,7000)))["receipt_id"]
            assert (await get(first))["manual_pending_cents"]==3000
            assert (await get(second))["manual_pending_cents"]==7000
            assert (await get(mine,ha))["manual_pending_cents"]==3000
            reviews=await asyncio.gather(*[client.post(prefix+f"/manual-receipts/{receipt_id}/CONFIRM",json={**review,"request_id":str(uuid4())},headers=h) for receipt_id in (rid1,rid2)])
            assert all(x.status_code==200 for x in reviews),[(x.status_code,x.text) for x in reviews]
            a1,a2=await get(first),await get(second)
            assert a1["manual_documented_cents"]==a1["member_capital_documented_cents"]==a1["paid_cents"]==3000
            assert a2["manual_documented_cents"]==a2["member_capital_documented_cents"]==a2["paid_cents"]==7000
            assert a1["bank_reconciled"] is False and a2["bank_reconciled"] is False
            own=await get(mine,ha)
            assert own["paid_cents"]==3000 and "manual_documented_cents" not in own
            assert (await get(f"/cycles/{c2}/my-contributions",ha))["paid_cents"]==7000
            tx=await owner.fetchval("SELECT id FROM public.ledger_transactions WHERE tenant_id=$1 AND cycle_id=$2 LIMIT 1",t,UUID(c))
            wrong_account=await owner.fetchval("SELECT id FROM public.ledger_accounts WHERE tenant_id=$1 AND cycle_id=$2 AND cycle_account_kind='MANUAL_DOCUMENTED'",t,UUID(c2))
            try:
                await owner.execute("INSERT INTO public.ledger_entries(tenant_id,transaction_id,account_id,entry_type,amount_cents) VALUES($1,$2,$3,'DR',1)",t,tx,wrong_account)
            except asyncpg.CheckViolationError: pass
            else: raise AssertionError("cross-cycle entry accepted")
            try:
                await owner.execute("UPDATE public.ledger_transactions SET cycle_id=$2 WHERE id=$1",tx,UUID(c2))
            except asyncpg.CheckViolationError: pass
            else: raise AssertionError("cycle reassignment accepted")
            await post(f"/manual-receipts/{rid1}/CONTEST",{**review,"request_id":str(uuid4())},ha)
            assert (await get(first))["contested_receipts"]==1
            assert (await get(second))["contested_receipts"]==0
            await post(f"/manual-receipts/{rid1}/REVERSE",{**rev,"request_id":str(uuid4())})
            assert (await get(first))["manual_documented_cents"]==0
            assert (await get(second))["manual_documented_cents"]==7000
            assert (await get(mine,ha))["paid_cents"]==0
            assert await owner.fetchval("SELECT count(*) FROM public.ledger_entries e JOIN public.ledger_transactions x ON x.id=e.transaction_id JOIN public.ledger_accounts a ON a.id=e.account_id WHERE e.tenant_id=$1 AND x.cycle_id IS DISTINCT FROM a.cycle_id",t)==0
            assert await owner.fetchval("SELECT count(*) FROM (SELECT x.cycle_id,sum(CASE WHEN e.entry_type='DR' THEN e.amount_cents ELSE -e.amount_cents END) n FROM public.ledger_entries e JOIN public.ledger_transactions x ON x.id=e.transaction_id WHERE e.tenant_id=$1 GROUP BY x.cycle_id HAVING sum(CASE WHEN e.entry_type='DR' THEN e.amount_cents ELSE -e.amount_cents END)<>0) q",t)==0
            # M41350: managerial holds are not bank liquidity or journal postings.
            res1=f"/cycles/{c}/reserves"
            res2=f"/cycles/{c2}/reserves"
            await get(res2,ha,403)
            await get(res2,ho,403)
            hold=dict(request_id=str(uuid4()),action="HOLD",cents=4000,reason="CI reserva gerencial")
            await post(res1,hold,h,409)
            await post(res2,hold,ha,403)
            await post(res2,hold,ho,403)
            base_tx=await owner.fetchval("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=$1",t)
            holds=[hold,{**hold,"request_id":str(uuid4())}]
            hold_results=await asyncio.gather(*[client.post(prefix+res2,json=p,headers=h) for p in holds])
            assert sorted(x.status_code for x in hold_results)==[200,409],[(x.status_code,x.text) for x in hold_results]
            winner=next(i for i,x in enumerate(hold_results) if x.status_code==200)
            held=hold_results[winner].json()["event_id"]
            assert (await post(res2,holds[winner]))["event_id"]==held
            await post(res2,{**holds[winner],"cents":1},h,409)
            snap=await get(res2)
            assert snap["documented_cents"]==7000 and snap["reserved_cents"]==4000 and snap["unreserved_documented_cents"]==3000
            assert snap["bank_available_cents"]==0 and snap["payout_authorized"] is False and snap["bank_reconciled"] is False
            assert (await get(res1))["reserved_cents"]==0
            assert await owner.fetchval("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=$1",t)==base_tx
            # Suspension does not erase existing commitments or permit new holds.
            await owner.execute("UPDATE public.saas_license_entitlements SET status='SUSPENDED' WHERE id=$1",ent)
            await post(res2,{**hold,"request_id":str(uuid4()),"cents":1},h,403)
            assert (await post(res2,holds[winner]))["event_id"]==held
            assert (await get(first))["paid_cents"]==0
            assert (await get(f"/cycles/{c2}/my-contributions",ha))["paid_cents"]==7000
            await get(f"/cycles/{c2}/my-contributions",hb,403)
            await post(f"/manual-receipts/{rid2}/CONTEST",{**review,"request_id":str(uuid4())},ha)
            assert (await get(res2))["reserve_deficit_cents"]==4000
            await post(res2,{**hold,"request_id":str(uuid4()),"cents":1},h,403)
            # Compensation remains possible even when it exposes a reservation deficit.
            await post(f"/manual-receipts/{rid2}/REVERSE",{**rev,"request_id":str(uuid4())})
            assert (await get(res2))["documented_cents"]==0 and (await get(res2))["reserve_deficit_cents"]==4000
            release={**hold,"request_id":str(uuid4()),"action":"RELEASE","related_hold":held}
            await post(res1,release,h,403)
            await post(res2,{**release,"cents":3999},h,409)
            opts=lambda cycle,kind:f"/cycles/{cycle}/form-options?kind={kind}"
            before=await get(opts(c2,"RELEASE"))
            assert before["cycle_id"]==c2 and before["kind"]=="RELEASE"
            assert [x["id"] for x in before["items"]]==[held] and before["items"][0]["cents"]==4000
            assert (await get(opts(c,"RELEASE")))["items"]==[]
            await get(opts(c2,"RELEASE"),ha,403)
            await get(opts(c2,"RELEASE"),ho,403)
            await get(opts(c2,"CONTEST"),h,403)
            released=(await post(res2,release))["event_id"]
            assert (await post(res2,release))["event_id"]==released
            await post(res2,{**release,"request_id":str(uuid4())},h,409)
            assert (await get(res2))["reserved_cents"]==0 and (await get(res2))["reserve_deficit_cents"]==0
            assert (await get(opts(c2,"RELEASE")))["items"]==[]
            # Existing obligation can still be documented and corrected in suspension.
            continuation_receipt=(await post("/manual-receipts",new_receipt(obligation,100)))["receipt_id"]
            assert (await post(f"/manual-receipts/{continuation_receipt}/CONFIRM",{**review,"request_id":str(uuid4())}))["state"]=="CONFIRMED"
            assert (await post(f"/manual-receipts/{continuation_receipt}/REVERSE",{**rev,"request_id":str(uuid4())}))["state"]=="REVERSED"
            assert (await get(first))["paid_cents"]==0
            await owner.execute("UPDATE public.saas_license_entitlements SET status='ACTIVE' WHERE id=$1",ent)
            print("M41470_SUSPENSION_NEW_COMMITMENTS_DENIED_CONTINUITY_PRESERVED=PASS")
            # Synthetic canonical intent only: no provider call, no settlement.
            async def pix(ob,tenant_id=t,payer=member_a):
                return await owner.fetchval("INSERT INTO public.pix_payment_intents(tenant_id,contribution_id,payer_user_id,amount_cents,idempotency_key,pix_copy_paste,expires_at) VALUES($1,$2,$3,1000,$4,'CI_NOT_A_PIX_CODE',now()+interval '10 minutes') RETURNING id",tenant_id,ob,payer,uuid4().hex)
            async def rejected(operation):
                try: await operation
                except asyncpg.CheckViolationError: pass
                else: raise AssertionError("unsafe canonical intent accepted")
            await rejected(pix(obligation))
            await rejected(pix(obligation2,other))
            await rejected(pix(obligation2,t,member_b))
            intent=await pix(obligation2)
            await rejected(pix(obligation2))
            await post("/manual-receipts",new_receipt(obligation2,1000),h,409)
            await rejected(owner.execute("UPDATE public.pix_payment_intents SET status='LIQUIDADO_CONFIRMADO' WHERE id=$1",intent))
            await rejected(owner.execute("DELETE FROM public.pix_payment_intents WHERE id=$1",intent))
            await owner.execute("UPDATE public.pix_payment_intents SET status='EXPIRADO' WHERE id=$1",intent)
            await rejected(owner.execute("UPDATE public.pix_payment_intents SET status='PENDENTE' WHERE id=$1",intent))
            new=(await post("/manual-receipts",new_receipt(obligation2,1000)))["receipt_id"]
            await rejected(pix(obligation2))
            pending_options=await get(opts(c2,"CONFIRM"))
            assert [x["id"] for x in pending_options["items"]]==[new]
            assert pending_options["items"][0]["related_id"]==str(obligation2)
            assert (await get(opts(c,"CONFIRM")))["items"]==[]
            await get(opts(c2,"CONFIRM"),ha,403)
            await post(f"/manual-receipts/{new}/CONFIRM",{**review,"request_id":str(uuid4())})
            assert (await get(opts(c2,"CONFIRM")))["items"]==[]
            assert [x["id"] for x in (await get(opts(c2,"CONTEST"),ha))["items"]]==[new]
            assert [x["id"] for x in (await get(opts(c2,"REVERSE")))["items"]]==[new]
            await get(opts(c2,"CONTEST"),hb,403)
            await get(opts(c2,"CONTEST"),ho,403)
            await rejected(pix(obligation2))
            # Race on another contribution: only one channel can claim it.
            ob3=await owner.fetchval("SELECT id FROM public.contributions WHERE cycle_id=$1 AND membership_id=$2 AND id<>$3 ORDER BY due_date LIMIT 1",UUID(c2),ma,obligation2)
            async def pix_attempt():
                try: await pix(ob3)
                except asyncpg.CheckViolationError: return 409
                return 200
            async def manual_attempt():
                return (await client.post(prefix+"/manual-receipts",json=new_receipt(ob3,1000),headers=h)).status_code
            assert sorted(await asyncio.gather(pix_attempt(),manual_attempt()))==[200,409]
            assert await owner.fetchval("SELECT amount_paid FROM public.contributions WHERE id=$1",ob3)==0
            # M41360 real API readback for mobile: no unrelated cycle or member data.
            directory=await get("/cycles")
            assert directory["tenant_id"]==str(t) and directory["role"]=="TENANT_ADMIN" and directory["user_id"]==str(admin)
            assert {x["cycle_id"] for x in directory["items"]}=={c,c2,*extras}
            own_dir=await get("/cycles",ha)
            assert own_dir["role"]=="TENANT_MEMBER" and all(x["membership_state"] in ("ADMITTED","CONSENTED") for x in own_dir["items"])
            assert (await get("/cycles",hb))["items"]==[]
            await get("/cycles",ho,403)
            admin_workspace=await get(f"/cycles/{c2}/workspace")
            assert admin_workspace["policy"]["quota_cents"]==5000
            assert admin_workspace["reserves"]["bank_available_cents"]==0
            assert admin_workspace["summary"]["paid_cents"]==1000
            assert len(admin_workspace["items"])==11
            own_workspace=await get(f"/cycles/{c2}/workspace",ha)
            assert own_workspace["membership_id"]==str(ma) and own_workspace["reserves"] is None
            assert "manual_documented_cents" not in own_workspace["summary"]
            assert all(x["membership_id"]==str(ma) for x in own_workspace["items"])
            assert (await get(f"/cycles/{c2}/workspace?offset=10",ha))["items"][0]["due_date"]=="2027-11-10"
            await get(f"/cycles/{c2}/workspace",hb,403)
            await get(f"/cycles/{c2}/workspace",ho,403)
            await get(f"/cycles/{uuid4()}/workspace",h,403)
            pending_cycle=extras[1] if (await owner.fetchval("SELECT count(*) FROM public.fr_v23_admission WHERE cycle_id=$1",UUID(extras[0]))) else extras[0]
            docs=await get("/form-options")
            assert docs["kind"]=="DOCUMENT" and docs["cycle_id"] is None and docs["items"]
            assert all(len(x["document_hash"])==64 for x in docs["items"])
            await get("/form-options",ha,403)
            await get("/form-options",ho,403)
            assert (await get(opts(c2,"ADMIT")))["items"]==[]
            pending_options=await get(opts(pending_cycle,"ADMIT"))
            assert any(x["id"]==str(ma) and x["quotas"]>0 for x in pending_options["items"])
            await get(opts(pending_cycle,"ADMIT"),ha,403)
            assert (await get(opts(pending_cycle,"ADMIT")+"&offset=50"))["items"]==[]
            pending_workspace=await get(f"/cycles/{pending_cycle}/workspace",ha)
            assert pending_workspace["summary"] is None and pending_workspace["items"]==[] and pending_workspace["reserves"] is None
            async with pool.acquire() as conn:
                try: await conn.fetchval("SELECT count(*) FROM public.fr_v23_reservation_events")
                except asyncpg.InsufficientPrivilegeError: pass
                else: raise AssertionError("direct reserve access")
                try: await conn.fetchval("SELECT count(*) FROM public.fr_v23_receipts")
                except asyncpg.InsufficientPrivilegeError: pass
                else: raise AssertionError("direct table access")
                try: await conn.fetchval("SELECT count(*) FROM public.fr_v23_member_consent")
                except asyncpg.InsufficientPrivilegeError: pass
                else: raise AssertionError("direct consent table access")
            # M41400: compose canonical identity proof with cycle consent; no financial admission.
            from m41400_cycle_identity_ci import exercise
            person,new_member=await asyncio.to_thread(exercise,t,UUID(c),UUID(c2),h["Authorization"].split()[1],ha["Authorization"].split()[1],doc,payload["policy_hash"])
            new_headers=await token(t,person,"TENANT_MEMBER")
            new_directory=await get("/cycles",new_headers)
            assert [(x["cycle_id"],x["membership_state"]) for x in new_directory["items"]]==[(c,"CONSENTED")]
            new_ws=await get(f"/cycles/{c}/workspace",new_headers)
            assert new_ws["membership_id"]==str(new_member) and new_ws["summary"] is None and new_ws["items"]==[]
            await get(f"/cycles/{c2}/workspace",new_headers,403)
            await post(f"/cycles/{c}/admissions",dict(membership_id=str(new_member),joined="2027-01-10",quotas=2),h,409)
            # M41410: initial administrator, exact A, checkout and independent B.
            from m41410_admin_license_ci import exercise as exercise_admin, accept_b_and_member
            from hashlib import sha256
            from app.onboarding_readback_ci import TEXTS
            a_hash=sha256(TEXTS["CI_M41430_A"].encode()).hexdigest()
            b_hash=sha256(TEXTS["CI_M41430_B"].encode()).hexdigest()
            doc_a=await owner.fetchval("INSERT INTO public.contract_documents(document_kind,version_label,sha256,source_reference,published_at) VALUES('PLATFORM_LICENSE',$1,$2,'CI_M41430_A',now()) RETURNING id","CI-"+uuid4().hex,a_hash)
            doc_b=await owner.fetchval("INSERT INTO public.contract_documents(document_kind,version_label,sha256,source_reference,published_at) VALUES('TENANT_MEMBERSHIP',$1,$2,'CI_M41430_B',now()) RETURNING id","CI-"+uuid4().hex,b_hash)
            admin_results=await asyncio.to_thread(exercise_admin,other_admin,other,ho["Authorization"].split()[1],doc_a,price,doc_b,a_hash,b_hash)
            for index,(new_admin,new_tenant,admin_raw) in enumerate(admin_results):
                ap=f"/tenants/{new_tenant}/v23"
                ah={"Authorization":"Bearer "+admin_raw}
                form={**cycle,"request_id":str(uuid4()),"document_id":str(doc_b)}
                denied=await client.post(ap+"/policies/preview",json=form,headers=ah)
                assert denied.status_code==403
                await asyncio.to_thread(accept_b_and_member,"B",new_tenant,admin_raw,doc_b,b_hash)
                preview=await client.post(ap+"/policies/preview",json=form,headers=ah)
                assert preview.status_code==200,preview.text
                digest=preview.json()["policy_hash"]
                opened=await client.post(ap+"/cycles",json={**form,"policy_hash":digest,"accepted":True},headers=ah)
                assert opened.status_code==200,opened.text
                nc=opened.json()["cycle_id"]
                assert (await client.get(ap+f"/cycles/{nc}/workspace",headers=ho)).status_code==403
                assert (await client.get(ap+"/cycles",headers=ah)).json()["items"][0]["cycle_id"]==nc
                person,mid=await asyncio.to_thread(accept_b_and_member,"MEMBER",new_tenant,admin_raw,doc_b,b_hash,UUID(nc),digest)
                mh=await token(new_tenant,person,"TENANT_MEMBER")
                assert (await client.get(ap+"/cycles",headers=mh)).json()["items"][0]["membership_state"]=="CONSENTED"
                admitted=await client.post(ap+f"/cycles/{nc}/admissions",json=dict(membership_id=str(mid),joined="2027-01-10",quotas=2),headers=ah)
                assert admitted.status_code==200,admitted.text
                assert admitted.json()["obligations"]==11
                from m41480_saas_renewal_ci import exercise as exercise_renewal
                await asyncio.to_thread(exercise_renewal,new_tenant,new_admin,admin_raw,other,ho["Authorization"].split()[1],price,doc_a,a_hash,bool(index))
            await owner.execute("UPDATE public.sessions SET revoked_at=now() WHERE token_hash=encode(public.digest($1,'sha256'),'hex')",h["Authorization"].split()[1])
            await post("/manual-receipts",selected,h,403)
            await get("/form-options",h,403)
        print("M41320_CANONICAL_PG18_API_CYCLE_ADMISSION_MANUAL_CONCURRENCY=PASS")
        print("M41330_CANONICAL_LEDGER_CYCLE_SCOPE_SUMMARIES_REVERSAL=PASS")
        print("M41340_CANONICAL_POLICY_CONSENT_LICENSE_CAPACITY_RACE=PASS")
        print("M41350_CYCLE_RESERVES_DEFICIT_CANONICAL_PIX_EXCLUSION=PASS")
        print("M41360_CANONICAL_MOBILE_DIRECTORY_WORKSPACE_SCOPE=PASS")
        print("M41380_SCOPED_FORM_OPTIONS_READBACK=PASS")
        print("M41390_NOMINAL_CYCLE_INVITE_PRECONSENT_REVOCATION_SCOPE_RACE=PASS")
        print("M41400_NEW_IDENTITY_REISSUE_DUAL_PROOF_ATOMIC_CONSENT_RACE=PASS")
        print("M41410_PRELIMINARY_ADMIN_A_INDEPENDENT_SAAS_PERIODS_DRAFT_GATE_B=PASS")
    finally:
        await pool.close()
        await owner.close()

if __name__=="__main__": asyncio.run(main())
