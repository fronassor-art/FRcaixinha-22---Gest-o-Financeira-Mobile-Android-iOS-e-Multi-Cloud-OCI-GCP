import {classifyApiOrigin} from './apiOriginPolicy';

/** M37447: distinguishes an installable APK from a remotely usable backend.
 * No network requests here and never echoes a URL, token or credential.
 */
export type MobileBackendProfile={
 mobile:boolean;
 kind:'WEB'|'BLOCKED'|'LOCAL_DEBUG'|'REMOTE_HTTPS';
 label:string;
 description:string;
};
export function inspectMobileBackend(native:boolean,baseUrl:string):MobileBackendProfile{
 if(native!==true)return {
  mobile:false,kind:'WEB',label:'Ambiente web',
  description:'O ambiente web exige autenticação no servidor.'
 };
 const decision=classifyApiOrigin(baseUrl);
 if(decision.kind==='LOCAL_DEBUG')return {
  mobile:true,kind:'LOCAL_DEBUG',label:'APK de homologação local',
  description:'Esta compilação procura a API no próprio celular. Não representa a hospedagem OCI. O login só pode funcionar com uma API local acessível.'
 };
 if(decision.kind==='REMOTE_HTTPS')return {
  mobile:true,kind:'REMOTE_HTTPS',label:'APK com API HTTPS remota',
  description:'Há um endereço HTTPS configurado. A conexão e a autenticação ainda precisam ser verificadas.'
 };
 return {
  mobile:true,kind:'BLOCKED',label:'Servidor móvel não autorizado',
  description:'O endereço da API não atende à política de segurança do APK.'
 };
}

export function interpretAuthenticationStatus(raw:unknown):string{
 if(!raw || typeof raw!=='object'||Array.isArray(raw))
  return 'Resposta do servidor inválida. Não foi iniciada uma sessão.';
 const status=raw as Record<string,unknown>;
 if(status.configured!==true||status.status==='BLOCKED_PENDING_CONFIG')
  return 'Servidor de autenticação não confirmado. Não use este APK para testes de login real.';
 if(status.requiresAuthentication!==true)
  return 'A resposta não confirmou a exigência de autenticação. Login permanece não homologado.';
 return 'O servidor respondeu à consulta de status. Login do administrador e acesso à caixinha ainda precisam ser testados.';
}
