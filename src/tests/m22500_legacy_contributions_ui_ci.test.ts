import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLegacyContributionReview} from '../services/legacyContributionReviewBoundary';
const t='00000000-0000-4000-8000-0000000000a1';
const c='00000000-0000-4000-8000-0000000000b1';
const valid={
 contract:'AI_STUDIO_M22400_LEGACY_CONTRIBUTION_REVIEW_V1',
 source:'POSTGRESQL_RLS_REGISTERED_HISTORY_ONLY',tenant_id:t,cycle_id:c,
 cycle_year:2027,minimum_new_quota_cents:15000,
 legacy_registered_contributions:12,legacy_due_cents:120000,
 legacy_paid_recorded_cents:0,legacy_open_recorded_cents:120000,
 groups:[{registered_amount_cents:10000,registered_paid_cents:0,
          recorded_status:'PENDENTE',registered_contributions:12,
          bank_settlement_verified:false}],
 historical_obligations_changed:false,price_adjustment_authorized:false,
 bank_reconciled:false,real_payment_enabled:false,
 requires_administrator_review:true,
};
assert.equal(parseLegacyContributionReview(valid,t,c).legacy_due_cents,120000);
for(const change of [
 {tenant_id:'another'},{cycle_id:'another'},{legacy_due_cents:1},
 {legacy_open_recorded_cents:0},{legacy_registered_contributions:10},
 {bank_reconciled:true},{price_adjustment_authorized:true},
 {historical_obligations_changed:true},{real_payment_enabled:true},
 {minimum_new_quota_cents:10000},
 {groups:[{...valid.groups[0],registered_amount_cents:15000}]},
 {groups:[{...valid.groups[0],bank_settlement_verified:true}]},
 {groups:[{...valid.groups[0],registered_contributions:2}]},
]){
 assert.throws(()=>parseLegacyContributionReview({...valid,...change},t,c));
}
const view=readFileSync('src/components/ContributionsView.tsx','utf8');
const service=readFileSync('src/services/financialApiService.ts','utf8');
for(const phrase of [
 'Auditar competências antigas (somente leitura)',
 'Histórico não conciliado com banco',
 'legacyReview.data.legacy_registered_contributions',
 'fetchLegacyContributionReview',
 "state.currentRole!=='TENANT_ADMIN'",
 'authService.isSessionSnapshotCurrent',
]){
 assert.ok(view.includes(phrase),'missing UI guard: '+phrase);
}
assert.ok(service.includes("user.role!=='TENANT_ADMIN'"));
assert.ok(service.includes('parseLegacyContributionReview(raw,tenantId,cycleId)'));
console.log('PASS M22500 admin legacy review UI, tenant isolation, strict numeric parser');
