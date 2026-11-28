import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readFileSync} from 'node:fs';
import {MasterPermissionMatrixView} from '../components/MasterPermissionMatrixView';
import {RESOURCES,ROLES,parseMasterPermissionMatrix} from '../services/masterPermissionMatrix';
const code=readFileSync('src/components/MasterOnboardingView.tsx','utf8');
assert.match(code,/<MasterPermissionMatrixView state={state}\/>/);
const financial=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(financial,/admin-onboarding\/permission-matrix/);
const denied=renderToStaticMarkup(React.createElement(MasterPermissionMatrixView,{
  state:{currentRole:'TENANT_MEMBER',currentUserId:'ci',currentTenantId:'x'} as any,
}));
assert.match(denied,/restrito ao Master/);
assert.doesNotMatch(denied,/Matriz de permissões/);
const owner=renderToStaticMarkup(React.createElement(MasterPermissionMatrixView,{
  state:{currentRole:'MASTER',currentUserId:'ci',currentTenantId:null} as any,
}));
assert.match(owner,/Matriz de permissões/);
assert.match(owner,/autorização real depende de sessão validada/);
const grants=Object.fromEntries(RESOURCES.map(resource=>[
  resource,Object.fromEntries(ROLES.map(role=>[role,'DENIED']))
]));
const good={
  scope:'MASTER_ONBOARDING_PERMISSION_MATRIX',
  source:'DECLARED_POLICY_NOT_RUNTIME_AUTHORITY',
  mode:'DOCUMENTATION_AND_CI_ONLY',
  grants_changed:false,operations_enabled:false,database_migration_required:false,
  roles:[...ROLES],resources:[...RESOURCES],permissions:grants,
  enforcement:'FASTAPI_RBAC_PLUS_POSTGRESQL_RLS',
  sensitive_actions:'BLOCKED_PENDING_APPROVAL',
};
assert.equal(parseMasterPermissionMatrix(good).operations_enabled,false);
assert.throws(()=>parseMasterPermissionMatrix({...good,operations_enabled:true}));
assert.throws(()=>parseMasterPermissionMatrix({...good,grants_changed:true}));
assert.throws(()=>parseMasterPermissionMatrix({...good,roles:['MASTER']}));
assert.throws(()=>parseMasterPermissionMatrix({...good,permissions:{
  ...grants,INVITATION_ISSUANCE:{...grants.INVITATION_ISSUANCE,MASTER:'METADATA_ONLY'},
}}));
assert.throws(()=>parseMasterPermissionMatrix({...good,permissions:{
  ...grants,TENANT_FINANCIAL_DATA:{...grants.TENANT_FINANCIAL_DATA,MASTER:'OWN_RECORD_ONLY'},
}}));
console.log('MASTER_PERMISSION_MATRIX_UI=PASS');
