/** FR Caixinha AI Studio — M1081: revisão documental em sandbox. */
export type ReviewKind =
  'ADMIN_DOCUMENTS_REQUESTED'|'ADMIN_REVIEW_ACCEPTED_SANDBOX'|
  'ADMIN_REVIEW_REJECTED_SANDBOX'|'MEMBER_CONTESTED';
export interface ReviewEvent {
  event_id:string;event_seq:number;tenant_id:string;request_id:string;
  membership_id:string;actor_user_id:string;event_kind:ReviewKind;
  evidence_reference:string;recorded_at:string;
  financial_effect_applied:false;bank_reconciled:false;
}
export interface ReviewTimeline {
  tenant_id:string;request_id:string;membership_id:string;
  request_kind:'VOLUNTARY_EXIT'|'DELINQUENCY_REVIEW';
  latest_event_kind:ReviewKind|null;
  pending_technical_review:boolean;items:ReviewEvent[];
  has_more:false;financial_effect_applied:false;bank_reconciled:false;
  membership_status_changed:false;closing_authorized:false;payout_authorized:false;
}
export interface ReviewCapabilities {
  tenant_id:string;year:number;role:'TENANT_MEMBER'|'TENANT_ADMIN';
  schema_ready:boolean;sandbox_only:true;
  can_submit_contestation:boolean;can_review_independently:boolean;
  financial_effects_enabled:false;real_payout_enabled:false;
}
const uid=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const reference=/^[A-Za-z0-9._:-]{8,120}$/;
const kinds=new Set<ReviewKind>([
  'ADMIN_DOCUMENTS_REQUESTED','ADMIN_REVIEW_ACCEPTED_SANDBOX',
  'ADMIN_REVIEW_REJECTED_SANDBOX','MEMBER_CONTESTED'
]);
const object=(x:unknown):x is Record<string,unknown> =>
  x!==null&&typeof x==='object'&&!Array.isArray(x);
const sameKeys=(x:Record<string,unknown>,keys:readonly string[]) =>
  Object.keys(x).length===keys.length&&Object.keys(x).every(k=>keys.includes(k));
const validStamp=(x:unknown) =>
  typeof x==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(x)&&
  Number.isFinite(Date.parse(x));
const capKeys=[
 'tenant_id','year','role','schema_ready','sandbox_only',
 'can_submit_contestation','can_review_independently',
 'financial_effects_enabled','real_payout_enabled'
];
export function parseReviewCapabilities(
  raw:unknown,tenantId:string,year:number,role:'TENANT_MEMBER'|'TENANT_ADMIN'
):ReviewCapabilities{
 if(!object(raw)||!uid.test(tenantId)||raw.tenant_id!==tenantId||
    raw.year!==year||raw.role!==role||typeof raw.schema_ready!=='boolean'||
    raw.sandbox_only!==true||raw.financial_effects_enabled!==false||
    raw.real_payout_enabled!==false||
    typeof raw.can_submit_contestation!=='boolean'||
    typeof raw.can_review_independently!=='boolean'||!sameKeys(raw,capKeys)||
    (role==='TENANT_MEMBER'&&raw.can_review_independently)||
    (role==='TENANT_ADMIN'&&raw.can_submit_contestation)||
    (!raw.schema_ready&&(raw.can_submit_contestation||raw.can_review_independently)))
    throw Error('Capacidades de revisão inconsistentes: dinheiro bloqueado');
 return {
   tenant_id:tenantId,year,role,schema_ready:raw.schema_ready as boolean,
   sandbox_only:true,
   can_submit_contestation:raw.can_submit_contestation as boolean,
   can_review_independently:raw.can_review_independently as boolean,
   financial_effects_enabled:false,real_payout_enabled:false,
 };
}
const eventKeys=[
 'event_id','event_seq','tenant_id','request_id','membership_id','actor_user_id',
 'event_kind','evidence_reference','recorded_at',
 'financial_effect_applied','bank_reconciled',
];
export function parseReviewEvent(raw:unknown,tenantId:string,requestId:string):ReviewEvent{
 if(!object(raw)||!uid.test(tenantId)||!uid.test(requestId)||
    ![raw.event_id,raw.membership_id,raw.actor_user_id]
      .every(x=>typeof x==='string'&&uid.test(x))||
    raw.tenant_id!==tenantId||raw.request_id!==requestId||
    typeof raw.event_seq!=='number'||!Number.isSafeInteger(raw.event_seq)||
    raw.event_seq<1||
    !kinds.has(raw.event_kind as ReviewKind)||
    typeof raw.evidence_reference!=='string'||
    !reference.test(raw.evidence_reference)||!validStamp(raw.recorded_at)||
    raw.financial_effect_applied!==false||raw.bank_reconciled!==false||
    !sameKeys(raw,eventKeys))
    throw Error('Evento de revisão inválido ou com privilégios financeiros');
 return {
   event_id:raw.event_id as string,event_seq:raw.event_seq as number,
   tenant_id:tenantId,request_id:requestId,
   membership_id:raw.membership_id as string,
   actor_user_id:raw.actor_user_id as string,
   event_kind:raw.event_kind as ReviewKind,
   evidence_reference:raw.evidence_reference as string,
   recorded_at:raw.recorded_at as string,
   financial_effect_applied:false,bank_reconciled:false,
 };
}
const timelineKeys=[
 'tenant_id','request_id','membership_id','request_kind','latest_event_kind',
 'pending_technical_review','items','has_more','financial_effect_applied',
 'bank_reconciled','membership_status_changed','closing_authorized',
 'payout_authorized',
];
export function parseReviewTimeline(
  raw:unknown,tenantId:string,requestId:string
):ReviewTimeline{
 if(!object(raw)||!uid.test(tenantId)||!uid.test(requestId)||
    raw.tenant_id!==tenantId||raw.request_id!==requestId||
    typeof raw.membership_id!=='string'||!uid.test(raw.membership_id)||
    !['VOLUNTARY_EXIT','DELINQUENCY_REVIEW'].includes(String(raw.request_kind))||
    raw.has_more!==false||raw.financial_effect_applied!==false||
    raw.bank_reconciled!==false||raw.membership_status_changed!==false||
    raw.closing_authorized!==false||raw.payout_authorized!==false||
    typeof raw.pending_technical_review!=='boolean'||
    !Array.isArray(raw.items)||raw.items.length>100||
    !sameKeys(raw,timelineKeys))
    throw Error('Trilha de revisão inválida ou não autorizada');
 const items=raw.items.map(i=>parseReviewEvent(i,tenantId,requestId));
 if(items.some((v,i)=>v.membership_id!==raw.membership_id||
        (i>0&&v.event_seq<=items[i-1].event_seq))||
    new Set(items.map(v=>v.event_id)).size!==items.length)
    throw Error('Sequência de eventos inconsistente');
 const last=items.length?items[items.length-1].event_kind:null;
 const pending=!last||![
   'ADMIN_REVIEW_ACCEPTED_SANDBOX','ADMIN_REVIEW_REJECTED_SANDBOX'
 ].includes(last);
 if(raw.latest_event_kind!==last||raw.pending_technical_review!==pending)
    throw Error('Estado de revisão não confere com eventos');
 return {
   tenant_id:tenantId,request_id:requestId,
   membership_id:raw.membership_id as string,
   request_kind:raw.request_kind as ReviewTimeline['request_kind'],
   latest_event_kind:last,pending_technical_review:pending,
   items,has_more:false,financial_effect_applied:false,
   bank_reconciled:false,membership_status_changed:false,
   closing_authorized:false,payout_authorized:false,
 };
}
