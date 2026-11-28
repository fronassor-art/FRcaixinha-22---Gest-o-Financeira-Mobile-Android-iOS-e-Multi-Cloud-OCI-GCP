"""Use actual HTTP login and mobile parsers in the canonical onboarding exercise."""
from app.preliminary_onboarding_ci import _rate_key
from app.preliminary_token_ci import preliminary_digest
from app.security import hash_token
from m41420_onboarding_http_ci import get,post
from m41440_onboarding_form_bridge_ci import preliminary_view
from uuid import uuid4

def login(client,email,password,status=200):
    response=client.post("/v23/onboarding/admin/preliminary-login",json=dict(email=email,password=password))
    assert response.status_code==status,("preliminary login",response.status_code,status)
    assert response.headers.get("cache-control")=="no-store"
    assert password not in response.text
    data=response.json()
    if status==200:
        assert set(data)=={"preliminary_token","expires_at","journey"}
        assert preliminary_view("PRELIMINARY_LOGIN_VIEW",raw=data)==data["journey"]
    return data

def journey(client,tenant,actor,token,state,intent=None):
    row=get(client,f"/tenants/{tenant}/preliminary-journey",token)
    assert row["state"]==state and row["intent_id"]==(str(intent) if intent else None)
    assert preliminary_view("PRELIMINARY_JOURNEY_VIEW",raw=row,scope=dict(user_id=actor,tenant_id=tenant))==row
    return row

def begin(conn,client,tenant,actor,email,password,reviewer_token):
    path=f"/tenants/{tenant}/preliminary-journey"
    for _ in range(5):login(client,email,"M41450-invalid-password",403)
    login(client,email,password,403)
    assert conn.execute("SELECT attempts FROM public.auth_login_rate_limits WHERE key_hash=%s",(_rate_key(email),)).fetchone()[0]==5
    conn.execute("UPDATE public.auth_login_rate_limits SET blocked_until=now()-interval '1 second' WHERE key_hash=%s",(_rate_key(email),))
    first=login(client,email,password)["preliminary_token"]
    assert conn.execute("SELECT count(*) FROM public.sessions WHERE token_hash=%s",(hash_token(first),)).fetchone()[0]==0
    assert conn.execute("SELECT count(*) FROM public.sessions WHERE token_hash=%s",(preliminary_digest(first),)).fetchone()[0]==1
    journey(client,tenant,actor,first,"SELECT_OFFER")
    get(client,f"/tenants/{uuid4()}/preliminary-journey",first,403)
    get(client,path,reviewer_token,403)
    assert post(client,f"/tenants/{tenant}/preliminary-logout",{},first)["revoked"] is True
    get(client,path,first,403)
    second=login(client,email,password)["preliminary_token"]
    conn.execute("UPDATE public.sessions SET expires_at=now()-interval '1 second' WHERE token_hash=%s",(preliminary_digest(second),))
    get(client,path,second,403)
    third=login(client,email,password)["preliminary_token"]
    fourth=login(client,email,password)["preliminary_token"]
    get(client,path,third,403)
    journey(client,tenant,actor,fourth,"SELECT_OFFER")
    return fourth
