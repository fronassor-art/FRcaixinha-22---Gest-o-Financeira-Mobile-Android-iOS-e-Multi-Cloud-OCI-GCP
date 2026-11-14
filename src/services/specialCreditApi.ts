/** FR Finance AI Studio — Crédito Especial (somente homologação).
 * Sessão no backend + tenant explícito. Sem mocks, sem envio real, sem Pix.
 */
import { authService, getApiBaseUrl } from './authService';
import {
  requestSpecialCredit, assertSandboxCreditCapabilities,
} from './specialCreditRequestBoundary';

export type MarketingChannel = 'PUSH'|'EMAIL'|'WHATSAPP'|'SMS';
export type CreditReply = 'INTERESTED'|'DECLINED';

export interface EligibleMember {id:string;name:string}
export interface CreditGrant {
  id:string;member_id:string;member_name:string;ceiling_brl:string;
  expires_at:string;status:string;
}
export interface CreditOpportunity {
  recipient_id:string;campaign_id:string;grant_id:string;
  title:string;message:string;ceiling_brl:string;expires_at:string;
  response_status:'PENDING'|'INTERESTED'|'DECLINED';
}
export interface CreditCampaign {
  id:string;title:string;status:string;expires_at:string;recipients:number;
}
export interface CreditCapabilities {
  sandbox_enabled:boolean; grants_allow_request_only:boolean; real_credit_enabled:boolean;pix_real_enabled:boolean;
  channels:Record<MarketingChannel,{code_present:boolean;real_delivery_enabled:boolean}>;
}
export interface CreditCycleReadiness {
  current_open_cycle:boolean;
  campaign_creation_allowed:boolean;
  real_credit_enabled:false;
  external_dispatch:false;
}
export interface CreditPricePreview {
  grant_id:string;approved:boolean;reserved:boolean;disbursed:boolean;
  simulation:{
    principal:number;monthly_rate:number;term_months:number;
    uniform_payment:number;last_payment:number;total_interest:number;
    total_payable:number;
  };
}

async function call<T>(tenantId:string,path:string,body?:unknown):Promise<T> {
  return requestSpecialCredit<T>({
    origin:getApiBaseUrl,
    captureSession:()=>authService.captureSession(),
    isCurrent:snapshot=>authService.isSessionSnapshotCurrent(snapshot),
    getUser:()=>authService.getUser(),
    invalidateIfCurrent:snapshot=>authService.invalidateSessionIfCurrent(snapshot),
    send:(url,options)=>fetch(url,options),
  },tenantId,path,body);
}

export const specialCreditApi={
  capabilities:async (tenant:string)=>
    assertSandboxCreditCapabilities(await call<CreditCapabilities>(tenant,'/capabilities')),
  cycleReadiness:(tenant:string)=>call<CreditCycleReadiness>(tenant,'/cycle-readiness'),
  members:(tenant:string)=>call<EligibleMember[]>(tenant,'/members'),
  grants:(tenant:string)=>call<CreditGrant[]>(tenant,'/grants'),
  grant:(tenant:string,memberIds:string[],ceiling:string,expiry:string,reason:string)=>
    call<{grants:Array<{grant_id:string;member_id:string}>}>(tenant,'/grants',{
      member_ids:memberIds,ceiling_brl:ceiling,expires_at:expiry,
      reason,request_id:crypto.randomUUID(),
    }),
  revoke:(tenant:string,id:string)=>call(tenant,'/grants/'+encodeURIComponent(id)+'/revoke',{}),
  campaigns:(tenant:string)=>call<CreditCampaign[]>(tenant,'/campaigns'),
  createCampaign:(tenant:string,grantIds:string[],title:string,message:string,expiry:string)=>
    call<{id:string;status:string}>(tenant,'/campaigns',{
      grant_ids:grantIds,title,body:message,expires_at:expiry,
      request_id:crypto.randomUUID(),
    }),
  publish:(tenant:string,id:string)=>
    call<{status:string;external_dispatch:boolean}>(tenant,'/campaigns/'+encodeURIComponent(id)+'/publish',{}),
  cancel:(tenant:string,id:string)=>
    call(tenant,'/campaigns/'+encodeURIComponent(id)+'/cancel',{}),
  opportunities:(tenant:string)=>call<CreditOpportunity[]>(tenant,'/opportunities'),
  reply:(tenant:string,id:string,status:CreditReply)=>
    call(tenant,'/opportunities/'+encodeURIComponent(id)+'/reply',{status}),
  preferences:(tenant:string)=>call<{preferences:Record<MarketingChannel,boolean>;external_dispatch:boolean}>(tenant,'/preferences'),
  changePreference:(tenant:string,channel:MarketingChannel,optedIn:boolean)=>
    call(tenant,'/preferences',{channel,opted_in:optedIn}),
  simulate:(tenant:string,grantId:string,principal:string,months:number)=>
    call<CreditPricePreview>(tenant,'/simulate',{
      grant_id:grantId,principal,term_months:months,
    }),
};
