import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseMemberObligations} from '../services/memberObligationsBoundary';

const T='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const M='00000000-0000-4000-8000-000000000003';
const C='00000000-0000-4000-8000-000000000004';
const record={
 tenant_id:T,cycle_id:C,membership_id:M,cycle_year:2027,
 as_of:'2027-03-11',
 source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED',
 scope:'SELF_READ_ONLY',
 contribution_count:12,
 contribution_due_cents:180000,
 contribution_paid_recorded_cents:22500,
 contribution_open_cents:157500,
 contribution_now_open_cents:22500,
 contribution_overdue_count:2,
 loan_proposal_count:1,loan_active_count:0,loan_closed_count:0,
 loan_unscheduled_count:0,installment_count:5,
 loan_now_principal_cents:0,loan_now_interest_cents:0,
 loan_future_principal_cents:0,loan_future_interest_cents:0,
 loan_overdue_installment_count:0,registered_now_open_cents:22500,
 status:'REGISTERED_ONLY_NOT_RECONCILED',
 bank_reconciled:false,capital_reconciled_cents:null,
 net_exit_restitution_cents:null,accrued_mora_cents:null,
 accrued_fine_cents:null,profit_eligible:null,
 sanction_applied:false,closing_authorized:false,
 payout_authorized:false
};
const r=parseMemberObligations(record,T,2027,'TENANT_MEMBER');
assert.equal(r.contribution_open_cents,157500);
assert.equal(r.loan_proposal_count,1);
assert.equal(r.loan_now_principal_cents,0);
assert.equal(r.net_exit_restitution_cents,null);
assert.equal(r.profit_eligible,null);
assert.equal(r.payout_authorized,false);

const admin={...record,scope:'TENANT_ADMIN_READ_ONLY'};
assert.equal(parseMemberObligations(admin,T,2027,'TENANT_ADMIN',M).scope,
 'TENANT_ADMIN_READ_ONLY');
const malformed=[
 {...record,tenant_id:B},
 {...record,cycle_id:'NOT_UUID'},
 {...record,membership_id:B},
 {...record,cycle_year:2028},
 {...record,as_of:'2027-02-31'},
 {...record,source:'BANK_RECONCILED'},
 {...record,scope:'MASTER_READ_ONLY'},
 {...record,status:'FINANCIAL_RESTITUTION_ALLOWED'},
 {...record,bank_reconciled:true},
 {...record,capital_reconciled_cents:15000},
 {...record,net_exit_restitution_cents:10000},
 {...record,accrued_mora_cents:350},
 {...record,accrued_fine_cents:1000},
 {...record,profit_eligible:true},
 {...record,sanction_applied:true},
 {...record,closing_authorized:true},
 {...record,payout_authorized:true},
 {...record,contribution_open_cents:1},
 {...record,contribution_paid_recorded_cents:200000},
 {...record,contribution_now_open_cents:180000},
 {...record,contribution_count:11,contribution_overdue_count:12},
 {...record,registered_now_open_cents:22501},
 {...record,loan_unscheduled_count:1},
 {...record,loan_overdue_installment_count:6},
 {...record,loan_now_principal_cents:'8000'},
 {...record,loan_future_interest_cents:1.5},
 {...record,contribution_due_cents:-1},
 {...record,registered_now_open_cents:9999999999999},
 {...record,unknown_token:'secret'},
 {...record,cpf:'00000000000'},
];
for(const item of malformed)assert.throws(()=>
 parseMemberObligations(item,T,2027,'TENANT_MEMBER'));

for(let n=0;n<260;n++){
 const due=180000;
 const paid=n;
 const upcoming=60000;
 const open=due-paid;
 const now=Math.min(open,n*2);
 const principal=n%13;
 const interest=n%7;
 const rr={...record,contribution_paid_recorded_cents:paid,
  contribution_open_cents:open,contribution_now_open_cents:now,
  loan_active_count:n%2,loan_proposal_count:1,
  loan_now_principal_cents:principal,loan_now_interest_cents:interest,
  registered_now_open_cents:now+principal+interest,
  loan_future_principal_cents:upcoming,
 };
 const out=parseMemberObligations(rr,T,2027,'TENANT_MEMBER');
 assert.equal(out.registered_now_open_cents,
  out.contribution_now_open_cents+out.loan_now_principal_cents+
  out.loan_now_interest_cents);
 assert.equal(out.net_exit_restitution_cents,null);
 assert.equal(out.payout_authorized,false);
}
const api=readFileSync('src/services/financialApiService.ts','utf8');
const panel=readFileSync('src/components/MemberObligationsPanel.tsx','utf8');
const view=readFileSync('src/components/MemberAnnualPreviewView.tsx','utf8');
assert.match(api,/fetchMemberObligationsPreview/);
assert.match(api,/parseMemberObligations/);
assert.match(api,/assertTenantReadScope/);
assert.match(api,/\/member-obligations/);
assert.match(panel,/authService\.isSessionSnapshotCurrent/);
assert.match(panel,/Uma proposta\s+de empréstimo não é dívida/);
assert.match(panel,/Nenhum débito pode ser compensado/);
assert.match(panel,/loan_future_interest_cents/);
assert.match(panel,/loan_unscheduled_count/);
assert.match(view,/<MemberObligationsPanel state=\{state\}\/>/);
assert.doesNotMatch(panel,/localStorage|closeCycle|createPix|disburseLoan/);
console.log('M1401_MEMBER_OBLIGATIONS_UI=PASS; MALFORMED='+
  malformed.length+'; EXACT_CENT_SCENARIOS=260; REAL_PAYOUT=OFF');
