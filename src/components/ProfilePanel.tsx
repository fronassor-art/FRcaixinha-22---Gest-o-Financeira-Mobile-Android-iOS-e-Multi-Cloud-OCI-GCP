import React,{useEffect,useRef,useState} from 'react';
import {Camera, Fingerprint, Trash2, UserRound, ShieldCheck} from 'lucide-react';
import type {AuthenticatedUser} from '../services/authService';
import {authService} from '../services/authService';
import {
  deviceAccountKey,isAndroidSecuritySupported,biometricAvailable,
  biometricEnabled,biometricChallenge,updateBiometricPreference,
  readPrivateAvatar,savePrivateAvatar,removePrivateAvatar,preparePrivateJpeg,
} from '../services/deviceSecurity';

interface Props {
 user:AuthenticatedUser;
 onClose:()=>void;
 onAvatarChanged:(src:string|null)=>void;
 onBiometricChanged:(enabled:boolean)=>void;
}
/** Profile data is cosmetic and stored encrypted ON THIS ANDROID ONLY.
 * Backend full_name is immutable here; no alternative identity is invented.
 */
export const ProfilePanel:React.FC<Props>=({
 user,onClose,onAvatarChanged,onBiometricChanged,
})=>{
 const accountKey=deviceAccountKey(user);
 const native=isAndroidSecuritySupported();
 const snapshot=authService.captureSession();
 const fileInput=useRef<HTMLInputElement>(null);
 const [picture,setPicture]=useState<string|null>(null);
 const [bioReady,setBioReady]=useState(false);
 const [bioEnabled,setBioEnabled]=useState(false);
 const [busy,setBusy]=useState(false);
 const [message,setMessage]=useState('');
 const context=[user.id,user.role,user.tenantId].join(':');
 useEffect(()=>{
   let active=true;
   setPicture(null);setBioReady(false);setBioEnabled(false);setMessage('');
   const guard=authService.captureSession();
   if(!accountKey||!native)return()=>{active=false;};
   void Promise.allSettled([
     readPrivateAvatar(accountKey),biometricAvailable(),biometricEnabled(accountKey),
   ]).then(results=>{
     if(!active||!authService.isSessionSnapshotCurrent(guard))return;
     if(results[0].status==='fulfilled')setPicture(results[0].value);
     if(results[1].status==='fulfilled')setBioReady(results[1].value);
     if(results[2].status==='fulfilled')setBioEnabled(results[2].value);
   });
   return()=>{active=false;};
 },[context,accountKey,native]);

 const applyPicture=async(file:File|undefined)=>{
   if(!file||busy||!accountKey)return;
   const guard=authService.captureSession();
   setBusy(true);setMessage('');
   try{
     const encoded=await preparePrivateJpeg(file);
     if(!authService.isSessionSnapshotCurrent(guard))return;
     await savePrivateAvatar(accountKey,encoded);
     if(!authService.isSessionSnapshotCurrent(guard))return;
     const photo='data:image/jpeg;base64,'+encoded;
     setPicture(photo);onAvatarChanged(photo);
     setMessage('Foto salva com criptografia apenas neste aparelho.');
   }catch(err){
     if(authService.isSessionSnapshotCurrent(guard))
       setMessage(err instanceof Error?err.message:'Não foi possível atualizar a foto.');
   }finally{
     if(authService.isSessionSnapshotCurrent(guard))setBusy(false);
     if(fileInput.current)fileInput.current.value='';
   }
 };
 const clearPhoto=async()=>{
   if(busy||!accountKey)return;
   const guard=authService.captureSession();
   setBusy(true);setMessage('');
   try{
     await removePrivateAvatar(accountKey);
     if(!authService.isSessionSnapshotCurrent(guard))return;
     setPicture(null);onAvatarChanged(null);
     setMessage('Foto excluída do armazenamento privado do Android.');
   }catch(err){
     if(authService.isSessionSnapshotCurrent(guard))
       setMessage(err instanceof Error?err.message:'Não foi possível excluir a foto.');
   }finally{if(authService.isSessionSnapshotCurrent(guard))setBusy(false);}
 };
 const toggleBiometrics=async()=>{
   if(busy||!accountKey)return;
   const guard=authService.captureSession();
   setBusy(true);setMessage('');
   try{
     if(!bioEnabled){
       if(!await biometricAvailable())
         throw new Error('Configure digital ou biometria forte no Android.');
       await biometricChallenge(accountKey);
     }
     if(!authService.isSessionSnapshotCurrent(guard))return;
     const newValue=await updateBiometricPreference(accountKey,!bioEnabled);
     if(!authService.isSessionSnapshotCurrent(guard))return;
     setBioEnabled(newValue);onBiometricChanged(newValue);
     setMessage(newValue
      ? 'Proteção biométrica ativada para retornar ao aplicativo.'
      : 'Proteção biométrica desativada neste aparelho.');
   }catch(err){
     if(authService.isSessionSnapshotCurrent(guard))
       setMessage(err instanceof Error?err.message:'Biometria não confirmada.');
   }finally{if(authService.isSessionSnapshotCurrent(guard))setBusy(false);}
 };
 if(user.role==='MASTER')return null;
 return <section aria-label="Meu perfil FR Finance"
   className="relative z-40 max-h-[65dvh] overflow-y-auto border-b border-amber-200/40 bg-[#eff7f0] px-4 py-5 text-emerald-950">
   <div className="mx-auto max-w-xl space-y-4">
     <div className="flex items-center justify-between gap-3">
       <h2 className="text-lg font-bold">Meu perfil</h2>
       <button type="button" onClick={onClose}
         className="min-h-10 rounded-lg border border-emerald-700 px-4">Fechar</button>
     </div>
     <div className="flex items-center gap-4">
       <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-[#c39d53] bg-[#0b4d35] text-amber-200">
         {picture?<img src={picture} alt="Minha foto de perfil" className="h-full w-full object-cover"/>:
           <UserRound className="h-9 w-9" aria-hidden="true"/>}
       </div>
       <div className="min-w-0">
         <p className="break-words text-base font-bold">{user.name}</p>
         <p className="text-sm">{user.role==='TENANT_ADMIN'?'Administrador da caixinha':'Membro da caixinha'}</p>
         <p className="break-all text-xs text-slate-600">{user.email}</p>
       </div>
     </div>
     <div className="space-y-2 rounded-xl border border-emerald-200 bg-white p-3">
       <h3 className="font-semibold">Minha foto</h3>
       <p className="text-xs text-slate-600">Foto privada, armazenada com criptografia no Android. Não é enviada ao servidor e não aparece em outros aparelhos.</p>
       <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp"
         aria-label="Escolher foto do perfil" className="sr-only"
         onChange={event=>void applyPicture(event.target.files?.[0])}/>
       <div className="flex flex-wrap gap-2">
         <button type="button" disabled={!native||busy||!accountKey}
           onClick={()=>fileInput.current?.click()}
           className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-emerald-600 px-3 disabled:opacity-50">
           <Camera className="h-4 w-4"/> Escolher foto
         </button>
         {picture&&<button type="button" disabled={busy}
           onClick={()=>void clearPhoto()}
           className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-rose-300 px-3 text-rose-800 disabled:opacity-50">
           <Trash2 className="h-4 w-4"/> Excluir foto
         </button>}
       </div>
     </div>
     <div className="space-y-2 rounded-xl border border-emerald-200 bg-white p-3">
       <h3 className="flex items-center gap-2 font-semibold"><Fingerprint className="h-5 w-5"/> Biometria</h3>
       <p className="text-xs text-slate-600">Use a digital ou biometria forte para desbloquear o aplicativo depois de deixá-lo em segundo plano. A senha e a verificação do servidor continuam obrigatórias para entrar em uma nova sessão.</p>
       <button type="button" disabled={!native||!bioReady||busy||!accountKey}
         onClick={()=>void toggleBiometrics()}
         aria-pressed={bioEnabled}
         className="min-h-11 rounded-lg border border-emerald-600 px-3 font-semibold disabled:opacity-50">
         {bioEnabled?'Desativar proteção biométrica':'Ativar proteção biométrica'}
       </button>
       {bioEnabled&&<p className="flex items-center gap-2 text-xs text-emerald-800">
         <ShieldCheck className="h-4 w-4"/> Biometria ativada neste dispositivo</p>}
     </div>
     {!native&&<p role="note" className="text-xs">Foto privada e biometria disponíveis apenas no aplicativo Android de homologação.</p>}
     {message&&<p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">{message}</p>}
   </div>
 </section>;
};
