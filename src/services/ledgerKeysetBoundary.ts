/** M321-360: pagina parcial autorizada, cursor nao constitui credencial ou snapshot. */
import {parseLedgerAccountJournalPage} from './ledgerAccountJournalBoundary';
import type {LedgerAccountJournalEntry} from './ledgerAccountJournalBoundary';

export interface LedgerKeysetPage {
 source:'POSTGRESQL_RLS'; tenant_id:string; account_id:string;
 page_size:number; has_more:boolean; next_cursor:string|null;
 complete_ledger_verified:false; bank_reconciled:false;
 financial_closing_authorized:false; entries:LedgerAccountJournalEntry[];
}
const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const fields=['source','tenant_id','account_id','page_size','has_more','next_cursor',
 'complete_ledger_verified','bank_reconciled','financial_closing_authorized','entries'];
export function parseLedgerKeysetPage(
 raw:unknown,tenantId:string,accountId:string,pageSize:number
):LedgerKeysetPage {
 if(!record(raw)||Object.keys(raw).length!==fields.length||
    Object.keys(raw).some(k=>!fields.includes(k))||
    (raw.next_cursor!==null&&(typeof raw.next_cursor!=='string'||
      raw.next_cursor.length<1||raw.next_cursor.length>400||
      !/^[A-Za-z0-9_-]+$/.test(raw.next_cursor)))||
    (raw.has_more===true&&raw.next_cursor===null)||
    (raw.has_more===false&&raw.next_cursor!==null))
    throw Error('Cursor contábil incompatível.');
 const legacy={...raw,page:1};
 delete legacy.next_cursor;
 const page=parseLedgerAccountJournalPage(legacy,tenantId,accountId,1,pageSize);
 return {
  source:'POSTGRESQL_RLS',tenant_id:tenantId,account_id:accountId,
  page_size:pageSize,has_more:page.has_more,next_cursor:raw.next_cursor as string|null,
  complete_ledger_verified:false,bank_reconciled:false,
  financial_closing_authorized:false,entries:page.entries,
 };
}
