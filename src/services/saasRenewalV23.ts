/** M41490: scoped readback and ephemeral local preparation, no POST executor. */
import {uuid,type Transport} from './productTransactionalBoundaryV23';
import {parseDocument,type AdminScope} from './onboardingReadbackV23';
import {classifyApiOrigin} from './apiOriginPolicy';
const deny=():never=>{throw Error('Renovação indisponível ou inconsistente. Nenhuma operação autorizada.');};
function exact(v:unknown,keys:string){if(!v||typeof v!=='object'||Array.isArray(v))return deny();const x=v as Record<string,unknown>,k=keys.split(' ');if(Object.keys(x).length!==k.length||k.some(y=>!Object.hasOwn(x,y)))return deny();return x;}
function one<T extends string>(v:unknown,a:readonly T[]):T{if(typeof v!=='string'||!a.includes(v as T))return deny();return v as T;}
function cents(v:unknown,max=100000000){if(typeof v!=='number'||!Number.isSafeInteger(v)||v<1||v>max)return deny();return v;}
function stamp(v:unknown){if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(v)||!Number.isFinite(Date.parse(v)))return deny();return v;}
function id(v:unknown){const x=uuid(v);if(x==='00000000-0000-0000-0000-000000000000')deny();return x;}
function key(s:AdminScope){if(s.role!=='TENANT_ADMIN')deny();return JSON.stringify([id(s.userId),id(s.tenantId),s.role]);}
const periods=['MONTHLY','ANNUAL'] as const,tiers=['ESSENCIAL','INTERMEDIARIO'] as const;
export async function parseRenewalOverview(raw:unknown,s:AdminScope){
 const hasUpgrade=!!raw&&typeof raw==='object'&&Object.hasOwn(raw,'upgrade');
 const x=exact(raw,'user_id tenant_id role ci_only production_authorized real_payment_authorized observed_at access document segments renewals offer'+(hasUpgrade?' upgrade':''));
 if(key({userId:id(x.user_id),tenantId:id(x.tenant_id),role:x.role as 'TENANT_ADMIN'})!==key(s)||x.ci_only!==true||x.production_authorized!==false||x.real_payment_authorized!==false)deny();
 const observed_at=stamp(x.observed_at),now=Date.parse(observed_at),access=one(x.access,['CURRENT','CONTINUITY_ONLY'] as const);
 const document=await parseDocument(x.document,'PLATFORM_LICENSE');
 if(!Array.isArray(x.segments)||!x.segments.length||x.segments.length>50||!Array.isArray(x.renewals)||x.renewals.length>50)return deny();
 const ids=new Set<string>(),payments=new Set<string>();
 const segments=x.segments.map(v=>{
  const q=exact(v,'entitlement_id tier period cents valid_from valid_until state intent_id'),entitlement_id=id(q.entitlement_id),intent_id=id(q.intent_id);
  const valid_from=stamp(q.valid_from),valid_until=stamp(q.valid_until),start=Date.parse(valid_from),end=Date.parse(valid_until);
  const state=one(q.state,['CURRENT','SCHEDULED','EXPIRED','SUSPENDED','REFUNDED'] as const);
  if(ids.has(entitlement_id)||payments.has(intent_id)||start>=end||(state==='CURRENT'&&!(start<=now&&now<end))||(state==='SCHEDULED'&&start<=now)||(state==='EXPIRED'&&end>now))deny();
  ids.add(entitlement_id);payments.add(intent_id);
  return Object.freeze({entitlement_id,intent_id,tier:one(q.tier,tiers),period:one(q.period,periods),cents:cents(q.cents),valid_from,valid_until,state});
 });
 if(segments.filter(v=>v.state==='CURRENT').length!==(access==='CURRENT'?1:0))deny();
 const requests=new Set<string>(),predecessors=new Set<string>(),intents=new Set<string>();
 const renewals=x.renewals.map(v=>{
  const q=exact(v,'request_id predecessor intent_id price_version period cents expires_at entitlement_id state');
  const request_id=id(q.request_id),predecessor=id(q.predecessor),intent_id=id(q.intent_id),price_version=id(q.price_version),period=one(q.period,periods),amount=cents(q.cents),expires_at=stamp(q.expires_at);
  const state=one(q.state,['PENDING','REVIEW_REQUIRED','PAYMENT_REVIEW','CI_RECONCILED','REFUNDED','CANCELED'] as const);
  const entitlement_id=q.entitlement_id===null?null:id(q.entitlement_id),seg=segments.find(a=>a.entitlement_id===entitlement_id);
  if(requests.has(request_id)||(state!=='CANCELED'&&predecessors.has(predecessor))||intents.has(intent_id)||!ids.has(predecessor)||predecessor===entitlement_id)deny();
  if(state==='PENDING'||state==='REVIEW_REQUIRED'||state==='PAYMENT_REVIEW'||state==='CANCELED'){
   if(entitlement_id!==null||payments.has(intent_id)||(state!=='PAYMENT_REVIEW'&&(state==='PENDING')!==(now<Date.parse(expires_at))))deny();
  }else if(!seg||seg.intent_id!==intent_id||seg.period!==period||seg.cents!==amount||(state==='REFUNDED')!==(seg.state==='REFUNDED'))deny();
  requests.add(request_id);if(state!=='CANCELED')predecessors.add(predecessor);intents.add(intent_id);
  return Object.freeze({request_id,predecessor,intent_id,price_version,period,cents:amount,expires_at,entitlement_id,state});
 });
 const edges=renewals.filter(v=>v.entitlement_id!==null);
 const parents=new Map(edges.map(v=>[v.entitlement_id!,v.predecessor]));
 const roots=segments.filter(v=>!parents.has(v.entitlement_id));
 if(edges.length!==segments.length-1||parents.size!==edges.length||roots.length!==1)deny();
 for(const seg of segments){
  let node=seg.entitlement_id;const seen=new Set<string>();
  while(parents.has(node)){if(seen.has(node))deny();seen.add(node);node=parents.get(node)!;}
  if(node!==roots[0].entitlement_id)deny();
 }
 const paid=segments.filter(v=>v.state!=='REFUNDED').map(v=>[Date.parse(v.valid_from),Date.parse(v.valid_until)]).sort((a,b)=>a[0]-b[0]);
 if(paid.some((v,i)=>i>0&&paid[i-1][1]>v[0]))deny();
 const used=new Set(edges.map(v=>v.predecessor));
 const leaves=segments.filter(v=>!used.has(v.entitlement_id));
 if(leaves.length!==1)deny();
 let offer=null;
 if(x.offer!==null){
  if(renewals.some(v=>v.state==='PAYMENT_REVIEW'))deny();
  const q=exact(x.offer,'predecessor price_version tier members_limit quotas_limit monthly_cents annual_cents'),predecessor=id(q.predecessor),tier=one(q.tier,tiers);
  const prev=segments.find(a=>a.entitlement_id===predecessor);
  if(!prev||prev.tier!==tier||!['CURRENT','SCHEDULED','EXPIRED','REFUNDED'].includes(prev.state)||predecessors.has(predecessor)||leaves[0].entitlement_id!==predecessor)deny();
  offer=Object.freeze({predecessor,tier,price_version:id(q.price_version),members_limit:cents(q.members_limit,200),quotas_limit:cents(q.quotas_limit,400),monthly_cents:cents(q.monthly_cents),annual_cents:cents(q.annual_cents)});
 }
 let upgrade=null;
 if(hasUpgrade){
  const u=exact(x.upgrade,'request_id state difference_cents members_limit quotas_limit entitlement_ids');
  const state=one(u.state,['SETTLEMENT_REVIEW','CI_APPLIED'] as const);
  if(offer!==null||!Array.isArray(u.entitlement_ids)||u.entitlement_ids.length>50)return deny();
  const entitlement_ids=u.entitlement_ids.map(id);
  if(new Set(entitlement_ids).size!==entitlement_ids.length||entitlement_ids.some(v=>!ids.has(v)))deny();
  if(state==='SETTLEMENT_REVIEW'&&(entitlement_ids.length!==0||u.members_limit!==null||u.quotas_limit!==null))deny();
  if(state==='CI_APPLIED'&&entitlement_ids.length===0)deny();
  upgrade=Object.freeze({request_id:id(u.request_id),state,difference_cents:cents(u.difference_cents),
   members_limit:state==='CI_APPLIED'?cents(u.members_limit,200):null,quotas_limit:state==='CI_APPLIED'?cents(u.quotas_limit,400):null,
   entitlement_ids:Object.freeze(entitlement_ids)});
 }
 return Object.freeze({scope:key(s),observed_at,access,document,segments:Object.freeze(segments),renewals:Object.freeze(renewals),offer,upgrade});
}
export type RenewalOverview=Awaited<ReturnType<typeof parseRenewalOverview>>;
export function prepareRenewal(s:AdminScope,view:RenewalOverview,requestId:unknown,choice:unknown,accepted:unknown){
 if(view.scope!==key(s)||accepted!==true||!view.offer)return deny();
 const period=one(choice,periods),o=view.offer;
 return Object.freeze({path:'/tenants/'+id(s.tenantId)+'/renewal',body:Object.freeze({request_id:id(requestId),predecessor:o.predecessor,price_version:o.price_version,period,cents:period==='MONTHLY'?o.monthly_cents:o.annual_cents,document_id:view.document.document_id,document_hash:view.document.document_hash,accepted:true as const})});
}
export async function readRenewal(t:Transport,s:AdminScope){
 const snap=t.captureSession(),expected=key(s);
 const same=()=>{const u=t.getUser();return t.isCurrent(snap)&&!!snap.token&&!!u&&u.role==='TENANT_ADMIN'&&!!u.tenantId&&key({userId:u.id,tenantId:u.tenantId,role:u.role})===expected;};
 if(!same())return deny();
 const origin=classifyApiOrigin(t.origin());if(origin.kind==='BLOCKED')return deny();
 const res=await t.send(origin.origin+'/api/v1/v23/onboarding/tenants/'+id(s.tenantId)+'/renewal',{method:'GET',headers:{Authorization:'Bearer '+snap.token,Accept:'application/json'},cache:'no-store',credentials:'omit',redirect:'error'});
 if(!same())return deny();
 if(res.status===401){t.invalidateIfCurrent(snap);return deny();}
 if(!res.ok)throw Error('Renovação bloqueada ou indisponível (HTTP '+res.status+').');
 if(res.headers.get('cache-control')!=='no-store')return deny();
 const view=await parseRenewalOverview(await res.json(),s);
 if(!same())return deny();return view;
}
