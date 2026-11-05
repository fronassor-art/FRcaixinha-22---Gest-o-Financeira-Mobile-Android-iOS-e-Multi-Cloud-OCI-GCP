/** FR Caixinha AI Studio M20900: preview only, no permission to write. */
export type CycleOpeningPreview={
 contract:'AI_STUDIO_M20800_CYCLE_OPENING_PREVIEW_V1';
 source:'POSTGRESQL_RLS_AUTHENTICATED_ADMIN';tenant_id:string;
 year:number;start_date:string;end_date:string;
 amount_cents:number;minimum_amount_cents:15000;
 price_explicitly_entered:true;historical_obligations_unchanged:true;
 blocked_reasons:string[];preconditions_satisfied:boolean;
 cycle_creation_enabled:false;financial_effect:false;reason_recorded:false;
};
export function parseCycleOpeningPreview(raw:unknown,tenant:string):CycleOpeningPreview{
 if(!raw||typeof raw!=='object'||Array.isArray(raw))
  throw new Error('Prévia de abertura inválida.');
 const p=raw as Record<string,unknown>;
 if(p.contract!=='AI_STUDIO_M20800_CYCLE_OPENING_PREVIEW_V1'
 ||p.source!=='POSTGRESQL_RLS_AUTHENTICATED_ADMIN'
 ||p.tenant_id!==tenant
 ||!Number.isInteger(p.year)||Number(p.year)<2027||Number(p.year)>2100
 ||!Number.isSafeInteger(p.amount_cents)
 ||Number(p.amount_cents)<15000||Number(p.amount_cents)>1000000
 ||p.minimum_amount_cents!==15000||p.price_explicitly_entered!==true
 ||p.historical_obligations_unchanged!==true
 ||!Array.isArray(p.blocked_reasons)
 ||!p.blocked_reasons.every(x=>typeof x==='string'
  && ['TENANT_INACTIVE','YEAR_ALREADY_EXISTS','PREVIOUS_CYCLE_NOT_CLOSED',
  'YEAR_START_NOT_FUTURE'].includes(x))
 ||p.preconditions_satisfied!==(p.blocked_reasons.length===0)
 ||p.cycle_creation_enabled!==false||p.financial_effect!==false
 ||p.reason_recorded!==false
 ||typeof p.start_date!=='string'||typeof p.end_date!=='string'
 ||!/^\d{4}-\d{2}-\d{2}$/.test(p.start_date)
 ||!/^\d{4}-\d{2}-\d{2}$/.test(p.end_date)
 ) throw new Error('Resposta de abertura não autenticada ou insegura.');
 return p as CycleOpeningPreview;
}
