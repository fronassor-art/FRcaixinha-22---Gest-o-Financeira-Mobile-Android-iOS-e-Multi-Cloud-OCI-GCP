"""M23100 no network, DB or Vault; contract-only mocks."""
from hashlib import sha256
from urllib.parse import parse_qs,urlsplit
from uuid import UUID
import httpx
import pytest
from app.dependencies import AuthenticatedSession
from app.mp_oauth_sandbox_coordinator import OAuthSandboxCoordinator,SandboxConnectBlocked
from test_m2800_oci_mp_connectors_ci import PAYLOAD,APP_SECRET

T=UUID("00000000-0000-4000-8000-0000000000a1")
U=UUID("00000000-0000-4000-8000-0000000000a9")
B=UUID("00000000-0000-4000-8000-0000000000a2")
V=UUID("00000000-0000-4000-8000-0000000000a8")
NOW=1800000000
REDIRECT="https://app.example.invalid/connect/callback"

def session(t=T,u=U,role="TENANT_ADMIN",master=False):
    return AuthenticatedSession(str(u),role,str(t),"ci@example.invalid","CI",master)

class Attempts:
    def __init__(self):self.states={};self.consumes=0;self.seller_reads=0
    async def reserve_once(self,*,draft):
        key=sha256(draft.state.encode()).hexdigest()
        if key in self.states:return False
        self.states[key]=draft
        return True
    async def consume_once(self,*,tenant_id,actor_id,state_sha256,redirect_sha256,provided_state,now_epoch):
        self.consumes+=1
        draft=self.states.get(state_sha256)
        if (sha256(provided_state.encode()).hexdigest()!=state_sha256
            or draft is None or draft.tenant_id!=tenant_id
            or draft.initiated_by!=actor_id
            or sha256(draft.redirect_uri.encode()).hexdigest()!=redirect_sha256
            or now_epoch>draft.created_at_epoch+600):
            return None
        return self.states.pop(state_sha256)
    async def expected_seller(self,*,tenant_id,actor_id):
        self.seller_reads+=1
        return "2002" if tenant_id==T and actor_id==U else None

class Sink:
    def __init__(self):self.records=[];self.allowed=True
    async def persist_sandbox_connection(self,*,draft,tokens):
        self.records.append((draft.tenant_id,tokens.seller_id))
        return self.allowed

def setup():
    attempts=Attempts();vault=Sink();calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json=PAYLOAD)
    coordinator=OAuthSandboxCoordinator(
        attempts=attempts,vault=vault,client_secret=APP_SECRET,
        transport=httpx.MockTransport(handler))
    return coordinator,attempts,vault,calls

async def start(coordinator):
    url=await coordinator.begin(session=session(),tenant_id=T,
       client_id="123456",registered_redirect_uri=REDIRECT,now_epoch=NOW)
    return parse_qs(urlsplit(url).query)["state"][0],url

@pytest.mark.asyncio
async def test_admin_can_complete_one_sandbox_callback():
    service,repo,vault,calls=setup()
    state,url=await start(service)
    assert "code_verifier" not in url and APP_SECRET not in url
    result=await service.complete(
        session=session(),tenant_id=T,state=state,
        authorization_code="TG-M23100-CODE",redirect_uri=REDIRECT,now_epoch=NOW+10)
    assert result.seller_id=="2002"
    assert result.status=="SANDBOX_VAULT_PERSISTENCE_REPORTED"
    assert result.real_payments_enabled is False
    assert result.bank_reconciled is False and result.ledger_written is False
    assert len(calls)==1 and len(vault.records)==1
    assert "TEST_SANDBOX_ACCESS_TOKEN" not in repr(result)

@pytest.mark.asyncio
async def test_second_callback_denied_before_http():
    service,repo,vault,calls=setup()
    state,_=await start(service)
    kwargs=dict(session=session(),tenant_id=T,state=state,
       authorization_code="TG-M23100-CODE",redirect_uri=REDIRECT,now_epoch=NOW+5)
    await service.complete(**kwargs)
    with pytest.raises(SandboxConnectBlocked):
        await service.complete(**kwargs)
    assert len(calls)==1 and len(vault.records)==1

@pytest.mark.asyncio
async def test_cross_tenant_actor_or_redirect_cannot_complete():
    service,repo,vault,calls=setup()
    state,_=await start(service)
    for change in (
        {"session":session(B,V),"tenant_id":B},
        {"session":session(T,V),"tenant_id":T},
        {"redirect_uri":"https://other.invalid/callback"},
    ):
        kwargs=dict(session=session(),tenant_id=T,state=state,
           authorization_code="TG-M23100-CODE",redirect_uri=REDIRECT,now_epoch=NOW+5)
        kwargs.update(change)
        with pytest.raises(SandboxConnectBlocked):
            await service.complete(**kwargs)
    assert not calls and not vault.records

@pytest.mark.parametrize("kind",["member","master","cross"])
@pytest.mark.asyncio
async def test_non_admin_cannot_reserve_state(kind):
    service,repo,vault,calls=setup()
    who={"member":session(role="TENANT_MEMBER"),
         "master":session(role="MASTER",master=True),
         "cross":session(B,V)}[kind]
    with pytest.raises(Exception):
        await service.begin(session=who,tenant_id=T,client_id="123456",
            registered_redirect_uri=REDIRECT,now_epoch=NOW)
    assert repo.states=={} and not calls

@pytest.mark.asyncio
async def test_vault_failure_consumes_state_but_no_success_receipt():
    service,repo,vault,calls=setup()
    vault.allowed=False
    state,_=await start(service)
    with pytest.raises(SandboxConnectBlocked):
        await service.complete(session=session(),tenant_id=T,state=state,
            authorization_code="TG-M23100-CODE",redirect_uri=REDIRECT,now_epoch=NOW+5)
    assert repo.states=={} and len(calls)==1

@pytest.mark.asyncio
async def test_without_mock_network_adapter_is_disabled():
    service,repo,vault,calls=setup()
    service._transport=None
    state,_=await start(service)
    with pytest.raises(SandboxConnectBlocked):
        await service.complete(session=session(),tenant_id=T,state=state,
            authorization_code="TG-M23100-CODE",redirect_uri=REDIRECT,now_epoch=NOW+5)
    assert not calls and not vault.records

@pytest.mark.asyncio
async def test_untrusted_repository_cannot_swap_actor():
    service,repo,vault,calls=setup()
    state,_=await start(service)
    async def forged(**kw):return next(iter(repo.states.values()))
    repo.consume_once=forged
    with pytest.raises(SandboxConnectBlocked):
        await service.complete(session=session(T,V),tenant_id=T,state=state,
            authorization_code="TG-M23100-CODE",redirect_uri=REDIRECT,now_epoch=NOW+5)
    assert not calls and not vault.records
