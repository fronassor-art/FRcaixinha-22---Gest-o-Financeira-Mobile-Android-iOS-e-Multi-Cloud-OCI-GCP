/** FR Caixinha AI Studio M1401: obrigações CADASTRAIS, nunca liquidação. */
export interface MemberObligationsPreview {
  tenant_id:string;
  cycle_id:string;
  membership_id:string;
  cycle_year:number;
  as_of:string;
  source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED';
  scope:'SELF_READ_ONLY'|'TENANT_ADMIN_READ_ONLY';
  contribution_count:number;
  contribution_due_cents:number;
  contribution_paid_recorded_cents:number;
  contribution_open_cents:number;
  contribution_now_open_cents:number;
  contribution_overdue_count:number;
  loan_proposal_count:number;
  loan_active_count:number;
  loan_closed_count:number;
  loan_unscheduled_count:number;
  installment_count:number;
  loan_now_principal_cents:number;
  loan_now_interest_cents:number;
  loan_future_principal_cents:number;
  loan_future_interest_cents:number;
  loan_overdue_installment_count:number;
  registered_now_open_cents:number;
  status:'REGISTERED_ONLY_NOT_RECONCILED'|'INCOMPLETE_REGISTERED_LOAN_SCHEDULE';
  bank_reconciled:false;
  capital_reconciled_cents:null;
  net_exit_restitution_cents:null;
  accrued_mora_cents:null;
  accrued_fine_cents:null;
  profit_eligible:null;
  sanction_applied:false;
  closing_authorized:false;
  payout_authorized:false;
}

const uid=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const isRecord=(x:unknown):x is Record<string,unknown>=>
 x!==null&&typeof x==='object'&&!Array.isArray(x);
const day=(value:unknown):value is string=>{
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;
 const parsed=new Date(value+'T00:00:00Z');
 return Number.isFinite(parsed.getTime())&&
        parsed.toISOString().slice(0,10)===value;
};
const totals=[
 'contribution_due_cents','contribution_paid_recorded_cents',
 'contribution_open_cents','contribution_now_open_cents',
 'loan_now_principal_cents','loan_now_interest_cents',
 'loan_future_principal_cents','loan_future_interest_cents',
 'registered_now_open_cents'
] as const;
const counts=[
 'contribution_count','contribution_overdue_count',
 'loan_proposal_count','loan_active_count','loan_closed_count',
 'loan_unscheduled_count','installment_count','loan_overdue_installment_count'
] as const;
const allKeys=new Set([
 'tenant_id','cycle_id','membership_id','cycle_year','as_of',
 'source','scope',...totals,...counts,'status','bank_reconciled',
 'capital_reconciled_cents','net_exit_restitution_cents',
 'accrued_mora_cents','accrued_fine_cents','profit_eligible',
 'sanction_applied','closing_authorized','payout_authorized'
]);
export function parseMemberObligations(
 raw:unknown,tenantId:string,year:number,
 role:'TENANT_MEMBER'|'TENANT_ADMIN',memberId?:string
):MemberObligationsPreview{
 const scope=role==='TENANT_MEMBER'?'SELF_READ_ONLY':'TENANT_ADMIN_READ_ONLY';
 if(!isRecord(raw)||!uid.test(tenantId)||raw.tenant_id!==tenantId||
   !uid.test(String(raw.cycle_id))||!uid.test(String(raw.membership_id))||
   (memberId!==undefined&&raw.membership_id!==memberId)||
   raw.cycle_year!==year||!Number.isSafeInteger(year)||year<2020||year>2100||
   !day(raw.as_of)||raw.source!=='POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED'||
   raw.scope!==scope||
   !['REGISTERED_ONLY_NOT_RECONCILED','INCOMPLETE_REGISTERED_LOAN_SCHEDULE']
     .includes(String(raw.status))||
   raw.bank_reconciled!==false||
   raw.capital_reconciled_cents!==null||
   raw.net_exit_restitution_cents!==null||
   raw.accrued_mora_cents!==null||raw.accrued_fine_cents!==null||
   raw.profit_eligible!==null||
   raw.sanction_applied!==false||raw.closing_authorized!==false||
   raw.payout_authorized!==false||
   Object.keys(raw).length!==allKeys.size||
   Object.keys(raw).some(key=>!allKeys.has(key))||
   !totals.every(k=>typeof raw[k]==='number'&&Number.isSafeInteger(raw[k])&&
      (raw[k] as number)>=0&&(raw[k] as number)<=999999999999)||
   !counts.every(k=>typeof raw[k]==='number'&&Number.isSafeInteger(raw[k])&&
      (raw[k] as number)>=0&&(raw[k] as number)<=500))
   throw Error('Prévia de obrigações não homologada ou com privilégio financeiro');
 const r=raw as unknown as MemberObligationsPreview;
 if((r.contribution_count>0&&r.contribution_due_cents<r.contribution_count*15000)||
    r.contribution_paid_recorded_cents>r.contribution_due_cents||
    r.contribution_open_cents!==r.contribution_due_cents-r.contribution_paid_recorded_cents||
    r.contribution_now_open_cents>r.contribution_open_cents||
    r.contribution_overdue_count>r.contribution_count||
    r.loan_unscheduled_count>r.loan_active_count||
    r.loan_overdue_installment_count>r.installment_count||
    r.registered_now_open_cents!==
      r.contribution_now_open_cents+r.loan_now_principal_cents+
      r.loan_now_interest_cents||
    (r.status==='INCOMPLETE_REGISTERED_LOAN_SCHEDULE'&&r.loan_unscheduled_count===0)||
    (r.status==='REGISTERED_ONLY_NOT_RECONCILED'&&r.loan_unscheduled_count!==0))
    throw Error('Totais cadastrais divergentes; restituição não pode ser calculada');
 return {
   tenant_id:tenantId,cycle_id:r.cycle_id,membership_id:r.membership_id,
   cycle_year:year,as_of:r.as_of,source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED',
   scope,contribution_count:r.contribution_count,
   contribution_due_cents:r.contribution_due_cents,
   contribution_paid_recorded_cents:r.contribution_paid_recorded_cents,
   contribution_open_cents:r.contribution_open_cents,
   contribution_now_open_cents:r.contribution_now_open_cents,
   contribution_overdue_count:r.contribution_overdue_count,
   loan_proposal_count:r.loan_proposal_count,
   loan_active_count:r.loan_active_count,
   loan_closed_count:r.loan_closed_count,
   loan_unscheduled_count:r.loan_unscheduled_count,
   installment_count:r.installment_count,
   loan_now_principal_cents:r.loan_now_principal_cents,
   loan_now_interest_cents:r.loan_now_interest_cents,
   loan_future_principal_cents:r.loan_future_principal_cents,
   loan_future_interest_cents:r.loan_future_interest_cents,
   loan_overdue_installment_count:r.loan_overdue_installment_count,
   registered_now_open_cents:r.registered_now_open_cents,
   status:r.status,bank_reconciled:false,capital_reconciled_cents:null,
   net_exit_restitution_cents:null,accrued_mora_cents:null,
   accrued_fine_cents:null,profit_eligible:null,
   sanction_applied:false,closing_authorized:false,payout_authorized:false,
 };
}
