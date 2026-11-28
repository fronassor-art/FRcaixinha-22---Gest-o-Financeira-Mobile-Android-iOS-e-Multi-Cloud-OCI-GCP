/* M25600 — Master requirements list never enables privileged operations. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {LaunchReadinessPanel} from '../components/LaunchReadinessPanel';
import {parseLaunchReadiness} from '../services/launchReadiness';
import {isRoleTabAllowed} from '../services/roleScope';

const ids=Array.from({length:20},(_,i)=>'GATE_TEST_'+String(i).padStart(2,'0'));
const report={
  source:'REPOSITORY_AND_CONFIGURATION_DECLARATIONS',
  scope:'AI_STUDIO_MASTER_RELEASE_READINESS',
  mode:'READ_ONLY_NO_ACTIVATION',
  status:'BLOCKED',
  workstream:'AI_STUDIO',
  production_auth_config_syntax_valid:true,
  smtp_config_syntax_valid:true,
  public_https_origin_syntax_valid:true,
  config_valid_is_live_proof:false,
  real_invites_active:false,password_reset_active:false,
  real_pix_active:false,financial_closing_authorized:false,
  writes_performed:false,total_gates:20,unverified_gates:20,
  requirements:ids.map(id=>({
    id,category:'cadastro',status:'INTEGRATION_AND_ATTESTATION_REQUIRED',
    engineering_source_present:true,production_verified:false,
    required_evidence:'Confirmação por teste real independente em staging.',
  })),
};
assert.equal(parseLaunchReadiness(report).unverified_gates,20);
for(const changed of [
  {...report,status:'READY'},
  {...report,real_invites_active:true},
  {...report,password_reset_active:true},
  {...report,real_pix_active:true},
  {...report,financial_closing_authorized:true},
  {...report,config_valid_is_live_proof:true},
  {...report,unverified_gates:0},
  {...report,requirements:report.requirements.slice(0,10)},
  {...report,requirements:[...report.requirements.slice(0,19),
      {...report.requirements[19],production_verified:true}]},
]){
  assert.throws(()=>parseLaunchReadiness(changed));
}
assert.equal(isRoleTabAllowed('MASTER','ONBOARDING'),true);
assert.equal(isRoleTabAllowed('TENANT_ADMIN','ONBOARDING'),false);
const denied=renderToStaticMarkup(React.createElement(LaunchReadinessPanel,{
  state:{currentRole:'TENANT_ADMIN',currentUserId:'tester',currentTenantId:'t'} as any,
}));
assert.equal(denied,'');
const owner=renderToStaticMarkup(React.createElement(LaunchReadinessPanel,{
  state:{currentRole:'MASTER',currentUserId:'tester',currentTenantId:''} as any,
}));
assert.match(owner,/Mapa de conclusão e integrações/);
assert.match(owner,/nenhuma integração real|Nenhuma integração real|implementação de um módulo não equivale|implementação de um módulo/);
const panel=readFileSync('src/components/LaunchReadinessPanel.tsx','utf8');
const onboarding=readFileSync('src/components/MasterOnboardingView.tsx','utf8');
const api=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(panel,/financialApi\.fetchMasterLaunchReadiness/);
assert.match(onboarding,/LaunchReadinessPanel state=\{state\}/);
assert.match(api,/api\/v1\/master\/launch-readiness/);
assert.doesNotMatch(panel,/acceptInvitation|createInvitation|enablePix|turnOnProduction/);
console.log('M25600_MASTER_LAUNCH_READINESS_UI=PASS');
