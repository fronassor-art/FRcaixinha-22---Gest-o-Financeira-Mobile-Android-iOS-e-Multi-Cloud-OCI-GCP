/** Prévia contábil, sem autorização de pagamento ou conciliação bancária. */
export type LedgerIntegrityPreview={
  source:'POSTGRESQL_RLS';
  scope:'TENANT_ADMIN_READ_ONLY';
  tenant_id:string;
  checked_transactions:number;
  balanced_transactions:number;
  review_required_transactions:number;
  status:'BALANCED'|'REVIEW_REQUIRED'|'NO_TRANSACTIONS';
  bank_reconciled:false;
  financial_closing_authorized:false;
};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const fields=new Set(['source','scope','tenant_id','checked_transactions',
  'balanced_transactions','review_required_transactions','status',
  'bank_reconciled','financial_closing_authorized']);
const record=(v:unknown):v is Record<string,unknown>=>
  v!==null&&typeof v==='object'&&!Array.isArray(v);
const count=(v:unknown):v is number=>
  typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<=500;
export function parseLedgerIntegrityPreview(raw:unknown,tenantId:string):LedgerIntegrityPreview{
  if(!uuid.test(tenantId)||!record(raw)||
    Object.keys(raw).some(k=>!fields.has(k))||
    raw.source!=='POSTGRESQL_RLS'||raw.scope!=='TENANT_ADMIN_READ_ONLY'||
    raw.tenant_id!==tenantId||
    !count(raw.checked_transactions)||!count(raw.balanced_transactions)||
    !count(raw.review_required_transactions)||
    raw.checked_transactions!==raw.balanced_transactions+raw.review_required_transactions||
    raw.bank_reconciled!==false||raw.financial_closing_authorized!==false)
    throw Error('Prévia contábil sem origem ou integridade comprovada.');
  const status=raw.checked_transactions===0?'NO_TRANSACTIONS':
    raw.review_required_transactions>0?'REVIEW_REQUIRED':'BALANCED';
  if(raw.status!==status)throw Error('Status de integridade contábil inconsistente.');
  return {
    source:'POSTGRESQL_RLS',scope:'TENANT_ADMIN_READ_ONLY',tenant_id:tenantId,
    checked_transactions:raw.checked_transactions,
    balanced_transactions:raw.balanced_transactions,
    review_required_transactions:raw.review_required_transactions,
    status,
    bank_reconciled:false,financial_closing_authorized:false
  };
}
