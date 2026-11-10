import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseMemberAnnualPreview} from '../services/memberAnnualPreview';

const T='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const record={
  source:'POSTGRESQL_RLS',tenant_id:T,year:2027,
  contribution_count:12,pending_count:12,
  total_due:'1800.00',amount_paid_recorded:'0.00',
  remaining_due:'1800.00',result_status:'PREVIA_NAO_E_LIQUIDACAO',
  profit_amount:null,
};
const view=parseMemberAnnualPreview(record,T,2027);
assert.equal(view.total_due,1800);
assert.equal(view.amount_paid_recorded,0);
assert.equal(view.remaining_due,1800);
assert.equal(view.profit_amount,null);
assert.equal(view.pending_count,12);
for(const invalid of [
 {...record,tenant_id:B},{...record,year:2026},
 {...record,total_due:'1200.00',remaining_due:'1200.00'},{...record,pending_count:13},
 {...record,total_due:'1200.001'}, {...record,remaining_due:'0.00'},
 {...record,amount_paid_recorded:'1200.01'},
 {...record,total_due:'-1'}, {...record,amount_paid_recorded:NaN},
 {...record,profit_amount:1},{...record,source:'LOCAL_SEED'},
 {...record,cpf:'restricted'}, {...record,admin_share:'100.00'},
 ])assert.throws(()=>parseMemberAnnualPreview(invalid,T,2027));
const component=readFileSync('src/components/MemberAnnualPreviewView.tsx','utf8');
const app=readFileSync('src/App.tsx','utf8');
assert.match(component,/fetchMemberAnnualPreview\(tenant,2027\)/);
assert.match(component,/result\.key===key/);
assert.match(component,/Lucro, rendimentos e rateio anual ainda não apurados/);
assert.match(app,/MemberAnnualPreviewView state=\{state\}/);
assert.doesNotMatch(component,/localStorage|closeCycle|payContribution|approveLoan/);
console.log('PACOTE_20_PREVIA_MEMBRO_POSTGRES_CI=PASS');
