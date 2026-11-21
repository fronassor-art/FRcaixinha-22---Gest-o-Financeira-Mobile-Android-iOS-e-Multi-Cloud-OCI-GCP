/** AI Studio M20400 — signed-session tenant-cycle contribution policy boundary. */
export type CycleContributionPolicy={
 contract:string;source:'POSTGRESQL_VERIFIED_SESSION';tenant_id:string;
 cycle_id:string;cycle_year:number;start_date:string;end_date:string;
 amount_cents:number;policy_version:number;registered_contributions:number;
 can_edit:boolean;blocked_reason:string;pending_requested_cents:number|null;
 real_payments_enabled:false;
};
export type CyclePriceChangeResult={
 change_status:'APPLIED'|'PENDING_REVIEW';amount_cents:number;request_id:string;
 existing_contributions_repriced:false;
};
const obj=(v:unknown):v is Record<string,unknown>=>
 v!==null&&typeof v==='object'&&!Array.isArray(v);
const uuid=(v:unknown)=>typeof v==='string'&&
 /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(v);
const whole=(v:unknown,max:number):v is number=>
 typeof v==='number'&&Number.isSafeInteger(v)&&v>=0&&v<=max;
export function parseCycleContributionPolicy(raw:unknown,tenant:string):CycleContributionPolicy{
 if(!obj(raw)||raw.contract!=='AI_STUDIO_M20400_CYCLE_PRICE_REVIEW_V1'
 ||raw.source!=='POSTGRESQL_VERIFIED_SESSION'
 ||raw.tenant_id!==tenant||!uuid(raw.cycle_id)
 ||!whole(raw.cycle_year,2100)||raw.cycle_year<2020
 ||typeof raw.start_date!=='string'||typeof raw.end_date!=='string'
 ||!/^\d{4}-\d{2}-\d{2}$/.test(raw.start_date)||!/^\d{4}-\d{2}-\d{2}$/.test(raw.end_date)
 ||!whole(raw.amount_cents,1000000)||raw.amount_cents<15000
 ||!whole(raw.policy_version,100000)
 ||!whole(raw.registered_contributions,1000000)
 ||typeof raw.can_edit!=='boolean'
 ||!['COMPETENCIAS_JA_REGISTRADAS','CICLO_JA_INICIADO',
       'EDITAVEL_ANTES_DA_PRIMEIRA_COMPETENCIA'].includes(String(raw.blocked_reason))
 ||raw.real_payments_enabled!==false
 ||(raw.pending_requested_cents!==null&&
 (!whole(raw.pending_requested_cents,1000000)||raw.pending_requested_cents<15000)))
 throw new Error('Política da contribuição incompatível com o ciclo autenticado.');
 const d=raw;
 return {
 contract:d.contract as string,source:'POSTGRESQL_VERIFIED_SESSION',tenant_id:tenant,
 cycle_id:d.cycle_id as string,cycle_year:d.cycle_year as number,
 start_date:d.start_date as string,end_date:d.end_date as string,
 amount_cents:d.amount_cents as number,policy_version:d.policy_version as number,
 registered_contributions:d.registered_contributions as number,
 can_edit:d.can_edit as boolean,blocked_reason:d.blocked_reason as string,
 pending_requested_cents:d.pending_requested_cents as number|null,
 real_payments_enabled:false,
 };
}
export function parseCyclePriceInput(raw:string):number{
 const m=/^([1-9]\d{0,4})(?:[.,](\d{1,2}))?$/.exec(raw.trim());
 if(!m)throw new Error('Informe o valor com até duas casas decimais.');
 const cents=Number(m[1])*100+Number((m[2]??'').padEnd(2,'0'));
 if(!Number.isSafeInteger(cents)||cents<15000||cents>1000000)
 throw new Error('Valor por cota fora do intervalo permitido (mínimo R$ 150 a R$ 10.000).');
 return cents;
}
export function parseCyclePriceChange(raw:unknown):CyclePriceChangeResult{
 if(!obj(raw)||raw.contract!=='AI_STUDIO_M20400_CYCLE_PRICE_REVIEW_V1'
 ||raw.source!=='POSTGRESQL_VERIFIED_SESSION'
 ||!['APPLIED','PENDING_REVIEW'].includes(String(raw.change_status))
 ||!whole(raw.amount_cents,100000000)||!uuid(raw.request_id)
 ||raw.existing_contributions_repriced!==false
 ||raw.real_payments_enabled!==false)
 throw new Error('Resposta de revisão de cotas inválida.');
 return {change_status:raw.change_status as CyclePriceChangeResult['change_status'],
 amount_cents:raw.amount_cents as number,request_id:raw.request_id as string,
 existing_contributions_repriced:false};
}
