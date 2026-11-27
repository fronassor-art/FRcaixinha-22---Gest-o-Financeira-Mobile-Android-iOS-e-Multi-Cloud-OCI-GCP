/** M41440: pure, ephemeral CI candidate form preparation. No network or storage. */
import {parseScopedDocument,parseInvitationTerms,parseOffers,prepareCheckout,type MasterScope,type AdminScope} from './onboardingReadbackV23';
import {uuid} from './productTransactionalBoundaryV23';
import {civilDateDayNumberV22} from './cycleWindowV22';
const denied=():never=>{throw Error('Formulário incompatível. Nenhuma operação autorizada.');};
function exact(value:unknown,fields:string){if(!value||typeof value!=='object'||Array.isArray(value))return denied();const x=value as Record<string,unknown>,keys=fields.split(' ');if(Object.keys(x).length!==keys.length||keys.some(k=>!Object.hasOwn(x,k)))return denied();return x;}
function text(v:unknown,min:number,max:number){if(typeof v!=='string'||v.length<min||v.length>max||/[\u0000-\u001f\u007f]/.test(v))return denied();return v;}
function label(v:unknown){const x=text(v,3,255).trim();if(x.length<3)denied();return x;}
function email(v:unknown){const x=text(v,3,254).trim().toLowerCase();if(!/^[a-z0-9][a-z0-9._+-]*@example\.invalid$/.test(x))denied();return x;}
function password(v:unknown){return text(v,12,256);}
function proof(v:unknown){const x=text(v,32,512);if(!/^[A-Za-z0-9_-]+$/.test(x))denied();return x;}
function cpf(v:unknown){const x=text(v,11,11);if(!/^\d{11}$/.test(x)||new Set(x).size===1)denied();const d=Array.from(x,Number);for(const n of [9,10]){let a=0;for(let i=0;i<n;i++)a+=d[i]*(n+1-i);if(d[n]!==((a*10)%11)%10)denied();}return x;}
function phone(v:unknown){const x=text(v,8,20);if(!/^[0-9+() -]{8,20}$/.test(x))denied();return x;}
function accept(v:unknown){if(v!==true)denied();return true as const;}
function documentFields(d:{document_id:string;document_hash:string}){return {document_id:d.document_id,document_hash:d.document_hash};}
function admin(s:AdminScope){if(s.role!=='TENANT_ADMIN')denied();uuid(s.userId);return uuid(s.tenantId);}
export async function masterInviteForm(s:MasterScope,raw:unknown,id:string,form:unknown){
 if(s.role!=='MASTER'||s.tenantId!==null)denied();
 const d=await parseScopedDocument(raw,s,id),f=exact(form,'email master_password confirmed');
 accept(f.confirmed);return {path:'/master/invitations',body:{...documentFields(d),email:email(f.email),master_password:password(f.master_password)}};
}
export async function adminBForm(s:AdminScope,raw:unknown,id:string,accepted:unknown){
 const tenant=admin(s),d=await parseScopedDocument(raw,s,id);
 return {path:'/tenants/'+tenant+'/contract-b',body:{...documentFields(d),accepted:accept(accepted)}};
}
export function memberInviteForm(s:AdminScope,cycleId:string,form:unknown){
 const tenant=admin(s),cycle=uuid(cycleId),f=exact(form,'email joined quotas previous_id confirmed');
 accept(f.confirmed);civilDateDayNumberV22(f.joined);
 if(typeof f.quotas!=='number'||!Number.isSafeInteger(f.quotas)||f.quotas<1||f.quotas>400)denied();
 return {path:'/tenants/'+tenant+'/cycles/'+cycle+'/member-invitations',body:{email:email(f.email),joined:f.joined as string,quotas:f.quotas,previous_id:f.previous_id===null?null:uuid(f.previous_id)}};
}
export function invitationProofForm(raw:unknown){
 const f=exact(raw,'invitation_token verification_token'),a=proof(f.invitation_token),b=proof(f.verification_token);
 if(a===b)denied();return Object.freeze({invitation_token:a,verification_token:b});
}
// Bind the exact readback and its two proofs in a closure. No caller-supplied
// document, policy, role, tenant, date or quota may override the readback.
export async function registrationForm(rawTerms:unknown,rawProofs:unknown){
 const proofs=invitationProofForm(rawProofs),t=await parseInvitationTerms(rawTerms);
 const doc=Object.freeze(documentFields(t.document)),role=t.role,terms=t.terms?Object.freeze({...t.terms}):null;
 let used=false;
 return Object.freeze({role,document:t.document,terms,prepare(form:unknown){
  if(used)denied();
  const f=exact(form,role==='TENANT_ADMIN'?'name cpf phone password confirm_password tenant_name accepted':'name cpf phone password confirm_password accepted');
  const pwd=password(f.password);if(pwd!==f.confirm_password)denied();
  const common={...proofs,...doc,accepted:accept(f.accepted),name:label(f.name),cpf:cpf(f.cpf),phone:phone(f.phone),password:pwd};
  const request=role==='TENANT_ADMIN'?{path:'/admin/registration',body:{...common,tenant_name:label(f.tenant_name)}}:
   {path:'/member/registration',body:{...common,...terms}};
  used=true;return request;
 },discard(){used=true;}});
}
export function checkoutForm(s:AdminScope,raw:unknown,id:string,period:unknown,accepted:unknown){
 const tenant=admin(s);return {path:'/tenants/'+tenant+'/checkout',body:prepareCheckout(s,parseOffers(raw,s),id,period,accepted)};
}
