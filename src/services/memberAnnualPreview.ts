/** Contrato de resumo individual de contribuições: não faz rateio ou fechamento. */
export interface MemberAnnualPreview {
  source:'POSTGRESQL_RLS';
  tenant_id:string;
  year:number;
  contribution_count:number;
  pending_count:number;
  total_due:number;
  amount_paid_recorded:number;
  remaining_due:number;
  result_status:'PREVIA_NAO_E_LIQUIDACAO';
  profit_amount:null;
}
const UUID=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const rec=(x:unknown):x is Record<string,unknown> =>
  typeof x==='object'&&x!==null&&!Array.isArray(x);
function count(n:unknown):number{
  if(typeof n!=='number'||!Number.isSafeInteger(n)||n<0||n>100000)
    throw Error('Quantidade inválida no demonstrativo');
  return n;
}
function money(x:unknown):number{
  if(typeof x==='string'&&!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(x))
    throw Error('Valor inválido no demonstrativo');
  if(typeof x!=='string'&&typeof x!=='number')
    throw Error('Valor inválido no demonstrativo');
  const n=Number(x);
  if(!Number.isFinite(n)||n<0||n>1000000000||
    Math.abs(n*100-Math.round(n*100))>1e-6 ||
    !Number.isSafeInteger(Math.round(n*100)))
    throw Error('Valor inválido no demonstrativo');
  return Math.round(n*100);
}
export function parseMemberAnnualPreview(raw:unknown,tenantId:string,year:number):MemberAnnualPreview{
  if(!rec(raw)||!UUID.test(tenantId)||raw.tenant_id!==tenantId||
    raw.source!=='POSTGRESQL_RLS'||raw.year!==year||
    raw.result_status!=='PREVIA_NAO_E_LIQUIDACAO'||
    raw.profit_amount!==null ||
    ['cpf','email','phone','balance','member_name','other_members','admin_share','password_hash','token']
      .some(k=>Object.prototype.hasOwnProperty.call(raw,k)))
    throw Error('Resumo individual fora do contexto autorizado');
  const total=count(raw.contribution_count),pending=count(raw.pending_count);
  if(pending>total)throw Error('Quantidade inconsistente');
  const due=money(raw.total_due),paid=money(raw.amount_paid_recorded),
    remaining=money(raw.remaining_due);
  if(paid>due||remaining!==due-paid)throw Error('Saldo não concilia');
  return {
    source:'POSTGRESQL_RLS',tenant_id:tenantId,year,
    contribution_count:total,pending_count:pending,
    total_due:due/100,amount_paid_recorded:paid/100,
    remaining_due:remaining/100,
    result_status:'PREVIA_NAO_E_LIQUIDACAO',profit_amount:null
  };
}
