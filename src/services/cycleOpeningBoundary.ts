/** FR Caixinha AI Studio M20900: preview only, no permission to write. */
export type CycleOpeningPreview={
 contract:'AI_STUDIO_M20800_CYCLE_OPENING_PREVIEW_V1';
 source:'POSTGRESQL_RLS_AUTHENTICATED_ADMIN';tenant_id:string;
 year:number;start_date:string;end_date:string;
 amount_cents:number;minimum_amount_cents:15000;
 price_explicitly_entered:true;historical_obligations_unchanged:true;
 blocked_reasons:string[];preconditions_satisfied:boolean;
 cycle_creation_enabled:boolean;financial_effect:false;reason_recorded:false;
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
 ||(typeof p.cycle_creation_enabled!=='boolean')
 ||(p.cycle_creation_enabled&&!p.preconditions_satisfied)||p.financial_effect!==false
 ||p.reason_recorded!==false
 ||typeof p.start_date!=='string'||typeof p.end_date!=='string'
 ||!/^\d{4}-\d{2}-\d{2}$/.test(p.start_date)
 ||!/^\d{4}-\d{2}-\d{2}$/.test(p.end_date)
 ) throw new Error('Resposta de abertura não autenticada ou insegura.');
 return p as CycleOpeningPreview;
}

export type CycleOpeningReceipt={
 contract:'FR_FINANCE_M37423_CYCLE_OPENING_V1';
 source:'POSTGRESQL_AUTHENTICATED_ADMIN_M044';tenant_id:string;
 opened_cycle_id:string;opened_policy_id:string;year:number;amount_cents:number;
 opening_status:'CREATED'|'REPLAY';opening_audit_persisted:true;
 existing_contributions_repriced:false;payments_executed:false;
};
export function parseCycleOpeningReceipt(raw:unknown,tenantId:string):CycleOpeningReceipt{
 if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('Recibo de ciclo inválido');
 const p=raw as Record<string,unknown>;
 const uid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
 if(p.contract!=='FR_FINANCE_M37423_CYCLE_OPENING_V1'||p.source!=='POSTGRESQL_AUTHENTICATED_ADMIN_M044'
 ||p.tenant_id!==tenantId||!uid.test(String(p.opened_cycle_id))||!uid.test(String(p.opened_policy_id))
 ||!Number.isInteger(p.year)||Number(p.year)<2027||Number(p.year)>2100
 ||!Number.isSafeInteger(p.amount_cents)||Number(p.amount_cents)<15000||Number(p.amount_cents)>1000000
 ||!['CREATED','REPLAY'].includes(String(p.opening_status))||p.opening_audit_persisted!==true
 ||p.existing_contributions_repriced!==false||p.payments_executed!==false)
 throw Error('Recibo de abertura não comprovado');
 return p as CycleOpeningReceipt;
}


/** M37446: a server preview is valid only for the exact authorized form intent. */
export type CycleOpeningFormIntent={tenantId:string;year:number;amountCents:number;reason:string};
export function openingPreviewMatchesForm(
 preview:CycleOpeningPreview,
 authorized:CycleOpeningFormIntent,
 current:CycleOpeningFormIntent,
):boolean{
 if(!preview||!authorized||!current)return false;
 const fields=[authorized,current];
 if(fields.some(f=>!f||typeof f.tenantId!=='string'||
  !Number.isSafeInteger(f.year)||!Number.isSafeInteger(f.amountCents)||
  typeof f.reason!=='string'||f.reason.length<12||f.reason.length>500||
  f.reason!==f.reason.trim()))return false;
 return authorized.tenantId===current.tenantId &&
  authorized.year===current.year &&
  authorized.amountCents===current.amountCents &&
  authorized.reason===current.reason &&
  preview.tenant_id===authorized.tenantId &&
  preview.year===authorized.year &&
  preview.amount_cents===authorized.amountCents;
}
