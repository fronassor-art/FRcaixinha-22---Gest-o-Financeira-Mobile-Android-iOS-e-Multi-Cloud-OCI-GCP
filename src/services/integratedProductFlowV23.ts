/** Single ephemeral product workspace; no network, storage, real IDs or execution. */
import {addCycle,emptyDemo,firstDemoCycle,cycleDueDates,recordManual,paid,previewDemoLicense,
  type Cycle,type Demo,type ManualInput,type Obligation,type Role} from './productHomologationV23';
import {civilDateDayNumberV22 as day} from './cycleWindowV22';
import {calculateCapitalDaysV22,type CapitalEventV22} from './capitalDaysV22';
import {calculateEligibleProfitBasisV22,type ProfitBasisLineV22} from './eligibleProfitBasisV22';

type Offer=Readonly<{monthly:string;annual:string;period:'MONTHLY'|'ANNUAL';members:number;quotas:number}>;
type Admission=Readonly<{cycleId:string;member:string;quotas:number;joined:string;state:'INVITED'|'ACCEPTED'|'EXIT_REQUESTED'}>;
type CashEvent=Readonly<{id:string;cycleId:string;date:string;cents:number;kind:'EXPENSE'|'CREDIT_OUT'|'PRINCIPAL_IN'|'INTEREST_IN'|'PAYOUT';evidence:string;reference:string;member?:string}>;
type Installment=Readonly<{due:string;principal:number;interest:number;paidPrincipal:number;paidInterest:number}>;
type Loan=Readonly<{id:string;cycleId:string;member:string;principal:number;rateBps:number;disbursement:string;installments:readonly Installment[];
 state:'REQUESTED'|'RESERVED'|'DISBURSED'|'REJECTED'|'PAID'}>;
type Campaign=Readonly<{id:string;cycleId:string;members:readonly string[];amount:number;validUntil:string;responses:Readonly<Record<string,'INTERESTED'|'DECLINED'>>}>;
type Closing=Readonly<{cycleId:string;cutoff:string;net:string;admin:string;memberPool:string;pending:string;rows:readonly {member:string;capital:number;profit:number;weight:string}[];ready:boolean;fingerprint:string}>;
export type Flow=Demo&Readonly<{step:number;offer:Offer|null;admissions:readonly Admission[];cashEvents:readonly CashEvent[];loans:readonly Loan[];campaigns:readonly Campaign[];settled:readonly string[];imports:readonly string[]}>;
const demand=(ok:unknown,msg:string):void=>{if(!ok)throw Error(msg)};
const money=(n:number)=>Number.isSafeInteger(n)&&n>0&&n<=100000000;
const refOk=(v:string)=>/^DEMO-[A-Za-z0-9_-]{3,100}$/.test(v);
const evidenceOk=(v:string)=>v.trim()===v&&v.length>=3&&v.length<=160;
const memberOk=(v:string)=>/^demo-member-[a-z0-9-]{1,40}$/.test(v);
const admin=(role:Role)=>demand(role==='TENANT_ADMIN','Ação exclusiva do administrador fictício.');
const getCycle=(f:Flow,id:string):Cycle=>{const c=f.cycles.find(c=>c.id===id);if(!c)throw Error('Ciclo inexistente.');return c;};
const open=(f:Flow,id:string):Cycle=>{const c=getCycle(f,id);demand(!f.settled.includes(id),'Ciclo liquidado; histórico preservado.');return c;};
const inCycle=(c:Cycle,date:string)=>day(date)>=day(c.start)&&day(date)<=day(c.closing);
const active=(f:Flow,cycleId:string,member:string)=>f.admissions.some(a=>a.cycleId===cycleId&&a.member===member&&a.state==='ACCEPTED');
const sampleOffer:Offer={monthly:'100,00',annual:'850,00',period:'MONTHLY',members:200,quotas:400};
export const demoOffer=sampleOffer;
export function newFlow(seed=false):Flow{
 const base=seed?addCycle(emptyDemo(),'TENANT_ADMIN',firstDemoCycle):emptyDemo();
 return {...base,step:seed?5:0,offer:seed?sampleOffer:null,admissions:seed?['demo-member-a','demo-member-b'].map(member=>({cycleId:firstDemoCycle.id,member,quotas:1,joined:firstDemoCycle.start,state:'ACCEPTED' as const})):[],
 cashEvents:[],loans:[],campaigns:[],settled:[],imports:[]};
}
/** The real profile never changes; the actor here is a labelled fictitious workflow role. */
export function onboarding(f:Flow,actor:'MASTER'|'TENANT_ADMIN',action:'INVITE'|'REGISTER'|'OFFER'|'ACCEPT'|'PAY',offer?:Offer,proof?:string):Flow{
 const order=['INVITE','REGISTER','OFFER','ACCEPT','PAY'] as const;
 demand(f.step<5&&order[f.step]===action,'Conclua a etapa anterior primeiro.');
 demand(actor===(action==='INVITE'?'MASTER':'TENANT_ADMIN'),'Perfil fictício incorreto.');
 if(action==='OFFER'){
   demand(!!offer,'Oferta obrigatória.');const o=offer!;
   previewDemoLicense(o.monthly,o.annual,o.period,o.members,o.quotas);
   return {...f,step:3,offer:{...o}};
 }
 if(action==='ACCEPT')demand(proof==='DEMO_CONTRATO_A_ACCEPTED','Aceite fictício explícito necessário.');
 if(action==='PAY')demand(proof==='DEMO_PIX_WEBHOOK_GET_SETTLEMENT','Somente confirmação fictícia do Pix SaaS.');
 return {...f,step:f.step+1};
}
export function openFlowCycle(f:Flow,role:Role,c:Cycle,accepted:boolean):Flow{
 admin(role);demand(f.step===5&&!!f.offer&&accepted,'Licença e política fictícias devem ser aceitas antes do ciclo.');
 // Reuse validation but generate obligations only after a member accepts Contract B.
 const d=addCycle(f,role,c);
 return {...f,...d,obligations:f.obligations};
}
export function inviteMember(f:Flow,role:Role,cycleId:string,member:string,quotas:number,joined:string):Flow{
 admin(role);const c=open(f,cycleId);demand(memberOk(member)&&Number.isInteger(quotas)&&quotas>0&&quotas<=400&&money(quotas*c.cents)&&inCycle(c,joined)&&joined<=c.last,'Convite, cotas ou adesão inválidos.');
 demand(!f.admissions.some(a=>a.cycleId===cycleId&&a.member===member),'Convite já existente neste ciclo.');
 return {...f,admissions:[...f.admissions,{cycleId,member,quotas,joined,state:'INVITED'}]};
}
export function acceptMember(f:Flow,member:string,cycleId:string,accepted:boolean):Flow{
 const c=open(f,cycleId),a=f.admissions.find(a=>a.cycleId===cycleId&&a.member===member);
 demand(!!a&&accepted&&a!.state==='INVITED'&&!!f.offer,'Convite e aceite do Contrato B obrigatórios.');
 const used=f.admissions.filter(x=>x.state!=='INVITED'&&!f.settled.includes(x.cycleId));
 demand(new Set([...used.map(x=>x.member),member]).size<=f.offer!.members&&used.reduce((n,x)=>n+x.quotas,0)+a!.quotas<=f.offer!.quotas,'Capacidade simultânea do plano excedida.');
 const obligations:Obligation[]=cycleDueDates(c).filter(d=>d>=a!.joined).map(due=>({id:cycleId+'/'+member+'/'+due,cycleId,member,due,cents:c.cents*a!.quotas}));
 demand(obligations.length>0,'Adesão posterior à última competência.');
 return {...f,admissions:f.admissions.map(x=>x===a?{...x,state:'ACCEPTED'}:x),obligations:[...f.obligations,...obligations]};
}
export function requestExit(f:Flow,member:string,cycleId:string):Flow{
 open(f,cycleId);demand(active(f,cycleId,member),'Adesão ativa necessária.');
 // Preserve obligations and capital: settlement/release is not inferred.
 return {...f,admissions:f.admissions.map(a=>a.cycleId===cycleId&&a.member===member?{...a,state:'EXIT_REQUESTED'}:a)};
}
export function mergeFinance(f:Flow,d:Demo):Flow{
 for(const r of d.receipts){const o=d.obligations.find(o=>o.id===r.obligationId);demand(!!o,'Competência inválida.');const a=f.admissions.find(a=>a.cycleId===o!.cycleId&&a.member===o!.member);demand(!!a&&a!.state!=='INVITED'&&r.date>=a!.joined,'Recebimento anterior à adesão ou sem aceite.');demand(!f.cashEvents.some(e=>e.reference===r.reference),'Referência já usada em outra operação.');}
 for(const id of f.settled){
   const relevant=(x:Demo)=>JSON.stringify([x.cycles.filter(c=>c.id===id),x.obligations.filter(o=>o.cycleId===id),x.receipts.filter(r=>x.obligations.some(o=>o.id===r.obligationId&&o.cycleId===id)),x.journal.filter(j=>j.cycleId===id)]);
   demand(relevant(f)===relevant(d),'Ciclo liquidado; alterações proibidas.');
 }
 const next={...f,...d};
 for(const c of next.cycles){const dates=new Set([...next.receipts.filter(r=>next.obligations.some(o=>o.id===r.obligationId&&o.cycleId===c.id)).flatMap(r=>r.reversalDate?[r.date,r.reversalDate]:[r.date]),...next.cashEvents.filter(e=>e.cycleId===c.id).map(e=>e.date)]);for(const date of dates){const b=balances(next,c.id,date);demand(b.manual>=0&&b.provider>=0,'Alteração exige revisão de caixa: insuficiência histórica.');}}
 return next;
}
function receiptValueAt(r:Demo['receipts'][number],asOf:string){return r.state!=='PENDING'&&r.date<=asOf&&(!r.reversalDate||r.reversalDate>asOf)?r.cents:0;}
function paidAt(f:Flow,id:string,date:string){return f.receipts.filter(r=>r.obligationId===id).reduce((n,r)=>n+receiptValueAt(r,date),0);}
export function balances(f:Flow,cycleId:string,asOf='9999-12-31'){
 getCycle(f,cycleId);
 const ob=new Set(f.obligations.filter(o=>o.cycleId===cycleId).map(o=>o.id));
 const receipts=f.receipts.filter(r=>ob.has(r.obligationId));
 const manualIn=receipts.filter(r=>r.origin==='MANUAL').reduce((n,r)=>n+receiptValueAt(r,asOf),0),provider=receipts.filter(r=>r.origin==='PSP_DEMO').reduce((n,r)=>n+receiptValueAt(r,asOf),0);
 const events=f.cashEvents.filter(x=>x.cycleId===cycleId&&x.date<=asOf);
 const incoming=events.filter(x=>x.kind==='PRINCIPAL_IN'||x.kind==='INTEREST_IN').reduce((n,x)=>n+x.cents,0);
 const outgoing=events.filter(x=>x.kind==='EXPENSE'||x.kind==='CREDIT_OUT'||x.kind==='PAYOUT').reduce((n,x)=>n+x.cents,0);
 const manual=manualIn+incoming-outgoing;
 const cash=manual+provider;
 const reserved=f.loans.filter(l=>l.cycleId===cycleId&&l.state==='RESERVED').reduce((n,l)=>n+l.principal,0);
 const capital=manualIn+provider;
 const interest=events.filter(x=>x.kind==='INTEREST_IN').reduce((n,x)=>n+x.cents,0);
 const expenses=events.filter(x=>x.kind==='EXPENSE').reduce((n,x)=>n+x.cents,0);
 return {manual,provider,cash,reserved,available:Math.max(0,cash-reserved),manualAvailable:Math.max(0,manual-reserved),capital,interest,expenses};
}
function uniqueRef(f:Flow,reference:string):void{
 demand(refOk(reference)&&!f.cashEvents.some(x=>x.reference===reference)&&!f.receipts.some(x=>x.reference===reference),'Referência fictícia inválida ou duplicada.');
}
export function expense(f:Flow,role:Role,cycleId:string,amount:number,date:string,reference:string,evidence:string):Flow{
 admin(role);const c=open(f,cycleId);uniqueRef(f,reference);
 demand(c.mode!=='MERCADO_PAGO'&&money(amount)&&inCycle(c,date)&&evidenceOk(evidence)&&amount<=balances(f,cycleId,date).manualAvailable,'Despesa sem evidência, modo compatível ou caixa disponível.');
 return {...f,cashEvents:[...f.cashEvents,{id:'demo-cash-'+(f.cashEvents.length+1),cycleId,date,cents:amount,kind:'EXPENSE',evidence,reference}]};
}
export function importBatch(f:Flow,role:Role,cycleId:string,batchId:string,cutoff:string,rows:readonly ManualInput[],accepted:boolean):Flow{
 admin(role);const c=open(f,cycleId);demand(refOk(batchId)&&accepted&&inCycle(c,cutoff)&&rows.length>0&&rows.length<=1000,'Lote, corte ou aceite inválido.');
 if(f.imports.includes(batchId))throw Error('Lote já importado; confira histórico.');
 let next:Demo=f;
 const seen=new Set<string>();
 for(const row of rows){
  demand(refOk(row.reference)&&!seen.has(row.reference)&&!f.receipts.some(r=>r.reference===row.reference)&&!f.cashEvents.some(x=>x.reference===row.reference)&&row.date<=cutoff&&f.obligations.some(o=>o.id===row.obligationId&&o.cycleId===cycleId),'Referência repetida, evento posterior ao corte ou fora do ciclo.');
  seen.add(row.reference);
  next=recordManual(next,role,row); // remains pending until explicit evidence review
 }
 return {...mergeFinance(f,next),imports:[...f.imports,batchId]};
}
export function offerCredit(f:Flow,role:Role,cycleId:string,members:readonly string[],amount:number,validUntil:string):Flow{
 admin(role);const c=open(f,cycleId);demand(members.length>0&&new Set(members).size===members.length&&members.every(m=>active(f,cycleId,m))&&money(amount)&&inCycle(c,validUntil),'Oferta, público ou validade inválidos.');
 return {...f,campaigns:[...f.campaigns,{id:'demo-offer-'+(f.campaigns.length+1),cycleId,members:[...members],amount,validUntil,responses:{}}]};
}
export function respondCredit(f:Flow,member:string,id:string,response:'INTERESTED'|'DECLINED',date:string):Flow{
 const o=f.campaigns.find(x=>x.id===id);demand(!!o&&['INTERESTED','DECLINED'].includes(response),'Oferta inexistente.');
 const c=open(f,o!.cycleId);demand(o!.members.includes(member)&&active(f,o!.cycleId,member)&&inCycle(c,date)&&date<=o!.validUntil,'Oferta vencida ou de outro membro.');
 return {...f,campaigns:f.campaigns.map(x=>x===o?{...x,responses:{...x.responses,[member]:response}}:x)};
}
const rounded=(num:bigint,den:bigint)=>Number((num*2n+den)/(den*2n));
function anchored(first:string,offset:number):string{
 const y=Number(first.slice(0,4)),m=Number(first.slice(5,7))-1,d=Number(first.slice(8));
 const b=new Date(Date.UTC(y,m+offset,1));const last=new Date(Date.UTC(b.getUTCFullYear(),b.getUTCMonth()+1,0)).getUTCDate();
 return new Date(Date.UTC(b.getUTCFullYear(),b.getUTCMonth(),Math.min(d,last))).toISOString().slice(0,10);
}
/** Price in rational integer arithmetic; first period days/30, explicit civil anchor. */
export function price(c:Cycle,principal:number,rateBps:number,n:number,disbursement:string):Installment[]{
 demand(money(principal)&&Number.isInteger(rateBps)&&rateBps>=0&&rateBps<=10000&&Number.isInteger(n)&&n>=1&&n<=12&&inCycle(c,disbursement),'Condições de crédito inválidas.');
 // Due day follows the first contribution anchor, first due in next civil month.
 const next=anchored(disbursement.slice(0,7)+'-'+c.first.slice(8),1);
 const dates=Array.from({length:n},(_,i)=>anchored(next.slice(0,7)+'-'+c.first.slice(8),i));
 demand(dates[n-1]<=c.closing&&dates[0]>disbursement,'Parcelas fora do ciclo.');
 const firstDays=day(dates[0])-day(disbursement);
 const den=300000n;const factors=dates.map((_,i)=>BigInt(rateBps)*BigInt(i===0?firstDays:30));
 // Sum of inverse cumulative factors using exact numerator and denominator.
 let p=1n,q=1n,sumN=0n,sumD=1n;
 for(const f of factors){p*=den+f;q*=den;sumN=sumN*p+q*sumD;sumD*=p;}
 const installment=rounded(BigInt(principal)*sumD,sumN);
 let balance=principal;
 return dates.map((due,i)=>{
   const interest=rounded(BigInt(balance)*factors[i],den);
   const amort=i===n-1?balance:installment-interest;
   demand(amort>0&&amort<=balance&&money(amort+interest),'Prestação não amortiza o principal.');
   balance-=amort;return {due,principal:amort,interest,paidPrincipal:0,paidInterest:0};
 });
}
export function requestCredit(f:Flow,member:string,cycleId:string,principal:number,rateBps:number,term:number,date:string,accepted:boolean):Flow{
 const c=open(f,cycleId);demand(active(f,cycleId,member)&&accepted,'Adesão ativa e aceite da simulação necessários.');
 const capital=f.obligations.filter(o=>o.cycleId===cycleId&&o.member===member).reduce((n,o)=>n+paidAt(f,o.id,date),0);
 const overdue=f.obligations.filter(o=>o.cycleId===cycleId&&o.member===member&&o.due<date&&paidAt(f,o.id,date)<o.cents);
 const late=overdue.some(o=>day(date)-day(o.due)>=c.lateDays)||new Set(overdue.map(o=>o.due.slice(0,7))).size>=c.lateCompetences;
 demand(principal<=capital&&!late&&!f.loans.some(l=>l.cycleId===cycleId&&l.member===member&&!['REJECTED','PAID'].includes(l.state)),'Crédito fictício exige capital confirmado, elegibilidade e ausência de outro pedido impeditivo.');
 return {...f,loans:[...f.loans,{id:'demo-loan-'+(f.loans.length+1),cycleId,member,principal,rateBps,disbursement:date,installments:price(c,principal,rateBps,term,date),state:'REQUESTED'}]};
}
function getLoan(f:Flow,id:string):Loan{const l=f.loans.find(l=>l.id===id);if(!l)throw Error('Pedido inexistente.');return l;}
export function decideCredit(f:Flow,role:Role,id:string,approved:boolean):Flow{
 admin(role);const l=getLoan(f,id);open(f,l.cycleId);
 demand(l.state==='REQUESTED'&&active(f,l.cycleId,l.member),'Pedido não decidível.');
 if(approved)demand(l.principal<=balances(f,l.cycleId,l.disbursement).manualAvailable,'Caixa livre insuficiente.');
 return {...f,loans:f.loans.map(x=>x===l?{...x,state:approved?'RESERVED':'REJECTED'}:x)};
}
export function disburseCredit(f:Flow,role:Role,id:string,date:string,reference:string,evidence:string):Flow{
 admin(role);const l=getLoan(f,id),c=open(f,l.cycleId);uniqueRef(f,reference);
 const capital=f.obligations.filter(o=>o.cycleId===l.cycleId&&o.member===l.member).reduce((n,o)=>n+paidAt(f,o.id,date),0);
 demand(c.mode!=='MERCADO_PAGO'&&l.state==='RESERVED'&&date===l.disbursement&&active(f,l.cycleId,l.member)&&capital>=l.principal&&evidenceOk(evidence)&&balances(f,l.cycleId,date).manual>=balances(f,l.cycleId,date).reserved,'Desembolso fictício sem reserva, evidência, elegibilidade ou data aceita; reavalie a simulação.');
 return {...f,loans:f.loans.map(x=>x===l?{...x,state:'DISBURSED'}:x),cashEvents:[...f.cashEvents,{id:'demo-cash-'+(f.cashEvents.length+1),cycleId:l.cycleId,member:l.member,date,cents:l.principal,kind:'CREDIT_OUT',reference,evidence}]};
}
export function repayCredit(f:Flow,role:Role,id:string,amount:number,date:string,reference:string,evidence:string):Flow{
 admin(role);const l=getLoan(f,id),c=open(f,l.cycleId);uniqueRef(f,reference);
 demand(l.state==='DISBURSED'&&money(amount)&&inCycle(c,date)&&evidenceOk(evidence)&&c.mode!=='MERCADO_PAGO','Recebimento de crédito inválido.');
 // This demo models on-date partial payments; late fees/early settlement require the accepted policy, not invented defaults.
 const first=l.installments.find(i=>i.paidPrincipal<i.principal||i.paidInterest<i.interest);
 demand(!!first&&date===first!.due,'Neste ensaio, use a data da parcela aberta; encargos de atraso e quitação antecipada exigem integração da política.');
 const remaining=first!.principal-first!.paidPrincipal+first!.interest-first!.paidInterest;
 demand(amount<=remaining,'Valor excede a parcela selecionada.');
 const interest=Math.min(amount,first!.interest-first!.paidInterest),principal=amount-interest;
 const installments=l.installments.map(i=>i===first?{...i,paidInterest:i.paidInterest+interest,paidPrincipal:i.paidPrincipal+principal}:i);
 const events:CashEvent[]=[];for(const [kind,cents] of [['INTEREST_IN',interest],['PRINCIPAL_IN',principal]] as const){if(cents)events.push({id:'demo-cash-'+(f.cashEvents.length+events.length+1),cycleId:l.cycleId,member:l.member,date,cents,kind,reference,evidence});}
 return {...f,loans:f.loans.map(x=>x===l?{...x,installments,state:installments.every(i=>i.principal===i.paidPrincipal&&i.interest===i.paidInterest)?'PAID':'DISBURSED'}:x),cashEvents:[...f.cashEvents,...events]};
}
export function previewClosing(f:Flow,role:Role,cycleId:string,cutoff:string):Closing{
 admin(role);const c=open(f,cycleId);
 demand(day(cutoff)>day(c.last)&&day(cutoff)<=day(c.closing)+1,'Selecione explicitamente o corte exclusivo após a última competência.');
 const scope={tenantId:'demo-tenant-only',cycleId};
 const window={mode:'EXPLICIT_ACCEPTED_WINDOW' as const,scope,cycleStart:c.start,cycleEndExclusive:cutoff,versionId:'demo-policy-'+cycleId,policyDigest:'a'.repeat(64),accepted:true,acceptedAt:'2026-01-01T00:00:00.000Z',frozenAt:'2026-01-01T00:00:00.000Z',acceptanceEvidenceRef:'DEMO_ONLY_NOT_AUTHENTICATED'};
 const ob=f.obligations.filter(o=>o.cycleId===cycleId),rs=f.receipts.filter(r=>ob.some(o=>o.id===r.obligationId)),cs=f.cashEvents.filter(e=>e.cycleId===cycleId);
 demand(rs.every(r=>r.date<cutoff&&(!r.reversalDate||r.reversalDate<cutoff))&&cs.every(e=>e.date<cutoff),'Eventos após o corte: revisão necessária.');
 const members=f.admissions.filter(a=>a.cycleId===cycleId&&a.state!=='INVITED').map(a=>{
   const events:CapitalEventV22[]=[];
   for(const r of rs.filter(r=>ob.some(o=>o.id===r.obligationId&&o.member===a.member)&&r.state!=='PENDING')){
     events.push({...scope,membershipId:a.member,eventId:r.id,effectiveDate:r.date,kind:'CONTRIBUTION',amountCents:r.cents,status:'CONFIRMED'});
     if(r.state==='REVERSED')events.push({...scope,membershipId:a.member,eventId:r.id+'-reversal',effectiveDate:r.reversalDate??r.date,kind:'REVERSAL',amountCents:r.cents,status:'CONFIRMED',reversesEventId:r.id});
   }
   return {...scope,membershipId:a.member,openingCapitalCents:0,eligibilityPeriods:[{startDate:a.joined,endDateExclusive:cutoff}],events};
 });
 const profitLines:ProfitBasisLineV22[]=cs.filter(e=>e.kind==='INTEREST_IN'||e.kind==='EXPENSE').map(e=>({...scope,lineId:e.id,kind:e.kind==='INTEREST_IN'?'REALIZED_REVENUE':'RECOGNIZED_EXPENSE',status:'CONFIRMED',currency:'BRL',amountCents:e.cents,competenceDate:e.date,recognizedDate:e.date,financialDate:e.date,reconciled:true,policyAccepted:true,evidenceRef:'DEMO:'+e.evidence,authorizationRef:'DEMO_ONLY'}));
 const p=calculateEligibleProfitBasisV22({scope,cycleStart:c.start,cycleEndExclusive:cutoff,cycleWindowAcceptance:window,lines:profitLines});
 const result=calculateCapitalDaysV22({scope,cycleStart:c.start,cycleEndExclusive:cutoff,cycleWindowAcceptance:window,netProfitCents:Number(p.distributableNetProfitCents),adminShareBps:c.adminBps,members});
 const rows=result.members.map(m=>({member:m.membershipId,capital:ob.filter(o=>o.member===m.membershipId).reduce((n,o)=>n+paid(f,o.id),0),profit:Number(m.memberShareCents),weight:m.eligibleCapitalDays}));
 const needed=rows.reduce((n,row)=>n+row.capital+row.profit,Number(result.adminShareCents));
 // No automatic confiscation, no distribution when evidence/obligations/eligibility or liquidity is unresolved.
 const ready=c.mode!=='MERCADO_PAGO'&&members.length>0&&ob.every(o=>paid(f,o.id)===o.cents)&&rs.every(r=>r.state!=='PENDING'&&r.state!=='CONTESTED')&&
  f.admissions.filter(a=>a.cycleId===cycleId).every(a=>a.state==='ACCEPTED')&&f.loans.filter(l=>l.cycleId===cycleId).every(l=>l.state==='PAID'||l.state==='REJECTED')&&
  result.memberPoolPendingCents==='0'&&balances(f,cycleId,c.closing).manualAvailable>=needed;
 return {cycleId,cutoff,net:p.rawNetResultCents,admin:result.adminShareCents,memberPool:result.memberPoolCents,pending:result.memberPoolPendingCents,rows,ready,fingerprint:JSON.stringify([c,ob,rs,cs,f.loans.filter(l=>l.cycleId===cycleId),f.admissions.filter(a=>a.cycleId===cycleId),cutoff])};
}
export function settleClosing(f:Flow,role:Role,review:Closing,date:string,reference:string,evidence:string):Flow{
 admin(role);const c=open(f,review.cycleId);uniqueRef(f,reference);
 const fresh=previewClosing(f,role,c.id,review.cutoff);
 demand(fresh.ready&&fresh.fingerprint===review.fingerprint&&date===c.closing&&evidenceOk(evidence),'Prévia desatualizada, pendência, falta de liquidez ou evidência; não encerrar.');
 const payouts=[...fresh.rows.map(r=>({member:r.member,cents:r.capital+r.profit})),{member:'demo-admin',cents:Number(fresh.admin)}].filter(x=>x.cents>0);
 return {...f,settled:[...f.settled,c.id],cashEvents:[...f.cashEvents,...payouts.map((x,i)=>({id:'demo-cash-'+(f.cashEvents.length+i+1),cycleId:c.id,date,cents:x.cents,member:x.member,kind:'PAYOUT' as const,reference,evidence}))]};
}

// Derive balanced postings for every cash event; receipt postings are the existing immutable journal.
export function integratedJournal(f:Flow,cycleId:string){
 const accounts={EXPENSE:['DESPESA_DEMO','CAIXA_MANUAL_DEMO'],CREDIT_OUT:['CREDITO_A_RECEBER_DEMO','CAIXA_MANUAL_DEMO'],PRINCIPAL_IN:['CAIXA_MANUAL_DEMO','CREDITO_A_RECEBER_DEMO'],INTEREST_IN:['CAIXA_MANUAL_DEMO','RECEITA_JUROS_DEMO'],PAYOUT:['LIQUIDACAO_DIREITOS_DEMO','CAIXA_MANUAL_DEMO']} as const;
 return [...f.journal.filter(j=>j.cycleId===cycleId).map(j=>({id:j.receiptId,debit:j.debit,credit:j.credit,cents:j.cents})),...f.cashEvents.filter(e=>e.cycleId===cycleId).map(e=>({id:e.id,debit:accounts[e.kind][0],credit:accounts[e.kind][1],cents:e.cents}))];
}
