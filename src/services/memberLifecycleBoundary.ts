/** Fila de ciclo — não altera status de membro, capital, lucros ou Pix. */
export interface LifecycleItem {
 id:string;
 tenant_id:string;
 cycle_id:string;
 membership_id:string;
 requested_by_user_id:string;
 request_kind:'VOLUNTARY_EXIT'|'DELINQUENCY_REVIEW';
 policy_reference:string;
 status:'PENDING_REVIEW';
 requested_at:string;
 latest_review_event:
    'ADMIN_DOCUMENTS_REQUESTED'|'ADMIN_REVIEW_ACCEPTED_SANDBOX'|
    'ADMIN_REVIEW_REJECTED_SANDBOX'|'MEMBER_CONTESTED'|null;
 technical_review_pending:boolean;
 sandbox_only:true;
 bank_reconciled:false;
 financial_effect_applied:false;
 member_status_changed:false;
 profit_rights_modified:false;
 payment_authorized:false;
}
export interface LifecycleQueue {
 tenant_id:string;year:number;
 scope:'SELF_READ_ONLY'|'TENANT_ADMIN_READ_ONLY';
 items:LifecycleItem[];has_more:false;
 bank_reconciled:false;financial_effect_applied:false;
}
const uuid=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const validDate=(v:unknown):v is string=>typeof v==='string'&&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(v)&&
    Number.isFinite(Date.parse(v));
const obj=(v:unknown):v is Record<string,unknown>=>
    v!==null&&typeof v==='object'&&!Array.isArray(v);
const ITEM=new Set([
 'id','tenant_id','cycle_id','membership_id','requested_by_user_id',
 'request_kind','policy_reference','status','requested_at',
 'latest_review_event','technical_review_pending',
 'sandbox_only','bank_reconciled','financial_effect_applied',
 'member_status_changed','profit_rights_modified','payment_authorized'
]);
const QUEUE=new Set([
 'tenant_id','year','scope','items','has_more','bank_reconciled',
 'financial_effect_applied'
]);
export function parseLifecycleItem(v:unknown,tenantId:string):LifecycleItem{
 if(!obj(v)||Object.keys(v).length!==ITEM.size||
    Object.keys(v).some(k=>!ITEM.has(k))||
    ![v.id,v.tenant_id,v.cycle_id,v.membership_id,v.requested_by_user_id]
      .every(x=>typeof x==='string'&&uuid.test(x))||
    v.tenant_id!==tenantId||
    !['VOLUNTARY_EXIT','DELINQUENCY_REVIEW'].includes(String(v.request_kind))||
    v.status!=='PENDING_REVIEW'||!validDate(v.requested_at)||
    !(v.latest_review_event===null||
      ['ADMIN_DOCUMENTS_REQUESTED','ADMIN_REVIEW_ACCEPTED_SANDBOX',
       'ADMIN_REVIEW_REJECTED_SANDBOX','MEMBER_CONTESTED']
       .includes(String(v.latest_review_event)))||
    typeof v.technical_review_pending!=='boolean'||
    v.technical_review_pending!== !(
      v.latest_review_event==='ADMIN_REVIEW_ACCEPTED_SANDBOX'||
      v.latest_review_event==='ADMIN_REVIEW_REJECTED_SANDBOX'
    )||
    typeof v.policy_reference!=='string'||
    !/^[A-Za-z0-9._:-]{8,120}$/.test(v.policy_reference)||
    v.sandbox_only!==true||v.bank_reconciled!==false||
    v.financial_effect_applied!==false||v.member_status_changed!==false||
    v.profit_rights_modified!==false||v.payment_authorized!==false)
      throw Error('Solicitação fora do contrato de homologação');
 return {
   id:v.id as string,tenant_id:tenantId,cycle_id:v.cycle_id as string,
   membership_id:v.membership_id as string,
   requested_by_user_id:v.requested_by_user_id as string,
   request_kind:v.request_kind as LifecycleItem['request_kind'],
   policy_reference:v.policy_reference as string,
   status:'PENDING_REVIEW',requested_at:v.requested_at as string,
   latest_review_event:v.latest_review_event as LifecycleItem['latest_review_event'],
   technical_review_pending:v.technical_review_pending as boolean,
   sandbox_only:true,bank_reconciled:false,financial_effect_applied:false,
   member_status_changed:false,profit_rights_modified:false,
   payment_authorized:false
 };
}
export function parseLifecycleQueue(
  v:unknown,tenantId:string,year:number,
  role:'TENANT_ADMIN'|'TENANT_MEMBER'
):LifecycleQueue{
 const scope=role==='TENANT_ADMIN'?'TENANT_ADMIN_READ_ONLY':'SELF_READ_ONLY';
 if(!obj(v)||!uuid.test(tenantId)||v.tenant_id!==tenantId||
    v.year!==year||!Number.isSafeInteger(year)||year<2020||year>2100||
    v.scope!==scope||v.has_more!==false||
    v.bank_reconciled!==false||v.financial_effect_applied!==false||
    !Array.isArray(v.items)||v.items.length>100||
    Object.keys(v).length!==QUEUE.size||
    Object.keys(v).some(k=>!QUEUE.has(k)))
    throw Error('Fila de ciclo fora do contrato autorizado');
 const items=v.items.map(item=>parseLifecycleItem(item,tenantId));
 if(new Set(items.map(x=>x.id)).size!==items.length)
    throw Error('Duplicação de solicitação');
 return {
   tenant_id:tenantId,year,scope,items,has_more:false,
   bank_reconciled:false,financial_effect_applied:false,
 };
}


/** Capability publicada APENAS pelo backend autenticado. */
export interface LifecycleCapabilities {
 tenant_id:string;
 year:number;
 role:'TENANT_MEMBER'|'TENANT_ADMIN';
 schema_ready:boolean;
 sandbox_only:true;
 can_submit_voluntary_exit:boolean;
 can_submit_delinquency_review:boolean;
 financial_effects_enabled:false;
 bank_reconciled:false;
 production_payments_enabled:false;
}
const CAP_FIELDS=new Set([
 'tenant_id','year','role','schema_ready','sandbox_only',
 'can_submit_voluntary_exit','can_submit_delinquency_review',
 'financial_effects_enabled','bank_reconciled','production_payments_enabled'
]);
export function parseLifecycleCapabilities(
 v:unknown,tenantId:string,year:number,role:'TENANT_MEMBER'|'TENANT_ADMIN'
):LifecycleCapabilities{
 if(!obj(v)||!uuid.test(tenantId)||v.tenant_id!==tenantId||
    v.year!==year||v.role!==role||
    typeof v.schema_ready!=='boolean'||
    typeof v.can_submit_voluntary_exit!=='boolean'||
    typeof v.can_submit_delinquency_review!=='boolean'||
    v.sandbox_only!==true||v.financial_effects_enabled!==false||
    v.bank_reconciled!==false||v.production_payments_enabled!==false||
    Object.keys(v).length!==CAP_FIELDS.size||
    Object.keys(v).some(x=>!CAP_FIELDS.has(x))||
    (!v.schema_ready&&(
      v.can_submit_voluntary_exit||v.can_submit_delinquency_review))||
    (role==='TENANT_ADMIN'&&v.can_submit_voluntary_exit)||
    (role==='TENANT_MEMBER'&&v.can_submit_delinquency_review))
    throw Error('Capacidade de homologação não é segura');
 return {
   tenant_id:tenantId,year,role,schema_ready:v.schema_ready as boolean,
   sandbox_only:true,
   can_submit_voluntary_exit:v.can_submit_voluntary_exit as boolean,
   can_submit_delinquency_review:v.can_submit_delinquency_review as boolean,
   financial_effects_enabled:false,bank_reconciled:false,
   production_payments_enabled:false
 };
}


/** Resumo de obrigações cadastradas; NÃO é autorização de fechamento. */
export interface LifecycleClosingGates {
 tenant_id:string;
 cycle_id:string;
 year:number;
 pending_voluntary_exits:number;
 pending_delinquency_reviews:number;
 registered_unsettled_contributions:number;
 unclosed_loans:number;
 status:'REVIEW_AND_BANK_EVIDENCE_REQUIRED';
 bank_reconciled:false;
 can_close_cycle:false;
 can_distribute_profit:false;
 real_payout_enabled:false;
}
const GATE_FIELDS=new Set([
 'tenant_id','cycle_id','year','pending_voluntary_exits',
 'pending_delinquency_reviews','registered_unsettled_contributions',
 'unclosed_loans','status','bank_reconciled',
 'can_close_cycle','can_distribute_profit','real_payout_enabled',
]);
export function parseLifecycleClosingGates(
 v:unknown,tenantId:string,year:number
):LifecycleClosingGates{
 if(!obj(v)||!uuid.test(tenantId)||v.tenant_id!==tenantId||
    !uuid.test(String(v.cycle_id))||v.year!==year||
    v.status!=='REVIEW_AND_BANK_EVIDENCE_REQUIRED'||
    v.bank_reconciled!==false||v.can_close_cycle!==false||
    v.can_distribute_profit!==false||v.real_payout_enabled!==false||
    Object.keys(v).length!==GATE_FIELDS.size||
    Object.keys(v).some(k=>!GATE_FIELDS.has(k))||
    !['pending_voluntary_exits','pending_delinquency_reviews',
       'registered_unsettled_contributions','unclosed_loans']
     .every(k=>typeof v[k]==='number'&&Number.isSafeInteger(v[k])&&
            (v[k] as number)>=0&&(v[k] as number)<=999999999))
    throw Error('Estado de fechamento inseguro: nenhuma autorização concedida');
 return {
   tenant_id:tenantId,cycle_id:v.cycle_id as string,year,
   pending_voluntary_exits:v.pending_voluntary_exits as number,
   pending_delinquency_reviews:v.pending_delinquency_reviews as number,
   registered_unsettled_contributions:v.registered_unsettled_contributions as number,
   unclosed_loans:v.unclosed_loans as number,
   status:'REVIEW_AND_BANK_EVIDENCE_REQUIRED',
   bank_reconciled:false,can_close_cycle:false,
   can_distribute_profit:false,real_payout_enabled:false
 };
}
