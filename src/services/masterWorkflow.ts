/** Simulador Master: contrato de cenário em memória, nunca convite ou auditoria real. */
export const WORKFLOW_STATES=[
  'REQUESTED','EMAIL_VERIFIED','MASTER_REVIEW','APPROVED',
  'INVITE_PREPARED','DELIVERED','ACCEPTED','ACTIVE',
  'REJECTED','REVOKED','EXPIRED',
] as const;
export type WorkflowState=typeof WORKFLOW_STATES[number];
export type ActorRole='MASTER'|'TENANT_ADMIN'|'TENANT_MEMBER';
export type WorkflowPreviewRequest={
  currentState:WorkflowState;proposedState:WorkflowState;actorRole:ActorRole;
  candidateIsActor:boolean;emailVerified:boolean;tenantActive:boolean;
  independentApproval:boolean;tokenValid:boolean;
  expectedRevision:number;observedRevision:number;
  idempotencyKey:string;previouslyUsedKeys:string[];
};
export type WorkflowContract={
  scope:'MASTER_ONBOARDING_WORKFLOW_CONTRACT';
  mode:'SPECIFICATION_AND_SIMULATION_ONLY';operations_enabled:false;
  audit_persisted:false;states:WorkflowState[];
  edges:Record<WorkflowState,WorkflowState[]>;
  required_gates:string[];transaction_guards:string[];
  proposed_audit_fields:string[];max_previous_keys:32;
  next_action:'SECURITY_AND_SCHEMA_APPROVAL_REQUIRED';
};
export type WorkflowPreview={
  scope:'MASTER_ONBOARDING_TRANSITION_PREVIEW';
  mode:'MEMORY_ONLY_NOT_AUDIT';result:'EXECUTION_DENIED';
  current_state:WorkflowState;proposed_state:WorkflowState;
  graph_valid:boolean;revision_conflict:boolean;
  idempotency_replay_detected:boolean;scenario_fingerprint:string;
  fingerprint_is_audit_proof:false;reasons:string[];
  state_unchanged:true;projected_next_state:null;
  writes_performed:false;audit_persisted:false;invitation_created:false;
  account_changed:false;allowed_for_real_execution:false;
};
const obj=(value:unknown):value is Record<string,unknown>=>
  typeof value==='object'&&value!==null&&!Array.isArray(value);
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const states=new Set<string>(WORKFLOW_STATES);
const int=(x:unknown):x is number=>Number.isSafeInteger(x)&&Number(x)>=0&&Number(x)<=1000000;
const bool=(x:unknown)=>typeof x==='boolean';
export function validateWorkflowPreviewRequest(value:WorkflowPreviewRequest):void{
  if(!states.has(value.currentState)||!states.has(value.proposedState)||
     !['MASTER','TENANT_ADMIN','TENANT_MEMBER'].includes(value.actorRole)||
     ![value.candidateIsActor,value.emailVerified,value.tenantActive,
       value.independentApproval,value.tokenValid].every(bool)||
     !int(value.expectedRevision)||!int(value.observedRevision)||
     !uuid.test(value.idempotencyKey)||!Array.isArray(value.previouslyUsedKeys)||
     value.previouslyUsedKeys.length>32||
     !value.previouslyUsedKeys.every(x=>typeof x==='string'&&uuid.test(x))){
    throw Error('Cenário de transição inválido');
  }
}
export function parseWorkflowContract(raw:unknown):WorkflowContract{
  if(!obj(raw)||raw.scope!=='MASTER_ONBOARDING_WORKFLOW_CONTRACT'||
     raw.mode!=='SPECIFICATION_AND_SIMULATION_ONLY'||
     raw.operations_enabled!==false||raw.audit_persisted!==false||
     raw.max_previous_keys!==32||
     raw.next_action!=='SECURITY_AND_SCHEMA_APPROVAL_REQUIRED'||
     !Array.isArray(raw.states)||raw.states.join('|')!==WORKFLOW_STATES.join('|')||
     !obj(raw.edges)||!WORKFLOW_STATES.every(state=>{
       const row=raw.edges as Record<string,unknown>;
       const edges=row[state];
       return Array.isArray(edges)&&edges.every(x=>typeof x==='string'&&states.has(x));
     })||
     !Array.isArray(raw.required_gates)||raw.required_gates.length<9||
     !Array.isArray(raw.transaction_guards)||raw.transaction_guards.length<8||
     !Array.isArray(raw.proposed_audit_fields)||raw.proposed_audit_fields.length<8){
    throw Error('Contrato de fluxo Master inválido');
  }
  return raw as WorkflowContract;
}
export function parseWorkflowPreview(raw:unknown):WorkflowPreview{
  if(!obj(raw)||raw.scope!=='MASTER_ONBOARDING_TRANSITION_PREVIEW'||
     raw.mode!=='MEMORY_ONLY_NOT_AUDIT'||raw.result!=='EXECUTION_DENIED'||
     typeof raw.current_state!=='string'||!states.has(raw.current_state)||
     typeof raw.proposed_state!=='string'||!states.has(raw.proposed_state)||
     !bool(raw.graph_valid)||!bool(raw.revision_conflict)||
     !bool(raw.idempotency_replay_detected)||
     typeof raw.scenario_fingerprint!=='string'||!/^[0-9a-f]{64}$/.test(raw.scenario_fingerprint)||
     raw.fingerprint_is_audit_proof!==false||
     !Array.isArray(raw.reasons)||!raw.reasons.includes('RUNTIME_OPERATIONS_DISABLED')||
     !raw.reasons.every((reason:unknown)=>typeof reason==='string'&&reason.length<=90)||
     raw.state_unchanged!==true||raw.projected_next_state!==null||
     raw.writes_performed!==false||raw.audit_persisted!==false||
     raw.invitation_created!==false||raw.account_changed!==false||
     raw.allowed_for_real_execution!==false){
    throw Error('Prévia do fluxo administrativo inválida');
  }
  return raw as WorkflowPreview;
}
