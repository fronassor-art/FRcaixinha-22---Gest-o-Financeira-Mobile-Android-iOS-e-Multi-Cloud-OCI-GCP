/** M22500: strict per-tenant, per-cycle legacy contribution read-only review. */
export type LegacyContributionGroup={
  registered_amount_cents:number;
  registered_paid_cents:number;
  recorded_status:'PENDENTE'|'PARCIAL'|'QUITADA';
  registered_contributions:number;
  bank_settlement_verified:false;
};
export type LegacyContributionReview={
  contract:'AI_STUDIO_M22400_LEGACY_CONTRIBUTION_REVIEW_V1';
  source:'POSTGRESQL_RLS_REGISTERED_HISTORY_ONLY';
  tenant_id:string;cycle_id:string;cycle_year:number;
  minimum_new_quota_cents:15000;
  legacy_registered_contributions:number;
  legacy_due_cents:number;
  legacy_paid_recorded_cents:number;
  legacy_open_recorded_cents:number;
  groups:LegacyContributionGroup[];
  historical_obligations_changed:false;
  price_adjustment_authorized:false;
  bank_reconciled:false;
  real_payment_enabled:false;
  requires_administrator_review:boolean;
};
const obj=(v:unknown):v is Record<string,unknown>=>
  v!==null&&typeof v==='object'&&!Array.isArray(v);
const integer=(v:unknown,upper:number):v is number=>
  typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<=upper;
const max=999999999999;
export function parseLegacyContributionReview(
 raw:unknown,tenantId:string,cycleId:string,
):LegacyContributionReview{
 if(!obj(raw)||raw.contract!=='AI_STUDIO_M22400_LEGACY_CONTRIBUTION_REVIEW_V1'
  ||raw.source!=='POSTGRESQL_RLS_REGISTERED_HISTORY_ONLY'
  ||raw.tenant_id!==tenantId||raw.cycle_id!==cycleId
  ||!integer(raw.cycle_year,2100)||raw.cycle_year<2020
  ||raw.minimum_new_quota_cents!==15000
  ||!integer(raw.legacy_registered_contributions,1000000000)
  ||!integer(raw.legacy_due_cents,max)
  ||!integer(raw.legacy_paid_recorded_cents,max)
  ||!integer(raw.legacy_open_recorded_cents,max)
  ||!Array.isArray(raw.groups)||raw.groups.length>200
  ||raw.historical_obligations_changed!==false
  ||raw.price_adjustment_authorized!==false
  ||raw.bank_reconciled!==false||raw.real_payment_enabled!==false
  ||raw.requires_administrator_review!==(raw.legacy_registered_contributions>0)){
   throw new Error('Revisão de histórico incompatível com a caixinha autenticada.');
 }
 let rows=0,due=0,paid=0;
 const groups:LegacyContributionGroup[]=[];
 for(const item of raw.groups){
  if(!obj(item)||!integer(item.registered_amount_cents,14999)
   ||item.registered_amount_cents<1
   ||!integer(item.registered_paid_cents,14999)
   ||item.registered_paid_cents>item.registered_amount_cents
   ||!integer(item.registered_contributions,1000000)
   ||item.registered_contributions<1
   ||!['PENDENTE','PARCIAL','QUITADA'].includes(String(item.recorded_status))
   ||item.bank_settlement_verified!==false){
    throw new Error('Grupo legado incompatível com os valores registrados.');
  }
  rows+=item.registered_contributions;
  due+=item.registered_amount_cents*item.registered_contributions;
  paid+=item.registered_paid_cents*item.registered_contributions;
  if(!Number.isSafeInteger(due)||!Number.isSafeInteger(paid)||due>max){
   throw new Error('Total legado excede capacidade.');
  }
  groups.push({
   registered_amount_cents:item.registered_amount_cents,
   registered_paid_cents:item.registered_paid_cents,
   recorded_status:item.recorded_status as LegacyContributionGroup['recorded_status'],
   registered_contributions:item.registered_contributions,
   bank_settlement_verified:false,
  });
 }
 if(rows!==raw.legacy_registered_contributions||due!==raw.legacy_due_cents
  ||paid!==raw.legacy_paid_recorded_cents
  ||due-paid!==raw.legacy_open_recorded_cents){
  throw new Error('Totais de histórico não conferem com as competências.');
 }
 return {...raw,groups} as LegacyContributionReview;
}
