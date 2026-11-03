import { Contribution } from '../types';

export interface DisplayContribution extends Contribution {
  member_name?: string | null;
}

/** A resposta deve pertencer à identidade/tenant/papel que realizou a consulta. */
export function contributionScopeKey(userId: string, tenantId: string, role: string): string {
  return JSON.stringify([userId, tenantId, role]);
}

const record=(v:unknown):v is Record<string,unknown> =>
  v!==null&&typeof v==='object'&&!Array.isArray(v);
const identifier=(v:unknown):v is string =>
  typeof v==='string'&&/^[A-Za-z0-9-]{1,100}$/.test(v);
const isoDate=(v:unknown):v is string => {
  if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(v))return false;
  const d=new Date(v+'T00:00:00Z');
  return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===v;
};
const isoTime=(v:unknown):v is string =>
  typeof v==='string'&&v.length<=48&&
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$/.test(v)&&
  Number.isFinite(Date.parse(v));
const sensitive=['cpf','email','phone','token','password','password_hash',
 'bank_account','pix_key','access_token','secret','balance','user_agent'];
const noSensitive=(v:Record<string,unknown>)=>
  !sensitive.some(key=>Object.prototype.hasOwnProperty.call(v,key));

/** Rejeita fração de centavo, NaN, negativos e overflow. Sem arredondar o pagamento. */
function centValue(v:unknown):number {
  if(typeof v==='string'){
    if(!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(v))
      throw new Error('Valor monetário inválido.');
  }else if(typeof v!=='number'||!Number.isFinite(v)){
    throw new Error('Valor monetário inválido.');
  }
  const n=Number(v);
  const scaled=n*100;
  if(!Number.isFinite(n)||n<0||!Number.isSafeInteger(Math.round(scaled))||
     Math.abs(scaled-Math.round(scaled))>1e-6)
    throw new Error('Valor monetário sem precisão de centavos.');
  return Math.round(scaled)/100;
}

/** Sem fallback local: normaliza somente dados válidos da API autorizada. */
export function normalizeContributions(value:unknown,tenantId:string):DisplayContribution[] {
  if(!identifier(tenantId)||!Array.isArray(value)||value.length>1000)
    throw new Error('Resposta de contribuições inválida.');
  const seen=new Set<string>();
  return value.map((item:unknown)=>{
    if(!record(item)||!noSensitive(item)||item.tenant_id!==tenantId||
       !identifier(item.id)||!identifier(item.membership_id)||
       !identifier(item.cycle_id)||typeof item.competence!=='string'||
       !/^\d{4}-(?:0[1-9]|1[0-2])$/.test(item.competence)||
       !isoDate(item.due_date)||
       !['PENDENTE','PARCIAL','QUITADA'].includes(String(item.payment_status))||
       !['NO_PRAZO','VENCIDA','REGULARIZADA'].includes(String(item.due_status))||
       (item.paid_at!=null&&!isoTime(item.paid_at))||
       (item.member_name!=null&&
        (typeof item.member_name!=='string'||!item.member_name.trim()||
          item.member_name.length>200)))
      throw new Error('Dados de contribuição inconsistentes.');
    const id=(item.id as string).toLowerCase();
    if(seen.has(id))throw new Error('Contribuição duplicada.');
    seen.add(id);
    const due=centValue(item.amount_due),paid=centValue(item.amount_paid);
    if(due<=0||paid>due)throw new Error('Valores de contribuição inconsistentes.');
    if(item.payment_status==='QUITADA'&&paid!==due)
      throw new Error('Quitação sem valor integral confirmado.');
    return {
      id:item.id as string,tenant_id:tenantId,
      cycle_id:item.cycle_id as string,membership_id:item.membership_id as string,
      competence:item.competence as string,due_date:item.due_date as string,
      amount_due:due,amount_paid:paid,
      payment_status:item.payment_status as DisplayContribution['payment_status'],
      due_status:(item.due_status==='NO_PRAZO'?'A_VENCER':item.due_status) as DisplayContribution['due_status'],
      paid_at:(item.paid_at??null) as DisplayContribution['paid_at'],
      member_name:(item.member_name??null) as string|null,
    };
  });
}
