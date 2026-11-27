/** M41460: CI-only response validation, no global auth or network executor. */
import {uuid} from './productTransactionalBoundaryV23';
import {parseDocument} from './onboardingReadbackV23';
const deny=():never=>{throw Error('Sessão ou licença indisponível. Nenhuma operação real autorizada.');};
function exact(v:unknown,fields:string){if(!v||typeof v!=='object'||Array.isArray(v))return deny();const x=v as Record<string,unknown>,k=fields.split(' ');if(Object.keys(x).length!==k.length||k.some(y=>!Object.hasOwn(x,y)))return deny();return x;}
export type AdminIdentity={user_id:string;tenant_id:string};
function scope(x:Record<string,unknown>,expected:AdminIdentity){
 const user_id=uuid(x.user_id),tenant_id=uuid(x.tenant_id);
 if(user_id!==uuid(expected.user_id)||tenant_id!==uuid(expected.tenant_id)||x.role!=='TENANT_ADMIN'||x.ci_only!==true||x.production_authorized!==false)deny();
 return {user_id,tenant_id,role:'TENANT_ADMIN' as const,ci_only:true as const,production_authorized:false as const};
}
export function parseAdminReauthentication(raw:unknown,expected:AdminIdentity,clock:()=>number=Date.now){
 const x=exact(raw,'session_token expires_at user_id tenant_id role ci_only production_authorized');
 const identity=scope(x,expected);
 if(typeof x.session_token!=='string'||!/^[A-Za-z0-9_-]{43}$/.test(x.session_token)||x.session_token.startsWith('frp_')||typeof x.expires_at!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(x.expires_at))return deny();
 const end=Date.parse(x.expires_at),now=clock();
 if(!Number.isFinite(end)||!Number.isFinite(now)||end<=now||end-now>960000)deny();
 let token:string|null=x.session_token;
 return Object.freeze({identity,authorization(){if(!token||!Number.isFinite(clock())||clock()>=end){token=null;return deny();}return 'Bearer '+token;},discard(){token=null;}});
}
export async function parseAdministratorReadiness(raw:unknown,expected:AdminIdentity,documentId:string){
 const x=exact(raw,'user_id tenant_id role state document acceptance_id ci_only production_authorized'),identity=scope(x,expected);
 const state=x.state;
 if(state!=='CONTRACT_B_REQUIRED'&&state!=='CYCLE_CONFIGURATION'&&state!=='CONTINUITY_ONLY')return deny();
 const acceptance_id=state==='CONTRACT_B_REQUIRED'?(x.acceptance_id===null?null:deny()):uuid(x.acceptance_id);
 const document=await parseDocument(x.document,'TENANT_MEMBERSHIP',documentId);
 return Object.freeze({...identity,state,document,acceptance_id});
}
