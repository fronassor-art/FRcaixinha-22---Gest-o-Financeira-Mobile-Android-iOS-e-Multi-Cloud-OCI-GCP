/** M39910 — strictly documentary history, never a balance or salary. */
export type CashboxHistoryScope =
  'MASTER_PLATFORM_SAAS_ONLY'|'TENANT_ADMIN_COLLECTIVE_REFERENCE_ONLY';
export type CashboxHistoryCategory =
  'SAAS_INTENT'|'SAAS_PREPARATION'|'TENANT_COLLECTIVE_LEDGER';
export type CashboxHistoryEntry = Readonly<{
  id:string;occurred_at:string;category:CashboxHistoryCategory;
  state:string;amount_cents:null;settlement_verified:false;
}>;
export type ExclusiveCashboxHistory = Readonly<{
  source:'POSTGRESQL_RLS';scope:CashboxHistoryScope;
  tenant_id:string|null;entries:readonly CashboxHistoryEntry[];
  available_balance_cents:null;cash_movement_verified:false;
  transfer_enabled:false;status:'DOCUMENTARY_ONLY_NOT_RECONCILED';
}>;

const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const iso=/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$/;
const paymentStates=['PENDING','APPROVED','REJECTED','CANCELED','REFUNDED'];
const preparationStates=['PENDING_PAYMENT','PAUSED_NO_PAYMENT','CANCELED'];
const entryFields=['id','occurred_at','category','state','amount_cents','settlement_verified'];
const rootFields=['source','scope','tenant_id','entries','available_balance_cents',
  'cash_movement_verified','transfer_enabled','status'];

function exactRecord(v:unknown,keys:readonly string[]):Record<string,unknown>{
  if(!v||typeof v!=='object'||Array.isArray(v))
    throw Error('Histórico documental inválido.');
  const row=v as Record<string,unknown>;
  if(Object.keys(row).length!==keys.length||
    keys.some(k=>!Object.prototype.hasOwnProperty.call(row,k)))
    throw Error('Histórico documental: campos inesperados ou ausentes.');
  return row;
}

export function parseExclusiveCashboxHistory(
  value:unknown,role:'MASTER'|'TENANT_ADMIN',tenantId?:string,
):ExclusiveCashboxHistory{
  const root=exactRecord(value,rootFields);
  const isMaster=role==='MASTER';
  if(root.source!=='POSTGRESQL_RLS'||
    root.scope!==(isMaster?'MASTER_PLATFORM_SAAS_ONLY':'TENANT_ADMIN_COLLECTIVE_REFERENCE_ONLY')||
    root.available_balance_cents!==null||root.cash_movement_verified!==false||
    root.transfer_enabled!==false||root.status!=='DOCUMENTARY_ONLY_NOT_RECONCILED')
    throw Error('Histórico documental não conciliado ou fora do escopo.');
  if(isMaster){
    if(root.tenant_id!==null)throw Error('Histórico Master não deve incluir tenant.');
  }else{
    if(!tenantId||!uuid.test(tenantId)||typeof root.tenant_id!=='string'||
      !uuid.test(root.tenant_id)||root.tenant_id.toLowerCase()!==tenantId.toLowerCase())
      throw Error('Histórico de outra caixinha não pode ser exibido.');
  }
  if(!Array.isArray(root.entries)||root.entries.length>10)
    throw Error('Histórico de tamanho inválido.');
  const seen=new Set<string>();
  let prior=Infinity;
  for(const item of root.entries){
    const e=exactRecord(item,entryFields);
    if(typeof e.id!=='string'||!uuid.test(e.id)||
      typeof e.category!=='string'||
      typeof e.occurred_at!=='string'||!iso.test(e.occurred_at)||
      !Number.isFinite(Date.parse(e.occurred_at))||
      e.amount_cents!==null||e.settlement_verified!==false)
      throw Error('Entrada documental inválida.');
    const ts=Date.parse(e.occurred_at);
    if(ts>prior)throw Error('Histórico fora de ordem.');
    prior=ts;
    let allowed:readonly string[]=[];
    if(isMaster&&e.category==='SAAS_INTENT')allowed=paymentStates;
    if(isMaster&&e.category==='SAAS_PREPARATION')allowed=preparationStates;
    if(!isMaster&&e.category==='TENANT_COLLECTIVE_LEDGER')
      allowed=['RECORDED_NOT_REMUNERATION'];
    if(!allowed.includes(e.state as string))
      throw Error('Origem ou estado financeiro não comprovado.');
    const key=String(e.category)+':'+e.id.toLowerCase();
    if(seen.has(key))throw Error('Histórico duplicado.');
    seen.add(key);
  }
  return root as unknown as ExclusiveCashboxHistory;
}
