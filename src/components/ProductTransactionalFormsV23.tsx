import React,{useEffect,useState} from 'react';
import {authService} from '../services/authService';
import type {Scope,Workspace} from '../services/productTransactionalBoundaryV23';
import {allowedKinds,prepareV23,type Kind,type Fields,type Prepared} from '../services/productTransactionalFormsV23';
import {productTransactionalApiV23 as api} from '../services/productTransactionalApiV23';
const labels:Record<Kind,string>={POLICY:'Configurar política e abertura',CONSENT:'Preparar aceite individual',ADMIT:'Preparar adesão',RECEIPT:'Preparar recebimento manual',CONFIRM:'Conferir recebimento',REVERSE:'Preparar compensação',CONTEST:'Preparar contestação',HOLD:'Preparar reserva gerencial',RELEASE:'Preparar liberação de reserva'};
const fields:Record<Kind,string[]>={POLICY:['start','first_due','last_due','closing','quota','admin_pct','late_days','late_competences','mode','document_id'],CONSENT:['cycle_id','policy_hash','joined','quotas'],ADMIT:['cycle_id','membership_id','joined','quotas'],RECEIPT:['contribution_id','amount','method','occurred','reference','evidence_ref'],CONFIRM:['receipt_id','occurred','evidence_ref'],REVERSE:['receipt_id','occurred','evidence_ref'],CONTEST:['receipt_id','occurred','evidence_ref'],HOLD:['cycle_id','amount','reason'],RELEASE:['cycle_id','related_hold','amount','reason']};
const title:Record<string,string>={start:'Início',first_due:'Primeiro vencimento',last_due:'Último vencimento',closing:'Encerramento',quota:'Valor por cota (R$)',admin_pct:'Remuneração do administrador (%)',late_days:'Dias de atraso',late_competences:'Competências em atraso',mode:'Modo de gestão',document_id:'ID do Contrato B publicado',cycle_id:'ID do ciclo',policy_hash:'SHA-256 da política',joined:'Ingresso',quotas:'Cotas',membership_id:'ID do vínculo do membro',contribution_id:'ID da contribuição',amount:'Valor (R$)',method:'Meio externo de recebimento',occurred:'Data do fato',reference:'Referência do recebimento',evidence_ref:'Referência da evidência',receipt_id:'ID do recibo',reason:'Justificativa',related_hold:'ID da reserva original'};
const dateFields=new Set(['start','first_due','last_due','closing','joined','occurred']);
const field='w-full min-h-11 rounded border border-slate-300 bg-white p-2 text-sm';
const button='min-h-11 rounded-lg border border-emerald-700 px-3 py-2 text-sm font-semibold disabled:opacity-50';
export function ProductTransactionalFormsV23({scope,cycle,workspace}:{scope:Scope;cycle:string;workspace:Workspace|null}){
 const kinds=allowedKinds(scope),[kind,setKind]=useState<Kind>(kinds[0]),[draft,setDraft]=useState<Fields>({}),[accepted,setAccepted]=useState(false),[prepared,setPrepared]=useState<Prepared|null>(null),[msg,setMsg]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{const reset=()=>{setDraft({});setAccepted(false);setPrepared(null);setMsg('');setBusy(false);};reset();return authService.subscribe(reset);},[scope.userId,scope.tenantId,scope.role,cycle]);
 function edit(k:string,v:string){setDraft(old=>({...old,[k]:v}));setPrepared(null);setAccepted(false);setMsg('');}
 function value(k:string){if(k==='cycle_id')return cycle;if(k==='policy_hash')return workspace?.policy.policy_hash??'';return draft[k]??'';}
 function prepare(){
  try{const snapshot=authService.captureSession(),u=authService.getUser();
   if(!u||u.id!==scope.userId||u.tenantId!==scope.tenantId||u.role!==scope.role||!authService.isSessionSnapshotCurrent(snapshot))throw Error('Sessão alterada.');
   const p=prepareV23(scope,kind,Object.fromEntries(fields[kind].map(k=>[k,value(k)])),crypto.randomUUID(),accepted);
   setPrepared(p);setMsg('Dados conferidos localmente. Não enviados; nenhum registro confirmado.');
  }catch(e){setPrepared(null);setMsg(e instanceof Error?e.message:'Dados inválidos.');}
 }
 async function check(){
  const snapshot=authService.captureSession();setBusy(true);
  try{await api.capabilities(scope);if(authService.isSessionSnapshotCurrent(snapshot))setMsg('Servidor mantém gravações V2.3 bloqueadas. Nenhuma operação enviada.');}
  catch{if(authService.isSessionSnapshotCurrent(snapshot))setMsg('Servidor não confirmou disponibilidade. Nenhuma operação enviada.');}
  finally{if(authService.isSessionSnapshotCurrent(snapshot))setBusy(false);}
 }
 return <section className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-3" aria-label="Preparação de formulários V2.3">
  <h4 className="font-semibold text-emerald-950">Preparação de operações V2.3</h4>
  <p className="text-xs">Somente conferência local. Não insira comprovantes, dados pessoais ou segredos reais. Nenhum aceite jurídico, lançamento, pagamento ou reserva é executado. IDs devem ser conferidos com o servidor quando a operação for autorizada.</p>
  <label className="block text-sm">Operação<select className={field} value={kind} onChange={e=>{setKind(e.target.value as Kind);setDraft({});setPrepared(null);setAccepted(false);setMsg('');}}>{kinds.map(k=><option key={k} value={k}>{labels[k]}</option>)}</select></label>
  {fields[kind].map(k=><label key={k} className="block text-sm">{title[k]}
   {k==='mode'||k==='method'?<select className={field} value={value(k)} onChange={e=>edit(k,e.target.value)}><option value="">Selecione</option>{(k==='mode'?['MANUAL','MERCADO_PAGO','HYBRID']:['DINHEIRO','PIX_EXTERNO','TRANSFERENCIA','DEPOSITO']).map(o=><option key={o}>{o}</option>)}</select>:
   k==='contribution_id'&&workspace?<select className={field} value={value(k)} onChange={e=>edit(k,e.target.value)}><option value="">Selecione a competência</option>{workspace.items.map(o=><option key={o.contribution_id} value={o.contribution_id}>{o.due_date} · {o.contribution_id}</option>)}</select>:
   <input className={field} type={dateFields.has(k)?'date':'text'} maxLength={160} readOnly={k==='cycle_id'||k==='policy_hash'} value={value(k)} onChange={e=>edit(k,e.target.value)}/>}
  </label>)}
  <label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e=>{setAccepted(e.target.checked);setPrepared(null);setMsg('');}}/> Conferi os campos para preparação local, sem aceite ou gravação real.</label>
  <div className="flex flex-wrap gap-2"><button type="button" className={button} disabled={!accepted||busy} onClick={prepare}>Conferir dados</button><button type="button" className={button} disabled={!prepared||busy} onClick={()=>void check()}>Verificar disponibilidade no servidor</button></div>
  {prepared&&<p className="text-xs">Formulário preparado; pendente de autorização do servidor. A prévia contratual definitiva depende de hash retornado pela API.</p>}
  {msg&&<p role="status" className="text-sm">{msg}</p>}
 </section>;
}
