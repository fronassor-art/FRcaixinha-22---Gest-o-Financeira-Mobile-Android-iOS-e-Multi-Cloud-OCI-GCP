"""M41420 ASGI adapter for the existing disposable PG18 exercises, not runtime."""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import psycopg
from app.account_lifecycle import LifecycleDenied
from app.routers import onboarding_v23 as api
from app.admin_license_onboarding_ci import (stage_admin_invite_ci,register_admin_ci,
    prepare_admin_checkout_ci,accept_admin_b_ci)
from app.cycle_identity_registration_ci import stage_cycle_identity_invite_ci,register_cycle_identity_ci
from m41400_cycle_identity_ci import connection
from app.onboarding_readback_ci import master_document_ci,admin_document_ci,invitation_terms_ci,offers_ci,checkout_status_ci

from app.preliminary_onboarding_ci import login_preliminary_ci,journey_ci,logout_preliminary_ci

def client_for(reviewer_token=None, reviewer_tenant=None):
    # Opaque delivery token is captured only inside this fixture, never in HTTP.
    delivery={}
    def execute(op,token,p):
        try:
            with connection() as conn:
                if op=="PRELIMINARY_LOGIN": return login_preliminary_ci(conn,**p)
                if op=="PRELIMINARY_JOURNEY": return journey_ci(conn,token,**p)
                if op=="PRELIMINARY_LOGOUT": return logout_preliminary_ci(conn,token,**p)
                if op=="MASTER_DOCUMENT": return master_document_ci(conn,token,**p)
                if op=="ADMIN_DOCUMENT": return admin_document_ci(conn,token,**p)
                if op=="INVITATION_TERMS": return invitation_terms_ci(conn,**p)
                if op=="OFFERS": return offers_ci(conn,token,**p)
                if op=="CHECKOUT_STATUS": return checkout_status_ci(conn,token,**p)
                if op=="INVITE_ADMIN":
                    inv,raw=stage_admin_invite_ci(conn,master_token=token,
                        reviewer_token=reviewer_token,reviewer_tenant=reviewer_tenant,**p)
                    delivery[str(inv)]=raw
                    return {"invitation_id":inv}
                if op=="REGISTER_ADMIN":
                    actor,tenant,acc=register_admin_ci(conn,**p)
                    return {"user_id":actor,"tenant_id":tenant,"acceptance_id":acc}
                if op=="CHECKOUT":
                    prep,intent=prepare_admin_checkout_ci(conn,admin_token=token,**p)
                    return {"preparation_id":prep,"intent_id":intent}
                if op=="ACCEPT_B":
                    return {"acceptance_id":accept_admin_b_ci(conn,admin_token=token,**p)}
                if op=="INVITE_MEMBER":
                    inv,raw=stage_cycle_identity_invite_ci(conn,admin_token=token,**p)
                    delivery[str(inv)]=raw
                    return {"invitation_id":inv}
                if op=="REGISTER_MEMBER":
                    actor,member,consent=register_cycle_identity_ci(conn,**p)
                    return {"user_id":actor,"membership_id":member,"consent_id":consent}
                raise AssertionError("unexpected operation")
        except (LifecycleDenied,psycopg.errors.InsufficientPrivilege) as exc:
            raise HTTPException(403,"Contratação fora do escopo.",headers={"Cache-Control":"no-store"}) from None
        except (psycopg.errors.CheckViolation,psycopg.errors.UniqueViolation):
            raise HTTPException(409,"Conflito de contratação.",headers={"Cache-Control":"no-store"}) from None
    app=FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.unreleased_onboarding]=lambda:execute
    return TestClient(app),delivery

def post(client,path,body,token=None,status=200):
    from fastapi.encoders import jsonable_encoder
    response=client.post("/v23/onboarding"+path,json=jsonable_encoder(body),
                         headers={"Authorization":"Bearer "+token} if token else {})
    assert response.status_code==status,(path,response.status_code,status)
    assert response.headers.get("cache-control")=="no-store"
    result=response.json()
    assert not any("token" in k or "password" in k for k in result)
    return result

def get(client,path,token,status=200):
    response=client.get("/v23/onboarding"+path,headers={"Authorization":"Bearer "+token})
    assert response.status_code==status,(path,response.status_code,status)
    assert response.headers.get("cache-control")=="no-store"
    return response.json()
