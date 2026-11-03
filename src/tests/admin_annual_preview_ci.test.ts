import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseMemberAnnualPreview} from '../services/memberAnnualPreview';

const T='00000000-0000-4000-8000-000000000001';
const normal={source:'POSTGRESQL_RLS',tenant_id:T,year:2027,
 contribution_count:12,pending_count:12,total_due:'1200.00',
 amount_paid_recorded:'0.00',remaining_due:'1200.00',
 result_status:'PREVIA_NAO_E_LIQUIDACAO',profit_amount:null};
const parsed=parseMemberAnnualPreview(normal,T,2027);
assert.equal(parsed.remaining_due,1200);
assert.equal(parsed.profit_amount,null);
for(const corrupt of [
 {...normal,tenant_id:'00000000-0000-4000-8000-000000000002'},
 {...normal,profit_amount:'10.00'},
 {...normal,total_due:'1200.001'},
 {...normal,remaining_due:'0.00'},
 {...normal,member_pool:'100.00'},
])assert.throws(()=>parseMemberAnnualPreview(corrupt,T,2027));
const api=readFileSync('src/services/financialApiService.ts','utf8');
const app=readFileSync('src/App.tsx','utf8');
const view=readFileSync('src/components/MemberAnnualPreviewView.tsx','utf8');
const backend=readFileSync('backend/app/routers/contributions.py','utf8');
assert.match(api,/fetchAdminAnnualPreview\(tenantId:string,year=2027\)/);
assert.match(api,/role!=='TENANT_ADMIN'/);
assert.match(api,/annual-preview\/admin\?year=/);
assert.match(app,/visibleTab === 'FECHAMENTO' && state.currentRole === 'TENANT_ADMIN'/);
assert.match(app,/MemberAnnualPreviewView state=\{state\}/);
assert.match(view,/fetchAdminAnnualPreview\(tenant,2027\)/);
assert.match(view,/fetchMemberAnnualPreview\(tenant,2027\)/);
assert.match(view,/result\.key===key/);
assert.match(view,/Nenhuma transferência foi executada por esta consulta/);
assert.doesNotMatch(view,/closeCycle\(|payContribution\(|localStorage/);
const route=backend.slice(backend.indexOf('async def get_admin_annual_preview'),
backend.indexOf('@router.post("/contributions/{contribution_id}/pay"'));
assert.match(route,/session.role != "TENANT_ADMIN"/);
assert.match(route,/require_tenant_access\(tenant_id, session\)/);
assert.match(route,/profit_amount=None/);
assert.doesNotMatch(route,/\b(INSERT|UPDATE|DELETE|GRANT|TRUNCATE)\b/i);
console.log('PACOTE_22_ADMIN_PREVIA_APK_190_CI=PASS');
