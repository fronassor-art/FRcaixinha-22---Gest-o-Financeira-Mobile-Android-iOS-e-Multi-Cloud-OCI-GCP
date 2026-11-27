"""Executed by the existing M41320 disposable PG18 integration after its regression assertions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4
import psycopg
from app.account_lifecycle import LifecycleDenied, simulate_invitation_delivery_ci, revoke_invitation_ci
from app.invite_registration_ci import prepare_invite_email_verification_ci, register_new_invited_identity_ci
from app.cycle_identity_registration_ci import stage_cycle_identity_invite_ci, register_cycle_identity_ci

def connection():
    return psycopg.connect(host="127.0.0.1",port=5432,dbname="frcaixinha_ci",
                           user="postgres",password="ci-test-only",autocommit=True)

def reject(fn,*args,**kwargs):
    try: fn(*args,**kwargs)
    except (LifecycleDenied,psycopg.errors.InsufficientPrivilege,psycopg.errors.CheckViolation,psycopg.errors.UniqueViolation): return
    raise AssertionError("M41400 unexpected success")

def exercise(tenant,cycle,other_cycle,admin_token,member_token,doc,digest):
    email=f"m41400-{uuid4()}@example.invalid"
    joined=date(2027,1,10)
    # No literal CPF may collide with historical fixtures: use a valid synthetic checksum.
    prefix=str(uuid4().int)[:9]
    digits=[int(v) for v in prefix]
    for n in (9,10):
        rem=(sum(digits[i]*(n+1-i) for i in range(n))*10)%11
        digits.append(0 if rem==10 else rem)
    cpf="".join(map(str,digits))
    with connection() as conn:
        stage=dict(admin_token=admin_token,tenant=tenant,cycle=cycle,email=email,joined=joined,quotas=2)
        reject(stage_cycle_identity_invite_ci,conn,**{**stage,"admin_token":member_token})
        inv,raw=stage_cycle_identity_invite_ci(conn,**stage)
        reject(stage_cycle_identity_invite_ci,conn,**stage)
        reject(stage_cycle_identity_invite_ci,conn,**stage,previous_id=inv)
        assert simulate_invitation_delivery_ci(conn,inv)
        old_proof=prepare_invite_email_verification_ci(conn,invitation_id=inv)
        assert revoke_invitation_ci(conn,inv)
        reject(stage_cycle_identity_invite_ci,conn,**{**stage,"cycle":other_cycle},previous_id=inv)
        new,raw2=stage_cycle_identity_invite_ci(conn,**stage,previous_id=inv)
        assert new!=inv and raw2!=raw
        assert conn.execute("SELECT revoked_at IS NOT NULL FROM public.invite_email_verification WHERE invitation_id=%s",(inv,)).fetchone()[0]
        assert simulate_invitation_delivery_ci(conn,new)
        expired_proof=prepare_invite_email_verification_ci(conn,invitation_id=new)
        # Simulate passage of time in the disposable fixture only.
        conn.execute("UPDATE public.invitations SET expires_at=now()-interval '1 minute' WHERE id=%s",(new,))
        final,raw3=stage_cycle_identity_invite_ci(conn,**stage,previous_id=new)
        assert final!=new and raw3!=raw2
        assert conn.execute("SELECT revoked_at IS NOT NULL FROM public.invite_email_verification WHERE invitation_id=%s",(new,)).fetchone()[0]
        assert simulate_invitation_delivery_ci(conn,final)
        proof=prepare_invite_email_verification_ci(conn,invitation_id=final)
        args=dict(invitation_token=raw3,verification_token=proof,cycle=cycle,policy_hash=digest,
            document_id=doc,document_hash="a"*64,joined=joined,quotas=2,accepted=True,
            name="Membro sintético M41400",cpf=cpf,phone="11999990000",password="CI-Only-M41400-Test-Password!")
        for change in ({"accepted":False},{"accepted":1},{"cycle":other_cycle},{"policy_hash":"f"*64},
                       {"document_hash":"f"*64},{"document_id":uuid4()},{"quotas":3},{"invitation_token":raw},{"invitation_token":raw2},{"verification_token":old_proof},{"verification_token":expired_proof}):
            reject(register_cycle_identity_ci,conn,**{**args,**change})
        # Legacy registration alone must roll back the identity, not skip V2.3 consent.
        reject(register_new_invited_identity_ci,conn,verification_token=proof,name=args["name"],cpf=cpf,
               phone=args["phone"],password=args["password"],document_id=doc,consent=True,accepted_document_sha256="a"*64)
        assert conn.execute("SELECT count(*) FROM public.users WHERE email=%s",(email,)).fetchone()[0]==0
        assert conn.execute("SELECT consumed_at IS NULL FROM public.invite_email_verification WHERE invitation_id=%s",(final,)).fetchone()[0]
        def attempt():
            with connection() as db:
                try: return register_cycle_identity_ci(db,**args)
                except LifecycleDenied: return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda _:attempt(),range(2)))
        assert sum(x is not None for x in results)==1
        person,member,consent=next(x for x in results if x is not None)
        reject(register_cycle_identity_ci,conn,**args)
        assert conn.execute("SELECT count(*) FROM public.users WHERE email=%s AND NOT is_master AND email_verified_at IS NOT NULL",(email,)).fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM public.fr_v23_member_consent WHERE id=%s AND membership_id=%s AND actor=%s AND cycle_id=%s",(consent,member,person,cycle)).fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM public.contributions WHERE membership_id=%s",(member,)).fetchone()[0]==0
        assert conn.execute("SELECT count(*) FROM public.sessions WHERE user_id=%s",(person,)).fetchone()[0]==0
        reject(stage_cycle_identity_invite_ci,conn,**stage)
        return person,member
