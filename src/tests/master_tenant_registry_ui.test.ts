/* Governanca de caixinhas: metadados reais, papeis e resposta sem seed. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MasterTenantRegistryView} from '../components/MasterTenantRegistryView';
import {parseMasterTenantRegistry,registryQuery} from '../services/masterRegistry';
import {tabsAllowedToRole,isRoleTabAllowed} from '../services/roleScope';

const masterTabs=tabsAllowedToRole('MASTER');
assert(masterTabs.includes('CAIXINHAS'));
assert(!tabsAllowedToRole('TENANT_ADMIN').includes('CAIXINHAS'));
assert(!tabsAllowedToRole('TENANT_MEMBER').includes('CAIXINHAS'));
assert.equal(isRoleTabAllowed('MASTER','CAIXINHAS'),true);
assert.equal(isRoleTabAllowed('TENANT_ADMIN','CAIXINHAS'),false);
assert.equal(isRoleTabAllowed('TENANT_MEMBER','CAIXINHAS'),false);
const app=readFileSync('src/App.tsx','utf8');
assert.match(app,/visibleTab === 'CAIXINHAS' && state.currentRole === 'MASTER'/);
const api=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(api,/master\/tenant-registry/);
const denied=renderToStaticMarkup(React.createElement(MasterTenantRegistryView,{
  state:{currentRole:'TENANT_MEMBER',currentUserId:'ci',currentTenantId:'ci'} as any
}));
assert.match(denied,/Acesso exclusivo/);
assert.doesNotMatch(denied,/Localizar caixinha/);
const master=renderToStaticMarkup(React.createElement(MasterTenantRegistryView,{
  state:{currentRole:'MASTER',currentUserId:'ci',currentTenantId:null} as any
}));
assert.match(master,/Gestão de caixinhas/);
assert.match(master,/Localizar caixinha/);
assert.match(master,/Convites e alterações de acesso aguardam implementação/);
assert.doesNotMatch(master,/Suspender conta|Aprovar administrador/);

assert.equal(registryQuery({search:'A&B',status:'ATIVO',page:2,pageSize:5}),
 'search=A%26B&tenant_status=ATIVO&page=2&page_size=5');
assert.throws(()=>registryQuery({search:'a'.repeat(81),status:'ATIVO',page:1}));
assert.throws(()=>registryQuery({search:'',status:'TODOS',page:0}));
const id='00000000-0000-4000-8000-000000000001';
const admin='00000000-0000-4000-8000-000000000002';
const page={
 source:'POSTGRESQL_RLS',scope:'MASTER_TENANT_REGISTRY',
 total:1,page:1,page_size:20,has_more:false,
 status_counts:{RASCUNHO_INATIVO:0,ATIVO:1,SUSPENSO:0,ENCERRADO:0},
 tenants:[{id,display_name:'Caixinha CI',status:'ATIVO',
   is_owner_box:false,admin_user_id:admin,created_at:'2026-11-02T00:00:00+00:00'}],
 admin_invitation_status:'NOT_IMPLEMENTED',
 admin_access_changes:'BLOCKED_PENDING_APPROVAL',
};
assert.equal(parseMasterTenantRegistry(page).tenants[0].id,id);
assert.throws(()=>parseMasterTenantRegistry({...page,source:'SEED_LOCAL'}));
assert.throws(()=>parseMasterTenantRegistry({...page,has_more:true}));
assert.throws(()=>parseMasterTenantRegistry({...page,tenants:[{...page.tenants[0],admin_user_id:'invalido'}]}));
assert.throws(()=>parseMasterTenantRegistry({...page,admin_access_changes:'ACTIVE'}));
console.log('MASTER_TENANT_REGISTRY_UI=PASS');
