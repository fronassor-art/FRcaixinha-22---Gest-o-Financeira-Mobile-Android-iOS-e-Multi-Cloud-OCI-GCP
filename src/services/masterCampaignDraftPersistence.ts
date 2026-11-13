/** FR Finance M39075 — rascunho local de campanha SaaS do Master.
 *
 * Guarda APENAS campos de formulário comercial, nunca token, senha, sessão,
 * membros, dados de caixinha ou objetos do PostgreSQL.
 * Escopo por UUID autenticado Master, TTL 72h e eliminação no logout explícito.
 * Não cria campanha no servidor, publicação, licença ou cobranças.
 */
export type CampaignDraftForm = {
  tier: 'ESSENCIAL' | 'INTERMEDIARIO';
  period: 'MONTHLY' | 'ANNUAL';
  priceText: string;
  title: string;
  benefit: string;
  startsAt: string;
  endsAt: string;
  reason: string;
};

export const EMPTY_MASTER_CAMPAIGN_DRAFT: CampaignDraftForm = {
  tier: 'ESSENCIAL',
  period: 'MONTHLY',
  priceText: '',
  title: '',
  benefit: '',
  startsAt: '',
  endsAt: '',
  reason: '',
};

export interface DraftKeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const PREFIX = 'frfinance:ui:master:saas-campaign-draft:v1:';
export const DRAFT_TTL_MS = 72 * 60 * 60 * 1000;
const MAX_STORED_BYTES = 3000;
const ID_PATTERN = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

function scopedKey(actorId: string | null | undefined): string | null {
  if (!actorId || !ID_PATTERN.test(actorId)) return null;
  return PREFIX + actorId.toLowerCase();
}

export function masterCampaignDraftStorage(): DraftKeyValueStorage | null {
  try {
    return typeof window !== 'undefined' && window.localStorage
      ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function hasDraftContent(draft: CampaignDraftForm): boolean {
  return draft.tier !== 'ESSENCIAL' || draft.period !== 'MONTHLY' ||
    Boolean(draft.priceText || draft.title || draft.benefit ||
      draft.startsAt || draft.endsAt || draft.reason);
}

function validatedDraft(input: unknown): CampaignDraftForm | null {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
  const x = input as Record<string, unknown>;
  if (x.tier !== 'ESSENCIAL' && x.tier !== 'INTERMEDIARIO') return null;
  if (x.period !== 'MONTHLY' && x.period !== 'ANNUAL') return null;
  const fields: ReadonlyArray<readonly [keyof CampaignDraftForm, number]> = [
    ['priceText', 32], ['title', 120], ['benefit', 500],
    ['startsAt', 50], ['endsAt', 50], ['reason', 500],
  ];
  for (const [field, max] of fields) {
    if (typeof x[field] !== 'string' || (x[field] as string).length > max) return null;
  }
  return {
    tier: x.tier, period: x.period,
    priceText: x.priceText as string,
    title: x.title as string,
    benefit: x.benefit as string,
    startsAt: x.startsAt as string,
    endsAt: x.endsAt as string,
    reason: x.reason as string,
  };
}

export function readMasterCampaignDraft(
  storage: DraftKeyValueStorage | null,
  actorId: string | null | undefined,
  now = Date.now(),
): CampaignDraftForm | null {
  const key = scopedKey(actorId);
  if (!storage || !key) return null;
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    if (raw.length > MAX_STORED_BYTES) {
      storage.removeItem(key);
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      storage.removeItem(key);
      return null;
    }
    const record = parsed as Record<string, unknown>;
    const savedAt = record.savedAt;
    if (record.version !== 1 || typeof savedAt !== 'number' ||
        !Number.isSafeInteger(savedAt) || now < savedAt ||
        now - savedAt > DRAFT_TTL_MS) {
      storage.removeItem(key);
      return null;
    }
    const draft = validatedDraft(record.form);
    if (!draft || !hasDraftContent(draft)) {
      storage.removeItem(key);
      return null;
    }
    return draft;
  } catch {
    // Armazenamento indisponível (modo privado/sem espaço) não pode bloquear UI.
    return null;
  }
}

export function saveMasterCampaignDraft(
  storage: DraftKeyValueStorage | null,
  actorId: string | null | undefined,
  input: CampaignDraftForm,
  now = Date.now(),
): boolean {
  const key = scopedKey(actorId);
  if (!storage || !key) return false;
  const draft = validatedDraft(input);
  if (!draft) return false;
  try {
    if (!hasDraftContent(draft)) {
      storage.removeItem(key);
      return true;
    }
    const serialized = JSON.stringify({version: 1, savedAt: now, form: draft});
    if (serialized.length > MAX_STORED_BYTES) return false;
    storage.setItem(key, serialized);
    return true;
  } catch {
    return false;
  }
}

export function discardMasterCampaignDraft(
  storage: DraftKeyValueStorage | null,
  actorId: string | null | undefined,
): void {
  const key = scopedKey(actorId);
  if (!storage || !key) return;
  try { storage.removeItem(key); } catch { /* nenhum dado crítico */ }
}

export function hasSavedMasterCampaignDraft(
  storage: DraftKeyValueStorage | null,
  actorId: string | null | undefined,
): boolean {
  return readMasterCampaignDraft(storage, actorId) !== null;
}
