/** FR Caixinha AI Studio: authenticated local in-app inbox, no fake fixtures. */
import { authService, getApiBaseUrl } from './authService';

export interface InboxNotification {
  id: string;
  kind: 'SELF_TEST' | 'SECURITY_SESSION_ALERT' | 'CONTRIBUTION_DUE_INFO';
  title: string;
  message: string;
  created_at: string;
  read_at: string | null;
}
export interface InboxPage {
  items: InboxNotification[];
  unread_count: number;
  has_more: boolean;
  next_cursor: string | null;
}

function uuid(value: unknown): value is string {
  return typeof value === 'string' &&
    /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value);
}
function when(value: unknown): value is string {
  return typeof value === 'string' && value.length < 45 &&
    Number.isFinite(Date.parse(value)) && /(?:Z|[+-]\d\d:\d\d)$/.test(value);
}
function validObject(value: unknown): value is Record<string,unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
export function parseInboxPage(value: unknown): InboxPage {
  if (!validObject(value) ||
      value.contract !== 'AI_STUDIO_M19000_IN_APP_LOCAL_INBOX_V1' ||
      !Array.isArray(value.items) || value.items.length > 50 ||
      typeof value.unread_count !== 'number' ||
      !Number.isSafeInteger(value.unread_count) || value.unread_count < 0 ||
      typeof value.has_more !== 'boolean' ||
      (value.next_cursor !== null && (
        typeof value.next_cursor !== 'string' || value.next_cursor.length > 1400)) ||
      (value.has_more && !value.next_cursor) ||
      (!value.has_more && value.next_cursor !== null)) {
    throw new Error('Resposta da caixa de entrada inválida.');
  }
  const seen = new Set<string>();
  const items: InboxNotification[] = value.items.map(item => {
    if (!validObject(item) || !uuid(item.id) || seen.has(item.id) ||
        !['SELF_TEST','SECURITY_SESSION_ALERT','CONTRIBUTION_DUE_INFO'].includes(String(item.kind)) ||
        typeof item.title !== 'string' || !item.title || item.title.length > 100 ||
        typeof item.message !== 'string' || !item.message || item.message.length > 280 ||
        !when(item.created_at) ||
        (item.read_at !== null && !when(item.read_at))) {
      throw new Error('Registro de notificação incompatível com o contrato.');
    }
    seen.add(item.id);
    return {
      id:item.id, kind:item.kind as InboxNotification['kind'],
      title:item.title,message:item.message,
      created_at:item.created_at,read_at:item.read_at,
    };
  });
  return {
    items,unread_count:value.unread_count as number,
    has_more:value.has_more,next_cursor:value.next_cursor as string | null,
  };
}

async function call(path: string, method:'GET'|'POST'='GET'): Promise<any> {
  const base = getApiBaseUrl();
  const snapshot = authService.captureSession();
  if (!base || !snapshot.token) throw new Error('Sessão ou servidor local indisponível.');
  let response: Response;
  try {
    response = await fetch(base + path, {
      method,
      headers:{
        Authorization:'Bearer '+snapshot.token,
        'X-Requested-With':'XMLHttpRequest','Cache-Control':'no-store',
      },
      cache:'no-store',credentials:'include',
    });
  } catch {
    throw new Error('Não foi possível conectar à FastAPI local. Confira o Termux.');
  }
  if (!authService.isSessionSnapshotCurrent(snapshot)) {
    throw new Error('A sessão mudou. Reabra as notificações.');
  }
  if (response.status === 401) {
    authService.invalidateSession();
    throw new Error('Sessão expirada; entre novamente.');
  }
  if (!response.ok) {
    if (response.status === 503) throw new Error('Inbox indisponível. Verifique a migração 031 e a API local.');
    if (response.status === 429) throw new Error('Limite de avisos de teste atingido. Tente depois.');
    throw new Error('Servidor recusou a operação de notificações ('+response.status+').');
  }
  const result = await response.json();
  if (!authService.isSessionSnapshotCurrent(snapshot)) {
    throw new Error('A sessão mudou durante a leitura.');
  }
  return result;
}
export async function inboxCapabilities(): Promise<boolean> {
  const data=await call('/api/v1/notifications/capabilities');
  if (!validObject(data)) throw new Error('Capacidades inválidas.');
  return data.inbox_read_available === true &&
         data.inbox_schema_connected === true &&
         data.in_app_delivery_active === true;
}
export async function fetchInbox(after: string | null=null): Promise<InboxPage> {
  const args=new URLSearchParams({limit:'20'});
  if(after) args.set('cursor',after);
  return parseInboxPage(await call('/api/v1/notifications?'+args.toString()));
}
export async function createSelfTest(): Promise<string> {
  const data=await call('/api/v1/notifications/self-test','POST');
  if (!validObject(data) || !uuid(data.id) || data.kind !== 'SELF_TEST' ||
      data.channel !== 'IN_APP' ||
      data.external_send_authorized !== false ||
      data.financial_effect_authorized !== false) {
    throw new Error('Servidor não confirmou o teste interno.');
  }
  return data.id;
}
export async function acknowledgeInbox(id: string): Promise<'READ'|'ALREADY_READ'> {
  if (!uuid(id)) throw new Error('Identificador de aviso inválido.');
  const data=await call('/api/v1/notifications/'+id+'/read','POST');
  if (!validObject(data) || data.id!==id ||
      !['READ','ALREADY_READ'].includes(String(data.status)) ||
      data.financial_effect_authorized !== false) {
    throw new Error('Leitura não confirmada pelo servidor.');
  }
  return data.status as 'READ'|'ALREADY_READ';
}
