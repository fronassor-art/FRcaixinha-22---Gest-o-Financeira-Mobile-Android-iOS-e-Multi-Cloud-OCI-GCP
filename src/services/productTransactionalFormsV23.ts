/** M41370 — V2.3 typed preparation. No network, persistence or authorization. */
import {uuid,type Scope} from './productTransactionalBoundaryV23';
import {civilDateDayNumberV22} from './cycleWindowV22';
export type Kind='POLICY'|'CONSENT'|'ADMIT'|'RECEIPT'|'CONFIRM'|'REVERSE'|'CONTEST'|'HOLD'|'RELEASE';
export type Fields=Record<string,string>;
export type Prepared=Readonly<{scope:string;kind:Kind;path:string;body:Readonly<Record<string,string|number|boolean|null>>}>;
export type PolicyProof=Readonly<{fingerprint:string;policyHash:string}>;
const deny=(m='Dados V2.3 inválidos.'):never=>{throw Error(m);};
function require(ok:unknown,m?:string){if(!ok)deny(m);}
function int(v:string,min:number,max:number){require(typeof v==='string'&&/^\d{1,12}$/.test(v),'Informe um número inteiro.');const n=Number(v);require(Number.isSafeInteger(n)&&n>=min&&n<=max,'Valor fora do intervalo técnico.');return n;}
export function cents(v:string,max=100000000,allowZero=false){require(typeof v==='string'&&/^\d{1,9}(?:[,.]\d{1,2})?$/.test(v),'Informe valor com até duas casas decimais.');const [a,b='']=v.replace(',','.').split('.');const n=Number(a)*100+Number(b.padEnd(2,'0'));require(Number.isSafeInteger(n)&&n>=(allowZero?0:1)&&n<=max,'Valor fora do intervalo técnico.');return n;}
function day(v:string){civilDateDayNumberV22(v);return v;}
function text(v:string,min:number,max:number){require(typeof v==='string'&&v===v.trim()&&v.length>=min&&v.length<=max&&!/[\u0000-\u001f\u007f]/.test(v),'Referência ou evidência inválida.');return v;}
function pick(v:string,options:string[]){require(options.includes(v));return v;}
function digest(v:string){require(typeof v==='string'&&/^[0-9a-f]{64}$/.test(v),'Hash de política inválido.');return v;}
export function scopeKey(s:Scope){require(s.role==='TENANT_ADMIN'||s.role==='TENANT_MEMBER','Perfil não autorizado.');return JSON.stringify([uuid(s.userId),uuid(s.tenantId),s.role]);}
export function allowedKinds(s:Scope):Kind[]{scopeKey(s);return s.role==='TENANT_ADMIN'?['POLICY','ADMIT','RECEIPT','CONFIRM','REVERSE','HOLD','RELEASE']:['CONSENT','CONTEST'];}
export function prepareV23(s:Scope,kind:Kind,f:Fields,requestId:string,accepted:boolean):Prepared{
 const scope=scopeKey(s);require(allowedKinds(s).includes(kind),'Operação não pertence ao perfil.');require(accepted===true,'Confirme a conferência explícita dos dados.');
 const request_id=uuid(requestId);let path:string;let body:Record<string,string|number|boolean|null>;
 const cycle=()=>'/cycles/'+uuid(f.cycle_id);
 if(kind==='POLICY'){
  const start=day(f.start),first_due=day(f.first_due),last_due=day(f.last_due),closing=day(f.closing);
  require(start<=first_due&&first_due<=last_due&&last_due<=closing,'Datas fora da sequência do ciclo.');
  const n=(Number(last_due.slice(0,4))-Number(first_due.slice(0,4)))*12+Number(last_due.slice(5,7))-Number(first_due.slice(5,7));
  require(n>=0&&n<=119,'Calendário fora do limite técnico.');
  const y=Number(first_due.slice(0,4)),m=Number(first_due.slice(5,7))-1,d=Number(first_due.slice(8)),base=new Date(Date.UTC(y,m+n,1));
  const anchor=Math.min(d,new Date(Date.UTC(base.getUTCFullYear(),base.getUTCMonth()+1,0)).getUTCDate());
  require(new Date(Date.UTC(base.getUTCFullYear(),base.getUTCMonth(),anchor)).toISOString().slice(0,10)===last_due,'Último vencimento não corresponde à âncora mensal.');
  path='/policies/preview';body={request_id,start,first_due,last_due,closing,quota_cents:cents(f.quota),admin_bps:cents(f.admin_pct,10000,true),late_days:int(f.late_days,1,3650),late_competences:int(f.late_competences,1,120),mode:pick(f.mode,['MANUAL','MERCADO_PAGO','HYBRID']),document_id:uuid(f.document_id)};
 }else if(kind==='CONSENT'){
  path=cycle()+'/policy-acceptance';body={policy_hash:digest(f.policy_hash),joined:day(f.joined),quotas:int(f.quotas,1,400),accepted:true};
 }else if(kind==='ADMIT'){
  path=cycle()+'/admissions';body={membership_id:uuid(f.membership_id),joined:day(f.joined),quotas:int(f.quotas,1,400)};
 }else if(kind==='RECEIPT'){
  path='/manual-receipts';body={request_id,contribution_id:uuid(f.contribution_id),cents:cents(f.amount),method:pick(f.method,['DINHEIRO','PIX_EXTERNO','TRANSFERENCIA','DEPOSITO']),occurred:day(f.occurred),reference:text(f.reference,3,100),evidence_ref:text(f.evidence_ref,3,160)};
 }else if(kind==='CONFIRM'||kind==='REVERSE'||kind==='CONTEST'){
  path='/manual-receipts/'+uuid(f.receipt_id)+'/'+kind;body={request_id,occurred:day(f.occurred),evidence_ref:text(f.evidence_ref,3,160)};
 }else{
  path=cycle()+'/reserves';body={request_id,action:kind,cents:cents(f.amount,100000000000),related_hold:kind==='RELEASE'?uuid(f.related_hold):null,reason:text(f.reason,8,160)};
 }
 return Object.freeze({scope,kind,path,body:Object.freeze(body)});
}
export function fingerprint(p:Prepared){return JSON.stringify([p.scope,p.kind,p.path,p.body]);}
export function bindPolicyPreview(p:Prepared,raw:unknown):PolicyProof{
 require(p.kind==='POLICY'&&p.path==='/policies/preview');require(raw&&typeof raw==='object'&&!Array.isArray(raw)&&Object.keys(raw).length===1);
 return Object.freeze({fingerprint:fingerprint(p),policyHash:digest((raw as {policy_hash:string}).policy_hash)});
}
export function prepareCycleOpening(p:Prepared,proof:PolicyProof,accepted:boolean):Prepared{
 require(p.kind==='POLICY'&&p.path==='/policies/preview'&&accepted===true&&proof.fingerprint===fingerprint(p),'Confira novamente a política antes do aceite.');
 return Object.freeze({...p,path:'/cycles',body:Object.freeze({...p.body,policy_hash:digest(proof.policyHash),accepted:true})});
}
/** In-memory retry identity. Editing an attempt after an ambiguous send is NOT a retry. */
export function reuseAttempt(previous:Prepared|null,next:Prepared):Prepared{
 if(!previous)return next;
 const stable=(p:Prepared)=>{const {request_id,...body}=p.body;return JSON.stringify([p.scope,p.kind,p.path,body]);};
 require(stable(previous)===stable(next),'O conteúdo mudou. Não reutilize a tentativa anterior.');
 return previous;
}
/** Candidate transport only. Production code does not bind this function to fetch.
 * The caller must provide an isolated test transport. No capability flag enables real writes.
 */
export async function exerciseCandidate(p:Prepared,s:Scope,send:(path:string,body:Prepared['body'])=>Promise<unknown>){
 require(p.scope===scopeKey(s)&&allowedKinds(s).includes(p.kind),'Contexto alterado.');
 const raw=await send(p.path,p.body);
 if(p.kind==='POLICY'&&p.path==='/policies/preview')return bindPolicyPreview(p,raw);
 require(raw&&typeof raw==='object'&&!Array.isArray(raw)&&Object.keys(raw).length===1,'Resposta não confirmada.');
 const x=raw as Record<string,unknown>;
 if(p.kind==='ADMIT'){require(typeof x.obligations==='number'&&Number.isInteger(x.obligations)&&x.obligations>=1&&x.obligations<=120);return {obligations:x.obligations};}
 if(p.kind==='CONFIRM'||p.kind==='REVERSE'||p.kind==='CONTEST'){const expected={CONFIRM:'CONFIRMED',REVERSE:'REVERSED',CONTEST:'CONTESTED'}[p.kind];require(x.state===expected,'Estado não confirmado.');return {state:expected};}
 const key=p.kind==='POLICY'?'cycle_id':p.kind==='CONSENT'?'consent_id':p.kind==='RECEIPT'?'receipt_id':'event_id';return {[key]:uuid(x[key])};
}
