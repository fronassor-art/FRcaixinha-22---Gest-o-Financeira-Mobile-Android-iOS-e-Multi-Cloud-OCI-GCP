/** M41450: explicit non-operational session contract. No network/storage/global auth integration. */
import {uuid} from './productTransactionalBoundaryV23';
const deny=():never=>{throw Error('Sessão preliminar indisponível. Nenhuma operação autorizada.');};
function exact(v:unknown,fields:string){if(!v||typeof v!=='object'||Array.isArray(v))return deny();const x=v as Record<string,unknown>,k=fields.split(' ');if(Object.keys(x).length!==k.length||k.some(y=>!Object.hasOwn(x,y)))return deny();return x;}
export type PreliminaryState='SELECT_OFFER'|'PAYMENT_PENDING'|'REAUTH_REQUIRED';
export type PreliminaryScope={user_id:string;tenant_id:string};
export function parsePreliminaryJourney(v:unknown,expected?:PreliminaryScope){
 const x=exact(v,'user_id tenant_id role state intent_id cents period ci_only operational_access');
 const user_id=uuid(x.user_id),tenant_id=uuid(x.tenant_id);
 if(x.role!=='TENANT_ADMIN'||x.ci_only!==true||x.operational_access!==false||(expected&&(user_id!==uuid(expected.user_id)||tenant_id!==uuid(expected.tenant_id))))deny();
 const state=x.state;
 if(state!=='SELECT_OFFER'&&state!=='PAYMENT_PENDING'&&state!=='REAUTH_REQUIRED')return deny();
 let intent_id:string|null=null,cents:number|null=null,period:'MONTHLY'|'ANNUAL'|null=null;
 if(state==='SELECT_OFFER'){if(x.intent_id!==null||x.cents!==null||x.period!==null)deny();}
 else{
  intent_id=uuid(x.intent_id);
  if(typeof x.cents!=='number'||!Number.isSafeInteger(x.cents)||x.cents<1||x.cents>100000000)return deny();
  cents=x.cents;
  if(x.period!=='MONTHLY'&&x.period!=='ANNUAL')return deny();
  period=x.period;
 }
 return Object.freeze({user_id,tenant_id,role:'TENANT_ADMIN' as const,state,intent_id,cents,period,ci_only:true as const,operational_access:false as const});
}
export type PreliminaryJourney=ReturnType<typeof parsePreliminaryJourney>;
const order:Record<PreliminaryState,number>={SELECT_OFFER:0,PAYMENT_PENDING:1,REAUTH_REQUIRED:2};
export function preliminaryContext(v:unknown,clock:()=>number=Date.now){
 const x=exact(v,'preliminary_token expires_at journey');
 if(typeof x.preliminary_token!=='string'||!/^frp_[A-Za-z0-9_-]{43}$/.test(x.preliminary_token)||typeof x.expires_at!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(x.expires_at))return deny();
 const until=Date.parse(x.expires_at),now=clock();
 if(!Number.isFinite(until)||!Number.isFinite(now)||until<=now||until-now>660000)deny();
 let token:string|null=x.preliminary_token,current=parsePreliminaryJourney(x.journey);
 function active(){if(!token||!Number.isFinite(clock())||clock()>=until){token=null;return deny();}return token;}
 return Object.freeze({
  initial:current,
  // This credential is scoped to preliminary routes, never authService.
  authorization(){return 'Bearer '+active();},
  update(raw:unknown){
   active();const next=parsePreliminaryJourney(raw,current);
   if(order[next.state]<order[current.state]||(current.intent_id!==null&&(next.intent_id!==current.intent_id||next.cents!==current.cents||next.period!==current.period))){token=null;return deny();}
   current=next;return current;
  },
  discard(){token=null;}
 });
}
