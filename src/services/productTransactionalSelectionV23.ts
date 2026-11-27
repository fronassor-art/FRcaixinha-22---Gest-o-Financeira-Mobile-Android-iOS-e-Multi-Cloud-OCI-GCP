/** M41380: selected references are readback, never proof of authorization or a write. */
import {uuid,type Scope,type Workspace,type FormOptions,type OptionKind} from './productTransactionalBoundaryV23';
import {prepareV23,cents,scopeKey,type Fields,type Kind} from './productTransactionalFormsV23';
export const optionKind=(k:Kind):OptionKind|null=>k==='POLICY'?'DOCUMENT':k==='ADMIT'||k==='CONFIRM'||k==='REVERSE'||k==='CONTEST'||k==='RELEASE'?k:null;
export const optionField=(k:Kind):string=>k==='POLICY'?'document_id':k==='ADMIT'?'membership_id':k==='RELEASE'?'related_hold':'receipt_id';
const require=(v:unknown)=>{if(!v)throw Error('Seleção não conferida ou desatualizada. Consulte novamente o servidor.');};
export function prepareSelectedV23(s:Scope,k:Kind,f:Fields,request:string,accepted:boolean,cycle:string,ws:Workspace|null,options:FormOptions|null){
 const fields={...f};
 if(k!=='POLICY'){
  require(ws&&scopeKey(ws.scope)===scopeKey(s)&&ws.cycle_id===uuid(cycle));
  fields.cycle_id=cycle;fields.policy_hash=ws!.policy.policy_hash;
 }
 const ok=optionKind(k);
 if(ok){
  require(options&&scopeKey(options.scope)===scopeKey(s)&&options.kind===ok&&options.cycle_id===(ok==='DOCUMENT'?null:uuid(cycle)));
  const item=options!.items.find(x=>x.id===fields[optionField(k)]);
  if(!item)throw Error('Selecione uma referência disponível no servidor.');
  if(k==='ADMIT'){
   require(typeof item.date==='string'&&typeof item.quotas==='number');
   fields.joined=item.date!;fields.quotas=String(item.quotas);
  }else if(k==='RELEASE'){
   require(typeof item.cents==='number');fields.amount=(item.cents!/100).toFixed(2);
  }else if(k==='CONFIRM'||k==='REVERSE'||k==='CONTEST'){
   require(typeof item.date==='string'&&fields.occurred>=item.date&&fields.occurred<=ws!.policy.closing);
  }
 }
 if(k==='RECEIPT'){
  const row=ws!.items.find(x=>x.contribution_id===fields.contribution_id);
  require(row&&ws!.policy.mode!=='MERCADO_PAGO'&&cents(fields.amount)<=row.due_cents-row.paid_cents-row.pending_manual_cents&&fields.occurred>=ws!.policy.start_date&&fields.occurred<=ws!.policy.closing);
 }
 if(k==='HOLD')require(ws!.reserves&&cents(fields.amount,100000000000)<=ws!.reserves.unreserved_documented_cents);
 if(k==='CONSENT')require(fields.joined>=ws!.policy.start_date&&fields.joined<=ws!.policy.last_due);
 return prepareV23(s,k,fields,request,accepted);
}
