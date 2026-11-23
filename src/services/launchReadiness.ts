/** M25600 — release readiness is evidence inventory, never a feature switch. */
export type ReleaseRequirement = {
  id: string;
  category: 'identidade' | 'cadastro' | 'infra' | 'pagamentos';
  status: 'INTEGRATION_AND_ATTESTATION_REQUIRED';
  engineering_source_present: boolean;
  production_verified: false;
  required_evidence: string;
};

/** M40937: SQL authorization remains blocked regardless of source-only CI. */
export type SqlTrustReadiness = {
  status: 'NO_GO';
  evidence: 'SOURCE_ONLY_NOT_RUNTIME_ATTESTED';
  guc_identity_boundary_verified: false;
  app_direct_saas_insert_revoked_verified: false;
  independent_master_custody_verified: false;
  staging_sql_roles_acl_verified: false;
  master_write_operations_enabled: false;
  blockers: {code:string;description:string}[];
};

const noGoSqlFallback = ():SqlTrustReadiness => ({
  status:'NO_GO',evidence:'SOURCE_ONLY_NOT_RUNTIME_ATTESTED',
  guc_identity_boundary_verified:false,
  app_direct_saas_insert_revoked_verified:false,
  independent_master_custody_verified:false,
  staging_sql_roles_acl_verified:false,
  master_write_operations_enabled:false,
  blockers:[
    {code:'M40570',description:'Proveniência de identidade SQL não atestada.'},
    {code:'M40730',description:'Custódia independente de comandos Master pendente.'},
    {code:'M40936',description:'Privilégios de escrita ainda não atestados em staging.'},
  ],
});

export type LaunchReadiness = {
  scope: 'AI_STUDIO_MASTER_RELEASE_READINESS';
  source: 'REPOSITORY_AND_CONFIGURATION_DECLARATIONS';
  mode: 'READ_ONLY_NO_ACTIVATION';
  status: 'BLOCKED';
  total_gates: number;
  unverified_gates: number;
  production_auth_config_syntax_valid: boolean;
  smtp_config_syntax_valid: boolean;
  public_https_origin_syntax_valid: boolean;
  config_valid_is_live_proof: false;
  real_invites_active: false;
  password_reset_active: false;
  real_pix_active: false;
  financial_closing_authorized: false;
  writes_performed: false;
  requirements: ReleaseRequirement[];
  sql_trust: SqlTrustReadiness;
};

const object = (value:unknown):value is Record<string,unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const categories = new Set(['identidade','cadastro','infra','pagamentos']);
export function parseSqlTrustReadiness(raw:unknown):SqlTrustReadiness {
  // Older backend without the M40937 field also fails closed.
  if(raw === undefined) return noGoSqlFallback();
  if(!object(raw) || raw.status!=='NO_GO' ||
      raw.evidence!=='SOURCE_ONLY_NOT_RUNTIME_ATTESTED' ||
      raw.guc_identity_boundary_verified!==false ||
      raw.app_direct_saas_insert_revoked_verified!==false ||
      raw.independent_master_custody_verified!==false ||
      raw.staging_sql_roles_acl_verified!==false ||
      raw.master_write_operations_enabled!==false ||
      !Array.isArray(raw.blockers) || raw.blockers.length<2 ||
      raw.blockers.length>10) {
    throw new Error('Fronteira SQL não homologada ou resposta inválida');
  }
  const codes=new Set<string>();
  for(const item of raw.blockers) {
    if(!object(item) || typeof item.code!=='string' ||
        !/^M[0-9]{5}$/.test(item.code) || codes.has(item.code) ||
        typeof item.description!=='string' ||
        item.description.length<15 || item.description.length>180) {
      throw new Error('Bloqueio SQL inválido');
    }
    codes.add(item.code);
  }
  if(!codes.has('M40570') || !codes.has('M40730')) {
    throw new Error('Fronteiras SQL obrigatórias não declaradas');
  }
  return raw as SqlTrustReadiness;
}
export function parseLaunchReadiness(raw:unknown):LaunchReadiness {
  if (!object(raw) || raw.scope !== 'AI_STUDIO_MASTER_RELEASE_READINESS' ||
      raw.source !== 'REPOSITORY_AND_CONFIGURATION_DECLARATIONS' ||
      raw.mode !== 'READ_ONLY_NO_ACTIVATION' || raw.status !== 'BLOCKED' ||
      raw.config_valid_is_live_proof !== false || raw.real_invites_active !== false ||
      raw.password_reset_active !== false || raw.real_pix_active !== false ||
      raw.financial_closing_authorized !== false || raw.writes_performed !== false ||
      typeof raw.smtp_config_syntax_valid !== 'boolean' ||
      typeof raw.production_auth_config_syntax_valid !== 'boolean' ||
      typeof raw.public_https_origin_syntax_valid !== 'boolean' ||
      !Array.isArray(raw.requirements) || raw.requirements.length < 18 ||
      raw.requirements.length > 50 ||
      raw.total_gates !== raw.requirements.length ||
      raw.unverified_gates !== raw.requirements.length) {
    throw new Error('Inventário de lançamento inválido');
  }
  const ids = new Set<string>();
  for (const item of raw.requirements) {
    if (!object(item) || typeof item.id !== 'string' ||
        !/^[A-Z0-9_]{4,40}$/.test(item.id) || ids.has(item.id) ||
        !categories.has(String(item.category)) ||
        item.status !== 'INTEGRATION_AND_ATTESTATION_REQUIRED' ||
        item.production_verified !== false ||
        typeof item.engineering_source_present !== 'boolean' ||
        typeof item.required_evidence !== 'string' ||
        item.required_evidence.length < 15 || item.required_evidence.length > 300) {
      throw new Error('Evidência de lançamento inválida');
    }
    ids.add(item.id);
  }
  return {...raw,sql_trust:parseSqlTrustReadiness(raw.sql_trust)} as LaunchReadiness;
}
