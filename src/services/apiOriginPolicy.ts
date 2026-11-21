/** FR Finance M37974: única política de origem para autenticação e diagnóstico.
 * VITE_API_URL válido não significa API alcançável nem staging homologado.
 */
export type ApiOriginKind = 'BLOCKED' | 'LOCAL_DEBUG' | 'REMOTE_HTTPS';
export type ApiOriginDecision = Readonly<{kind: ApiOriginKind; origin: string}>;
const BLOCKED: ApiOriginDecision = Object.freeze({kind:'BLOCKED', origin:''});
const LOOPBACK = new Set(['127.0.0.1','localhost','[::1]']);
const RESERVED = ['.local','.localhost','.invalid','.internal','.example','.test'];
const DNS = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;

export function classifyApiOrigin(value:unknown):ApiOriginDecision {
  if(typeof value!=='string'||!value||value!==value.trim()||
     value.length>2048||/[\u0000-\u0020\u007f\\]/.test(value)) return BLOCKED;
  let url:URL;
  try {url=new URL(value);} catch {return BLOCKED;}
  if(!url.hostname||url.username||url.password||url.search||url.hash||
     !['','/'].includes(url.pathname))return BLOCKED;
  const host=url.hostname.toLowerCase();
  if(url.protocol==='http:'&&LOOPBACK.has(host))
    return {kind:'LOCAL_DEBUG',origin:url.origin};
  if(url.protocol!=='https:'||LOOPBACK.has(host)||!DNS.test(host)||
     host.endsWith('.')||RESERVED.some(suffix=>host.endsWith(suffix)))
    return BLOCKED;
  return {kind:'REMOTE_HTTPS',origin:url.origin};
}
