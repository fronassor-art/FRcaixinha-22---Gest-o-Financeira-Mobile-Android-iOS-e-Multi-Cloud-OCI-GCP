import React,{useEffect,useRef,useState} from 'react';
import {authService} from '../services/authService';
import {masterInviteForm,memberInviteForm,adminBForm,registrationForm} from '../services/onboardingFormsV23';
import type {MasterScope,AdminScope} from '../services/onboardingReadbackV23';
type Audience='MASTER'|'TENANT_ADMIN'|'INVITED';
type Mode='INVITE_ADMIN'|'INVITE_MEMBER'|'ACCEPT_B'|'REGISTER_ADMIN'|'REGISTER_MEMBER';
const modes:Record<Audience,readonly Mode[]>={MASTER:['INVITE_ADMIN'],TENANT_ADMIN:['ACCEPT_B','INVITE_MEMBER'],INVITED:['REGISTER_ADMIN','REGISTER_MEMBER']};
const labels:Record<Mode,string>={INVITE_ADMIN:'Convite do administrador',INVITE_MEMBER:'Convite do membro',ACCEPT_B:'Conferência do Contrato B',REGISTER_ADMIN:'Cadastro de administrador',REGISTER_MEMBER:'Cadastro de membro'};
const id=(n:number)=>'aaaaaaaa-aaaa-4aaa-8aaa-'+String(n).padStart(12,'0');
const master:MasterScope={userId:id(1),tenantId:null,role:'MASTER'};
const admin:AdminScope={userId:id(2),tenantId:id(3),role:'TENANT_ADMIN'};
const identity={name:'Pessoa fictícia de homologação',cpf:'52998224725',phone:'11999990000',password:'M41440-Sintetico-Only!',confirm_password:'M41440-Sintetico-Only!'};
const field='w-full min-h-11 rounded border border-slate-300 bg-white p-2 text-sm';
const btn='min-h-11 rounded border border-emerald-700 px-3 text-sm disabled:opacity-50';
async function specimen(mode:Mode){
 const kind=mode==='INVITE_ADMIN'||mode==='REGISTER_ADMIN'?'PLATFORM_LICENSE':'TENANT_MEMBERSHIP';
 const text=kind==='PLATFORM_LICENSE'?'Exemplo local A. Licença de software, sem contratação ou pagamento.':'Exemplo local B. Política de ciclo e adesão, sem efeito jurídico.';
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
 return {document_id:id(kind==='PLATFORM_LICENSE'?4:5),kind,version:'ENSAIO-LOCAL-M41440',document_hash:hash,text,ci_only:true};
}
type Specimen=Awaited<ReturnType<typeof specimen>>;
export function OnboardingFormsV23({audience}:{audience:Audience}){
 const [mode,setMode]=useState<Mode>(modes[audience][0]),[doc,setDoc]=useState<Specimen|null>(null),[accepted,setAccepted]=useState(false),[quota,setQuota]=useState('2'),[joined,setJoined]=useState('2027-01-10'),[reissue,setReissue]=useState(false),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const seq=useRef(0),working=useRef(false);
 function reset(){seq.current++;working.current=false;setDoc(null);setAccepted(false);setNotice('');setBusy(false);setQuota('2');setJoined('2027-01-10');setReissue(false);}
 useEffect(()=>{reset();setMode(modes[audience][0]);const stop=authService.subscribe(reset);return()=>{seq.current++;working.current=false;stop();};},[audience]);
 async function begin(){
  reset();const n=++seq.current;setBusy(true);
  try{const d=await specimen(mode);if(n===seq.current)setDoc(d);}
  catch{if(n===seq.current)setNotice('Integridade local indisponível. Nenhuma operação efetuada.');}
  finally{if(n===seq.current)setBusy(false);}
 }
 async function prepare(){
  if(!doc||!accepted||busy||working.current)return;
  working.current=true;const n=++seq.current;setBusy(true);setNotice('');
  try{
   const scope=mode==='INVITE_ADMIN'?master:admin;
   const raw={user_id:scope.userId,tenant_id:scope.tenantId,role:scope.role,document:doc};
   if(mode==='INVITE_ADMIN')await masterInviteForm(master,raw,doc.document_id,{email:'administrador@example.invalid',master_password:identity.password,confirmed:accepted});
   else if(mode==='ACCEPT_B')await adminBForm(admin,raw,doc.document_id,accepted);
   else if(mode==='INVITE_MEMBER')memberInviteForm(admin,id(6),{email:'membro@example.invalid',joined,quotas:Number(quota),previous_id:reissue?id(8):null,confirmed:accepted});
   else{
    const isAdmin=mode==='REGISTER_ADMIN';
    const terms={invitation_id:id(7),role:isAdmin?'TENANT_ADMIN':'TENANT_MEMBER',document:doc,terms:isAdmin?null:{cycle:id(6),policy_hash:'a'.repeat(64),joined:'2027-01-10',quotas:2}};
    const form=await registrationForm(terms,{invitation_token:'x'.repeat(32),verification_token:'y'.repeat(32)});
    if(n!==seq.current){form.discard();return;}
    form.prepare({...identity,accepted,...(isAdmin?{tenant_name:'Caixinha fictícia'}:{})});
    form.discard();
   }
   if(n===seq.current){setNotice('Preparação local validada e descartada. Nenhum convite, cadastro, aceite ou pagamento enviado.');setAccepted(false);setDoc(null);}
  }catch{if(n===seq.current){setAccepted(false);setNotice('Formulário inválido. Revise os dados sintéticos; nenhuma operação efetuada.');}}
  finally{if(n===seq.current){working.current=false;setBusy(false);}}
 }
 const registering=mode==='REGISTER_ADMIN'||mode==='REGISTER_MEMBER';
 return <section aria-label="Ensaio local de formulários" className="rounded border bg-white p-3 space-y-2 text-slate-900">
  <h5 className="font-semibold">Formulários de contratação V2.3</h5>
  <p className="text-xs">Ensaio local explícito, sem servidor, com dados exclusivamente fictícios. Não use dados pessoais reais. Nenhum envio ou consentimento jurídico.</p>
  <label className="block text-sm">Etapa<select className={field} value={mode} onChange={e=>{reset();setMode(e.target.value as Mode);}}>{modes[audience].map(m=><option key={m} value={m}>{labels[m]}</option>)}</select></label>
  <button type="button" className={btn} disabled={busy} onClick={()=>void begin()}>Iniciar ensaio sintético</button>
  {doc&&<>
    <article className="text-sm"><p className="font-semibold">{doc.version}</p><p>{doc.text}</p><p className="break-all text-xs">{doc.document_hash}</p></article>
    {mode==='INVITE_ADMIN'&&<><label className="block text-sm">E-mail fictício<input className={field} value="administrador@example.invalid" readOnly autoComplete="off"/></label><label className="block text-sm">Reautenticação fictícia<input className={field} type="password" value={identity.password} readOnly autoComplete="off"/></label></>}
    {mode==='INVITE_MEMBER'&&<><label className="block text-sm">E-mail fictício<input className={field} value="membro@example.invalid" readOnly autoComplete="off"/></label><label className="block text-sm">Ingresso simulado<input className={field} type="date" value={joined} onChange={e=>{setJoined(e.target.value);setAccepted(false);}}/></label><label className="block text-sm">Cotas simuladas<input className={field} type="number" min={1} max={400} step={1} value={quota} onChange={e=>{setQuota(e.target.value);setAccepted(false);}}/></label><label className="flex gap-2 text-sm"><input type="checkbox" checked={reissue} onChange={e=>{setReissue(e.target.checked);setAccepted(false);}}/> Ensaio de reemissão com referência anterior fictícia</label></>}
    {registering&&<>
     <p className="text-xs">Duas provas fictícias independentes. Não utiliza o token do link real.</p>
     <label className="block text-sm">Nome fictício<input className={field} value={identity.name} readOnly autoComplete="off"/></label>
     <label className="block text-sm">CPF de teste<input className={field} value="***.***.***-25" readOnly autoComplete="off"/></label>
     <label className="block text-sm">Telefone fictício<input className={field} value="(**) *****-0000" readOnly autoComplete="off"/></label>
     <label className="block text-sm">Senha fictícia<input type="password" className={field} value={identity.password} readOnly autoComplete="off"/></label>
     <label className="block text-sm">Confirmação fictícia<input type="password" className={field} value={identity.confirm_password} readOnly autoComplete="off"/></label>
     {mode==='REGISTER_ADMIN'?<label className="block text-sm">Caixinha fictícia<input className={field} value="Caixinha fictícia" readOnly/></label>:<p className="text-sm">Ciclo fictício · ingresso 10/01/2027 · 2 cotas (vinculados ao convite).</p>}
    </>}
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> Conferi os dados e o instrumento somente para este ensaio local.</label>
    <button type="button" className={btn} disabled={busy||!accepted} onClick={()=>void prepare()}>Validar preparação local</button>
    <button type="button" className={btn} onClick={reset}>Descartar ensaio</button>
  </>}
  {notice&&<p className="text-sm" role="status">{notice}</p>}
 </section>;
}
