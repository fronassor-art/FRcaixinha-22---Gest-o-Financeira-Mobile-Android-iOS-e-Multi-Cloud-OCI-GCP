/** M41430: validated readback and local preparation; no POST executor in mobile. */
import {classifyApiOrigin} from './apiOriginPolicy';
import {uuid,type Transport} from './productTransactionalBoundaryV23';
import {civilDateDayNumberV22} from './cycleWindowV22';
export type AdminScope={userId:string;tenantId:string;role:'TENANT_ADMIN'};
export type MasterScope={userId:string;tenantId:null;role:'MASTER'};
export type OnboardingScope=AdminScope|MasterScope;
const deny=():never=>{throw Error('Dados de contratação incompatíveis. Nenhuma operação autorizada.');};
function exact(v:unknown,keys:string){if(!v||typeof v!=='object'||Array.isArray(v))return deny();const o=v as Record<string,unknown>,k=keys.split(' ');if(Object.keys(o).length!==k.length||k.some(x=>!Object.hasOwn(o,x)))return deny();return o;}
function str(v:unknown,min:number,max:number){if(typeof v!=='string'||v.length<min||v.length>max)return deny();return v;}
function num(v:unknown,min=1,max=100000000){if(typeof v!=='number'||!Number.isSafeInteger(v)||v<min||v>max)return deny();return v;}
function hash(v:unknown){const x=str(v,64,64);if(!/^[0-9a-f]{64}$/.test(x))deny();return x;}
function scope(x:Record<string,unknown>,s:OnboardingScope){if(uuid(x.user_id)!==uuid(s.userId)||x.role!==s.role||(s.tenantId===null?x.tenant_id!==null:uuid(x.tenant_id)!==uuid(s.tenantId)))deny();}
function period(v:unknown):'MONTHLY'|'ANNUAL'{if(v!=='MONTHLY'&&v!=='ANNUAL')return deny();return v;}
export async function parseDocument(v:unknown,kind:'PLATFORM_LICENSE'|'TENANT_MEMBERSHIP',expectedId?:string){
 const x=exact(v,'document_id kind version document_hash text ci_only'),id=uuid(x.document_id),text=str(x.text,1,100000),digest=hash(x.document_hash);
 if(x.kind!==kind||x.ci_only!==true||(expectedId&&id!==uuid(expectedId)))deny();
 const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
 if(actual!==digest)deny();
 return Object.freeze({document_id:id,kind,version:str(x.version,1,60),document_hash:digest,text,ci_only:true as const});
}
export async function parseScopedDocument(v:unknown,s:OnboardingScope,id:string){
 const x=exact(v,'user_id tenant_id role document');scope(x,s);
 return parseDocument(x.document,s.role==='MASTER'?'PLATFORM_LICENSE':'TENANT_MEMBERSHIP',id);
}
export async function parseInvitationTerms(v:unknown){
 const x=exact(v,'invitation_id role document terms'),id=uuid(x.invitation_id);
 if(x.role==='TENANT_ADMIN'){if(x.terms!==null)deny();return {invitation_id:id,role:'TENANT_ADMIN' as const,document:await parseDocument(x.document,'PLATFORM_LICENSE'),terms:null};}
 if(x.role!=='TENANT_MEMBER')return deny();
 const q=exact(x.terms,'cycle policy_hash joined quotas');civilDateDayNumberV22(q.joined);
 return {invitation_id:id,role:'TENANT_MEMBER' as const,document:await parseDocument(x.document,'TENANT_MEMBERSHIP'),terms:{cycle:uuid(q.cycle),policy_hash:hash(q.policy_hash),joined:q.joined as string,quotas:num(q.quotas,1,400)}};
}
export function parseOffers(v:unknown,s:AdminScope){
 const x=exact(v,'user_id tenant_id role ci_only offers');scope(x,s);
 if(x.ci_only!==true||!Array.isArray(x.offers)||x.offers.length>2)return deny();
 const seen=new Set<string>(),ids=new Set<string>();
 const offers=x.offers.map(v=>{
  const o=exact(v,'price_version tier members_limit quotas_limit monthly_cents annual_cents'),id=uuid(o.price_version),tier=o.tier;
  if((tier!=='ESSENCIAL'&&tier!=='INTERMEDIARIO')||seen.has(tier)||ids.has(id))return deny();
  seen.add(tier);ids.add(id);
  return Object.freeze({price_version:id,tier,members_limit:num(o.members_limit,1,200),quotas_limit:num(o.quotas_limit,1,400),monthly_cents:num(o.monthly_cents),annual_cents:num(o.annual_cents)});
 });
 return Object.freeze({scope:JSON.stringify([uuid(s.userId),uuid(s.tenantId),s.role]),offers:Object.freeze(offers)});
}
export type Offers=ReturnType<typeof parseOffers>;
export function prepareCheckout(s:AdminScope,offers:Offers,id:string,choice:unknown,accepted:unknown){
 if(offers.scope!==JSON.stringify([uuid(s.userId),uuid(s.tenantId),s.role])||s.role!=='TENANT_ADMIN'||accepted!==true)deny();
 const p=period(choice),o=offers.offers.find(x=>x.price_version===uuid(id));if(!o)return deny();
 return Object.freeze({price_version:o.price_version,period:p,accepted_cents:p==='MONTHLY'?o.monthly_cents:o.annual_cents,accepted:true as const});
}
export function parseCheckoutStatus(v:unknown,s:AdminScope,intent:string){
 const x=exact(v,'user_id tenant_id role intent_id state cents period ci_only real_payment_authorized');scope(x,s);
 if(uuid(x.intent_id)!==uuid(intent)||x.ci_only!==true||x.real_payment_authorized!==false||(x.state!=='PENDING'&&x.state!=='CI_RECONCILED'))return deny();
 return {state:x.state,cents:num(x.cents),period:period(x.period)};
}
type Query={kind:'document';id:string}|{kind:'offers'}|{kind:'status';id:string};
export async function readOnboarding(t:Transport,s:OnboardingScope,q:Query){
 const snap=t.captureSession(),u=t.getUser();
 const same=()=>t.isCurrent(snap)&&!!snap.token&&!!u&&uuid(u.id)===uuid(s.userId)&&u.role===s.role&&(s.tenantId===null?!u.tenantId:!!u.tenantId&&uuid(u.tenantId)===uuid(s.tenantId));
 if(!same())return deny();
 const origin=classifyApiOrigin(t.origin());if(origin.kind==='BLOCKED')return deny();
 let path:string;
 if(s.role==='MASTER'){if(q.kind!=='document'||s.tenantId!==null)return deny();path='/master/documents/'+uuid(q.id);}
 else{const root='/tenants/'+uuid(s.tenantId);path=q.kind==='document'?root+'/documents/'+uuid(q.id):q.kind==='offers'?root+'/offers':root+'/checkout/'+uuid(q.id);}
 const res=await t.send(origin.origin+'/api/v1/v23/onboarding'+path,{method:'GET',headers:{Authorization:'Bearer '+snap.token,Accept:'application/json'},cache:'no-store',credentials:'omit',redirect:'error'});
 if(!same())return deny();
 if(res.status===401){t.invalidateIfCurrent(snap);return deny();}
 if(!res.ok)throw Error('Consulta de contratação indisponível (HTTP '+res.status+').');
 const json:unknown=await res.json();
 const result=q.kind==='document'?await parseScopedDocument(json,s,q.id):s.role==='TENANT_ADMIN'?(q.kind==='offers'?parseOffers(json,s):parseCheckoutStatus(json,s,q.id)):deny();
 if(!same())return deny();return result;
}
export type DocumentReadback=Awaited<ReturnType<typeof parseDocument>>;
export type CheckoutStatus=ReturnType<typeof parseCheckoutStatus>;
