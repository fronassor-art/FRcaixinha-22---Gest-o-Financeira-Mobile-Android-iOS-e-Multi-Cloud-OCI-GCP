/** M531 — Dados REGISTRADOS do ciclo: jamais saldo conciliado, bloqueio ou rateio. */
export interface MemberCycleRiskPreview {
  source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED';
  scope:'SELF_READ_ONLY'|'TENANT_ADMIN_READ_ONLY';
  tenant_id:string;
  cycle_year:number;
  membership_id:string;
  as_of:string;
  owner_box:boolean;
  registered_contributions_count:number;
  registered_due_cents:number;
  registered_paid_cents:number;
  registered_open_cents:number;
  longest_registered_overdue_days:number;
  currently_unpaid_consecutive_months:number;
  potential_three_unpaid_trigger_date:string|null;
  membership_profit_eligible:null;
  reconciled_principal_cents:null;
  capital_days_weight:null;
  contractual_effect_applied:false;
  real_financial_operations_enabled:false;
  financial_closing_authorized:false;
  bank_reconciled:false;
  result_status:'HISTORY_AND_PROOF_NOT_ATTESTED';
}
const UUID=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const isoDay=/^\d{4}-\d{2}-\d{2}$/;
const object=(v:unknown):v is Record<string,unknown> =>
  !!v&&typeof v==='object'&&!Array.isArray(v);
function cents(value:unknown):number{
  if(typeof value!=='number'||!Number.isSafeInteger(value)||
     value<0||value>999999999999)throw Error('Centavos registrados inválidos');
  return value;
}
function count(value:unknown,max=120):number{
  if(typeof value!=='number'||!Number.isSafeInteger(value)||
    value<0||value>max)throw Error('Contagem inválida no histórico');
  return value;
}
function dateString(v:unknown):v is string{
  if(typeof v!=='string'||!isoDay.test(v))return false;
  const d=new Date(v+'T00:00:00Z');
  return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===v;
}
const KEYS=new Set([
  'source','scope','tenant_id','cycle_year','membership_id','as_of','owner_box',
  'registered_contributions_count','registered_due_cents',
  'registered_paid_cents','registered_open_cents',
  'longest_registered_overdue_days','currently_unpaid_consecutive_months',
  'potential_three_unpaid_trigger_date','membership_profit_eligible',
  'reconciled_principal_cents','capital_days_weight',
  'contractual_effect_applied','real_financial_operations_enabled',
  'financial_closing_authorized','bank_reconciled','result_status'
]);

export function parseMemberCycleRiskPreview(
  raw:unknown,tenantId:string,year:number,role:'TENANT_ADMIN'|'TENANT_MEMBER',
  memberId?:string
):MemberCycleRiskPreview{
  const scope=role==='TENANT_MEMBER'?'SELF_READ_ONLY':'TENANT_ADMIN_READ_ONLY';
  if(!object(raw)||!UUID.test(tenantId)||raw.tenant_id!==tenantId||
    !UUID.test(String(raw.membership_id))||
    (memberId!==undefined&&raw.membership_id!==memberId)||
    raw.cycle_year!==year||!Number.isSafeInteger(year)||year<2020||year>2100||
    raw.source!=='POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED'||
    raw.scope!==scope||typeof raw.owner_box!=='boolean'||
    !dateString(raw.as_of)||
    (raw.potential_three_unpaid_trigger_date!==null&&
      !dateString(raw.potential_three_unpaid_trigger_date))||
    raw.membership_profit_eligible!==null||
    raw.reconciled_principal_cents!==null||raw.capital_days_weight!==null||
    raw.contractual_effect_applied!==false||
    raw.real_financial_operations_enabled!==false||
    raw.financial_closing_authorized!==false||
    raw.bank_reconciled!==false||
    raw.result_status!=='HISTORY_AND_PROOF_NOT_ATTESTED'||
    Object.keys(raw).length!==KEYS.size||
    Object.keys(raw).some(k=>!KEYS.has(k)))
    throw Error('Prévia de risco não homologada; dados descartados');
  const countRows=count(raw.registered_contributions_count);
  const due=cents(raw.registered_due_cents);
  const paid=cents(raw.registered_paid_cents);
  const open=cents(raw.registered_open_cents);
  const streak=count(raw.currently_unpaid_consecutive_months);
  const age=count(raw.longest_registered_overdue_days,36500);
  if(paid>due||open!==due-paid||streak>countRows||
      (countRows===0&&(due!==0||paid!==0||streak!==0||age!==0))||
      (raw.potential_three_unpaid_trigger_date!==null&&
       (raw.potential_three_unpaid_trigger_date as string) > (raw.as_of as string)))
    throw Error('Prévia inconsistente; sem autorização financeira');
  return {
    source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED',
    scope,tenant_id:tenantId,cycle_year:year,
    membership_id:raw.membership_id as string,
    as_of:raw.as_of as string,owner_box:raw.owner_box as boolean,
    registered_contributions_count:countRows,
    registered_due_cents:due,registered_paid_cents:paid,registered_open_cents:open,
    longest_registered_overdue_days:age,
    currently_unpaid_consecutive_months:streak,
    potential_three_unpaid_trigger_date:raw.potential_three_unpaid_trigger_date as string|null,
    membership_profit_eligible:null,reconciled_principal_cents:null,
    capital_days_weight:null,contractual_effect_applied:false,
    real_financial_operations_enabled:false,
    financial_closing_authorized:false,bank_reconciled:false,
    result_status:'HISTORY_AND_PROOF_NOT_ATTESTED'
  };
}
