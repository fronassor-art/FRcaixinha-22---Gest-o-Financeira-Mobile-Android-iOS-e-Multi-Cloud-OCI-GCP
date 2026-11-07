/** M25300 — contratos de convite: revisão local, nunca aceite ou cadastro. */
export type InvitationPreparerRole = 'MASTER' | 'TENANT_ADMIN';
export type InvitationTargetRole = 'TENANT_ADMIN' | 'TENANT_MEMBER';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHA256 = /^[0-9a-f]{64}$/;
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export function targetForPreparer(role: InvitationPreparerRole): InvitationTargetRole {
  return role === 'MASTER' ? 'TENANT_ADMIN' : 'TENANT_MEMBER';
}

export function validateReviewInput(
  role: InvitationPreparerRole,
  tenantId: string,
  documentId?: string,
  contractText?: string,
): void {
  if (role !== 'MASTER' && role !== 'TENANT_ADMIN') {
    throw new Error('Perfil sem permissão para preparar contratos');
  }
  if (!UUID.test(tenantId)) throw new Error('Informe um UUID válido da caixinha');
  if (documentId !== undefined && !UUID.test(documentId)) {
    throw new Error('Escolha uma versão publicada válida');
  }
  if (contractText !== undefined) {
    if (!contractText || new TextEncoder().encode(contractText).byteLength > 65536) {
      throw new Error('Informe o texto UTF-8 integral, com até 64 KiB');
    }
  }
}

export type PublishedContract = {
  document_id: string;
  version: string;
  sha256: string;
  published_at: string;
};

export type ContractCatalog = {
  source: 'POSTGRESQL_RLS';
  scope: 'AI_STUDIO_PUBLISHED_MEMBERSHIP_CONTRACT_CATALOG';
  status: 'BLOCKED';
  target_role: InvitationTargetRole;
  tenant_active_verified: boolean;
  documents: PublishedContract[];
  contract_body_available: false;
  acceptance_recorded: false;
  invitation_created: false;
  activation_authorized: false;
  writes_performed: false;
};

export type ContractDigestPreview = {
  source: 'POSTGRESQL_RLS';
  scope: 'AI_STUDIO_CONTRACT_BODY_DIGEST_PREFLIGHT';
  status: 'BLOCKED';
  target_role: InvitationTargetRole;
  tenant_active_verified: boolean;
  document_published_verified: boolean;
  exact_utf8_document_digest_matched: boolean;
  canonical_document_hosted: false;
  consent_verified: false;
  acceptance_recorded: false;
  invitation_created: false;
  activation_authorized: false;
  writes_performed: false;
};

function fail(): never { throw new Error('Resposta de contrato não confiável'); }

function verifyBlockedCommon(raw: Record<string, unknown>, scope: string, target: InvitationTargetRole) {
  if (raw.source !== 'POSTGRESQL_RLS' || raw.scope !== scope ||
      raw.target_role !== target || raw.status !== 'BLOCKED' ||
      raw.acceptance_recorded !== false || raw.invitation_created !== false ||
      raw.activation_authorized !== false || raw.writes_performed !== false ||
      typeof raw.tenant_active_verified !== 'boolean') fail();
}

export function parseContractCatalog(raw: unknown, target: InvitationTargetRole): ContractCatalog {
  if (!isObject(raw)) fail();
  verifyBlockedCommon(raw, 'AI_STUDIO_PUBLISHED_MEMBERSHIP_CONTRACT_CATALOG', target);
  if (raw.contract_body_available !== false || raw.document_kind !== 'TENANT_MEMBERSHIP' ||
      raw.delivery_verified !== false || !Array.isArray(raw.documents) ||
      raw.documents.length > 20) fail();
  if (!raw.tenant_active_verified && raw.documents.length !== 0) fail();
  for (const entry of raw.documents) {
    if (!isObject(entry) || typeof entry.document_id !== 'string' ||
        !UUID.test(entry.document_id) ||
        typeof entry.version !== 'string' || entry.version.length < 1 ||
        entry.version.length > 60 || typeof entry.sha256 !== 'string' ||
        !SHA256.test(entry.sha256) ||
        typeof entry.published_at !== 'string' ||
        !Number.isFinite(Date.parse(entry.published_at))) fail();
  }
  return raw as ContractCatalog;
}

export function parseContractDigestPreview(
  raw: unknown, target: InvitationTargetRole,
): ContractDigestPreview {
  if (!isObject(raw)) fail();
  verifyBlockedCommon(raw, 'AI_STUDIO_CONTRACT_BODY_DIGEST_PREFLIGHT', target);
  if (typeof raw.document_published_verified !== 'boolean' ||
      typeof raw.exact_utf8_document_digest_matched !== 'boolean' ||
      raw.canonical_document_hosted !== false ||
      raw.body_rendered_for_invitee !== false ||
      raw.consent_verified !== false || raw.email_sent !== false ||
      raw.user_created !== false || raw.membership_changed !== false) fail();
  if (raw.exact_utf8_document_digest_matched &&
      (!raw.document_published_verified || !raw.tenant_active_verified)) fail();
  return raw as ContractDigestPreview;
}
