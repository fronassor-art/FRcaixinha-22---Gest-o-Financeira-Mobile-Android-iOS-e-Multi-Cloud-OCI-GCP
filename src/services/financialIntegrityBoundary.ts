/** M601: auditoria cruzada registral, SEM prova bancária ou autorização. */
export interface FinancialIntegrityPreview {
  source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED';
  scope:'TENANT_ADMIN_READ_ONLY';
  tenant_id:string;
  cycle_id:string;
  year:number;
  status:'REGISTERED_INTEGRITY_ONLY'|'REVIEW_REQUIRED';
  findings:string[];
  members_links:number;
  members_distinct:number;
  member_role_links:number;
  admin_role_links:number;
  quota_value_cents:number|null;
  admin_percent:string|null;
  member_percent:string|null;
  registered_contributions:number;
  registered_due_cents:number;
  registered_paid_cents:number;
  registered_open_cents:number;
  complete_count:number;
  partial_count:number;
  pending_count:number;
  ledger_transactions:number;
  balanced_transactions:number;
  ledger_dr_cents:number;
  ledger_cr_cents:number;
  linked_contributions:number;
  linked_payment_cents:number;
  missing_ledger_count:number;
  incorrect_link_count:number;
  no_bank_evidence:true;
  bank_reconciled:false;
  cash_available_cents:null;
  member_profit_share_cents:null;
  master_saas_revenue_cents:null;
  closing_authorized:false;
  transfer_authorized:false;
}
const uuid=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const isRecord=(x:unknown):x is Record<string,unknown> =>
  x!==null&&typeof x==='object'&&!Array.isArray(x);
const FIELDS=new Set([
 'source','scope','tenant_id','cycle_id','year','status','findings',
 'members_links','members_distinct','member_role_links','admin_role_links',
 'quota_value_cents','admin_percent','member_percent',
 'registered_contributions','registered_due_cents','registered_paid_cents',
 'registered_open_cents','complete_count','partial_count','pending_count',
 'ledger_transactions','balanced_transactions','ledger_dr_cents','ledger_cr_cents',
 'linked_contributions','linked_payment_cents','missing_ledger_count',
 'incorrect_link_count','no_bank_evidence','bank_reconciled',
 'cash_available_cents','member_profit_share_cents','master_saas_revenue_cents',
 'closing_authorized','transfer_authorized',
]);
const numbers=[
 'members_links','members_distinct','member_role_links','admin_role_links',
 'registered_contributions','registered_due_cents','registered_paid_cents',
 'registered_open_cents','complete_count','partial_count','pending_count',
 'ledger_transactions','balanced_transactions','ledger_dr_cents','ledger_cr_cents',
 'linked_contributions','linked_payment_cents','missing_ledger_count',
 'incorrect_link_count',
] as const;
function safeInteger(value:unknown):value is number {
 return typeof value==='number'&&Number.isSafeInteger(value)&&
        value>=0&&value<=999999999999;
}
export function parseFinancialIntegrityPreview(
 raw:unknown,tenantId:string,year:number
):FinancialIntegrityPreview{
 if(!isRecord(raw)||!uuid.test(tenantId)||!uuid.test(String(raw.cycle_id))||
    raw.tenant_id!==tenantId||raw.year!==year||
    raw.source!=='POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED'||
    raw.scope!=='TENANT_ADMIN_READ_ONLY'||
    !['REGISTERED_INTEGRITY_ONLY','REVIEW_REQUIRED'].includes(String(raw.status))||
    raw.no_bank_evidence!==true||raw.bank_reconciled!==false||
    raw.cash_available_cents!==null||raw.member_profit_share_cents!==null||
    raw.master_saas_revenue_cents!==null||raw.closing_authorized!==false||
    raw.transfer_authorized!==false||
    Object.keys(raw).length!==FIELDS.size||Object.keys(raw).some(x=>!FIELDS.has(x))||
    !Array.isArray(raw.findings)||raw.findings.length>40||
    raw.findings.some(x=>typeof x!=='string'||!/^[A-Z0-9_]{3,72}$/.test(x))||
    !numbers.every(field=>safeInteger(raw[field]))||
    (raw.quota_value_cents!==null&&!safeInteger(raw.quota_value_cents))||
    (raw.admin_percent!==null&&
     (typeof raw.admin_percent!=='string'||!/^\d{1,3}\.\d{2}$/.test(raw.admin_percent)))||
    (raw.member_percent!==null&&
     (typeof raw.member_percent!=='string'||!/^\d{1,3}\.\d{2}$/.test(raw.member_percent))))
    throw Error('Auditoria financeira não autenticada ou inconsistente');
 const c=raw as unknown as FinancialIntegrityPreview;
 if(c.registered_paid_cents>c.registered_due_cents||
    c.registered_open_cents!==c.registered_due_cents-c.registered_paid_cents||
    c.members_distinct>c.members_links||
    c.member_role_links+c.admin_role_links!==c.members_links||
    c.balanced_transactions>c.ledger_transactions||
    c.linked_contributions>c.ledger_transactions||
    c.linked_contributions>c.registered_contributions||
    c.complete_count+c.partial_count+c.pending_count>c.registered_contributions||
    (c.status==='REGISTERED_INTEGRITY_ONLY'&&
      (c.findings.length!==0||c.ledger_dr_cents!==c.ledger_cr_cents||
       c.complete_count+c.partial_count+c.pending_count!==c.registered_contributions||
       c.missing_ledger_count!==0||c.incorrect_link_count!==0))||
    (c.status==='REVIEW_REQUIRED'&&c.findings.length===0))
    throw Error('Totais de auditoria divergentes, não apresentar como conciliação');
 return {
   source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED',
   scope:'TENANT_ADMIN_READ_ONLY',tenant_id:tenantId,cycle_id:c.cycle_id,
   year,status:c.status,findings:[...c.findings],
   members_links:c.members_links,members_distinct:c.members_distinct,
   member_role_links:c.member_role_links,admin_role_links:c.admin_role_links,
   quota_value_cents:c.quota_value_cents,admin_percent:c.admin_percent,
   member_percent:c.member_percent,
   registered_contributions:c.registered_contributions,
   registered_due_cents:c.registered_due_cents,
   registered_paid_cents:c.registered_paid_cents,
   registered_open_cents:c.registered_open_cents,
   complete_count:c.complete_count,partial_count:c.partial_count,
   pending_count:c.pending_count,ledger_transactions:c.ledger_transactions,
   balanced_transactions:c.balanced_transactions,
   ledger_dr_cents:c.ledger_dr_cents,ledger_cr_cents:c.ledger_cr_cents,
   linked_contributions:c.linked_contributions,
   linked_payment_cents:c.linked_payment_cents,
   missing_ledger_count:c.missing_ledger_count,
   incorrect_link_count:c.incorrect_link_count,
   no_bank_evidence:true,bank_reconciled:false,cash_available_cents:null,
   member_profit_share_cents:null,master_saas_revenue_cents:null,
   closing_authorized:false,transfer_authorized:false,
 };
}
