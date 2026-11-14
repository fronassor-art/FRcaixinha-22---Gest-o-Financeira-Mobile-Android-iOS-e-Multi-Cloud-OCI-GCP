/** FR Finance M37980: public API health probe on Android/Capacitor.
 *
 * Tests reachability and checks the public FR Finance/FastAPI contract only.
 * This cannot attest a login, TLS identity, OCI tenancy, RLS, payments or
 * authorization for production. Never sends auth cookies or bearer tokens.
 */
import {classifyApiOrigin} from './apiOriginPolicy';

export type MobileHealthCheck = Readonly<{
  ok: boolean;
  databaseConfigured: boolean;
  code: 'URL_BLOCKED' | 'NETWORK_ERROR' | 'HTTP_ERROR' |
        'INVALID_RESPONSE' | 'BACKEND_ONLY' | 'BACKEND_WITH_DB_DECLARED';
  message: string;
}>;

const blocked=(code:MobileHealthCheck['code'],message:string):MobileHealthCheck=>({
  ok:false,databaseConfigured:false,code,message,
});

export async function probeMobileBackendHealth(
  native:boolean,baseUrl:string,
  requester:typeof fetch=fetch,
):Promise<MobileHealthCheck>{
  const parsed=classifyApiOrigin(baseUrl);
  if(parsed.kind==='BLOCKED' && (native || baseUrl!==''))
    return blocked('URL_BLOCKED',
      'Endereço da API bloqueado. Verifique a configuração do APK.');
  const endpoint=(parsed.kind==='BLOCKED'?'':parsed.origin)+'/api/health';
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),5000);
  try{
    const response=await requester(endpoint,{
      method:'GET',
      headers:{'Accept':'application/json','Cache-Control':'no-store'},
      cache:'no-store',credentials:'omit',redirect:'error',
      signal:controller.signal,
    });
    if(!response.ok)return blocked('HTTP_ERROR',
      'Diagnóstico da API indisponível (HTTP '+response.status+').');
    const media=response.headers.get('content-type')||'';
    const length=response.headers.get('content-length');
    if(!/^\s*application\/json(?:\s*;|$)/i.test(media) ||
       (length!==null && (!/^\d+$/.test(length) || Number(length)>2048)))
      return blocked('INVALID_RESPONSE',
        'A API respondeu, mas o formato do diagnóstico não é confiável.');
    const raw=await response.text();
    if(raw.length>2048)return blocked('INVALID_RESPONSE',
      'A resposta da API excedeu o limite permitido.');
    let data:unknown;
    try {data=JSON.parse(raw);} catch {
      return blocked('INVALID_RESPONSE',
        'A resposta de diagnóstico não contém JSON válido.');
    }
    if(!data||typeof data!=='object'||Array.isArray(data))
      return blocked('INVALID_RESPONSE','Resposta inválida do servidor.');
    const health=data as Record<string,unknown>;
    if(health.status!=='ONLINE' || health.app!=='FR Finance' ||
       health.framework!=='FastAPI (Python)' ||
       typeof health.database_configured!=='boolean')
      return blocked('INVALID_RESPONSE',
        'O servidor não confirmou o contrato público do FR Finance.');
    if(!health.database_configured)return {
      ok:true,code:'BACKEND_ONLY',databaseConfigured:false,
      message:'FastAPI do FR Finance respondeu, mas declarou banco não configurado. O login continua indisponível.',
    };
    return {
      ok:true,code:'BACKEND_WITH_DB_DECLARED',databaseConfigured:true,
      message:'FastAPI do FR Finance respondeu e declarou banco configurado. Login, sessões, RLS e produção ainda exigem testes reais.',
    };
  }catch{
    return blocked('NETWORK_ERROR',
      'Não foi possível consultar a API neste dispositivo.');
  }finally{
    clearTimeout(timeout);
  }
}
