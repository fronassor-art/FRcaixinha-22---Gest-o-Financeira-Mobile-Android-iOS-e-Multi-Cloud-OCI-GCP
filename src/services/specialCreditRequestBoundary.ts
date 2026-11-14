/** FR Finance M39048 — fronteira de sessão/caixinha para Crédito Especial.
 * Funções puras/injetáveis para testar sem login real, rede, API externa, PG ou Pix.
 * A aplicação usa authService como fonte oficial; UI não concede permissão.
 */
import type { AuthenticatedUser, AuthSessionSnapshot } from './authService';
import { classifyApiOrigin } from './apiOriginPolicy';

export interface SpecialCreditTransport {
  origin: () => string;
  captureSession: () => AuthSessionSnapshot;
  isCurrent: (snapshot: AuthSessionSnapshot) => boolean;
  getUser: () => AuthenticatedUser | null;
  invalidateIfCurrent: (snapshot: AuthSessionSnapshot) => boolean;
  send: (url: string, options: RequestInit) => Promise<Response>;
}

export function scopedCreditPath(tenantId:string):string {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(tenantId))
    throw new Error('Contexto de caixinha inválido.');
  return '/api/v1/tenants/' + encodeURIComponent(tenantId) + '/special-credit';
}

/** Falha local antes de enviar bearer/URL ao backend com o tenant errado. */
export async function requestSpecialCredit<T>(
  transport: SpecialCreditTransport,
  tenantId: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const endpoint = scopedCreditPath(tenantId);
  if (!path.startsWith('/') || path.startsWith('//') || /[?#]/.test(path))
    throw new Error('Caminho de crédito inválido.');
  const base = transport.origin();
  if (classifyApiOrigin(base).kind === 'BLOCKED')
    throw new Error('Servidor FR Finance não configurado.');

  const snapshot = transport.captureSession();
  const user = transport.getUser();
  if (!snapshot.token || !user || !transport.isCurrent(snapshot))
    throw new Error('Entre novamente para acessar o crédito especial.');
  if ((user.role !== 'TENANT_ADMIN' && user.role !== 'TENANT_MEMBER')
      || !user.tenantId || user.tenantId.toLowerCase() !== tenantId.toLowerCase())
    throw new Error('Acesso recusado: caixinha não corresponde à sessão ativa.');

  const response = await transport.send(base + endpoint + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      Authorization: 'Bearer ' + snapshot.token,
      'X-Requested-With': 'XMLHttpRequest',
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'include',
    cache: 'no-store',
  });
  if (!transport.isCurrent(snapshot))
    throw new Error('A sessão mudou. Reabra as oportunidades.');
  if (response.status === 401) {
    // Um 401 de login antigo jamais invalida um login posterior.
    transport.invalidateIfCurrent(snapshot);
    throw new Error('Sessão expirada. Entre novamente.');
  }
  if (response.status === 503)
    throw new Error('Módulo em preparação. Verifique habilitação local antes do teste.');
  if (!response.ok)
    throw new Error('Operação recusada pelo servidor (' + response.status + ').');

  const value: unknown = await response.json();
  if (!transport.isCurrent(snapshot))
    throw new Error('Sessão mudou durante a consulta.');
  return value as T;
}

/** O front-end não aceita alegação inesperada de Pix, crédito ou entrega real. */
export function assertSandboxCreditCapabilities<T>(capabilities: T): T {
  if (!capabilities || typeof capabilities !== 'object' || Array.isArray(capabilities))
    throw new Error('Contrato de Crédito Especial inválido.');
  const value = capabilities as Record<string, unknown>;
  if (typeof value.sandbox_enabled !== 'boolean' ||
      value.grants_allow_request_only !== true ||
      value.real_credit_enabled !== false ||
      value.pix_real_enabled !== false)
    throw new Error('Ativação financeira inesperada. Crédito Especial bloqueado.');

  const channels = value.channels;
  if (!channels || typeof channels !== 'object' || Array.isArray(channels))
    throw new Error('Contrato de canais de Crédito Especial inválido.');
  const record = channels as Record<string, unknown>;
  for (const channel of ['PUSH','EMAIL','WHATSAPP','SMS']) {
    const entry = record[channel];
    if (!entry || typeof entry !== 'object' || Array.isArray(entry) ||
        (entry as Record<string, unknown>).real_delivery_enabled !== false ||
        (entry as Record<string, unknown>).code_present !== true)
      throw new Error('Canal externo não homologado. Crédito Especial bloqueado.');
  }
  return capabilities;
}
