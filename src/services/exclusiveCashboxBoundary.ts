/** M39090: fail-closed parsing for two distinct READ-ONLY cashboxes.
 * No field may claim a bank-reconciled balance or a transferable amount.
 */
export interface MasterExclusiveCashbox {
  source:'POSTGRESQL_RLS';
  scope:'MASTER_PLATFORM_SAAS_ONLY';
  tenant_id:null;
  cashbox:'PLATFORM_SAAS';
  payment_intents_count:number;
  subscription_preparations_count:number;
  settled_balance_cents:null;
  bank_reconciled:false;
  transfer_enabled:false;
  real_payments_enabled:false;
  status:'AWAITING_PROVIDER_RECONCILIATION';
}
export interface TenantAdminExclusiveCashbox {
  source:'POSTGRESQL_RLS';
  scope:'TENANT_ADMIN_OWN_REMUNERATION_ONLY';
  tenant_id:string;
  cashbox:'TENANT_ADMIN_REMUNERATION';
  ledger_transactions_count:number;
  administrator_profit_share_pct:'15.00';
  members_profit_share_pct:'85.00';
  settled_balance_cents:null;
  bank_reconciled:false;
  closing_authorized:false;
  transfer_enabled:false;
  real_payments_enabled:false;
  status:'AWAITING_CLOSING_AND_RECONCILIATION';
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const masterFields=[
  'source','scope','tenant_id','cashbox','payment_intents_count',
  'subscription_preparations_count','settled_balance_cents',
  'bank_reconciled','transfer_enabled','real_payments_enabled','status',
];
const adminFields=[
  'source','scope','tenant_id','cashbox','ledger_transactions_count',
  'administrator_profit_share_pct','members_profit_share_pct',
  'settled_balance_cents','bank_reconciled','closing_authorized',
  'transfer_enabled','real_payments_enabled','status',
];
function record(value:unknown,fields:string[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value))
    throw Error('Caixa exclusivo: resposta inválida.');
  const obj=value as Record<string,unknown>;
  if(Object.keys(obj).some(k=>!fields.includes(k))||
      fields.some(k=>!(k in obj)))
    throw Error('Caixa exclusivo: campos inesperados ou ausentes.');
  if(obj.source!=='POSTGRESQL_RLS'||obj.settled_balance_cents!==null||
    obj.bank_reconciled!==false||obj.transfer_enabled!==false||
    obj.real_payments_enabled!==false)
    throw Error('Caixa exclusivo: conciliação financeira não comprovada.');
  return obj;
}
function count(value:unknown):boolean{
  return typeof value==='number'&&Number.isSafeInteger(value)&&
    value>=0&&value<=1000000000;
}
export function parseMasterExclusiveCashbox(value:unknown):MasterExclusiveCashbox{
  const r=record(value,masterFields);
  if(r.scope!=='MASTER_PLATFORM_SAAS_ONLY'||r.tenant_id!==null||
     r.cashbox!=='PLATFORM_SAAS'||r.status!=='AWAITING_PROVIDER_RECONCILIATION'||
     !count(r.payment_intents_count)||!count(r.subscription_preparations_count))
    throw Error('Caixa Master: origem financeira não validada.');
  return r as unknown as MasterExclusiveCashbox;
}
export function parseTenantAdminExclusiveCashbox(value:unknown,tenantId:string):TenantAdminExclusiveCashbox{
  if(!uuid.test(tenantId))throw Error('Caixa administrador: caixinha inválida.');
  const r=record(value,adminFields);
  if(r.scope!=='TENANT_ADMIN_OWN_REMUNERATION_ONLY'||
    typeof r.tenant_id!=='string'||!uuid.test(r.tenant_id)||
    r.tenant_id.toLowerCase()!==tenantId.toLowerCase()||
    r.cashbox!=='TENANT_ADMIN_REMUNERATION'||
    r.administrator_profit_share_pct!=='15.00'||r.members_profit_share_pct!=='85.00'||
    r.closing_authorized!==false||
    r.status!=='AWAITING_CLOSING_AND_RECONCILIATION'||
    !count(r.ledger_transactions_count))
    throw Error('Caixa administrador: escopo ou rateio inválidos.');
  return r as unknown as TenantAdminExclusiveCashbox;
}
