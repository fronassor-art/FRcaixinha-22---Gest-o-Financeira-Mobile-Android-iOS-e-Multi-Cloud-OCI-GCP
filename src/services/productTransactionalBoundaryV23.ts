/** M41360: typed V2.3 read boundary. No real money, no storage, no demo fallback. */
import type {AuthenticatedUser,AuthSessionSnapshot} from './authService';
import {classifyApiOrigin} from './apiOriginPolicy';
import {civilDateDayNumberV22} from './cycleWindowV22';
export type TenantRole='TENANT_ADMIN'|'TENANT_MEMBER';
export type Scope={userId:string;tenantId:string;role:TenantRole};
export type Transport={
 origin:()=>string;captureSession:()=>AuthSessionSnapshot;isCurrent:(s:AuthSessionSnapshot)=>boolean;
 getUser:()=>AuthenticatedUser|null;invalidateIfCurrent:(s:AuthSessionSnapshot)=>boolean;
 send:(url:string,options:RequestInit)=>Promise<Response>;
};
const fail=():never=>{throw Error('Resposta V2.3 inconsistente. Nenhum dado confirmado.');};
const rec=(v:unknown):Record<string,unknown>=>{if(!v||typeof v!=='object'||Array.isArray(v))return fail();return v as Record<string,unknown>;};
function exact(v:unknown,keys:string){const x=rec(v);const k=keys.split(' ');if(Object.keys(x).length!==k.length||k.some(s=>!Object.hasOwn(x,s)))return fail();return x;}
export function uuid(v:unknown):string {if(typeof v!=='string'||!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v))return fail();return v.toLowerCase();}
function date(v:unknown):string{civilDateDayNumberV22(v);return v as string;}
function num(v:unknown,min=0,max=Number.MAX_SAFE_INTEGER):number{if(typeof v!=='number'||!Number.isSafeInteger(v)||v<min||v>max)return fail();return v;}
function one<T extends string>(v:unknown,allowed:readonly T[]):T{if(typeof v!=='string'||!allowed.includes(v as T))return fail();return v as T;}
function hash(v:unknown):string{if(typeof v!=='string'||!/^[0-9a-f]{64}$/.test(v))return fail();return v;}
function off(v:unknown):false{if(v!==false)return fail();return false;}
function boolean(v:unknown):boolean{if(typeof v!=='boolean')return fail();return v;}
const modes=['MANUAL','MERCADO_PAGO','HYBRID'] as const;
function sameScope(x:Record<string,unknown>,s:Scope){if(uuid(x.user_id)!==uuid(s.userId)||uuid(x.tenant_id)!==uuid(s.tenantId)||x.role!==s.role)fail();}
function dates(x:Record<string,unknown>){const start=date(x.start_date),first=date(x.first_due),last=date(x.last_due),closing=date(x.closing);if(!(start<=first&&first<=last&&last<=closing))fail();return {start_date:start,first_due:first,last_due:last,closing};}
function page(x:Record<string,unknown>,offset:number){if(num(x.offset,0,10000)!==offset||!Array.isArray(x.items)||x.items.length>50)return fail();const has_more=boolean(x.has_more);if(has_more&&x.items.length!==50)return fail();return {items:x.items as unknown[],has_more};}
export function parseCapabilities(v:unknown){const x=exact(v,'contract available manual_receipts_enabled cycle_writes_enabled real_payments_enabled production_authorized');if(x.contract!=='FR_FINANCE_V23_TRANSACTION_V1')fail();return {available:off(x.available),manual_receipts_enabled:off(x.manual_receipts_enabled),cycle_writes_enabled:off(x.cycle_writes_enabled),real_payments_enabled:off(x.real_payments_enabled),production_authorized:off(x.production_authorized)};}
export function parseDirectory(v:unknown,s:Scope,offset:number){
 const x=exact(v,'tenant_id user_id role offset has_more items');sameScope(x,s);const p=page(x,offset);const seen=new Set<string>();
 const items=p.items.map(v=>{const y=exact(v,'cycle_id start_date first_due last_due closing quota_cents mode status membership_state');const id=uuid(y.cycle_id);if(seen.has(id))fail();seen.add(id);
 const membership_state=s.role==='TENANT_ADMIN'?(y.membership_state===null?null:fail()):one(y.membership_state,['ADMITTED','CONSENTED','INVITED'] as const);
 return {cycle_id:id,...dates(y),quota_cents:num(y.quota_cents,1,100000000),mode:one(y.mode,modes),status:one(y.status,['ABERTO','CONGELADO','EM_APURACAO','LIQUIDADO'] as const),membership_state};});
 return {items,has_more:p.has_more};
}
export function parseWorkspace(v:unknown,s:Scope,cycle:string,offset:number){
 const raw=rec(v);const hasInvitation=Object.hasOwn(raw,'invitation');
 const x=exact(v,'tenant_id user_id role cycle_id membership_id policy summary reserves offset has_more items'+(hasInvitation?' invitation':''));sameScope(x,s);if(uuid(x.cycle_id)!==uuid(cycle))fail();const p=page(x,offset);
 const m=s.role==='TENANT_ADMIN'?(x.membership_id===null?null:fail()):uuid(x.membership_id);
 const y=exact(x.policy,'policy_hash document_id document_hash start_date first_due last_due closing quota_cents admin_bps late_days late_competences mode');
 const policy={...dates(y),policy_hash:hash(y.policy_hash),document_id:uuid(y.document_id),document_hash:hash(y.document_hash),quota_cents:num(y.quota_cents,1,100000000),admin_bps:num(y.admin_bps,0,10000),late_days:num(y.late_days,1,3650),late_competences:num(y.late_competences,1,120),mode:one(y.mode,modes)};
 const admin=s.role==='TENANT_ADMIN';let summary:null|{obligation_cents:number;paid_cents:number;manual_pending_cents:number;contested_receipts:number;manual_documented_cents?:number;member_capital_documented_cents?:number}=null;
 if(x.summary!==null){const z=exact(x.summary,'cycle_id obligation_cents paid_cents manual_pending_cents contested_receipts bank_reconciled '+(admin?'manual_documented_cents member_capital_documented_cents':'membership_id'));
 if(uuid(z.cycle_id)!==uuid(cycle)||(!admin&&uuid(z.membership_id)!==m))fail();off(z.bank_reconciled);
 summary={obligation_cents:num(z.obligation_cents),paid_cents:num(z.paid_cents),manual_pending_cents:num(z.manual_pending_cents),contested_receipts:num(z.contested_receipts)};
 if(summary.paid_cents>summary.obligation_cents)fail();
 if(admin){summary.manual_documented_cents=num(z.manual_documented_cents);summary.member_capital_documented_cents=num(z.member_capital_documented_cents);}
 }else if(admin||p.items.length||p.has_more)fail();
 let reserves:null|{documented_cents:number;contested_cents:number;reserved_cents:number;unreserved_documented_cents:number;reserve_deficit_cents:number}=null;
 if(admin){const z=exact(x.reserves,'documented_cents contested_cents reserved_cents unreserved_documented_cents reserve_deficit_cents bank_available_cents bank_reconciled payout_authorized');
 if(z.bank_available_cents!==0)fail();off(z.bank_reconciled);off(z.payout_authorized);
 reserves={documented_cents:num(z.documented_cents),contested_cents:num(z.contested_cents),reserved_cents:num(z.reserved_cents),unreserved_documented_cents:num(z.unreserved_documented_cents),reserve_deficit_cents:num(z.reserve_deficit_cents)};
 const {documented_cents:d,contested_cents:c,reserved_cents:r,unreserved_documented_cents:u,reserve_deficit_cents:f}=reserves;
 if(c>d||u!==Math.max(d-c-r,0)||f!==Math.max(r-(d-c),0)||d!==summary?.manual_documented_cents)fail();
 }else if(x.reserves!==null)fail();
 const seen=new Set<string>();const items=p.items.map(v=>{const z=exact(v,'contribution_id membership_id competence due_date due_cents paid_cents payment_status pending_manual_cents');const id=uuid(z.contribution_id),member=uuid(z.membership_id),due=date(z.due_date),a=num(z.due_cents,1),b=num(z.paid_cents),pending=num(z.pending_manual_cents),status=one(z.payment_status,['PENDENTE','PARCIAL','QUITADA'] as const);
 if(seen.has(id)||(!admin&&member!==m)||due<policy.first_due||due>policy.last_due||z.competence!==due.slice(0,7)||b>a||pending>a-b||(status==='QUITADA'?b!==a:status==='PENDENTE'?b!==0:b<=0||b>=a))fail();seen.add(id);
 return {contribution_id:id,membership_id:member,due_date:due,due_cents:a,paid_cents:b,pending_manual_cents:pending,payment_status:status};});
 let invitation:null|{id:string;joined:string;quotas:number;policy_hash:string}=null;
 if(hasInvitation){const z=exact(x.invitation,'id joined quotas policy_hash');
  if(admin||summary!==null||reserves!==null||items.length||p.has_more)fail();
  invitation={id:uuid(z.id),joined:date(z.joined),quotas:num(z.quotas,1,400),policy_hash:hash(z.policy_hash)};
  if(invitation.policy_hash!==policy.policy_hash||invitation.joined<policy.start_date||invitation.joined>policy.last_due||invitation.quotas*policy.quota_cents>100000000)fail();
 }
 return {cycle_id:uuid(cycle),scope:{userId:uuid(s.userId),tenantId:uuid(s.tenantId),role:s.role},policy,summary,reserves,items,has_more:p.has_more,invitation};
}
export type Directory=ReturnType<typeof parseDirectory>;
export type Workspace=ReturnType<typeof parseWorkspace>;
export type OptionKind='DOCUMENT'|'ADMIT'|'CONFIRM'|'REVERSE'|'CONTEST'|'RELEASE';
export function parseFormOptions(v:unknown,s:Scope,kind:OptionKind,cycle:string|null,offset:number){
 const x=exact(v,'tenant_id user_id role cycle_id kind offset has_more items');sameScope(x,s);
 if(x.kind!==kind||(kind==='DOCUMENT')!==(cycle===null)||(cycle===null?x.cycle_id!==null:uuid(x.cycle_id)!==uuid(cycle)))fail();
 if(kind==='CONTEST'?s.role!=='TENANT_MEMBER':s.role!=='TENANT_ADMIN')fail();
 const p=page(x,offset),seen=new Set<string>();
 const items=p.items.map(v=>{
  const z=exact(v,'id date cents quotas state document_hash related_id'),id=uuid(z.id);
  if(seen.has(id))fail();seen.add(id);
  if(kind==='DOCUMENT'){if([z.date,z.cents,z.quotas,z.state,z.related_id].some(y=>y!==null))fail();return {id,document_hash:hash(z.document_hash)};}
  if(z.document_hash!==null)fail();
  if(kind==='ADMIT'){if([z.cents,z.state,z.related_id].some(y=>y!==null))fail();return {id,date:date(z.date),quotas:num(z.quotas,1,400)};}
  if(z.quotas!==null)fail();
  if(kind==='RELEASE'){if([z.date,z.state,z.related_id].some(y=>y!==null))fail();return {id,cents:num(z.cents,1,100000000000)};}
  return {id,date:date(z.date),cents:num(z.cents,1,100000000),state:one(z.state,kind==='CONFIRM'?['PENDING']:kind==='CONTEST'?['CONFIRMED']:['CONFIRMED','CONTESTED']),related_id:uuid(z.related_id)};
 });
 return {kind,cycle_id:cycle===null?null:uuid(cycle),scope:{userId:uuid(s.userId),tenantId:uuid(s.tenantId),role:s.role},items,has_more:p.has_more,offset};
}
export type FormOptions=ReturnType<typeof parseFormOptions>;
type Read={kind:'options';optionKind:OptionKind;cycleId:string|null;offset:number}|{kind:'capabilities'}|{kind:'directory';offset:number}|{kind:'workspace';cycleId:string;offset:number};
export async function readV23(t:Transport,s:Scope,q:Read){
 const tenant=uuid(s.tenantId),userId=uuid(s.userId);if(s.role!=='TENANT_ADMIN'&&s.role!=='TENANT_MEMBER')fail();
 const snapshot=t.captureSession(),u=t.getUser();if(!snapshot.token||!u||!t.isCurrent(snapshot)||uuid(u.id)!==userId||!u.tenantId||uuid(u.tenantId)!==tenant||u.role!==s.role)throw Error('Sessão ou caixinha alterada.');
 const origin=classifyApiOrigin(t.origin());if(origin.kind==='BLOCKED')throw Error('Servidor FR Finance não configurado.');
 let path='/capabilities';if(q.kind==='directory')path='/cycles?offset='+num(q.offset,0,10000);if(q.kind==='workspace')path='/cycles/'+uuid(q.cycleId)+'/workspace?offset='+num(q.offset,0,10000);
 if(q.kind==='options'){
  if((q.optionKind==='DOCUMENT')!==(q.cycleId===null)||(q.optionKind==='CONTEST'?s.role!=='TENANT_MEMBER':s.role!=='TENANT_ADMIN'))fail();
  const pageOffset=num(q.offset,0,10000);
  path=q.cycleId===null?'/form-options?offset='+pageOffset:'/cycles/'+uuid(q.cycleId)+'/form-options?kind='+q.optionKind+'&offset='+pageOffset;
 }
 let res:Response;try{res=await t.send(origin.origin+'/api/v1/tenants/'+tenant+'/v23'+path,{method:'GET',headers:{Authorization:'Bearer '+snapshot.token,Accept:'application/json'},cache:'no-store',credentials:'omit',redirect:'error'});}
 catch{throw Error('Conexão V2.3 indisponível. Nenhum dado confirmado.');}
 if(!t.isCurrent(snapshot))throw Error('Sessão alterada durante consulta.');
 if(res.status===401){t.invalidateIfCurrent(snapshot);throw Error('Sessão expirada.');}
 if(res.status===503)throw Error('V2.3 bloqueada no servidor (HTTP 503). Nenhum dado confirmado.');
 if(res.status===404)throw Error('Rota V2.3 ausente (HTTP 404). Verifique a versão do servidor.');
 if(!res.ok)throw Error('Consulta V2.3 recusada (HTTP '+res.status+').');
 const v:unknown=await res.json();if(!t.isCurrent(snapshot))throw Error('Sessão alterada durante consulta.');
 return q.kind==='options'?parseFormOptions(v,s,q.optionKind,q.cycleId,q.offset):q.kind==='capabilities'?parseCapabilities(v):q.kind==='directory'?parseDirectory(v,s,q.offset):parseWorkspace(v,s,q.cycleId,q.offset);
}
