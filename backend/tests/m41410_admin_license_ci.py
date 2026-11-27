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

def _cpf():
    ds=[int(x) for x in str(uuid4().int)[:9]]
    for n in (9,10):
        v=(sum(ds[i]*(n+1-i) for i in range(n))*10)%11
        ds.append(0 if v==10 else v)
    return "".join(map(str,ds))

def exercise(reviewer,reviewer_tenant,reviewer_token,doc,price,contract_b):
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
        results=[]
        for period,cents in (("MONTHLY",8990),("ANNUAL",70033)):
            email=f"m41410-{uuid4()}@example.invalid"
            stage=dict(master_token=master_token,master_password=pwd,reviewer_token=reviewer_token,
                       reviewer_tenant=reviewer_tenant,email=email,document_id=doc,document_hash="c"*64)
            reject(stage_admin_invite_ci,conn,**{**stage,"master_token":reviewer_token})
            reject(stage_admin_invite_ci,conn,**{**stage,"master_password":"wrong"})
            reject(stage_admin_invite_ci,conn,**{**stage,"document_id":contract_b})
            inv,raw=stage_admin_invite_ci(conn,**stage)
            reject(stage_admin_invite_ci,conn,**stage)
            assert simulate_invitation_delivery_ci(conn,inv)
            proof=prepare_invite_email_verification_ci(conn,invitation_id=inv)
            args=dict(invitation_token=raw,verification_token=proof,document_id=doc,document_hash="c"*64,
                      accepted=True,name="Admin sintético",cpf=_cpf(),phone="11999990000",
                      password="M41410-CI-Only-Admin-Password!",tenant_name="Caixinha sintética")
            for changes in ({"accepted":False},{"accepted":1},{"document_id":contract_b},{"document_hash":"f"*64},{"invitation_token":proof}):
                reject(register_admin_ci,conn,**{**args,**changes})
            assert conn.execute("SELECT count(*) FROM public.users WHERE email=%s",(email,)).fetchone()[0]==0
            def attempt():
                with connection() as db:
                    try: return register_admin_ci(db,**args)
                    except LifecycleDenied: return None
            with ThreadPoolExecutor(max_workers=2) as pool:
                attempts=list(pool.map(lambda _:attempt(),range(2)))
            assert sum(x is not None for x in attempts)==1
            actor,tenant,acc=next(x for x in attempts if x is not None)
            assert conn.execute("SELECT status FROM public.tenants WHERE id=%s",(tenant,)).fetchone()[0]=="RASCUNHO_INATIVO"
            assert conn.execute("SELECT count(*) FROM public.contract_acceptances WHERE user_id=%s AND document_kind='TENANT_MEMBERSHIP'",(actor,)).fetchone()[0]==0
            reject(conn.execute,"UPDATE public.tenants SET status='ATIVO' WHERE id=%s",(tenant,))
            admin_token=uuid4().hex+uuid4().hex
            conn.execute("INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at) VALUES(%s,%s,'TENANT_ADMIN',%s,now()+interval '30 minutes')",(hash_token(admin_token),actor,tenant))
            reject(conn.execute,"SELECT public.fr_v23_actor(%s,%s,true)",(admin_token,tenant))
            reject(accept_admin_b_ci,conn,admin_token=admin_token,tenant=tenant,document_id=contract_b,document_hash="a"*64,accepted=True)
            offer=dict(admin_token=admin_token,tenant=tenant,price_version=price,period=period,accepted_cents=cents,accepted=True)
            reject(prepare_admin_checkout_ci,conn,**{**offer,"accepted_cents":cents+1})
            reject(prepare_admin_checkout_ci,conn,**{**offer,"admin_token":reviewer_token})
            prep,intent=prepare_admin_checkout_ci(conn,**offer)
            assert prepare_admin_checkout_ci(conn,**offer)==(prep,intent)
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
            assert reconcile_admin_checkout_ci(conn,**review)==ent
            assert conn.execute("SELECT status FROM public.tenants WHERE id=%s",(tenant,)).fetchone()[0]=="ATIVO"
            assert conn.execute("SELECT public.fr_v23_actor(%s,%s,true)",(admin_token,tenant)).fetchone()[0]==actor
            assert conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()==(20,40)
            assert conn.execute("SELECT count(*) FROM public.cycles WHERE tenant_id=%s",(tenant,)).fetchone()[0]==0
            assert conn.execute("SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s",(tenant,)).fetchone()[0]==0
            assert conn.execute("SELECT count(*) FROM public.memberships WHERE tenant_id=%s AND role='TENANT_MEMBER'",(tenant,)).fetchone()[0]==0
            assert conn.execute("SELECT count(*) FROM public.saas_license_entitlements WHERE tenant_id=%s",(tenant,)).fetchone()[0]==1
            results.append((actor,tenant,admin_token))
        return results

def accept_b_and_member(phase, tenant, admin_raw, doc, cycle=None, digest=None):
    """Compose the existing M41400 path after the new administrator's exact B."""
    from datetime import date
    from app.cycle_identity_registration_ci import stage_cycle_identity_invite_ci, register_cycle_identity_ci
    with connection() as conn:
        if phase=="B":
            args=dict(admin_token=admin_raw,tenant=tenant,document_id=doc,document_hash="a"*64,accepted=True)
            reject(accept_admin_b_ci,conn,**{**args,"accepted":False})
            reject(accept_admin_b_ci,conn,**{**args,"document_hash":"f"*64})
            reject(accept_admin_b_ci,conn,**{**args,"document_id":uuid4()})
            accepted=accept_admin_b_ci(conn,**args)
            assert accept_admin_b_ci(conn,**args)==accepted
            return accepted
        assert phase=="MEMBER"
        joined=date(2027,1,10)
        inv,raw=stage_cycle_identity_invite_ci(conn,admin_token=admin_raw,tenant=tenant,cycle=cycle,
                    email=f"m41410-member-{uuid4()}@example.invalid",joined=joined,quotas=2)
        assert simulate_invitation_delivery_ci(conn,inv)
        proof=prepare_invite_email_verification_ci(conn,invitation_id=inv)
        person,member,consent=register_cycle_identity_ci(conn,invitation_token=raw,verification_token=proof,
                    cycle=cycle,policy_hash=digest,document_id=doc,document_hash="a"*64,joined=joined,quotas=2,
                    accepted=True,name="Membro sintético",cpf=_cpf(),phone="11999990000",password="M41410-CI-Only-Member!")
        assert conn.execute("SELECT count(*) FROM public.contributions WHERE membership_id=%s",(member,)).fetchone()[0]==0
        return person,member
