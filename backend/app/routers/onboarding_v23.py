"""M41420 HTTP contract. No runtime executor; isolated tests inject one explicitly."""
from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import Field
from ..dependencies import bearer_token
from .product_v23 import Strict, Accepted

class PrivateValidationRoute(APIRoute):
    def get_route_handler(self):
        handler=super().get_route_handler()
        async def guarded(request):
            try:
                response=await handler(request)
            except RequestValidationError:
                raise HTTPException(422,"Dados de contratação inválidos.",headers={"Cache-Control":"no-store"}) from None
            except HTTPException as exc:
                # Preserve authentication headers without allowing private failures to be cached.
                raise HTTPException(exc.status_code,exc.detail,
                                    headers={**(exc.headers or {}),"Cache-Control":"no-store"}) from None
            response.headers["Cache-Control"]="no-store"
            return response
        return guarded

router=APIRouter(prefix="/v23/onboarding",tags=["FR Finance V2.3 onboarding"],route_class=PrivateValidationRoute)

def unreleased_onboarding():
    # No environment flag, DB connection, reviewer token or provider activates this.
    raise HTTPException(503,"Contratação V2.3 bloqueada.",headers={"Cache-Control":"no-store"})

class DocumentInput(Strict):
    document_id: UUID
    document_hash: str=Field(pattern=r"^[0-9a-f]{64}$")

class MasterInviteInput(DocumentInput):
    email: str=Field(min_length=3,max_length=254)
    master_password: str=Field(min_length=12,max_length=256)

class RegistrationInput(DocumentInput):
    invitation_token: str=Field(min_length=32,max_length=512)
    verification_token: str=Field(min_length=32,max_length=512)
    accepted: Accepted
    name: str=Field(min_length=3,max_length=255)
    cpf: str=Field(pattern=r"^[0-9]{11}$")
    phone: str=Field(min_length=8,max_length=20)
    password: str=Field(min_length=12,max_length=256)

class AdminRegistrationInput(RegistrationInput):
    tenant_name: str=Field(min_length=3,max_length=255)

class CheckoutInput(Strict):
    price_version: UUID
    period: Literal["MONTHLY","ANNUAL"]
    accepted_cents: int=Field(strict=True,gt=0,le=100000000)
    accepted: Accepted

class AdminBInput(DocumentInput):
    accepted: Accepted

class MemberInviteInput(Strict):
    email: str=Field(min_length=3,max_length=254)
    joined: date
    quotas: int=Field(strict=True,ge=1,le=400)
    previous_id: UUID|None=None

class MemberRegistrationInput(RegistrationInput):
    cycle: UUID
    policy_hash: str=Field(pattern=r"^[0-9a-f]{64}$")
    joined: date
    quotas: int=Field(strict=True,ge=1,le=400)

@router.get("/capabilities")
def capabilities():
    return {"contract":"FR_FINANCE_V23_ONBOARDING_V1","available":False,
            "invites_enabled":False,"registration_enabled":False,"checkout_enabled":False,
            "contract_acceptance_enabled":False,"real_payments_enabled":False,
            "production_authorized":False}

@router.post("/master/invitations")
def invite_admin(p:MasterInviteInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("INVITE_ADMIN",bearer_token(request),p.model_dump())

@router.post("/admin/registration")
def register_admin(p:AdminRegistrationInput,execute=Depends(unreleased_onboarding)):
    return execute("REGISTER_ADMIN",None,p.model_dump())

@router.post("/tenants/{tenant}/checkout")
def checkout(tenant:UUID,p:CheckoutInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("CHECKOUT",bearer_token(request),dict(p.model_dump(),tenant=tenant))

@router.post("/tenants/{tenant}/contract-b")
def accept_b(tenant:UUID,p:AdminBInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("ACCEPT_B",bearer_token(request),dict(p.model_dump(),tenant=tenant))

@router.post("/tenants/{tenant}/cycles/{cycle}/member-invitations")
def invite_member(tenant:UUID,cycle:UUID,p:MemberInviteInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("INVITE_MEMBER",bearer_token(request),dict(p.model_dump(),tenant=tenant,cycle=cycle))

@router.post("/member/registration")
def register_member(p:MemberRegistrationInput,execute=Depends(unreleased_onboarding)):
    return execute("REGISTER_MEMBER",None,p.model_dump())

class InvitationProofInput(Strict):
    invitation_token: str=Field(min_length=32,max_length=512)
    verification_token: str=Field(min_length=32,max_length=512)

@router.get("/master/documents/{document_id}")
def master_document(document_id:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("MASTER_DOCUMENT",bearer_token(request),dict(doc=document_id))

@router.post("/invitation-terms")
def invitation_terms(p:InvitationProofInput,execute=Depends(unreleased_onboarding)):
    # Both opaque proofs in the body, never URL or response.
    return execute("INVITATION_TERMS",None,p.model_dump())

@router.get("/tenants/{tenant}/documents/{document_id}")
def admin_document(tenant:UUID,document_id:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("ADMIN_DOCUMENT",bearer_token(request),dict(tenant=tenant,doc=document_id))

@router.get("/tenants/{tenant}/offers")
def offers(tenant:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("OFFERS",bearer_token(request),dict(tenant=tenant))

@router.get("/tenants/{tenant}/checkout/{intent}")
def checkout_status(tenant:UUID,intent:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("CHECKOUT_STATUS",bearer_token(request),dict(tenant=tenant,intent=intent))

class PreliminaryLoginInput(Strict):
    email: str=Field(min_length=3,max_length=254)
    password: str=Field(min_length=12,max_length=256)

@router.post("/admin/preliminary-login")
def preliminary_login(p:PreliminaryLoginInput,execute=Depends(unreleased_onboarding)):
    return execute("PRELIMINARY_LOGIN",None,p.model_dump())

@router.get("/tenants/{tenant}/preliminary-journey")
def preliminary_journey(tenant:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("PRELIMINARY_JOURNEY",bearer_token(request),dict(tenant=tenant))

@router.post("/tenants/{tenant}/preliminary-logout")
def preliminary_logout(tenant:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("PRELIMINARY_LOGOUT",bearer_token(request),dict(tenant=tenant))

class AdministratorReauthenticationInput(PreliminaryLoginInput):
    tenant: UUID

@router.post("/admin/reauthenticate")
def administrator_reauthenticate(p:AdministratorReauthenticationInput,execute=Depends(unreleased_onboarding)):
    return execute("ADMIN_REAUTHENTICATE",None,p.model_dump())

@router.get("/tenants/{tenant}/administrator-readiness/{document_id}")
def administrator_readiness(tenant:UUID,document_id:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("ADMIN_READINESS",bearer_token(request),dict(tenant=tenant,document_id=document_id))

@router.post("/tenants/{tenant}/administrator-logout")
def administrator_logout(tenant:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("ADMIN_LOGOUT",bearer_token(request),dict(tenant=tenant))

# M41490: no reviewer or payment-provider fields on the mobile-facing contract.
class RenewalInput(DocumentInput):
    request_id: UUID
    predecessor: UUID
    price_version: UUID
    period: Literal["MONTHLY","ANNUAL"]
    cents: int=Field(strict=True,gt=0,le=100000000)
    accepted: Accepted

@router.get("/tenants/{tenant}/renewal")
def renewal_overview(tenant:UUID,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("RENEWAL_OVERVIEW",bearer_token(request),dict(tenant=tenant))

@router.post("/tenants/{tenant}/renewal")
def renewal_prepare(tenant:UUID,p:RenewalInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("RENEWAL_PREPARE",bearer_token(request),dict(p.model_dump(),tenant=tenant))


# M41520: candidate only; unreleased_onboarding remains unconditional 503.
class PlanChangeQuoteInput(Strict):
    request_id: UUID
    target: Literal["ESSENCIAL","INTERMEDIARIO"]

class PlanChangeAcceptInput(DocumentInput):
    request_id: UUID
    offer_hash: str=Field(pattern=r"^[0-9a-f]{64}$")
    accepted: Accepted

@router.get("/tenants/{tenant}/plan-change/{target}")
def plan_change_preview(tenant:UUID,target:Literal["ESSENCIAL","INTERMEDIARIO"],request:Request,execute=Depends(unreleased_onboarding)):
    return execute("PLAN_CHANGE_PREVIEW",bearer_token(request),dict(tenant=tenant,target=target))

@router.post("/tenants/{tenant}/plan-change/quotes")
def plan_change_quote(tenant:UUID,p:PlanChangeQuoteInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("PLAN_CHANGE_QUOTE",bearer_token(request),dict(p.model_dump(),tenant=tenant))

@router.post("/tenants/{tenant}/plan-change/accept")
def plan_change_accept(tenant:UUID,p:PlanChangeAcceptInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("PLAN_CHANGE_ACCEPT",bearer_token(request),dict(p.model_dump(),tenant=tenant))

# M41570: same unconditional production 503; only CI injects an executor.
class SubscriptionCancelInput(DocumentInput):
    request_id: UUID
    predecessor: UUID
    accepted: Accepted

@router.post("/tenants/{tenant}/renewal/cancel-subscription")
def cancel_subscription(tenant:UUID,p:SubscriptionCancelInput,request:Request,execute=Depends(unreleased_onboarding)):
    return execute("SUBSCRIPTION_CANCEL",bearer_token(request),dict(p.model_dump(),tenant=tenant))
