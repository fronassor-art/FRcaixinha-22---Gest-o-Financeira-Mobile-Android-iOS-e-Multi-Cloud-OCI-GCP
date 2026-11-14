/* Contrato de simulação, nunca implantação de convites ou auditoria. */
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readFileSync} from 'node:fs';
import {MasterWorkflowAuditView} from '../components/MasterWorkflowAuditView';
import {
  WORKFLOW_STATES,parseWorkflowContract,parseWorkflowPreview,
  validateWorkflowPreviewRequest,
} from '../services/masterWorkflow';
const denied=renderToStaticMarkup(React.createElement(MasterWorkflowAuditView,{
  state:{currentRole:'TENANT_MEMBER',currentUserId:'ci',currentTenantId:'ci'} as any,
}));
assert.match(denied,/Simulação exclusiva do Master/);
assert.doesNotMatch(denied,/Simular transição sem executar/);
const owner=renderToStaticMarkup(React.createElement(MasterWorkflowAuditView,{
  state:{currentRole:'MASTER',currentUserId:'ci',currentTenantId:null} as any,
}));
assert.match(owner,/Simulador de fluxo e auditoria/);
assert.match(owner,/Nada é gravado, auditado ou enviado/);
const parent=readFileSync('src/components/MasterOnboardingView.tsx','utf8');
assert.match(parent,/<MasterWorkflowAuditView state={state}\/>/);
const api=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(api,/admin-onboarding\/workflow-contract/);
assert.match(api,/admin-onboarding\/transition-preview/);
const keys=['MASTER_MFA','DUAL_CONTROL','EMAIL_OWNERSHIP','INVITE_SINGLE_USE',
 'EXPIRATION_AND_REVOCATION','TRANSACTIONAL_AUDIT','IDENTITY_MEMBERSHIP_RECHECK',
 'DELIVERY_PROVIDER_VERIFIED','LEGAL_APPROVAL'];
const audit=['request_id','tenant_id','transition','actor_id','independent_approver_id',
 'expected_revision','observed_revision','decision','idempotency_key_hash',
 'previous_event_hash','event_hash','occurred_at'];
const contract={
 scope:'MASTER_ONBOARDING_WORKFLOW_CONTRACT',
 mode:'SPECIFICATION_AND_SIMULATION_ONLY',operations_enabled:false,
 audit_persisted:false,states:[...WORKFLOW_STATES],
 edges:Object.fromEntries(WORKFLOW_STATES.map(s=>[s,[]])),
 required_gates:keys,transaction_guards:keys,
 proposed_audit_fields:audit,max_previous_keys:32,
 next_action:'SECURITY_AND_SCHEMA_APPROVAL_REQUIRED',
};
assert.equal(parseWorkflowContract(contract).operations_enabled,false);
assert.throws(()=>parseWorkflowContract({...contract,operations_enabled:true}));
assert.throws(()=>parseWorkflowContract({...contract,states:['REQUESTED']}));
const key='00000000-0000-4000-8000-000000000001';
const params={
 currentState:'REQUESTED' as const,proposedState:'EMAIL_VERIFIED' as const,
 actorRole:'MASTER' as const,candidateIsActor:false,emailVerified:false,
 tenantActive:false,independentApproval:false,tokenValid:false,
 expectedRevision:1,observedRevision:1,
 idempotencyKey:key,previouslyUsedKeys:[],
};
validateWorkflowPreviewRequest(params);
assert.throws(()=>validateWorkflowPreviewRequest({...params,idempotencyKey:'wrong'}));
assert.throws(()=>validateWorkflowPreviewRequest({...params,expectedRevision:-1}));
const preview={
 scope:'MASTER_ONBOARDING_TRANSITION_PREVIEW',mode:'MEMORY_ONLY_NOT_AUDIT',
 result:'EXECUTION_DENIED',current_state:'REQUESTED',
 proposed_state:'EMAIL_VERIFIED',graph_valid:true,
 revision_conflict:false,idempotency_replay_detected:false,
 scenario_fingerprint:'a'.repeat(64),fingerprint_is_audit_proof:false,
 reasons:['RUNTIME_OPERATIONS_DISABLED'],state_unchanged:true,
 projected_next_state:null,writes_performed:false,
 audit_persisted:false,invitation_created:false,
 account_changed:false,allowed_for_real_execution:false,
};
assert.equal(parseWorkflowPreview(preview).audit_persisted,false);
assert.throws(()=>parseWorkflowPreview({...preview,audit_persisted:true}));
assert.throws(()=>parseWorkflowPreview({...preview,allowed_for_real_execution:true}));
assert.throws(()=>parseWorkflowPreview({...preview,reasons:[]}));
assert.throws(()=>parseWorkflowPreview({...preview,scenario_fingerprint:'not-a-hash'}));
console.log('MASTER_WORKFLOW_AUDIT_UI=PASS');
