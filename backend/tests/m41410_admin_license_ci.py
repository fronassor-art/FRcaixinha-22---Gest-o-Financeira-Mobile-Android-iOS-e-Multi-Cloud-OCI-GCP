"""M41410 canonical initial admin and independent SaaS terms in disposable PG18."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from decimal import Decimal
from app.account_lifecycle import LifecycleDenied, simulate_invitation_delivery_ci
from app.invite_registration_ci import prepare_invite_email_verification_ci
from app.security import hash_password_secure,hash_token
from app.admin_license_onboarding_ci import (stage_admin_invite_ci,register_admin_ci,
    prepare_admin_checkout_ci,reconcile_admin_checkout_ci,accept_admin_b_ci)
from m41400_cycle_identity_ci import connection,reject
from m41420_onboarding_http_ci import client_for,post,get
from hashlib import sha256
from m41440_onboarding_form_bridge_ci import form_request,scope_of
from uuid import UUID
from m41450_preliminary_session_ci import begin,login,journey
from app.preliminary_token_ci import preliminary_digest

def _cpf():
    ds=[int(x) for x in str(uuid4().int)[:9]]
    for n in (9,10):
        v=(sum(ds[i]*(n+1-i) for i in range(n))*10)%11
        ds.append(0 if v==10 else v)
    return "".join(map(str,ds))

def exercise(reviewer,reviewer_tenant,reviewer_token,doc,price,contract_b,a_hash,b_hash):
    with connection() as conn:
        master=uuid4()
        pwd="M41410-CI-Only-Master-Password!"
        conn.execute("INSERT INTO public.users(id,email,full_name,cpf,phone,is_master,email_verified_at) VALUES(%s,%s,'Master CI',%s,'11999990000',true,now())",
                     (master,f"m41410-{master}@example.invalid",_cpf()))
        digest=hash_password_secure(pwd)
        conn.execute("INSERT INTO public.credentials(user_id,password_hash,algorithm) VALUES(%s,%s,%s)",(master,digest,'argon2id' if digest.startswith('$argon2id$') else 'bcrypt'))
        master_token=uuid4().hex+uuid4().hex
        conn.execute("INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at) VALUES(%s,%s,'MASTER',NULL,now()+interval '30 minutes')",(hash_token(master_token),master))
        conn.execute("UPDATE public.users SET email_verified_at=now() WHERE id=%s",(reviewer,))
        client,delivery=client_for(reviewer_token,reviewer_tenant)
        full=get(client,f'/master/documents/{doc}',master_token)
        assert full['user_id']==str(master) and full['tenant_id'] is None
        assert sha256(full['document']['text'].encode()).hexdigest()==a_hash
        get(client,f'/master/documents/{doc}',reviewer_token,403)
        get(client,f'/master/documents/{contract_b}',master_token,403)
        results=[]
        for period,cents in (("MONTHLY",8990),("ANNUAL",70033)):
            email=f"m41410-{uuid4()}@example.invalid"
            stage=dict(master_token=master_token,master_password=pwd,reviewer_token=reviewer_token,
                       reviewer_tenant=reviewer_tenant,email=email,document_id=doc,document_hash=a_hash)
            reject(stage_admin_invite_ci,conn,**{**stage,"master_token":reviewer_token})
            reject(stage_admin_invite_ci,conn,**{**stage,"master_password":"wrong"})
            reject(stage_admin_invite_ci,conn,**{**stage,"document_id":contract_b})
            stage_body={k:v for k,v in stage.items() if k not in ('master_token','reviewer_token','reviewer_tenant')}
            post(client,'/master/invitations',stage_body,reviewer_token,403)
            prepared=form_request("MASTER",scope=scope_of(full),raw=full,id=doc,
                                  form=dict(email=email,master_password=pwd,confirmed=True))
            assert prepared==dict(path="/master/invitations",body={**stage_body,"document_id":str(doc)})
            response=post(client,prepared["path"],prepared["body"],master_token)
            inv=UUID(response['invitation_id']);raw=delivery.pop(str(inv))
            reject(stage_admin_invite_ci,conn,**stage)
            assert simulate_invitation_delivery_ci(conn,inv)
            proof=prepare_invite_email_verification_ci(conn,invitation_id=inv)
            proof_body=dict(invitation_token=raw,verification_token=proof)
            prepared=form_request("PROOFS",proofs=proof_body)
            assert prepared==dict(path="/invitation-terms",body=proof_body)
            terms=post(client,prepared["path"],prepared["body"])
            assert terms['document']==full['document'] and terms['terms'] is None and terms['role']=='TENANT_ADMIN'
            post(client,'/invitation-terms',{**proof_body,'verification_token':raw},status=403)
            args=dict(invitation_token=raw,verification_token=proof,document_id=doc,document_hash=a_hash,
                      accepted=True,name="Admin sintético",cpf=_cpf(),phone="11999990000",
                      password="M41410-CI-Only-Admin-Password!",tenant_name="Caixinha sintética")
            for changes in ({"accepted":False},{"accepted":1},{"document_id":contract_b},{"document_hash":"f"*64},{"invitation_token":proof}):
                reject(register_admin_ci,conn,**{**args,**changes})
            assert conn.execute("SELECT count(*) FROM public.users WHERE email=%s",(email,)).fetchone()[0]==0
            form={k:args[k] for k in ("name","cpf","phone","password","tenant_name","accepted")}
            prepared=form_request("REGISTER",raw=terms,proofs=proof_body,form={**form,"confirm_password":args["password"]})
            assert prepared==dict(path="/admin/registration",body={**args,"document_id":str(doc)})
            def attempt():
                from fastapi.encoders import jsonable_encoder
                local,_=client_for()
                res=local.post('/v23/onboarding'+prepared['path'],json=prepared['body'])
                assert res.status_code in (200,403,409)
                if res.status_code!=200:return None
                assert res.headers['cache-control']=='no-store'
                data=res.json()
                return tuple(UUID(data[k]) for k in ('user_id','tenant_id','acceptance_id'))
            with ThreadPoolExecutor(max_workers=2) as pool:
                attempts=list(pool.map(lambda _:attempt(),range(2)))
            assert sum(x is not None for x in attempts)==1
            actor,tenant,acc=next(x for x in attempts if x is not None)
            assert conn.execute("SELECT status FROM public.tenants WHERE id=%s",(tenant,)).fetchone()[0]=="RASCUNHO_INATIVO"
            assert conn.execute("SELECT count(*) FROM public.contract_acceptances WHERE user_id=%s AND document_kind='TENANT_MEMBERSHIP'",(actor,)).fetchone()[0]==0
            reject(conn.execute,"UPDATE public.tenants SET status='ATIVO' WHERE id=%s",(tenant,))
            admin_token=begin(conn,client,tenant,actor,email,args["password"],reviewer_token)
            reject(conn.execute,"SELECT public.fr_v23_actor(%s,%s,true)",(admin_token,tenant))
            reject(accept_admin_b_ci,conn,admin_token=admin_token,tenant=tenant,document_id=contract_b,document_hash=b_hash,accepted=True)
            offers=get(client,f'/tenants/{tenant}/offers',admin_token)
            get(client,f'/tenants/{tenant}/offers',reviewer_token,403)
            get(client,f'/tenants/{tenant}/documents/{contract_b}',admin_token,403)
            selected=next(x for x in offers['offers'] if x['price_version']==str(price))
            assert selected['monthly_cents']==8990 and selected['annual_cents']==70033
            assert all(x['tier']!='AMPLIADO' for x in offers['offers'])
            offer=dict(admin_token=admin_token,tenant=tenant,price_version=price,period=period,accepted_cents=cents,accepted=True)
            reject(prepare_admin_checkout_ci,conn,**{**offer,"accepted_cents":cents+1})
            reject(prepare_admin_checkout_ci,conn,**{**offer,"admin_token":reviewer_token})
            checkout_body={k:v for k,v in offer.items() if k not in ('admin_token','tenant')}
            path=f'/tenants/{tenant}/checkout'
            post(client,path,checkout_body,reviewer_token,403)
            prepared=form_request("CHECKOUT",scope=scope_of(offers),raw=offers,id=price,period=period,accepted=True)
            assert prepared==dict(path=path,body={**checkout_body,"price_version":str(price)})
            checkout=post(client,prepared["path"],prepared["body"],admin_token)
            prep,intent=UUID(checkout['preparation_id']),UUID(checkout['intent_id'])
            status_path=path+'/'+str(intent)
            assert get(client,status_path,admin_token)['state']=='PENDING'
            journey(client,tenant,actor,admin_token,"PAYMENT_PENDING",intent)
            # Reopen the journey after an interruption without creating a new intent.
            former=admin_token
            resumed=login(client,email,args["password"])
            admin_token=resumed["preliminary_token"]
            assert resumed["journey"]["intent_id"]==str(intent)
            assert resumed["journey"]["state"]=="PAYMENT_PENDING"
            get(client,status_path,former,403)
            offer["admin_token"]=admin_token
            get(client,status_path,reviewer_token,403)
            get(client,path+'/'+str(uuid4()),admin_token,403)
            assert get(client,f'/tenants/{tenant}/offers',admin_token)['offers']==[]
            post(client,'/invitation-terms',proof_body,status=403)
            assert prepare_admin_checkout_ci(conn,**offer)==(prep,intent)
            assert post(client,path,checkout_body,admin_token)==checkout
            reject(prepare_admin_checkout_ci,conn,**{**offer,"period":"ANNUAL" if period=="MONTHLY" else "MONTHLY","accepted_cents":70033 if period=="MONTHLY" else 8990})
            assert conn.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()[0]==0
            provider_id=str(uuid4().int)[:38]
            pay=dict(id=provider_id,collector_id="12345",external_reference=f"saas:{intent}",transaction_amount=str(Decimal(cents)/100),
                     transaction_amount_refunded="0.00",currency_id="BRL",status="approved",live_mode=False)
            review=dict(reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,tenant=tenant,intent=intent,payment=pay,
                        statement_gross_cents=cents,statement_fee_cents=10,statement_net_cents=cents-10)
            for changes in ({"payment":{**pay,"live_mode":True}},{"payment":{**pay,"collector_id":"999"}},{"payment":{**pay,"transaction_amount":"0.01"}},
                            {"payment":{**pay,"status":"pending"}},{"payment":{**pay,"transaction_amount_refunded":"1.00"}},
                            {"statement_net_cents":cents},{"reviewer_token":admin_token,"reviewer_tenant":tenant}):
                reject(reconcile_admin_checkout_ci,conn,**{**review,**changes})
            assert conn.execute("SELECT provider_payment_id FROM public.saas_payment_intents WHERE id=%s",(intent,)).fetchone()[0] is None
            ent=reconcile_admin_checkout_ci(conn,**review)
            journey(client,tenant,actor,admin_token,"REAUTH_REQUIRED",intent)
            # The same preliminary bearer is still not an ordinary financial/admin session.
            reject(conn.execute,"SELECT public.fr_v23_actor(%s,%s,true)",(admin_token,tenant))
            reject(accept_admin_b_ci,conn,admin_token=admin_token,tenant=tenant,document_id=contract_b,document_hash=b_hash,accepted=True)
            get(client,f'/tenants/{tenant}/documents/{contract_b}',admin_token,403)
            get(client,status_path,admin_token,403)
            post(client,path,checkout_body,admin_token,403)
            # Existing credential-change trigger invalidates the preliminary digest too.
            updated_password="M41450-CI-Only-New-Password!"
            conn.execute("UPDATE public.credentials SET password_hash=%s WHERE user_id=%s",(hash_password_secure(updated_password),actor))
            get(client,f"/tenants/{tenant}/preliminary-journey",admin_token,403)
            login(client,email,args["password"],403)
            fresh=login(client,email,updated_password)["preliminary_token"]
            journey(client,tenant,actor,fresh,"REAUTH_REQUIRED",intent)
            assert post(client,f"/tenants/{tenant}/preliminary-logout",{},fresh)["revoked"] is True
            # Standard login remains a distinct production-gated system. Use the
            # existing isolated ordinary-session fixture only after entitlement.
            admin_token=uuid4().hex+uuid4().hex
            conn.execute("INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at) VALUES(%s,%s,'TENANT_ADMIN',%s,now()+interval '30 minutes')",(hash_token(admin_token),actor,tenant))
            status=get(client,status_path,admin_token)
            assert status['state']=='CI_RECONCILED' and status['cents']==cents and status['period']==period
            assert status['real_payment_authorized'] is False
            get(client,f'/tenants/{tenant}/offers',admin_token,403)
            assert reconcile_admin_checkout_ci(conn,**review)==ent
            assert conn.execute("SELECT status FROM public.tenants WHERE id=%s",(tenant,)).fetchone()[0]=="ATIVO"
            assert conn.execute("SELECT public.fr_v23_actor(%s,%s,true)",(admin_token,tenant)).fetchone()[0]==actor
            assert conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()==(20,40)
            assert conn.execute("SELECT count(*) FROM public.cycles WHERE tenant_id=%s",(tenant,)).fetchone()[0]==0
            assert conn.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==0
            assert conn.execute("SELECT count(*) FROM public.memberships WHERE tenant_id=%s AND role='TENANT_MEMBER'",(tenant,)).fetchone()[0]==0
            assert conn.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()[0]==1
            results.append((actor,tenant,admin_token))
        print('M41420_ONBOARDING_HTTP_MASTER_ADMIN_CHECKOUT_RACE=PASS')
        print('M41450_PRELIMINARY_LOGIN_RATE_RESUME_REVOKE_NO_ESCALATION=PASS')
        return results

def accept_b_and_member(phase, tenant, admin_raw, doc, b_hash, cycle=None, digest=None):
    """Compose the existing M41400 path after the new administrator's exact B."""
    from datetime import date
    from app.cycle_identity_registration_ci import stage_cycle_identity_invite_ci, register_cycle_identity_ci
    with connection() as conn:
        if phase=="B":
            args=dict(admin_token=admin_raw,tenant=tenant,document_id=doc,document_hash=b_hash,accepted=True)
            reject(accept_admin_b_ci,conn,**{**args,"accepted":False})
            reject(accept_admin_b_ci,conn,**{**args,"document_hash":"f"*64})
            reject(accept_admin_b_ci,conn,**{**args,"document_id":uuid4()})
            client,_=client_for()
            readback=get(client,f'/tenants/{tenant}/documents/{doc}',admin_raw)
            document=readback['document']
            assert sha256(document['text'].encode()).hexdigest()==b_hash
            body={k:v for k,v in args.items() if k not in ('admin_token','tenant')}
            prepared=form_request("B",scope=scope_of(readback),raw=readback,id=doc,accepted=True)
            assert prepared==dict(path=f'/tenants/{tenant}/contract-b',body={**body,"document_id":str(doc)})
            accepted=UUID(post(client,prepared["path"],prepared["body"],admin_raw)['acceptance_id'])
            assert accept_admin_b_ci(conn,**args)==accepted
            return accepted
        assert phase=="MEMBER"
        joined=date(2027,1,10)
        client,delivery=client_for()
        actor=conn.execute("SELECT admin_user_id FROM public.tenants WHERE id=%s",(tenant,)).fetchone()[0]
        readback=get(client,f'/tenants/{tenant}/documents/{doc}',admin_raw)
        prepared=form_request("MEMBER_INVITE",scope=scope_of(readback),cycle=cycle,
                              form=dict(email=f'm41410-member-{uuid4()}@example.invalid',joined=joined,quotas=2,previous_id=None,confirmed=True))
        assert readback["user_id"]==str(actor)
        invite=post(client,prepared["path"],prepared["body"],admin_raw)
        inv=UUID(invite['invitation_id']);raw=delivery.pop(str(inv))
        assert simulate_invitation_delivery_ci(conn,inv)
        proof=prepare_invite_email_verification_ci(conn,invitation_id=inv)
        terms=post(client,'/invitation-terms',dict(invitation_token=raw,verification_token=proof))
        assert terms['role']=='TENANT_MEMBER' and terms['document']['document_hash']==b_hash
        assert terms['terms']==dict(cycle=str(cycle),policy_hash=digest,joined=joined.isoformat(),quotas=2)
        body=dict(invitation_token=raw,verification_token=proof,cycle=cycle,policy_hash=digest,document_id=doc,
                  document_hash=b_hash,joined=joined,quotas=2,accepted=True,name='Membro sintético',cpf=_cpf(),
                  phone='11999990000',password='M41410-CI-Only-Member!')
        post(client,'/member/registration',{**body,'policy_hash':'f'*64},status=403)
        form={k:body[k] for k in ("name","cpf","phone","password","accepted")}
        prepared=form_request("REGISTER",raw=terms,proofs=dict(invitation_token=raw,verification_token=proof),
                              form={**form,"confirm_password":body["password"]})
        from fastapi.encoders import jsonable_encoder
        assert prepared==dict(path="/member/registration",body=jsonable_encoder(body))
        registered=post(client,prepared["path"],prepared["body"])
        person,member,consent=map(UUID,(registered['user_id'],registered['membership_id'],registered['consent_id']))
        post(client,'/member/registration',body,status=403)
        print('M41420_ONBOARDING_HTTP_MEMBER_B_AND_REPLAY=PASS')
        print('M41430_SCOPED_DOCUMENT_TERMS_OFFERS_STATUS=PASS')
        print('M41440_MOBILE_FORMS_CANONICAL_HTTP_PG18=PASS')
        assert conn.execute("SELECT count(*) FROM public.contributions WHERE membership_id=%s",(member,)).fetchone()[0]==0
        return person,member
