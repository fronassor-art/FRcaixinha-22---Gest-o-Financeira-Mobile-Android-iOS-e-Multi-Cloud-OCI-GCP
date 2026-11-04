/** Navegação sem efeitos colaterais, segura contra resposta atrasada ou cursor ausente. */
import type {LedgerKeysetPage} from './ledgerKeysetBoundary';
export interface JournalNavigation {page:number;cursors:Array<string|null>}
export const INITIAL_JOURNAL_NAVIGATION:JournalNavigation={page:1,cursors:[null]};
export const initialJournalNavigation=():JournalNavigation=>({page:1,cursors:[null]});
export const previousJournalNavigation=(value:JournalNavigation):JournalNavigation=>
 value.page>1?{page:value.page-1,cursors:[...value.cursors]}:value;
export function canAdvanceJournalNavigation(
 value:JournalNavigation, response:Pick<LedgerKeysetPage,'has_more'|'next_cursor'>
):boolean {
 return Number.isSafeInteger(value.page)&&value.page>=1&&value.page<1000&&
  value.cursors.length>=value.page&&response.has_more===true&&
  typeof response.next_cursor==='string'&&
  /^[A-Za-z0-9_-]{1,400}$/.test(response.next_cursor)&&
  // Cursor de uma pagina anterior e replay, nunca seguir em loop.
  !value.cursors.slice(1,value.page).includes(response.next_cursor);
}
export function nextJournalNavigation(
 value:JournalNavigation, response:Pick<LedgerKeysetPage,'has_more'|'next_cursor'>
):JournalNavigation {
 if(!canAdvanceJournalNavigation(value,response))return value;
 return {page:value.page+1,
  cursors:[...value.cursors.slice(0,value.page),response.next_cursor]};
}
