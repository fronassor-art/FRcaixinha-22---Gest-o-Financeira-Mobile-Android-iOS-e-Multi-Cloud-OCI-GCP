/* Verifica escopo e proteção fail-closed no cliente de pré-análise. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MasterOnboardingView} from '../components/MasterOnboardingView';
import {
  parseOnboardingCapabilities,parseOnboardingPreflight,
  REQUIRED_GATES,ONBOARDING_FLOW_STATES,validatePreflightInput,
} from '../services/masterOnboarding';
import {isRoleTabAllowed} from '../services/roleScope';
assert.equal(isRoleTabAllowed('MASTER','ONBOARDING'),true);
assert.equal(isRoleTabAllowed('TENANT_ADMIN','ONBOARDING'),false);
assert.equal(isRoleTabAllowed('TENANT_MEMBER','ONBOARDING'),false);
const source=readFileSync('src/App.tsx','utf8');
assert.match(source,/visibleTab === 'ONBOARDING' && state.currentRole === 'MASTER'/);
const api=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(api,/admin-onboarding\/capabilities/);
assert.match(api,/admin-onboarding\/preflight/);
const admin=renderToStaticMarkup(React.createElement(MasterOnboardingView,{
  state:{currentRole:'TENANT_ADMIN',currentUserId:'synthetic',currentTenantId:'ci'} as any,
}));
assert.match(admin,/Acesso restrito/);
assert.doesNotMatch(admin,/UUID da caixinha/);
const owner=renderToStaticMarkup(React.createElement(MasterOnboardingView,{
  state:{currentRole:'MASTER',currentUserId:'synthetic',currentTenantId:null} as any,
}));
assert.match(owner,/Preparação de administradores/);
assert.match(owner,/execução real bloqueada/);
assert.doesNotMatch(owner,/Criar convite|Aprovar administrador/);
const gates=Object.fromEntries(REQUIRED_GATES.map(x=>[x,'BLOCKED']));
const capabilities={
  scope:'MASTER_ADMIN_ONBOARDING_PREPARATION',mode:'READ_ONLY_PREFLIGHT',
  operations_enabled:false,real_invites_enabled:false,
  real_account_changes_enabled:false,workflow_states:[...ONBOARDING_FLOW_STATES],
  gates,next_action:'REQUIRES_SEPARATE_SCHEMA_RLS_AND_SECURITY_APPROVAL',
};
assert.equal(parseOnboardingCapabilities(capabilities).operations_enabled,false);
assert.throws(()=>parseOnboardingCapabilities({...capabilities,operations_enabled:true}));
assert.throws(()=>parseOnboardingCapabilities({...capabilities,gates:{...gates,MASTER_MFA:'READY'}}));
const id='00000000-0000-4000-8000-000000000001';
validatePreflightInput({tenantId:id,purpose:'Justificativa técnica sintética'});
assert.throws(()=>validatePreflightInput({tenantId:'invalid',purpose:'Justificativa técnica sintética'}));
assert.throws(()=>validatePreflightInput({tenantId:id,purpose:'short'}));
const preflight={
  source:'POSTGRESQL_RLS',scope:'MASTER_ADMIN_ONBOARDING_PREFLIGHT',
  result:'BLOCKED_PREPARATION_ONLY',tenant:{
    id,display_name:'Caixinha CI',status:'ATIVO',is_owner_box:false,
  },target_role:'TENANT_ADMIN',candidate_reference_present:false,
  candidate_identity_verified:false,tenant_active:true,
  self_approval_blocked:false,
  blocking_reasons:REQUIRED_GATES.map(x=>'GATE_'+x+'_BLOCKED').concat(['CANDIDATE_NOT_PROVIDED']),
  writes_performed:false,invitation_created:false,
  approval_granted:false,real_account_changed:false,
};
assert.equal(parseOnboardingPreflight(preflight).invitation_created,false);
assert.throws(()=>parseOnboardingPreflight({...preflight,approval_granted:true}));
assert.throws(()=>parseOnboardingPreflight({...preflight,blocking_reasons:[]}));
assert.throws(()=>parseOnboardingPreflight({...preflight,tenant:{...preflight.tenant,status:'SUSPENSO'}}));
console.log('MASTER_ONBOARDING_PREFLIGHT_UI=PASS');
