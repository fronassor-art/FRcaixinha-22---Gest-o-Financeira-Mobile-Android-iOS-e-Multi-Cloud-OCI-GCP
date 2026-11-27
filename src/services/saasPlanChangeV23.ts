/** M41520: read-only candidate quote; no quote creation, acceptance or payment transport. */
import {uuid,type Transport} from './productTransactionalBoundaryV23';
import type {AdminScope} from './onboardingReadbackV23';
import {classifyApiOrigin} from './apiOriginPolicy';
const deny=():never=>{throw Error('Alteração de plano indisponível ou inconsistente.');};
const exact=(v:unknown,keys:string)=>{if(!v||typeof v!=='object'||Array.isArray(v))return deny();const x=v as Record<string,unknown>,k=keys.split(' ');if(Object.keys(x).length!==k.length||k.some(y=>!Object.hasOwn(x,y)))deny();return x;};
const integer=(v:unknown,min=0,max=100000000)=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=min&&v<=max?v:deny();
const sha=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v)?v:deny();
const stamp=(v:unknown)=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$/.test(v)&&Number.isFinite(Date.parse(v))?v:deny();
const micros=(v:string)=>BigInt(Date.parse(v))*1000n+BigInt(v.slice(23,26));
const tier=(v:unknown)=>v==='ESSENCIAL'||v==='INTERMEDIARIO'?v:deny();
const period=(v:unknown)=>v==='MONTHLY'||v==='ANNUAL'?v:deny();
const canonical=(v:unknown):string=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v!==null&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical((v as Record<string,unknown>)[k])).join(',')+'}':JSON.stringify(v);
export async function parsePlanChange(raw:unknown,s:AdminScope,target:unknown){
 const outer=exact(raw,'snapshot offer_hash'),q=exact(outer.snapshot,'user_id tenant_id role ci_only production_authorized real_payment_authorized current_tier target_tier target_price_version document_id document_hash calculated_at expires_at members_in_use quotas_in_use members_limit quotas_limit decision total_cents segments');
 if(s.role!=='TENANT_ADMIN'||uuid(q.user_id)!==s.userId||uuid(q.tenant_id)!==s.tenantId||q.role!==s.role||q.ci_only!==true||q.production_authorized!==false||q.real_payment_authorized!==false)deny();
 const current_tier=tier(q.current_tier),target_tier=tier(q.target_tier);
 if(current_tier===target_tier||target_tier!==target)deny();
 const calculated_at=stamp(q.calculated_at),expires_at=stamp(q.expires_at);
 if(Date.parse(expires_at)-Date.parse(calculated_at)!==900000)deny();
 const members_in_use=integer(q.members_in_use),quotas_in_use=integer(q.quotas_in_use),members_limit=integer(q.members_limit,1,400),quotas_limit=integer(q.quotas_limit,1,400);
 const total_cents=integer(q.total_cents),decision=q.decision;
 const upgrade=current_tier==='ESSENCIAL';
 if(decision!==(members_in_use>members_limit||quotas_in_use>quotas_limit?'CAPACITY_REVIEW':upgrade?(total_cents>0?'UPGRADE_REVIEW':'ZERO_DIFFERENCE_REVIEW'):'DOWNGRADE_NEXT_RENEWAL'))deny();
 if(!Array.isArray(q.segments)||q.segments.length<1||q.segments.length>50)return deny();
 const ids=new Set<string>();
 const segments=q.segments.map(v=>{
  const x=exact(v,'entitlement_id price_version period period_start period_end paid_cents target_cents difference_cents'),entitlement_id=uuid(x.entitlement_id),price_version=uuid(x.price_version);
  const period_start=stamp(x.period_start),period_end=stamp(x.period_end),paid_cents=integer(x.paid_cents,1),target_cents=integer(x.target_cents,1),difference_cents=integer(x.difference_cents);
  if(ids.has(entitlement_id)||period_start>=period_end||period_end<=calculated_at||difference_cents>(upgrade?Math.max(0,target_cents-paid_cents):0))deny();
  const span=micros(period_end)-micros(period_start),remaining=micros(period_end)-micros(period_start>calculated_at?period_start:calculated_at);
  if(span<=0n||remaining<=0n)deny();
  const delta=BigInt(upgrade?Math.max(0,target_cents-paid_cents):0);
  if(BigInt(difference_cents)!==(2n*delta*remaining+span)/(2n*span))deny();
  ids.add(entitlement_id);return Object.freeze({entitlement_id,price_version,period:period(x.period),period_start,period_end,paid_cents,target_cents,difference_cents});
 });
 if(segments.filter(x=>x.period_start<=calculated_at&&calculated_at<x.period_end).length!==1||segments.some((x,i)=>i>0&&segments[i-1].period_end>x.period_start)||segments.reduce((n,x)=>n+x.difference_cents,0)!==total_cents)deny();
 const offer_hash=sha(outer.offer_hash),digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(q))))).map(v=>v.toString(16).padStart(2,'0')).join('');
 if(digest!==offer_hash)deny();
 return Object.freeze({current_tier,target_tier,target_price_version:uuid(q.target_price_version),document_id:uuid(q.document_id),document_hash:sha(q.document_hash),calculated_at,expires_at,members_in_use,quotas_in_use,members_limit,quotas_limit,decision,total_cents,segments:Object.freeze(segments),offer_hash});
}
export type PlanChange=Awaited<ReturnType<typeof parsePlanChange>>;
export async function readPlanChange(t:Transport,s:AdminScope,target:unknown){
 const selected=tier(target),snap=t.captureSession();
 const same=()=>{const u=t.getUser();return t.isCurrent(snap)&&!!snap.token&&!!u&&u.role==='TENANT_ADMIN'&&u.id===s.userId&&u.tenantId===s.tenantId;};
 if(!same())return deny();
 const origin=classifyApiOrigin(t.origin());if(origin.kind==='BLOCKED')return deny();
 const res=await t.send(origin.origin+'/api/v1/v23/onboarding/tenants/'+uuid(s.tenantId)+'/plan-change/'+selected,{method:'GET',headers:{Authorization:'Bearer '+snap.token,Accept:'application/json'},cache:'no-store',credentials:'omit',redirect:'error'});
 if(!same())return deny();
 if(res.status===401){t.invalidateIfCurrent(snap);return deny();}
 if(!res.ok||res.headers.get('cache-control')!=='no-store')return deny();
 const view=await parsePlanChange(await res.json(),s,selected);
 if(!same())return deny();return view;
}
