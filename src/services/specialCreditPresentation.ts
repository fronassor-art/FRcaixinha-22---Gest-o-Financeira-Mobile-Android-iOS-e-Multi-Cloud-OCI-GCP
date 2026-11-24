/** M40420 — fail-closed presentation parser, no network or storage. */
import type {
  CreditCampaign, CreditOpportunity, MarketingChannel, CreditPricePreview,
} from './specialCreditApi';

const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MONEY=/^(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,2})?$/;
const CHANNELS=['PUSH','EMAIL','WHATSAPP','SMS'] as const;
const STATUS=['PENDING','INTERESTED','DECLINED'] as const;
const CAMPAIGN_STATUS=['DRAFT','PUBLISHED','CANCELLED'] as const;

function object(value:unknown):Record<string,unknown>{
  if(!value || typeof value!=='object' || Array.isArray(value))
    throw new Error('Dados de Crédito Especial inválidos. Operação bloqueada.');
  return value as Record<string,unknown>;
}
function uuid(value:unknown):value is string{
  return typeof value==='string' && UUID.test(value);
}
function safeText(value:unknown,limit:number):value is string{
  return typeof value==='string' && value.trim().length>0 &&
    value.length<=limit && !/[\u0000-\u001f\u007f]/.test(value);
}
function expiry(value:unknown):value is string{
  return typeof value==='string' && value.length<=40 &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value));
}
function amount(value:unknown):value is string{
  if(typeof value!=='string'||!MONEY.test(value))return false;
  const number=Number(value);
  return Number.isFinite(number)&&number>0&&number<=50000;
}
function oneOf<T extends readonly string[]>(v:unknown,types:T):v is T[number]{
  return typeof v==='string' && types.some(t=>t===v);
}
export function parseCreditOpportunities(raw:unknown):CreditOpportunity[]{
  if(!Array.isArray(raw)||raw.length>100)
    throw new Error('Lista de oportunidades inválida; nenhuma oferta exibida.');
  const seen=new Set<string>();
  return raw.map(item=>{
    const v=object(item);
    if(!uuid(v.recipient_id)||!uuid(v.campaign_id)||!uuid(v.grant_id)||
       !safeText(v.title,100)||!safeText(v.message,500)||
       !amount(v.ceiling_brl)||!expiry(v.expires_at)||
       !oneOf(v.response_status,STATUS)||seen.has(v.recipient_id))
      throw new Error('Oportunidade inválida; nenhuma oferta exibida.');
    seen.add(v.recipient_id);
    return {
      recipient_id:v.recipient_id,campaign_id:v.campaign_id,grant_id:v.grant_id,
      title:v.title,message:v.message,ceiling_brl:v.ceiling_brl,
      expires_at:v.expires_at,response_status:v.response_status,
    };
  });
}
export function parseCreditCampaigns(raw:unknown):CreditCampaign[]{
  if(!Array.isArray(raw)||raw.length>100)
    throw new Error('Lista de campanhas inválida; publicação bloqueada.');
  const seen=new Set<string>();
  return raw.map(item=>{
    const v=object(item);
    if(!uuid(v.id)||!safeText(v.title,100)||!expiry(v.expires_at)||
       !oneOf(v.status,CAMPAIGN_STATUS)||typeof v.recipients!=='number'||
       !Number.isInteger(v.recipients)||v.recipients<0||v.recipients>50||
       seen.has(v.id))
      throw new Error('Campanha inválida; publicação bloqueada.');
    seen.add(v.id);
    return {id:v.id,title:v.title,status:v.status,
      expires_at:v.expires_at,recipients:v.recipients};
  });
}
export function parseCreditPreferences(raw:unknown):{
  preferences:Record<MarketingChannel,boolean>;external_dispatch:false;
}{
  const root=object(raw),prefs=object(root.preferences);
  if(root.external_dispatch!==false ||
     Object.keys(prefs).some(k=>!CHANNELS.includes(k as MarketingChannel)) ||
     CHANNELS.some(c=>typeof prefs[c]!=='boolean'))
    throw new Error('Preferências de comunicação inválidas; canais bloqueados.');
  return {preferences:{
    PUSH:prefs.PUSH as boolean,EMAIL:prefs.EMAIL as boolean,
    WHATSAPP:prefs.WHATSAPP as boolean,SMS:prefs.SMS as boolean,
  },external_dispatch:false};
}
export function creditReplyLabel(state:CreditOpportunity['response_status']):string{
  switch(state){
    case 'PENDING':return 'Aguardando sua resposta';
    case 'INTERESTED':return 'Tenho interesse';
    case 'DECLINED':return 'Não tenho interesse';
  }
}
export function creditOpportunityCanReply(
  offer:CreditOpportunity,nowMs=Date.now(),
):boolean{
  return offer.response_status==='PENDING' &&
    Number.isFinite(nowMs)&&Date.parse(offer.expires_at)>nowMs;
}
export function creditOpportunityCanSimulate(
  offer:CreditOpportunity,nowMs=Date.now(),
):boolean{
  return offer.response_status!=='DECLINED' &&
    Number.isFinite(nowMs)&&Date.parse(offer.expires_at)>nowMs;
}


/** M40430 — fail-closed render when identity/tenant/role changes BEFORE
 * React effects clear cached data. Authentication still belongs to backend.
 */
export function creditContextCanRender(
  loadedKey:string|null,currentKey:string,enabled:boolean,loading:boolean,
):boolean{
  return !loading && enabled === true &&
    typeof loadedKey === 'string' && loadedKey.length > 0 &&
    loadedKey === currentKey;
}
export function creditMessageForContext(
  message:string,messageKey:string|null,currentKey:string,
):string{
  return messageKey===currentKey?message:'';
}


/** M40440: isolate repeated logins of the SAME account without storing tokens. */
export function creditSessionContextKey(
  userId:string,tenantId:string,role:string,generation:number,
):string{
  if(!Number.isSafeInteger(generation)||generation<0)return '';
  return [userId,tenantId,role,'g'+generation].join(':');
}
export function creditSessionCanRender(
  loadedKey:string|null,currentKey:string,enabled:boolean,loading:boolean,
  hasActiveToken:boolean,
):boolean{
  return hasActiveToken === true &&
    creditContextCanRender(loadedKey,currentKey,enabled,loading);
}


/** M40953: do not present a simulation unless the response confirms no
 * approval, reservation or disbursement and matches the requested grant. */
export function parseCreditPricePreview(
  raw:unknown,grantId:string,principal:string,months:number,
):CreditPricePreview{
  const root=object(raw),v=object(root.simulation);
  const fail=()=>{throw new Error('Simulação não confirmada; nenhum resultado exibido.');};
  const cents=(value:unknown):number=>{
    if(typeof value!=='number' && typeof value!=='string')return fail();
    if(typeof value==='string'&&!/^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$/.test(value))return fail();
    const n=Number(value),c=Math.round(n*100);
    if(!Number.isFinite(n)||n<0||!Number.isSafeInteger(c)||Math.abs(n*100-c)>1e-6)return fail();
    return c;
  };
  if(!uuid(grantId)||root.grant_id!==grantId||root.approved!==false||
     root.reserved!==false||root.disbursed!==false||!Number.isInteger(months)||
     months<1||months>6||v.term_months!==months||!amount(principal))return fail();
  const p=cents(v.principal),u=cents(v.uniform_payment),last=cents(v.last_payment);
  const interest=cents(v.total_interest),total=cents(v.total_payable);
  const rawRate=v.monthly_rate;
  if((typeof rawRate!=='number'&&typeof rawRate!=='string')||
     (typeof rawRate==='string'&&!/^(?:0|1)(?:\.[0-9]+)?$/.test(rawRate)))return fail();
  const rate=Number(rawRate);
  if(!Number.isFinite(rate)||rate<0||rate>1||p!==cents(principal)||u<=0||last<=0||
     total!==p+interest||total!==u*(months-1)+last)return fail();
  return {grant_id:grantId,approved:false,reserved:false,disbursed:false,
    simulation:{principal:p/100,monthly_rate:rate,term_months:months,
      uniform_payment:u/100,last_payment:last/100,total_interest:interest/100,total_payable:total/100}};
}
