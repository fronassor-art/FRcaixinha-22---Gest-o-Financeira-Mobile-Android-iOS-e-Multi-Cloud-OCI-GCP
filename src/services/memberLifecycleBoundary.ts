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
