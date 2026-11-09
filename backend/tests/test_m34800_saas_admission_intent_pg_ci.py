"""M34800: same-tenant admission intent, email ownership, contract and claim."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import os
import secrets
import pytest

TA="daba0000-0000-4000-8000-000000000010"
TB="daba0000-0000-4000-8000-000000000020"
ADMIN="daba0000-0000-4000-8000-000000000001"
OTHER_ADMIN="daba0000-0000-4000-8000-000000000002"

def test_transactional_admission_intent_excludes_unverified_or_double_admission():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("Only disposable GitHub Actions PostgreSQL")
    url=os.getenv("CI_SAAS_INTENT_WORKER_URL")
    owner_url=os.getenv("CI_SAAS_INTENT_OWNER_URL")
    app_url=os.getenv("CI_SAAS_INTENT_APP_URL")
    assert url and owner_url and app_url, "Disposable CI URLs absent"
    import psycopg

    target,document,invite,proof=uuid4(),uuid4(),uuid4(),uuid4()
    email="intent-"+uuid4().hex+"@example.invalid"
    with psycopg.connect(owner_url) as conn:
        claim=conn.execute("SELECT request_id FROM public.saas_capacity_claims_staging "
         "WHERE tenant_id=%s AND category='MEMBER' LIMIT 1",(TA,)).fetchone()
        assert claim is not None, "M32800 member claim required first"
        claim=claim[0]
        conn.execute("INSERT INTO public.users(id,email,full_name,cpf,phone,email_verified_at) "
            "VALUES(%s,%s,'Synthetic intent CI','99993480001','00000000000',"
            "clock_timestamp()-interval '3 minutes')",(target,email))
        conn.execute("INSERT INTO public.contract_documents "
            "(id,document_kind,version_label,sha256,source_reference,published_at) "
            "VALUES(%s,'TENANT_MEMBERSHIP',%s,%s,'SYNTHETIC_M34800_CI_ONLY',"
            "clock_timestamp()-interval '1 day')",
            (document,"CI-INTENT-"+uuid4().hex,"f"*64))
        conn.execute("INSERT INTO public.contract_acceptances "
            "(document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method) "
            "VALUES(%s,'TENANT_MEMBERSHIP',%s,%s,%s,'CI_VERIFIED_IDENTITY')",
            (document,target,TA,"e"*64))
        conn.execute("INSERT INTO public.invitations "
            "(id,tenant_id,inviter_user_id,target_email,target_role,token_hash,"
            "expires_at,required_document_id,delivery_status,delivered_at) "
            "VALUES(%s,%s,%s,%s,'TENANT_MEMBER',%s,clock_timestamp()+interval '30 minutes',"
            "%s,'DELIVERED',clock_timestamp()-interval '8 minutes')",
            (invite,TA,ADMIN,email,secrets.token_hex(32),document))
        conn.execute("INSERT INTO public.invite_email_verification "
            "(id,invitation_id,recipient_email,token_hash,created_at,expires_at,consumed_at) "
            "VALUES(%s,%s,%s,%s,clock_timestamp()-interval '9 minutes',"
            "clock_timestamp()+interval '20 minutes',clock_timestamp()-interval '4 minutes')",
            (proof,invite,email,secrets.token_hex(32)))
        baseline=conn.execute(
            "SELECT (SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas),"
            "(SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.ledger_entries)"
        ).fetchone()

    def admit(request,tenant=TA,admin=ADMIN,target_user=target,
              invitation=invite,doc=document,claim_id=claim,email_proof=proof,
              options="-c frcaixinha.admission_intent_ci=1"):
        with psycopg.connect(url,options=options) as conn:
            return conn.execute(
                "SELECT public.saas_member_admission_intent_ci(%s,%s,%s,%s,%s,%s,%s,%s)",
                (request,tenant,admin,target_user,invitation,doc,claim_id,email_proof)
            ).fetchone()[0]["state"]

    assert admit(uuid4(),tenant=TB)=="ACTOR_DENIED"
    assert admit(uuid4(),admin=OTHER_ADMIN)=="ACTOR_DENIED"
    assert admit(uuid4(),target_user=uuid4())=="IDENTITY_DENIED"
    assert admit(uuid4(),invitation=uuid4())=="INVITATION_DENIED"
    assert admit(uuid4(),doc=uuid4())=="INVITATION_DENIED"
    assert admit(uuid4(),email_proof=uuid4())=="EMAIL_OWNERSHIP_DENIED"
    assert admit(uuid4(),claim_id=uuid4())=="LICENSE_OR_MEMBER_CLAIM_DENIED"
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match="M34400_WORKER_DENIED"):
        admit(uuid4(),options="-c frcaixinha.admission_intent_ci=0")

    with psycopg.connect(app_url) as app:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with app.transaction():
                app.execute("SELECT public.saas_member_admission_intent_ci("
                    "%s,%s,%s,%s,%s,%s,%s,%s)",
                    (uuid4(),TA,ADMIN,target,invite,document,claim,proof))
    sync=Barrier(2)
    def race():
        sync.wait(timeout=10)
        return admit(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        f=[pool.submit(race) for _ in range(2)]
        states=[j.result(timeout=30) for j in f]
    assert sorted(states)==["PROOF_OR_CAPACITY_ALREADY_USED","VERIFIED_INTENT_CI_NO_ACTIVATION"]
    with psycopg.connect(owner_url) as conn:
        r=conn.execute("SELECT request_id FROM public.saas_member_admission_intents_staging "
             "WHERE claim_id=%s",(claim,)).fetchone()
        assert r is not None
        request=r[0]
    assert admit(request)=="REPLAY_CI_NO_ACTIVATION"
    assert admit(request,doc=uuid4())=="REQUEST_COLLISION_DENIED"
    assert admit(uuid4())=="PROOF_OR_CAPACITY_ALREADY_USED"

    with psycopg.connect(owner_url) as conn:
        assert conn.execute("SELECT count(*) FROM public.saas_member_admission_intents_staging").fetchone()[0]==1
        flags=conn.execute(
          "SELECT ci_only,provider_readback_verified,real_member_created,"
          "real_quota_created,real_charge_created,real_pix_enabled "
          "FROM public.saas_member_admission_intents_staging").fetchone()
        assert flags==(True,False,False,False,False,False)
        after=conn.execute(
            "SELECT (SELECT count(*) FROM public.memberships),"
            "(SELECT count(*) FROM public.quotas),"
            "(SELECT count(*) FROM public.saas_payment_intents),"
            "(SELECT count(*) FROM public.saas_license_entitlements),"
            "(SELECT count(*) FROM public.ledger_entries)"
        ).fetchone()
        assert after==baseline
        with pytest.raises(psycopg.Error,match="M34700_ADMISSION_INTENT_IMMUTABLE"):
            with conn.transaction():
                conn.execute("DELETE FROM public.saas_member_admission_intents_staging")
        with pytest.raises(psycopg.Error,match="M34700_ADMISSION_INTENT_IMMUTABLE"):
            with conn.transaction():
                conn.execute("TRUNCATE public.saas_member_admission_intents_staging")
