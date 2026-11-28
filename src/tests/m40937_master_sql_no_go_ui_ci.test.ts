/* M40937 — release-readiness SQL risk is visible but never a capability. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {parseLaunchReadiness,parseSqlTrustReadiness} from '../services/launchReadiness';
import {LaunchReadinessPanel} from '../components/LaunchReadinessPanel';

const sql={
  status:'NO_GO',evidence:'SOURCE_ONLY_NOT_RUNTIME_ATTESTED',
  guc_identity_boundary_verified:false,
  app_direct_saas_insert_revoked_verified:false,
  independent_master_custody_verified:false,
  staging_sql_roles_acl_verified:false,
  master_write_operations_enabled:false,
  blockers:[
    {code:'M40570',description:'GUC SQL falsificável e sem atestação independente.'},
    {code:'M40730',description:'Custódia do emissor SQL ainda não homologada.'},
    {code:'M40936',description:'ACL somente validada no PostgreSQL descartável.'},
  ],
};
const base={
  source:'REPOSITORY_AND_CONFIGURATION_DECLARATIONS',
  scope:'AI_STUDIO_MASTER_RELEASE_READINESS',
  mode:'READ_ONLY_NO_ACTIVATION',
  status:'BLOCKED',
  workstream:'AI_STUDIO',
  production_auth_config_syntax_valid:false,
  smtp_config_syntax_valid:false,
  public_https_origin_syntax_valid:false,
  config_valid_is_live_proof:false,
  real_invites_active:false,password_reset_active:false,
  real_pix_active:false,financial_closing_authorized:false,
  writes_performed:false,total_gates:20,unverified_gates:20,
  requirements:Array.from({length:20},(_,i)=>({
    id:'M40937_GATETEST_'+String(i).padStart(2,'0'),
    category:'identidade',status:'INTEGRATION_AND_ATTESTATION_REQUIRED',
    engineering_source_present:false,production_verified:false,
    required_evidence:'Verificação independente e validação em staging.',
  })),
};
const fresh=parseLaunchReadiness({...base,sql_trust:sql});
assert.equal(fresh.sql_trust.status,'NO_GO');
assert.equal(fresh.sql_trust.blockers.length,3);
assert.equal(fresh.sql_trust.master_write_operations_enabled,false);

// Older Termux API without this additional field must fail CLOSED in UI.
const old=parseLaunchReadiness(base);
assert.equal(old.sql_trust.status,'NO_GO');
assert.equal(old.sql_trust.guc_identity_boundary_verified,false);
assert.match(old.sql_trust.blockers[0].description,/não atestada/i);

for(const mutation of [
  {...sql,status:'READY'},
  {...sql,evidence:'LIVE_ATTESTED'},
  {...sql,guc_identity_boundary_verified:true},
  {...sql,app_direct_saas_insert_revoked_verified:true},
  {...sql,independent_master_custody_verified:true},
  {...sql,staging_sql_roles_acl_verified:true},
  {...sql,master_write_operations_enabled:true},
  {...sql,blockers:[sql.blockers[2]]},
  {...sql,blockers:[sql.blockers[0],sql.blockers[0]]},
  {...sql,blockers:[{code:'M40570',description:'x'},sql.blockers[1]]},
]) {
  assert.throws(()=>parseSqlTrustReadiness(mutation));
  assert.throws(()=>parseLaunchReadiness({...base,sql_trust:mutation}));
}
const panelSource=readFileSync('src/components/LaunchReadinessPanel.tsx','utf8');
assert.match(panelSource,/Segurança SQL: NÃO HOMOLOGADA/);
assert.match(panelSource,/current\.report\.sql_trust\.blockers\.map/);
assert.doesNotMatch(panelSource,/set.*PIX_REAL|enableProduction|enablePix|approveMasterSql/);
const other=renderToStaticMarkup(React.createElement(LaunchReadinessPanel,{
  state:{currentRole:'TENANT_MEMBER',currentUserId:'test',currentTenantId:'t'} as any,
}));
assert.equal(other,'');
const master=renderToStaticMarkup(React.createElement(LaunchReadinessPanel,{
  state:{currentRole:'MASTER',currentUserId:'test',currentTenantId:''} as any,
}));
assert.match(master,/Mapa de conclusão e integrações/);
console.log('M40937_MASTER_SQL_RELEASE_UI=PASS_NO_GO');
