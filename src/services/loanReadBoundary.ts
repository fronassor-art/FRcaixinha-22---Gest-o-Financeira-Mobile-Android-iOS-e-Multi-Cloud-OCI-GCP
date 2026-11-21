/** Proteção complementar de dados retornados por FastAPI/RLS.
 * Nenhum dado não validado é exibido como informação financeira.
 */
export interface DisplayLoanInstallment {
  id:string;installment_number:number;due_date:string;status:string;
}
export interface DisplayLoan {
  id:string;tenant_id:string;borrower_name?:string;
  principal:number;term_months:number;monthly_payment:number;
  total_interest:number;status:string;installments:DisplayLoanInstallment[];
}
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const date=/^\d{4}-\d{2}-\d{2}$/;
const record=(v:unknown):v is Record<string,unknown> =>
  v!==null&&typeof v==='object'&&!Array.isArray(v);
const safeText=(v:unknown,n:number):v is string=>
  typeof v==='string'&&v.trim().length>0&&v.length<=n;
const money=(v:unknown):number=>{
  if(typeof v!=='number'&&!(typeof v==='string'&&/^\d+(\.\d{1,2})?$/.test(v)))
    throw Error('Valor monetário inválido');
  const x=Number(v);
  if(!Number.isFinite(x)||x<0||x>1000000000)throw Error('Valor fora de faixa');
  return x;
};
const confidential=['cpf','email','phone','password','password_hash','token',
  'token_hash','bank_account','pix_key','access_token','secret','balance'];
const hasConfidential=(v:Record<string,unknown>)=>
  confidential.some(k=>Object.prototype.hasOwnProperty.call(v,k));

export function parseTenantLoans(value:unknown,tenantId:string):DisplayLoan[]{
  if(!uuid.test(tenantId)||!Array.isArray(value)||value.length>500)
    throw Error('Lista de empréstimos inválida');
  const seen=new Set<string>();
  return value.map((raw:unknown)=>{
    if(!record(raw)||hasConfidential(raw)||typeof raw.id!=='string'||
      !uuid.test(raw.id)||raw.tenant_id!==tenantId||
      !safeText(raw.status,64)||!Number.isInteger(raw.term_months)||
      Number(raw.term_months)<1||Number(raw.term_months)>6||
      !Array.isArray(raw.installments)||raw.installments.length>6)
      throw Error('Empréstimo inconsistente ou fora da caixinha');
    const id=raw.id.toLowerCase();
    if(seen.has(id))throw Error('Empréstimo duplicado');
    seen.add(id);
    if(raw.borrower_name!==null&&raw.borrower_name!==undefined&&
       !safeText(raw.borrower_name,200))throw Error('Nome inválido');
    const principal=money(raw.principal);
    const monthlyPayment=money(raw.monthly_payment);
    const interest=money(raw.total_interest);
    if(principal<=0)throw Error('Principal inválido');
    const insSeen=new Set<string>(),numberSeen=new Set<number>();
    const installments=raw.installments.map((ins:unknown)=>{
      if(!record(ins)||hasConfidential(ins)||typeof ins.id!=='string'||
         !uuid.test(ins.id)||!Number.isInteger(ins.installment_number)||
         Number(ins.installment_number)<1||
         Number(ins.installment_number)>Number(raw.term_months)||
         !safeText(ins.due_date,10)||!date.test(ins.due_date)||
         !Number.isFinite(Date.parse(ins.due_date+'T12:00:00Z'))||
         !safeText(ins.status,64))
        throw Error('Parcela inconsistente');
      const normalized=ins.id.toLowerCase();
      if(insSeen.has(normalized)||numberSeen.has(ins.installment_number as number))
        throw Error('Parcela duplicada');
      insSeen.add(normalized);numberSeen.add(ins.installment_number as number);
      return {
        id:ins.id as string,installment_number:ins.installment_number as number,
        due_date:ins.due_date as string,status:ins.status as string,
      };
    });
    return {
      id:raw.id as string,tenant_id:tenantId,
      ...(raw.borrower_name?{borrower_name:raw.borrower_name as string}:{}),
      principal,term_months:raw.term_months as number,
      monthly_payment:monthlyPayment,total_interest:interest,
      status:raw.status as string,installments,
    };
  });
}
