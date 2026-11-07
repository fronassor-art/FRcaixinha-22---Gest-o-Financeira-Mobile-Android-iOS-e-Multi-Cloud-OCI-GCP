/** M25600 — release readiness is evidence inventory, never a feature switch. */
export type ReleaseRequirement = {
  id: string;
  category: 'identidade' | 'cadastro' | 'infra' | 'pagamentos';
  status: 'INTEGRATION_AND_ATTESTATION_REQUIRED';
  engineering_source_present: boolean;
  production_verified: false;
  required_evidence: string;
};

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
};

const object = (value:unknown):value is Record<string,unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const categories = new Set(['identidade','cadastro','infra','pagamentos']);
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
  return raw as LaunchReadiness;
}
