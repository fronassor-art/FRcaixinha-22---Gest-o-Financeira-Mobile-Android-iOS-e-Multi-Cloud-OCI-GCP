/** FR Finance: diagnóstico explícito de push Android no APK de homologação.
 * Nenhum token sai do aparelho, é persistido, logado ou enviado a terceiros
 * por este serviço. O registro no FCM é iniciado somente por ação do membro.
 * Este diagnóstico NÃO comprova transporte ou entrega de push.
 */
import {Capacitor} from '@capacitor/core';
import {PushNotifications} from '@capacitor/push-notifications';

export type PushDiagnosticPhase =
  'UNSUPPORTED_PLATFORM' | 'DISABLED_BY_BUILD' | 'CONSENT_REQUIRED' |
  'PERMISSION_DENIED' | 'REGISTERING' | 'TOKEN_RECEIVED_NOT_STORED' |
  'REGISTRATION_FAILED' | 'NOTIFICATION_RECEIVED' | 'READY_TO_REGISTER';

export interface PushDiagnostic {
  phase:PushDiagnosticPhase;
  detail:string;
  stop:()=>Promise<void>;
}

const noop=async()=>{};
function result(phase:PushDiagnosticPhase,detail:string):PushDiagnostic{
  return {phase,detail,stop:noop};
}

/** Must be called by an explicit user click, never an effect/background job. */
export async function diagnoseAndroidPush(
  optIn:boolean,
  notify:(phase:PushDiagnosticPhase,detail:string)=>void,
):Promise<PushDiagnostic>{
  if(!Capacitor.isNativePlatform() || Capacitor.getPlatform()!=='android'){
    return result('UNSUPPORTED_PLATFORM','Push nativo precisa de APK Android.');
  }
  if(import.meta.env.VITE_FR_FINANCE_PUSH_DIAGNOSTIC!=='YES'){
    return result('DISABLED_BY_BUILD','Diagnóstico push não autorizado neste build.');
  }
  if(optIn!==true){
    return result('CONSENT_REQUIRED','Ative voluntariamente a preferência Push primeiro.');
  }
  let permission=await PushNotifications.checkPermissions();
  if(permission.receive!=='granted'){
    permission=await PushNotifications.requestPermissions();
  }
  if(permission.receive!=='granted'){
    return result('PERMISSION_DENIED','Permissão de notificação negada pelo Android.');
  }
  const handlers=await Promise.all([
    PushNotifications.addListener('registration',(_token)=>{
      // NEVER echo, store, send or log the raw FCM token.
      notify('TOKEN_RECEIVED_NOT_STORED',
        'FCM retornou um token ao aparelho. Ele não foi armazenado ou enviado.');
    }),
    PushNotifications.addListener('registrationError',(_error)=>{
      notify('REGISTRATION_FAILED','FCM ainda não está configurado ou respondeu com erro.');
    }),
    PushNotifications.addListener('pushNotificationReceived',(_notification)=>{
      notify('NOTIFICATION_RECEIVED','O aparelho recebeu um aviso de teste autorizado.');
    }),
    PushNotifications.addListener('pushNotificationActionPerformed',(_event)=>{
      notify('NOTIFICATION_RECEIVED','Aviso aberto no aplicativo; consulte Minhas Oportunidades.');
    }),
  ]);
  const stop=async()=>{await Promise.all(handlers.map(h=>h.remove()));};
  try{
    notify('REGISTERING','Solicitando registro nativo, sem enviar campanha ou token à API.');
    await PushNotifications.register();
    return {phase:'READY_TO_REGISTER',
      detail:'Registro solicitado ao Android. Entrega real depende de Firebase e provedor.',
      stop};
  }catch(_error){
    await stop();
    return result('REGISTRATION_FAILED','Registro FCM indisponível neste APK.');
  }
}
