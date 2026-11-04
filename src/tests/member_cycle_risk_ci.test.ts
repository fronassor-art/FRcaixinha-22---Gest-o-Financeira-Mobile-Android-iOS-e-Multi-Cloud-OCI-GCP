import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseMemberCycleRiskPreview} from '../services/memberCycleRiskBoundary';

const T='00000000-0000-4000-8000-0000000000a1';
const B='00000000-0000-4000-8000-0000000000b1';
const M='00000000-0000-4000-8000-0000000000a2';

const record={
  source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED',
  scope:'SELF_READ_ONLY',
  tenant_id:T,
  cycle_year:2027,
  membership_id:M,
  as_of:'2027-12-31',
  owner_box:true,
  registered_contributions_count:12,
  registered_due_cents:180000,
  registered_paid_cents:22500,
  registered_open_cents:157500,
  longest_registered_overdue_days:294,
  currently_unpaid_consecutive_months:10,
  potential_three_unpaid_trigger_date:'2027-04-11',
  membership_profit_eligible:null,
  reconciled_principal_cents:null,
  capital_days_weight:null,
  contractual_effect_applied:false,
  real_financial_operations_enabled:false,
  financial_closing_authorized:false,
  bank_reconciled:false,
  result_status:'HISTORY_AND_PROOF_NOT_ATTESTED',
};
const parsed=parseMemberCycleRiskPreview(record,T,2027,'TENANT_MEMBER');
assert.equal(parsed.registered_paid_cents,22500);
assert.equal(parsed.membership_profit_eligible,null);
assert.equal(parsed.contractual_effect_applied,false);
assert.equal(parsed.bank_reconciled,false);
const admin=parseMemberCycleRiskPreview({
  ...record,scope:'TENANT_ADMIN_READ_ONLY'
},T,2027,'TENANT_ADMIN',M);
assert.equal(admin.membership_id,M);

const invalid=[
  {...record,tenant_id:B},
  {...record,scope:'TENANT_ADMIN_READ_ONLY'},
  {...record,cycle_year:2028},
  {...record,bank_reconciled:true},
  {...record,financial_closing_authorized:true},
  {...record,real_financial_operations_enabled:true},
  {...record,contractual_effect_applied:true},
  {...record,reconciled_principal_cents:22500},
  {...record,capital_days_weight:'225.0000'},
  {...record,membership_profit_eligible:false},
  {...record,registered_paid_cents:180001},
  {...record,registered_paid_cents:-1},
  {...record,registered_paid_cents:22.50},
  {...record,registered_open_cents:1},
  {...record,registered_open_cents:157501},
  {...record,longest_registered_overdue_days:-1},
  {...record,currently_unpaid_consecutive_months:13},
  {...record,potential_three_unpaid_trigger_date:'2028-01-01'},
  {...record,potential_three_unpaid_trigger_date:'2027-02-30'},
  {...record,as_of:'2027-02-30'},
  {...record,source:'LOCAL_TEST_DATA'},
  {...record,registered_contributions_count:121},
  {...record,cpf:'00000000000'},
  {...record,security:'MASTER_ACCESS'},
  {...record,owner_box:1},
  {...record,result_status:'READY_FOR_PAYOUT'}
];
for(const example of invalid){
  assert.throws(()=>parseMemberCycleRiskPreview(example,T,2027,'TENANT_MEMBER'));
}
assert.throws(()=>parseMemberCycleRiskPreview(record,B,2027,'TENANT_MEMBER'));
assert.throws(()=>parseMemberCycleRiskPreview(record,T,2028,'TENANT_MEMBER'));
assert.throws(()=>parseMemberCycleRiskPreview(record,T,2027,'TENANT_ADMIN'));
assert.throws(()=>parseMemberCycleRiskPreview(record,T,2027,'TENANT_MEMBER',B));

const api=readFileSync('src/services/financialApiService.ts','utf8');
const app=readFileSync('src/components/MemberAnnualPreviewView.tsx','utf8');
const panel=readFileSync('src/components/MemberCycleRiskPanel.tsx','utf8');
assert.match(api,/fetchMemberCycleRiskPreview/);
assert.match(api,/parseMemberCycleRiskPreview/);
assert.match(api,/member-risk/);
assert.match(api,/assertTenantReadScope/);
assert.match(panel,/fetchTenantMembers/);
assert.match(panel,/fetchMemberCycleRiskPreview/);
assert.match(panel,/authService\.isSessionSnapshotCurrent/);
assert.match(panel,/Esta consulta não bloqueia direitos/);
assert.match(panel,/membership_profit_eligible/);
assert.match(panel,/financial_closing_authorized/);
assert.match(app,/<MemberCycleRiskPanel state=\{state\}\/>/);
assert.doesNotMatch(panel,/localStorage|closeCycle|payContribution|releaseLoan|settleCycle/);

console.log('M531_FRONTEND_RISCO_MEMBRO_ISOLADO=PASS; INVALID_SCENARIOS='+invalid.length);
