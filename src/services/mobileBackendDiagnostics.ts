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
 if(typeof baseUrl!=='string'||!baseUrl.trim())return {
  mobile:true,kind:'BLOCKED',label:'API móvel não configurada',
  description:'Este APK não possui endereço de API válido. Não é possível autenticar.'
 };
 let url:URL;
 try{url=new URL(baseUrl);}catch{return {
  mobile:true,kind:'BLOCKED',label:'Endereço da API inválido',
  description:'É necessário configurar um endereço de API seguro antes do login.'
 }}
 if(url.username||url.password||url.search||url.hash ||
    !['','/'].includes(url.pathname))return {
  mobile:true,kind:'BLOCKED',label:'Configuração de API rejeitada',
  description:'O endereço do servidor contém parâmetros não permitidos.'
 };
 if(url.protocol==='http:' && ['127.0.0.1','localhost','[::1]'].includes(url.hostname))
  return {
   mobile:true,kind:'LOCAL_DEBUG',label:'APK de homologação local',
   description:'Esta compilação procura a API no próprio celular. Não representa a hospedagem OCI. O login só pode funcionar com uma API local acessível.'
  };
 if(url.protocol==='https:' && url.hostname.includes('.') &&
    !['localhost','127.0.0.1','[::1]'].includes(url.hostname) &&
    !url.hostname.endsWith('.local')&&!url.hostname.endsWith('.invalid') &&
    !url.hostname.endsWith('.internal')&&!url.hostname.endsWith('.example'))
  return {
   mobile:true,kind:'REMOTE_HTTPS',label:'APK com API HTTPS remota',
   description:'Há um endereço HTTPS configurado. A conexão e a autenticação ainda precisam ser verificadas.'
  };
 return {
  mobile:true,kind:'BLOCKED',label:'Servidor móvel não autorizado',
  description:'Este endereço não é permitido para um APK de homologação segura.'
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
