/** Dados de erro HTTP são não confiáveis; mensagem de backend nunca vira autorização.
 * Sem leitura de armazenamento local e sem alteração financeira ou de sessão.
 */
type ErrorEnvelope={message?:string;detail?:string;code?:string};
const isRecord=(v:unknown):v is Record<string,unknown> =>
  typeof v==='object'&&v!==null&&!Array.isArray(v);

/** Evita exibir HTML, stack trace, segredos e payloads arbitrários no painel. */
function safeText(value:unknown):string|undefined {
  if(typeof value!=='string')return undefined;
  const text=value.trim();
  if(text.length===0||text.length>180||
     /[\u0000-\u001F\u007F<>]/.test(text)||
     /(?:bearer\s|token|password|secret|senha|api[_ -]?key|traceback|\/data\/data\/|postgresql:\/\/)/i.test(text)) {
    return undefined;
  }
  return text;
}

export function parseApiErrorEnvelope(raw:unknown):ErrorEnvelope {
  if(!isRecord(raw))return {};
  const nested=isRecord(raw.detail)?raw.detail:null;
  const message=safeText(raw.message) || safeText(nested?.message);
  const detail=safeText(raw.detail) || safeText(nested?.detail) ||
    safeText(nested?.message);
  const code=typeof raw.code==='string'&&/^[A-Z][A-Z0-9_]{2,63}$/.test(raw.code)
    ?raw.code:undefined;
  return {message,detail,code};
}

export class ApiResponseIntegrityError extends Error {
  readonly code='INVALID_BACKEND_RESPONSE';
  constructor(message='Resposta inválida do servidor. Nenhum dado foi confirmado.'){
    super(message);
    this.name='ApiResponseIntegrityError';
  }
}
