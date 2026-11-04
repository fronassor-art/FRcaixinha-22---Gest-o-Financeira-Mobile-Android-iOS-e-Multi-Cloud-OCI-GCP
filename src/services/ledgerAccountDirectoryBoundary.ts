/** FR Caixinha / AI Studio: metadados sem saldos para mostrar contas em livro vazio. */
export interface LedgerAccountDirectoryItem {
  id:string;
  account_code:string;
  account_name:string;
  account_type:string;
}
export interface LedgerAccountDirectory {
  source:'POSTGRESQL_RLS';
  scope:'TENANT_ADMIN_READ_ONLY';
  tenant_id:string;
  accounts:LedgerAccountDirectoryItem[];
  balance_values_hidden:true;
  complete_ledger_verified:false;
  bank_reconciled:false;
  financial_closing_authorized:false;
}
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const obj=(x:unknown):x is Record<string,unknown>=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const exact=(x:Record<string,unknown>,keys:string[])=>Object.keys(x).length===keys.length&&
 Object.keys(x).every(key=>keys.includes(key));
const fields=['source','scope','tenant_id','accounts','balance_values_hidden',
 'complete_ledger_verified','bank_reconciled','financial_closing_authorized'];
const itemFields=['id','account_code','account_name','account_type'];
const name=(v:unknown,max:number)=>typeof v==='string'&&v.trim().length>0&&
 v.length<=max&&!/[\x00-\x1f\x7f]/.test(v);
const code=(v:unknown)=>typeof v==='string'&&v.length>=1&&v.length<=24&&
 /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(v);
export function parseLedgerAccountDirectory(raw:unknown,tenantId:string):LedgerAccountDirectory {
 if(!UUID.test(tenantId)||!obj(raw)||!exact(raw,fields)||
    raw.source!=='POSTGRESQL_RLS'||raw.scope!=='TENANT_ADMIN_READ_ONLY'||
    raw.tenant_id!==tenantId||raw.balance_values_hidden!==true||
    raw.complete_ledger_verified!==false||raw.bank_reconciled!==false||
    raw.financial_closing_authorized!==false||
    !Array.isArray(raw.accounts)||raw.accounts.length>500)
    throw Error('Diretório contábil não autorizado ou incompleto.');
 const ids=new Set<string>(),codes=new Set<string>();
 const accounts:LedgerAccountDirectoryItem[]=raw.accounts.map((a:unknown)=>{
  if(!obj(a)||!exact(a,itemFields)||typeof a.id!=='string'||!UUID.test(a.id)||
     !code(a.account_code)||!name(a.account_name,160)||!name(a.account_type,48))
     throw Error('Conta contábil inválida.');
  const id=(a.id as string).toLowerCase(),key=(a.account_code as string);
  if(ids.has(id)||codes.has(key))throw Error('Conta duplicada.');
  ids.add(id);codes.add(key);
  return {id:a.id as string,account_code:a.account_code as string,
   account_name:a.account_name as string,account_type:a.account_type as string};
 });
 return {source:'POSTGRESQL_RLS',scope:'TENANT_ADMIN_READ_ONLY',
  tenant_id:tenantId,accounts,balance_values_hidden:true,
  complete_ledger_verified:false,bank_reconciled:false,
  financial_closing_authorized:false};
}
