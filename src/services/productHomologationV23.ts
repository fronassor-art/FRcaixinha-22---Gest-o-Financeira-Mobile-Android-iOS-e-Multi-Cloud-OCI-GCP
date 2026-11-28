/** FR Finance — isolated, fictitious product demonstrator. No storage, network,
 * real tenant IDs, provider credentials, payment execution or production activation. */
import {civilDateDayNumberV22} from './cycleWindowV22';
export type Mode = 'MANUAL'|'MERCADO_PAGO'|'HYBRID';
export type Role = 'TENANT_ADMIN'|'TENANT_MEMBER';
export type Method = 'DINHEIRO'|'PIX_EXTERNO'|'TRANSFERENCIA'|'DEPOSITO';
export type Cycle = Readonly<{id:string;start:string;first:string;last:string;closing:string;
  cents:number;quotas:number;adminBps:number;lateDays:number;lateCompetences:number;mode:Mode}>;
export type Obligation = Readonly<{id:string;cycleId:string;member:string;due:string;cents:number}>;
export type Receipt = Readonly<{id:string;obligationId:string;reference:string;cents:number;
  method:Method|'PSP_DEMO';date:string;evidence:string;state:'PENDING'|'CONFIRMED'|'CONTESTED'|'REVERSED';
  origin:'MANUAL'|'PSP_DEMO';reconciled:boolean;reason?:string;reversalDate?:string}>;
export type Journal = Readonly<{receiptId:string;cycleId:string;member:string;debit:string;credit:string;cents:number}>;
export type Demo = Readonly<{cycles:readonly Cycle[];obligations:readonly Obligation[];
  receipts:readonly Receipt[];journal:readonly Journal[]}>;
export const emptyDemo = ():Demo => ({cycles:[],obligations:[],receipts:[],journal:[]});
const members=['demo-member-a','demo-member-b'] as const;
const demand=(ok:unknown,message:string):void=>{if(!ok)throw Error(message)};
const date=(v:string)=>civilDateDayNumberV22(v);
const cents=(v:number)=>Number.isSafeInteger(v)&&v>0&&v<=100000000;
const text=(v:string)=>typeof v==='string'&&v.trim()===v&&v.length>=3&&v.length<=160;
export function parseDemoMoney(value:string):number {
  const v=value.trim().replace(',','.');
  demand(/^\d{1,7}(\.\d{1,2})?$/.test(v),'Informe valor positivo com até dois centavos decimais.');
  const [a,b='']=v.split('.'); const n=Number(a)*100+Number(b.padEnd(2,'0'));
  demand(cents(n),'Valor fora do intervalo técnico da demonstração.');return n;
}
function monthAt(first:string,index:number):string {
  const y=Number(first.slice(0,4)), m=Number(first.slice(5,7))-1, d=Number(first.slice(8));
  const base=new Date(Date.UTC(y,m+index,1));
  const day=Math.min(d,new Date(Date.UTC(base.getUTCFullYear(),base.getUTCMonth()+1,0)).getUTCDate());
  return new Date(Date.UTC(base.getUTCFullYear(),base.getUTCMonth(),day)).toISOString().slice(0,10);
}
export function cycleDueDates(c:Cycle):string[]{
  demand(/^demo-cycle-[a-zA-Z0-9-]+$/.test(c.id),'Identidade fictícia inválida.');
  demand(date(c.start)<=date(c.first)&&date(c.first)<=date(c.last)&&date(c.last)<=date(c.closing),'Calendário inválido.');
  demand(cents(c.cents)&&Number.isSafeInteger(c.quotas)&&c.quotas>=1&&c.quotas<=400&&
    cents(c.cents*c.quotas),'Valor ou cotas inválidos.');
  demand(Number.isInteger(c.adminBps)&&c.adminBps>=0&&c.adminBps<=10000,'Percentual inválido.');
  demand(Number.isInteger(c.lateDays)&&c.lateDays>=1&&c.lateDays<=3650&&Number.isInteger(c.lateCompetences)&&c.lateCompetences>=1&&c.lateCompetences<=120,'Política de atraso inválida.');
  demand(['MANUAL','MERCADO_PAGO','HYBRID'].includes(c.mode),'Modo inválido.');
  const dates:string[]=[];
  for(let i=0;i<120;i++){const due=monthAt(c.first,i);if(due>c.last)break;dates.push(due);if(due===c.last)return dates;}
  throw Error('A última contribuição deve coincidir com a âncora mensal. Limite técnico desta demonstração: 120 competências.');
}
export function addCycle(d:Demo,role:Role,c:Cycle):Demo {
  demand(role==='TENANT_ADMIN','Somente administrador fictício configura ciclos.');
  demand(!d.cycles.some(x=>x.id===c.id),'Ciclo já existe; configuração aceita não é editada.');
  const dates=cycleDueDates(c);
  return {...d,cycles:[...d.cycles,{...c}],obligations:[...d.obligations,...members.flatMap(member=>
    dates.map(due=>({id:c.id+'/'+member+'/'+due,cycleId:c.id,member,due,cents:c.cents*c.quotas})))]};
}
function getObligation(d:Demo,id:string):Obligation {
  const o=d.obligations.find(x=>x.id===id);if(!o)throw Error('Competência fictícia inexistente.');return o;
}
function getReceipt(d:Demo,id:string):Receipt {
  const r=d.receipts.find(x=>x.id===id);if(!r)throw Error('Registro fictício inexistente.');return r;
}
export function paid(d:Demo,id:string):number {
  return d.receipts.filter(r=>r.obligationId===id&&(r.state==='CONFIRMED'||r.state==='CONTESTED')).reduce((sum,r)=>sum+r.cents,0);
}
function pending(d:Demo,id:string):number {
  return d.receipts.filter(r=>r.obligationId===id&&r.state==='PENDING').reduce((sum,r)=>sum+r.cents,0);
}
function replaceReceipt(d:Demo,r:Receipt):Demo {return {...d,receipts:d.receipts.map(x=>x.id===r.id?r:x)}}
function entry(d:Demo,r:Receipt,reverse=false):Demo {
  const o=getObligation(d,r.obligationId);
  const cash=r.origin==='MANUAL'?'CAIXA_MANUAL_DEMO':'PSP_DEMO';
  return {...d,journal:[...d.journal,{receiptId:r.id,cycleId:o.cycleId,member:o.member,
    debit:reverse?'CAPITAL_MEMBRO_DEMO':cash,credit:reverse?cash:'CAPITAL_MEMBRO_DEMO',cents:r.cents}]};
}
export type ManualInput=Readonly<{obligationId:string;reference:string;cents:number;method:Method;date:string;evidence:string}>;
export function recordManual(d:Demo,role:Role,input:ManualInput):Demo {
  demand(role==='TENANT_ADMIN','Somente administrador registra recebimento.');
  const o=getObligation(d,input.obligationId), c=d.cycles.find(x=>x.id===o.cycleId)!;
  demand(c.mode!=='MERCADO_PAGO','Ciclo integrado não aceita baixa manual.');
  demand(cents(input.cents)&&text(input.reference)&&text(input.evidence)&&
    ['DINHEIRO','PIX_EXTERNO','TRANSFERENCIA','DEPOSITO'].includes(input.method),'Dados de recebimento inválidos.');
  demand(date(input.date)>=date(c.start)&&date(input.date)<=date(c.closing),'Data fora do ciclo fictício.');
  const old=d.receipts.find(r=>r.reference===input.reference);
  if(old){demand(old.origin==='MANUAL'&&old.obligationId===input.obligationId&&old.cents===input.cents&&old.method===input.method&&old.date===input.date&&old.evidence===input.evidence,'Referência econômica já usada ou divergente.');return d;}
  demand(paid(d,o.id)+pending(d,o.id)+input.cents<=o.cents,'Recebimento excede saldo aberto, considerando pendências.');
  const receipt:Receipt={...input,id:'demo-receipt-'+(d.receipts.length+1),state:'PENDING',origin:'MANUAL',reconciled:false};
  return {...d,receipts:[...d.receipts,receipt]};
}
export function confirmManual(d:Demo,role:Role,id:string,checked:boolean):Demo {
  demand(role==='TENANT_ADMIN'&&checked===true,'Conferência explícita do administrador necessária.');
  const r=getReceipt(d,id),o=getObligation(d,r.obligationId);
  demand(r.origin==='MANUAL','Origem incorreta.');
  if(r.state==='CONFIRMED')return d;
  demand(r.state==='PENDING'&&paid(d,o.id)+r.cents<=o.cents,'Registro não confirmável.');
  return entry(replaceReceipt(d,{...r,state:'CONFIRMED'}),r);
}
/** Mock provider event is explicitly synthetic. Real webhook/GET proof remains mandatory outside demo. */
export function reconcileMockProvider(d:Demo,role:Role,input:{obligationId:string;reference:string;cents:number;date:string;proof:'DEMO_WEBHOOK_AND_GET'}):Demo {
  demand(role==='TENANT_ADMIN'&&input.proof==='DEMO_WEBHOOK_AND_GET','Prova fictícia do provedor obrigatória.');
  const o=getObligation(d,input.obligationId),c=d.cycles.find(x=>x.id===o.cycleId)!;
  demand(c.mode!=='MANUAL'&&cents(input.cents)&&text(input.reference)&&date(input.date)>=date(c.start)&&date(input.date)<=date(c.closing),'Evento incompatível com o ciclo.');
  const previous=d.receipts.find(r=>r.reference===input.reference);
  if(previous){
    demand(previous.obligationId===o.id&&previous.cents===input.cents&&previous.date===input.date&&previous.state==='CONFIRMED','Divergência: revisar referência existente, sem nova baixa.');
    if(previous.reconciled)return d;
    demand(c.mode==='HYBRID'&&previous.origin==='MANUAL','Origem não conciliável.');
    return replaceReceipt(d,{...previous,reconciled:true});
  }
  demand(paid(d,o.id)+pending(d,o.id)+input.cents<=o.cents,'Evento excede saldo disponível.');
  const r:Receipt={id:'demo-receipt-'+(d.receipts.length+1),obligationId:o.id,reference:input.reference,cents:input.cents,date:input.date,
    method:'PSP_DEMO',evidence:'DEMO_WEBHOOK_AND_GET',origin:'PSP_DEMO',state:'CONFIRMED',reconciled:true};
  return entry({...d,receipts:[...d.receipts,r]},r);
}
export function contest(d:Demo,member:string,id:string,reason:string):Demo {
  const r=getReceipt(d,id);demand(getObligation(d,r.obligationId).member===member&&r.state==='CONFIRMED'&&text(reason),'Contestação inválida ou fora da própria competência.');
  return replaceReceipt(d,{...r,state:'CONTESTED',reason});
}
export function reverseManual(d:Demo,role:Role,id:string,reason:string,reversalDate?:string):Demo {
  demand(role==='TENANT_ADMIN'&&text(reason),'Justificativa de estorno obrigatória.');
  const r=getReceipt(d,id);demand(r.origin==='MANUAL'&&!r.reconciled,'Evento PSP ou reconciliado exige revisão do provedor.');
  if(r.state==='REVERSED'){demand(r.reason===reason,'Estorno já registrado.');return d;}
  demand(r.state==='CONFIRMED'||r.state==='CONTESTED','Registro não estornável.');
  const when=reversalDate??r.date, o=getObligation(d,r.obligationId), c=d.cycles.find(x=>x.id===o.cycleId)!;
  demand(date(when)>=date(r.date)&&date(when)<=date(c.closing),'Data de estorno fora do ciclo ou anterior ao recebimento.');
  return entry(replaceReceipt(d,{...r,state:'REVERSED',reason,reversalDate:when}),r,true);
}
export function memberObligations(d:Demo,role:Role,member:string):readonly Obligation[]{
  demand(role==='TENANT_ADMIN'||role==='TENANT_MEMBER','Perfil fictício inválido.');
  return role==='TENANT_ADMIN'?d.obligations:d.obligations.filter(o=>o.member===member);
}
export function risk(d:Demo,cycleId:string,member:string,asOf:string){
  const c=d.cycles.find(x=>x.id===cycleId);if(!c)throw Error('Ciclo inexistente.');
  const overdue=d.obligations.filter(o=>o.cycleId===cycleId&&o.member===member&&date(o.due)<date(asOf)&&paid(d,o.id)<o.cents);
  return {days:Math.max(0,...overdue.map(o=>date(asOf)-date(o.due))),competences:new Set(overdue.map(o=>o.due.slice(0,7))).size,
    byDays:overdue.some(o=>date(asOf)-date(o.due)>=c.lateDays),byCompetences:new Set(overdue.map(o=>o.due.slice(0,7))).size>=c.lateCompetences};
}
export const firstDemoCycle:Cycle={id:'demo-cycle-1',start:'2026-12-10',first:'2026-12-10',last:'2027-11-10',closing:'2027-12-20',
  cents:15000,quotas:1,adminBps:1500,lateDays:90,lateCompetences:3,mode:'MANUAL'};
export const expandedDemoCapacity=Object.freeze({members:200,quotas:400,commercialActivation:false});
export function previewDemoLicense(monthly:string,annual:string,period:'MONTHLY'|'ANNUAL',memberCount:number,quotaCount:number){
  const m=parseDemoMoney(monthly),a=parseDemoMoney(annual);
  demand(period==='MONTHLY'||period==='ANNUAL','Periodicidade inválida.');
  demand(Number.isInteger(memberCount)&&memberCount>=1&&memberCount<=expandedDemoCapacity.members&&Number.isInteger(quotaCount)&&quotaCount>=memberCount&&quotaCount<=expandedDemoCapacity.quotas,'Capacidade fora do plano demonstrativo.');
  return {amountCents:period==='MONTHLY'?m:a,months:period==='MONTHLY'?1:12,channel:'MERCADO_PAGO_PIX_DEMO' as const,activation:false as const};
}
