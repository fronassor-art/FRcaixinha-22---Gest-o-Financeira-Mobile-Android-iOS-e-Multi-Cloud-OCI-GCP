import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {classifyCyclePolicyLoadFailure} from '../services/cyclePolicyLoadBoundary';
import {FinancialApiHttpError,FinancialBackendUnavailableError,SessionBoundaryError} from '../services/financialApiService';

const empty=classifyCyclePolicyLoadFailure(new FinancialApiHttpError('no active cycle',404));
assert.equal(empty.kind,'empty');
assert.match(empty.message,/Nenhum ciclo aberto nesta caixinha/);
for(const [status,expected] of [[401,'blocked'],[403,'blocked'],[409,'blocked'],
 [500,'unavailable'],[503,'unavailable'],[422,'unavailable']] as const){
 const result=classifyCyclePolicyLoadFailure(new FinancialApiHttpError('synthetic',status));
 assert.equal(result.kind,expected);
 assert.notEqual(result.kind,'empty');
}
for(const err of [
 new FinancialBackendUnavailableError('network offline'),
 new SessionBoundaryError('session changed','SESSION_CHANGED_DURING_REQUEST'),
 new Error('invalid payload')
])assert.notEqual(classifyCyclePolicyLoadFailure(err).kind,'empty');

const ui=readFileSync('src/components/ContributionsView.tsx','utf8');
const api=readFileSync('backend/app/routers/cycle_contribution_price.py','utf8');
assert(api.includes('HTTPException(404,"Ciclo aberto com política ativa não encontrado.")'));
for(const token of [
 "classifyCyclePolicyLoadFailure(failure)",
 "empty:outcome.kind==='empty'",
 'cyclePrice.empty && <p role="status"',
 '!cyclePrice.empty && cyclePrice.error && <p role="alert"',
 'CycleOpeningPreviewPanel key={key}',
 'state.currentRole,state.currentTenantId,revision'
])assert(ui.includes(token),token);
assert(!ui.includes('Ciclo de teste com valor não homologado'));
console.log('M37449_NO_CYCLE_404_AND_SECURITY_FAILURES=PASS');
