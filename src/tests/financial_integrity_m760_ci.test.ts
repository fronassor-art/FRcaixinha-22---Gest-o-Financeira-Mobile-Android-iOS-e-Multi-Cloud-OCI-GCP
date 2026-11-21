import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseFinancialIntegrityPreview} from '../services/financialIntegrityBoundary';

const T='00000000-0000-4000-8000-0000000000a1';
const M='00000000-0000-4000-8000-0000000000a2';
const S='00000000-0000-4000-8000-0000000000a3';

const record={
 source:'POSTGRESQL_RLS_REGISTERED_NOT_BANK_RECONCILED',
 scope:'TENANT_ADMIN_READ_ONLY',
 tenant_id:T,cycle_id:M,year:2027,
 status:'REGISTERED_INTEGRITY_ONLY',findings:[],
 members_links:5,members_distinct:4,member_role_links:4,
 admin_role_links:1,quota_value_cents:15000,admin_percent:'15.00',
 member_percent:'85.00',registered_contributions:48,
 registered_due_cents:720000,registered_paid_cents:382500,
 registered_open_cents:337500,complete_count:25,partial_count:1,
 pending_count:22,ledger_transactions:26,balanced_transactions:26,
 ledger_dr_cents:382500,ledger_cr_cents:382500,
 linked_contributions:26,linked_payment_cents:382500,
 missing_ledger_count:0,incorrect_link_count:0,
 no_bank_evidence:true,bank_reconciled:false,cash_available_cents:null,
 member_profit_share_cents:null,master_saas_revenue_cents:null,
 closing_authorized:false,transfer_authorized:false
};
const good=parseFinancialIntegrityPreview(record,T,2027);
assert.equal(good.status,'REGISTERED_INTEGRITY_ONLY');
assert.equal(good.registered_paid_cents,382500);
assert.equal(good.registered_open_cents,337500);
assert.equal(good.members_links,5);
assert.equal(good.members_distinct,4);
assert.equal(good.bank_reconciled,false);
assert.equal(good.master_saas_revenue_cents,null);
assert.equal(good.cash_available_cents,null);

const invalid=[
 {...record,tenant_id:S},{...record,cycle_id:'fake'},
 {...record,year:2028},{...record,source:'LOCAL_SIMULATION'},
 {...record,scope:'MASTER_READ_ONLY'},
 {...record,cash_available_cents:382500},
 {...record,master_saas_revenue_cents:1000},
 {...record,member_profit_share_cents:8500},
 {...record,closing_authorized:true},
 {...record,transfer_authorized:true},
 {...record,no_bank_evidence:false},
 {...record,bank_reconciled:true},
 {...record,registered_paid_cents:999999},
 {...record,registered_paid_cents:-1},
 {...record,registered_paid_cents:0.5},
 {...record,registered_due_cents:'720000'},
 {...record,registered_open_cents:1},
 {...record,registered_contributions:12},
 {...record,complete_count:49},
 {...record,balanced_transactions:27},
 {...record,ledger_dr_cents:382501},
 {...record,member_role_links:7},
 {...record,members_distinct:6},
 {...record,missing_ledger_count:1},
 {...record,incorrect_link_count:1},
 {...record,status:'REVIEW_REQUIRED',findings:[]},
 {...record,findings:['UNEXPECTED'],status:'REGISTERED_INTEGRITY_ONLY'},
 {...record,findings:['INVALID<script>'],status:'REVIEW_REQUIRED'},
 {...record,unknown_secret:'LEAKED'},
 {...record,cpf:'00000000000'},
 {...record,quota_value_cents:1.5},
 {...record,admin_percent:'abc'},
 {...record,member_percent:'85,00'},
 {...record,findings:[...Array(41)].map(()=>'A'),status:'REVIEW_REQUIRED'},
];
for(const candidate of invalid){
  assert.throws(()=>parseFinancialIntegrityPreview(candidate,T,2027));
}
for(let n=0;n<180;n++){
  const updated={...record,registered_paid_cents:n,
    registered_open_cents:720000-n,
    ledger_transactions:n?1:0,balanced_transactions:n?1:0,
    ledger_dr_cents:n,ledger_cr_cents:n,
    linked_contributions:n?1:0,linked_payment_cents:n,
  };
  const v=parseFinancialIntegrityPreview(updated,T,2027);
  assert.equal(v.registered_due_cents-v.registered_paid_cents,
               v.registered_open_cents);
  assert.equal(v.cash_available_cents,null);
}
const api=readFileSync('src/services/financialApiService.ts','utf8');
const component=readFileSync('src/components/FinancialIntegrityPanel.tsx','utf8');
const annual=readFileSync('src/components/MemberAnnualPreviewView.tsx','utf8');
assert.match(api,/fetchTenantFinancialIntegrityPreview/);
assert.match(api,/financial-integrity\/preview/);
assert.match(api,/parseFinancialIntegrityPreview/);
assert.match(api,/assertTenantReadScope/);
assert.match(component,/authService\.isSessionSnapshotCurrent/);
assert.match(component,/Banco não conciliado/);
assert.match(component,/missing_ledger_count/);
assert.match(component,/incorrect_link_count/);
assert.match(annual,/<FinancialIntegrityPanel state=\{state\}\/>/);
assert.doesNotMatch(component,/localStorage|approveLoan|createPix|closeCycle/);
console.log('M601_FRONTEND_CROSS_LEDGER=PASS; MALFORMED='+invalid.length+
            '; CENT_VARIATIONS=180; BANK_RECONCILED=FALSE');
