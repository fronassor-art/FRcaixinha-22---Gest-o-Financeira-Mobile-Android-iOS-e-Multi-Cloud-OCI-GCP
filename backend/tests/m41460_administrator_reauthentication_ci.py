"""Real role-separated proof issuance and HTTP readback in existing PG18 CI."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from app.administrator_reauthentication_ci import _role_connection,_verified_identity,_proof
from app.security import generate_session_token,hash_token
from m41420_onboarding_http_ci import get,post
from m41440_onboarding_form_bridge_ci import administrator_view
from m41400_cycle_identity_ci import reject

def reauthenticate(client,email,password,tenant,actor=None,status=200):
    response=client.post("/v23/onboarding/admin/reauthenticate",json=dict(email=email,password=password,tenant=str(tenant)))
    assert response.status_code==status,("reauthenticate",response.status_code,status)
    assert response.headers.get("cache-control")=="no-store"
    assert password not in response.text
    body=response.json()
    if status==200:
        scope=dict(user_id=str(actor),tenant_id=str(tenant))
        assert administrator_view("ADMIN_REAUTH_VIEW",raw=body,scope=scope)=={
            **scope,"role":"TENANT_ADMIN","ci_only":True,"production_authorized":False}
        return body["session_token"]
    assert "session_token" not in body

def readiness(client,tenant,actor,doc,token,state):
    row=get(client,f"/tenants/{tenant}/administrator-readiness/{doc}",token)
    assert row["state"]==state
    assert administrator_view("ADMIN_READINESS_VIEW",raw=row,scope=dict(user_id=actor,tenant_id=tenant),id=doc)==row
    return row

def proof_race(owner,actor,email,password):
    with _role_connection(owner,"frcaixinha_pg18_verifier") as verifier:
        # Real privilege denials on the existing independent SQL logins.
        assert not verifier.execute("SELECT has_function_privilege(current_user,'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')").fetchone()[0]
        assert not verifier.execute("SELECT has_table_privilege(current_user,'public.sessions','INSERT')").fetchone()[0]
        verified=_verified_identity(verifier,email,password)
        assert verified and verified[0]==actor
        proof=_proof(verifier,*verified)
    def attempt(_):
        raw,_=generate_session_token()
        with _role_connection_for_fixture() as issuer:
            assert not issuer.execute("SELECT has_column_privilege(current_user,'public.credentials','password_hash','SELECT')").fetchone()[0]
            assert not issuer.execute("SELECT has_column_privilege(current_user,'public.auth_login_proofs','proof_hash','INSERT')").fetchone()[0]
            accepted=issuer.execute("SELECT public.auth_issue_pending_session(%s,%s,%s)",(actor,raw,proof)).fetchone()[0]
            if accepted:
                assert issuer.execute("SELECT public.auth_revoke_session(%s)",(raw,)).fetchone()[0]
            return accepted
    # Each worker has a separate owner guard and independent issuer connection.
    from m41400_cycle_identity_ci import connection
    from contextlib import contextmanager
    @contextmanager
    def _role_connection_for_fixture():
        with connection() as guard, _role_connection(guard,"frcaixinha_pg18_auth") as issuer:
            yield issuer
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(attempt,range(2)))==1
    assert owner.execute("SELECT consumed_at IS NOT NULL FROM public.auth_login_proofs WHERE proof_hash=%s",(hash_token(proof),)).fetchone()[0]
    with _role_connection(owner,"frcaixinha_pg18_auth") as issuer:
        assert not issuer.execute("SELECT public.auth_issue_pending_session(%s,%s,%s)",(actor,generate_session_token()[0],proof)).fetchone()[0]

def exercise(owner,client,actor,tenant,email,password,ent,doc,b_hash,reviewer_token):
    reauthenticate(client,email,"M41460-invalid-password",tenant,status=403)
    reauthenticate(client,email,password,uuid4(),status=403)
    proof_race(owner,actor,email,password)
    raw=reauthenticate(client,email,password,tenant,actor)
    assert owner.execute("SELECT active_role,active_tenant_id FROM public.sessions WHERE token_hash=%s",(hash_token(raw),)).fetchone()==("TENANT_ADMIN",tenant)
    readiness(client,tenant,actor,doc,raw,"CONTRACT_B_REQUIRED")
    get(client,f"/tenants/{tenant}/administrator-readiness/{doc}",reviewer_token,403)
    get(client,f"/tenants/{uuid4()}/administrator-readiness/{doc}",raw,403)
    get(client,f"/tenants/{tenant}/administrator-readiness/{uuid4()}",raw,403)
    # Status change and elapsed validity are both exercised, without altering
    # the authoritative database; restore only the synthetic fixture values.
    original=owner.execute("SELECT valid_from,valid_until FROM public.saas_license_entitlements WHERE id=%s",(ent,)).fetchone()
    for mode in ("SUSPENDED","EXPIRED_TIME"):
        if mode=="SUSPENDED":
            owner.execute("UPDATE public.saas_license_entitlements SET status='SUSPENDED' WHERE id=%s",(ent,))
        else:
            owner.execute("UPDATE public.saas_license_entitlements SET valid_from=now()-interval '2 days',valid_until=now()-interval '1 day' WHERE id=%s",(ent,))
        try:
            reauthenticate(client,email,password,tenant,status=403)
            get(client,f"/tenants/{tenant}/administrator-readiness/{doc}",raw,403)
            post(client,f"/tenants/{tenant}/contract-b",dict(document_id=doc,document_hash=b_hash,accepted=True),raw,403)
        finally:
            owner.execute("UPDATE public.saas_license_entitlements SET status='ACTIVE',valid_from=%s,valid_until=%s WHERE id=%s",(*original,ent))
    assert post(client,f"/tenants/{tenant}/administrator-logout",{},raw)["revoked"] is True
    get(client,f"/tenants/{tenant}/administrator-readiness/{doc}",raw,403)
    fresh=reauthenticate(client,email,password,tenant,actor)
    readiness(client,tenant,actor,doc,fresh,"CONTRACT_B_REQUIRED")
    return fresh
