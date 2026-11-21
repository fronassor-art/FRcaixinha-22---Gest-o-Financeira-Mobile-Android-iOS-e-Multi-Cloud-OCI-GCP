/** Regressão contratual Master SaaS: estados, filtros, paginação e ausência de vazamentos. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseMasterSaasPortfolio} from '../services/masterSaasPortfolio';
const tenant={
 id:'1a2b3c4d-1234-1234-1234-123456789abc',
 admin_user_id:'2a2b3c4d-1234-1234-1234-123456789abc',
 display_name:'Caixinha Inaugural',tenant_status:'ATIVO',
 registered_at:'2026-11-03T12:00:00+00:00',
 admin_total:3,admin_active:1,admin_suspended:1,admin_draft:1,admin_closed:0,
 licensed_plan:null,license_status:null,effective_status:null,
 valid_from:null,valid_until:null,prepared_plan:'ESSENCIAL',
 prepared_period:'ANNUAL',preparation_status:'PREPARING',
 prepared_at:'2026-11-03T12:00:00+00:00',
 members_limit:null,quotas_limit:null
};
const data={
 source:'POSTGRESQL_RLS',scope:'MASTER_SAAS_PORTFOLIO',
 boxes_limit_policy:'NOT_DEFINED',
 total:1,page:1,page_size:20,tenant_status_filter:'ATIVO',has_more:false,
 tenants:[tenant]
};
assert.equal(parseMasterSaasPortfolio(data,'ATIVO',1).tenants[0].admin_suspended,1);
const reject=(v:unknown)=>assert.throws(()=>parseMasterSaasPortfolio(v,'ATIVO',1));
reject({...data,tenant_status_filter:'TODOS'});
reject({...data,tenants:[{...tenant,admin_active:2}]});
reject({...data,tenants:[{...tenant,email:'private@example.test'}]});
reject({...data,tenants:[{...tenant,licensed_plan:'ESSENCIAL'}]});
reject({...data,tenants:[{...tenant,tenant_status:'SUSPENSO'}]});
reject({...data,tenants:[{...tenant,valid_until:'2027-11-01T00:00:00Z'}]});
reject({...data,has_more:true});
reject({...data,tenants:[tenant,tenant]});
reject({...data,scope:'TENANT_FINANCIAL'});
const file=(p:string)=>readFileSync(p,'utf8');
const view=file('src/components/MasterSaasPortfolioView.tsx');
const api=file('src/services/financialApiService.ts');
assert.match(view,/Situação cadastral/);
assert.match(view,/Sem licença confirmada no PostgreSQL/);
assert.match(view,/Quantidade de novas caixinhas permitidas/);
assert.match(view,/role="alert"/);
assert.match(view,/t\.admin_suspended/);
assert.match(view,/t\.admin_draft/);
assert.match(view,/t\.admin_closed/);
assert.match(api,/parseMasterSaasPortfolio\(raw,filter,page\)/);
console.log('MACROPACOTE_120_MASTER_SAAS_FRONTEND=PASS');
