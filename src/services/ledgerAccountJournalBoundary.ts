/** FR Caixinha: apenas o histórico parcial de UMA conta autorizada. */
export interface LedgerAccountJournalEntry {
 id:string;transaction_id:string;transaction_date:string;description:string;
 reference_id:string;entry_type:'DR'|'CR';amount_cents:number;
}
export interface LedgerAccountJournalPage {
 source:'POSTGRESQL_RLS';tenant_id:string;account_id:string;page:number;
 page_size:number;has_more:boolean;complete_ledger_verified:false;
 bank_reconciled:false;financial_closing_authorized:false;
 entries:LedgerAccountJournalEntry[];
}
const UUID=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const exact=(v:Record<string,unknown>,keys:string[])=>Object.keys(v).length===keys.length&&
 Object.keys(v).every(k=>keys.includes(k));
const fields=['source','tenant_id','account_id','page','page_size','has_more',
 'complete_ledger_verified','bank_reconciled','financial_closing_authorized','entries'];
const entryFields=['id','transaction_id','transaction_date','description',
 'reference_id','entry_type','amount_cents','amount_brl'];
const str=(v:unknown,max:number)=>typeof v==='string'&&v.trim().length>0&&v.length<=max&&
 !/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v);
const date=(v:unknown)=>typeof v==='string'&&v.length<=40&&
 /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$/.test(v)&&
 Number.isFinite(Date.parse(v));
const money=(raw:unknown,cents:number)=>{
 if(typeof raw!=='string'&&typeof raw!=='number')return false;
 if(typeof raw==='string'&&!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(raw))return false;
 return Number.isFinite(Number(raw))&&Math.abs(Number(raw)*100-cents)<1e-6;
};
export function parseLedgerAccountJournalPage(
 raw:unknown,tenantId:string,accountId:string,page:number,pageSize:number
):LedgerAccountJournalPage {
 if(!UUID.test(tenantId)||!UUID.test(accountId)||
    !Number.isSafeInteger(page)||page<1||page>1000||
    !Number.isSafeInteger(pageSize)||pageSize<1||pageSize>50||
    !record(raw)||!exact(raw,fields)||
    raw.source!=='POSTGRESQL_RLS'||raw.tenant_id!==tenantId||
    raw.account_id!==accountId||raw.page!==page||raw.page_size!==pageSize||
    typeof raw.has_more!=='boolean'||raw.complete_ledger_verified!==false||
    raw.bank_reconciled!==false||raw.financial_closing_authorized!==false||
    !Array.isArray(raw.entries)||raw.entries.length>pageSize)
    throw Error('Página contábil incompatível com a sessão ou o contrato.');
 const ids=new Set<string>();
 const entries:LedgerAccountJournalEntry[]=raw.entries.map((e:unknown)=>{
  if(!record(e)||!exact(e,entryFields)||typeof e.id!=='string'||
     typeof e.transaction_id!=='string'||!UUID.test(e.id)||
     !UUID.test(e.transaction_id)||!date(e.transaction_date)||
     !str(e.description,500)||!str(e.reference_id,200)||
     (e.entry_type!=='DR'&&e.entry_type!=='CR')||
     typeof e.amount_cents!=='number'||!Number.isSafeInteger(e.amount_cents)||
     e.amount_cents<=0||e.amount_cents>100000000000||
     !money(e.amount_brl,e.amount_cents))
      throw Error('Lançamento contábil inválido.');
  const id=(e.id as string).toLowerCase();
  if(ids.has(id))throw Error('Lançamento repetido.');
  ids.add(id);
  return {id:e.id as string,transaction_id:e.transaction_id as string,
    transaction_date:e.transaction_date as string,
    description:e.description as string,reference_id:e.reference_id as string,
    entry_type:e.entry_type as 'DR'|'CR',amount_cents:e.amount_cents as number};
 });
 if(raw.has_more&&entries.length!==pageSize)
   throw Error('Indicador de próxima página incompatível.');
 return {source:'POSTGRESQL_RLS',tenant_id:tenantId,account_id:accountId,
  page,page_size:pageSize,has_more:raw.has_more as boolean,
  complete_ledger_verified:false,bank_reconciled:false,
  financial_closing_authorized:false,entries};
}
