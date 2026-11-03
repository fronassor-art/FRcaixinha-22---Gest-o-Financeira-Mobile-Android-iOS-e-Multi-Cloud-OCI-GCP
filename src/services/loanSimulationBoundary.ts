/** Defesa de apresentação do cronograma Price, sem recalcular juros da política. */
export interface LoanSimulationInstallment {
  installment_number:number;due_date:string;opening_balance:number;
  monthly_payment:number;interest_portion:number;
  amortization_portion:number;closing_balance:number;
  is_cents_adjusted:boolean;
}
export interface LoanSimulation {
  principal:number;monthly_rate:number;term_months:number;
  uniform_payment:number;last_payment:number;
  total_interest:number;total_payable:number;
  schedule:LoanSimulationInstallment[];
  is_irregular_first_period:boolean;first_period_days:number|null;
  effective_first_rate:number;
}
export type LoanSimulationRequest={principal:number;term_months:number};
const obj=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const RESPONSE_FIELDS=new Set(['principal','monthly_rate','term_months',
  'uniform_payment','last_payment','total_interest','total_payable',
  'is_irregular_first_period','first_period_days','effective_first_rate','schedule']);
const INSTALLMENT_FIELDS=new Set(['installment_number','due_date',
  'opening_balance','monthly_payment','interest_portion','amortization_portion',
  'closing_balance','is_cents_adjusted']);
const clean=(v:Record<string,unknown>,allowed:Set<string>)=>
  Object.keys(v).every(k=>allowed.has(k));
const cents=(v:unknown):number=>{
  if(typeof v==='string'&&!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(v))
    throw Error('Valor monetário inválido na simulação.');
  if(typeof v!=='number'&&typeof v!=='string')
    throw Error('Valor monetário inválido na simulação.');
  const n=Number(v);
  if(!Number.isFinite(n)||n<0||n>1000000000||
     Math.abs(n*100-Math.round(n*100))>1e-6)
    throw Error('Valor fora de centavos na simulação.');
  return Math.round(n*100);
};
const rate=(v:unknown):number=>{
  if(typeof v!=='number'&&!(typeof v==='string'&&/^(?:0|[1-9]\d*)(?:\.\d{1,8})?$/.test(v)))
    throw Error('Taxa inválida na simulação.');
  const x=Number(v);
  if(!Number.isFinite(x)||x<0||x>10)throw Error('Taxa inválida na simulação.');
  return x;
};
const month=(v:unknown):number=>{
  if(typeof v!=='string'||! /^\d{4}-\d{2}-\d{2}$/.test(v))
    throw Error('Data inválida na simulação.');
  const d=new Date(v+'T12:00:00Z');
  if(!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==v||
     d.getUTCDate()!==10)throw Error('Data inválida na simulação.');
  return d.getUTCFullYear()*12+d.getUTCMonth();
};
export function validateSimulationRequest(req:LoanSimulationRequest):LoanSimulationRequest{
  if(!obj(req)||typeof req.principal!=='number'||!Number.isFinite(req.principal)||
     req.principal<=0||req.principal>50000||
     !Number.isInteger(req.term_months)||req.term_months<1||req.term_months>6)
    throw Error('Valor ou prazo inválido para simulação.');
  const amount=cents(req.principal);
  if(amount<1||amount>5000000)throw Error('Principal fora do limite.');
  return {principal:amount/100,term_months:req.term_months};
}
export function parseLoanSimulation(raw:unknown,requested:LoanSimulationRequest):LoanSimulation{
  const req=validateSimulationRequest(requested);
  if(!obj(raw)||!clean(raw,RESPONSE_FIELDS)||raw.term_months!==req.term_months||
     !Array.isArray(raw.schedule)||raw.schedule.length!==req.term_months||
     typeof raw.is_irregular_first_period!=='boolean')
    throw Error('Contrato de simulação incompatível.');
  const p=cents(raw.principal),uniform=cents(raw.uniform_payment),
    last=cents(raw.last_payment),interest=cents(raw.total_interest),
    total=cents(raw.total_payable);
  if(p!==cents(req.principal)||total!==p+interest)
    throw Error('Totais financeiros incompatíveis.');
  const monthlyRate=rate(raw.monthly_rate),effectiveRate=rate(raw.effective_first_rate);
  const days=raw.first_period_days;
  if(days!==null&&days!==undefined&&
     (!Number.isInteger(days)||Number(days)<1||Number(days)>62))
    throw Error('Período inválido na simulação.');
  if((raw.is_irregular_first_period===true && (days===null||days===undefined||days===30)) ||
     (raw.is_irregular_first_period===false && days!==null && days!==undefined && days!==30))
    throw Error('Período e classificação inconsistentes.');
  if(days!==null&&days!==undefined &&
     Math.abs(monthlyRate*Number(days)/30-effectiveRate)>1e-7)
    throw Error('Taxa do primeiro período divergente.');
  if((days===null||days===undefined)&&Math.abs(monthlyRate-effectiveRate)>1e-7)
    throw Error('Taxa regular divergente.');
  let balance=p,prevMonth=-1,paid=0,amortized=0,interestPaid=0;
  const schedule:LoanSimulationInstallment[]=raw.schedule.map((row:unknown,i:number)=>{
    if(!obj(row)||!clean(row,INSTALLMENT_FIELDS)||row.installment_number!==i+1||
       typeof row.is_cents_adjusted!=='boolean')
      throw Error('Parcela fora de sequência.');
    const dueMonth=month(row.due_date);
    if(i>0&&dueMonth!==prevMonth+1)throw Error('Vencimentos não consecutivos.');
    prevMonth=dueMonth;
    const opening=cents(row.opening_balance),payment=cents(row.monthly_payment),
      part=cents(row.amortization_portion),fee=cents(row.interest_portion),
      closing=cents(row.closing_balance);
    if(opening!==balance||payment!==part+fee||opening!==part+closing||
       part<=0||(i<req.term_months-1&&payment!==uniform)||
       (i===req.term_months-1&&closing!==0))
      throw Error('Parcela com valores inconsistentes.');
    balance=closing;paid+=payment;amortized+=part;interestPaid+=fee;
    return {installment_number:i+1,due_date:row.due_date as string,
      opening_balance:opening/100,monthly_payment:payment/100,
      interest_portion:fee/100,amortization_portion:part/100,
      closing_balance:closing/100,is_cents_adjusted:row.is_cents_adjusted as boolean};
  });
  if(amortized!==p||interestPaid!==interest||paid!==total||
     cents(raw.schedule[req.term_months-1].monthly_payment)!==last)
    throw Error('Somatório da simulação divergente.');
  return {principal:p/100,monthly_rate:monthlyRate,term_months:req.term_months,
    uniform_payment:uniform/100,last_payment:last/100,
    total_interest:interest/100,total_payable:total/100,schedule,
    is_irregular_first_period:raw.is_irregular_first_period,
    first_period_days:days===undefined?null:days as number|null,
    effective_first_rate:effectiveRate};
}
