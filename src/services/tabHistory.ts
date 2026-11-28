/** Tab history is scoped to the authenticated session. Never store private page data. */
export type TabHistory = Readonly<{entries: readonly string[]; index: number}>;
export const startTabHistory=(first:string):TabHistory=>({entries:[first],index:0});
export function visitTab(history:TabHistory,tab:string,allow:(tab:string)=>boolean):TabHistory{
 if(!allow(tab))return history;
 if(history.entries[history.index]===tab)return history;
 const entries=[...history.entries.slice(0,history.index+1),tab].slice(-24);
 return {entries,index:entries.length-1};
}
export function stepTab(history:TabHistory,direction:-1|1):TabHistory{
 const next=history.index+direction;
 return next>=0&&next<history.entries.length?{...history,index:next}:history;
}
export const canStepTab=(history:TabHistory,direction:-1|1):boolean=>
 history.index+direction>=0&&history.index+direction<history.entries.length;
