/** FRcaixinha AI Studio: fronteira de apresentação do livro-razão. */
export interface DisplayLedgerAccount {
 id:string;tenant_id:string;account_code:string;account_name:string;
 account_type:string;balance_cents:number;
}
export interface DisplayLedgerEntry {
 id:string;account_id:string;account_name:string;
 entry_type:'DR'|'CR';amount_cents:number;
}
export interface DisplayLedgerTransaction {
 id:string;tenant_id:string;description:string;
 transaction_date:string;reference_id:string;entries:DisplayLedgerEntry[];
}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const record=(x:unknown):x is Record<string,unknown>=>
 x!==null&&typeof x==='object'&&!Array.isArray(x);
const only=(x:Record<string,unknown>,keys:readonly string[])=>
 Object.keys(x).every(k=>keys.includes(k));
const uuid=(x:unknown):x is string=>typeof x==='string'&&UUID.test(x);
const text=(x:unknown,max:number):x is string=>
 typeof x==='string'&&x.trim().length>0&&x.length<=max&&
 !/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(x);
const cents=(x:unknown,positive=false):x is number=>
 typeof x==='number'&&Number.isSafeInteger(x)&&
 Math.abs(x)<=100000000000&&(positive?x>0:true);
const valueMatches=(raw:unknown,stored:number)=>{
 if(typeof raw!=='string'&&typeof raw!=='number')return false;
 if(typeof raw==='string'&&!/^-?(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(raw))return false;
 const n=Number(raw);
 return Number.isFinite(n)&&Math.abs(n*100-stored)<1e-6;
};
const accountKeys=['id','tenant_id','account_code','account_name','account_type','balance_cents','balance_brl'];
const txKeys=['id','tenant_id','transaction_date','description','reference_id','entries'];
const entryKeys=['id','account_id','account_name','entry_type','amount_cents','amount_brl'];
const safeDate=(x:unknown):x is string=>{
 if(typeof x!=='string'||x.length>40||
   !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$/.test(x)||
   !Number.isFinite(Date.parse(x)))return false;
 const year=Number(x.slice(0,4)),month=Number(x.slice(5,7)),day=Number(x.slice(8,10));
 const date=new Date(Date.UTC(year,month-1,day));
 return date.getUTCFullYear()===year&&date.getUTCMonth()===month-1&&date.getUTCDate()===day;
};
export function parseLedgerAccounts(raw:unknown,tenantId:string):DisplayLedgerAccount[]{
 if(!uuid(tenantId)||!Array.isArray(raw)||raw.length>500)throw Error('Plano de contas inválido.');
 const ids=new Set<string>(),codes=new Set<string>();
 return raw.map(v=>{
  if(!record(v)||!only(v,accountKeys)||!uuid(v.id)||v.tenant_id!==tenantId||
     !text(v.account_code,24)||!/^[0-9A-Za-z][0-9A-Za-z.\-_]*$/.test(v.account_code)||
     !text(v.account_name,160)||!text(v.account_type,48)||
     !cents(v.balance_cents)||!valueMatches(v.balance_brl,v.balance_cents as number))
    throw Error('Conta contábil inconsistente.');
  const id=(v.id as string).toLowerCase();
  if(ids.has(id)||codes.has(v.account_code as string))throw Error('Conta duplicada.');
  ids.add(id);codes.add(v.account_code as string);
  return {id:v.id as string,tenant_id:tenantId,account_code:v.account_code as string,
   account_name:v.account_name as string,account_type:v.account_type as string,
   balance_cents:v.balance_cents as number};
 });
}
export function parseLedgerTransactions(raw:unknown,tenantId:string):DisplayLedgerTransaction[]{
 if(!uuid(tenantId)||!Array.isArray(raw)||raw.length>500)throw Error('Lançamentos contábeis inválidos.');
 const transactions=new Set<string>();
 return raw.map(v=>{
  if(!record(v)||!only(v,txKeys)||!uuid(v.id)||v.tenant_id!==tenantId||
     !text(v.description,500)||!text(v.reference_id,200)||
     !safeDate(v.transaction_date)||!Array.isArray(v.entries)||
     v.entries.length<2||v.entries.length>100)
    throw Error('Lançamento contábil incompatível.');
  const id=(v.id as string).toLowerCase();
  if(transactions.has(id))throw Error('Lançamento duplicado.');
  transactions.add(id);
  const entries=new Set<string>();let dr=0,cr=0,drCount=0,crCount=0;
  const parsedEntries:DisplayLedgerEntry[]=v.entries.map(item=>{
   if(!record(item)||!only(item,entryKeys)||!uuid(item.id)||!uuid(item.account_id)||
      !text(item.account_name,160)||(item.entry_type!=='DR'&&item.entry_type!=='CR')||
      !cents(item.amount_cents,true)||!valueMatches(item.amount_brl,item.amount_cents as number))
    throw Error('Contrapartida contábil inválida.');
   const entryId=(item.id as string).toLowerCase();
   if(entries.has(entryId))throw Error('Linha contábil duplicada.');
   entries.add(entryId);
   const money=item.amount_cents as number;
   if(item.entry_type==='DR'){dr+=money;drCount++;}else{cr+=money;crCount++;}
   if(!Number.isSafeInteger(dr)||!Number.isSafeInteger(cr))throw Error('Soma contábil fora da faixa.');
   return {id:item.id as string,account_id:item.account_id as string,
    account_name:item.account_name as string,
    entry_type:item.entry_type as 'DR'|'CR',amount_cents:money};
  });
  if(drCount===0||crCount===0||dr!==cr)throw Error('Partidas dobradas inconsistentes.');
  return {id:v.id as string,tenant_id:tenantId,transaction_date:v.transaction_date as string,
   description:v.description as string,reference_id:v.reference_id as string,entries:parsedEntries};
 });
}
/** Apenas vinculação local; não confirma conciliação bancária. */
export function validateLedgerAccountLinks(accounts:DisplayLedgerAccount[],
 transactions:DisplayLedgerTransaction[]):void{
 const ids=new Map(accounts.map(a=>[a.id.toLowerCase(),a]));
 for(const tx of transactions)for(const entry of tx.entries){
  const account=ids.get(entry.account_id.toLowerCase());
  if(!account||account.account_name!==entry.account_name)
   throw Error('Lançamento com conta contábil ausente ou divergente.');
 }
}
