/** M38090-M38109: Master preflight replies must stay in the issuing context. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createMasterOnboardingFence} from '../services/masterOnboardingRequestFence';

const T1='00000000-0000-4000-8000-0000000000a1';
const T2='00000000-0000-4000-8000-0000000000b2';
const S1='00000000-0000-4000-8000-0000000000c3:MASTER:';
const S2='00000000-0000-4000-8000-0000000000d4:MASTER:';
const fence=createMasterOnboardingFence();
const first=fence.issue(S1,T1,1);
assert(fence.isCurrent(first,S1,T1,1));
assert(fence.isCurrent(first,S1,T1.toUpperCase(),1));
assert(!fence.isCurrent(first,S2,T1,1));
assert(!fence.isCurrent(first,S1,T2,1));
assert(!fence.isCurrent(first,S1,T1,2));
fence.cancel();
assert(!fence.isCurrent(first,S1,T1,1));
const next=fence.issue(S1,T1,1);
assert(fence.isCurrent(next,S1,T1,1));
assert(!fence.isCurrent(first,S1,T1,1));
const latest=fence.issue(S1,T2,1);
assert(!fence.isCurrent(next,S1,T1,1));
assert(fence.isCurrent(latest,S1,T2,1));
fence.cancel();
assert(!fence.isCurrent(latest,S1,T2,1));

for (const invalid of ['', '00000000-0000-0000-0000-000000000000', 'bad']) {
  if(invalid!=='00000000-0000-0000-0000-000000000000'){
    assert.throws(()=>fence.issue(S1,invalid,1));
  }
}
for (const bad of [-1,NaN,1.5,Infinity]) {
  assert.throws(()=>fence.issue(S1,T1,bad));
}
assert.throws(()=>fence.issue('',T1,1));
const allowed=fence.issue(S1,T1,0);
assert(fence.isCurrent(allowed,S1,T1,0));

const ui=readFileSync('src/components/MasterOnboardingView.tsx','utf8');
for (const snippet of [
  'authService.captureSession()',
  'authService.isSessionSnapshotCurrent(session)',
  'authService.subscribe(()=>',
  'fence.current.cancel()',
  'fence.current.issue(scope,requestTenant,session.generation)',
  'fence.current.isCurrent(ticket,scope,requestTenant,session.generation)',
  'if(current())setPreflight({ticket,data:check});',
  'if(ticket===null||current())setPending(false);',
  'fence.current.isCurrent(preflight.ticket,scope,tenantId.trim(),activeSession.generation)',
  'visiblePreflight.tenant.display_name',
  'visiblePreflight.self_approval_blocked',
  'invalidatePreflight();setTenantId(e.target.value)',
  'invalidatePreflight();setCandidateUserId(e.target.value)',
  'invalidatePreflight();setPurpose(e.target.value)',
  'Acesso restrito à governança Master.',
  'Pré-análise técnica sem criação de contas, convites ou mudanças de permissões.',
]){
  assert(ui.includes(snippet),'Missing Master preflight fence: '+snippet);
}
assert(!ui.includes('setPreflight(check)'));
assert(!/localStorage.setItem\(|acceptInvitation\(|registerNewUser\(/.test(ui));
console.log('M38109 MASTER_SCOPE_SESSION_FORM_REQUEST_FENCE=PASS_OFFLINE');
