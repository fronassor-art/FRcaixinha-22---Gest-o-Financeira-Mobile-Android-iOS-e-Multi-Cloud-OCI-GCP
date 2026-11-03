/* Painel de administradores: apenas Master; validacao de dados do servidor. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MasterAdminRegistryView} from '../components/MasterAdminRegistryView';
import {parseMasterAdminRegistry,adminRegistryQuery} from '../services/masterAdminRegistry';
import {tabsAllowedToRole,isRoleTabAllowed} from '../services/roleScope';
const source=(p:string)=>readFileSync(p,'utf8');
assert(tabsAllowedToRole('MASTER').includes('ADMINISTRADORES'));
assert(!tabsAllowedToRole('TENANT_ADMIN').includes('ADMINISTRADORES'));
assert(!tabsAllowedToRole('TENANT_MEMBER').includes('ADMINISTRADORES'));
assert.equal(isRoleTabAllowed('MASTER','ADMINISTRADORES'),true);
assert.equal(isRoleTabAllowed('TENANT_ADMIN','ADMINISTRADORES'),false);
assert.equal(isRoleTabAllowed('TENANT_MEMBER','ADMINISTRADORES'),false);
assert.match(source('src/App.tsx'),/visibleTab === 'ADMINISTRADORES' && state.currentRole === 'MASTER'/);
assert.match(source('src/services/financialApiService.ts'),/master\/admin-registry/);
const denied=renderToStaticMarkup(React.createElement(MasterAdminRegistryView,{
  state:{currentRole:'TENANT_MEMBER',currentUserId:'ci',currentTenantId:'ci'} as any,
}));
assert.match(denied,/Acesso exclusivo/);
assert.doesNotMatch(denied,/Localizar responsável/);
const allowed=renderToStaticMarkup(React.createElement(MasterAdminRegistryView,{
  state:{currentRole:'MASTER',currentUserId:'ci',currentTenantId:null} as any,
}));
assert.match(allowed,/Administradores da plataforma/);
assert.match(allowed,/Localizar responsável/);
assert.match(allowed,/Convites, aprovações e suspensões indisponíveis/);
assert.doesNotMatch(allowed,/Aprovar administrador|Suspender administrador/);
assert.equal(adminRegistryQuery({search:'a&b',page:2,pageSize:5}),
  'search=a%26b&page=2&page_size=5');
assert.throws(()=>adminRegistryQuery({search:'a'.repeat(37),page:1}));
assert.throws(()=>adminRegistryQuery({search:'',page:0}));
const id='00000000-0000-4000-8000-000000000002';
const payload={
  source:'POSTGRESQL_RLS',scope:'MASTER_PRIMARY_ADMIN_REGISTRY',
  total:1,page:1,page_size:20,has_more:false,
  identity_status:'UNVERIFIED_REFERENCE_ONLY',
  invitation_status:'NOT_IMPLEMENTED',
  access_changes:'BLOCKED_PENDING_APPROVAL',
  administrators:[{
    admin_user_id:id,tenant_count:2,active_count:1,
    suspended_count:1,draft_count:0,closed_count:0,
  }],
};
assert.equal(parseMasterAdminRegistry(payload).administrators[0].admin_user_id,id);
assert.throws(()=>parseMasterAdminRegistry({...payload,source:'SEED'}));
assert.throws(()=>parseMasterAdminRegistry({...payload,has_more:true}));
assert.throws(()=>parseMasterAdminRegistry({...payload,invitation_status:'READY'}));
assert.throws(()=>parseMasterAdminRegistry({...payload,administrators:[
  {...payload.administrators[0],tenant_count:3},
]}));
console.log('MASTER_ADMIN_REGISTRY_UI=PASS');
