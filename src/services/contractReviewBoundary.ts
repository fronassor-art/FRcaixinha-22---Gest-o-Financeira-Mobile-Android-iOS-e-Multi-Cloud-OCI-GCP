/** FR Finance M38014: transient UI contract-review context.
 * Never a consent, contract signature, session token or invitation grant.
 * Authorization remains exclusively in FastAPI and PostgreSQL RLS.
 */
import type {AuthenticatedUser} from './authService';
import type {InvitationPreparerRole} from './invitationContractReview';

const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ZERO='00000000-0000-0000-0000-000000000000';
const valid=(v:unknown):v is string=>
  typeof v==='string'&&UUID.test(v)&&v.toLowerCase()!==ZERO;

export function contractReviewScopeKey(
  role:InvitationPreparerRole,
  targetTenantId:string,
  user:AuthenticatedUser|null,
  generation:number
):string|null{
  if(!user||!valid(user.id)||!valid(targetTenantId)||
     !Number.isSafeInteger(generation)||generation<1)return null;
  if(role==='MASTER'){
    if(user.role!=='MASTER'||(user.tenantId??null)!==null)return null;
  }else if(role==='TENANT_ADMIN'){
    if(user.role!=='TENANT_ADMIN'||!valid(user.tenantId)||
       user.tenantId.toLowerCase()!==targetTenantId.toLowerCase())return null;
  }else return null;
  return [generation,user.id.toLowerCase(),role,targetTenantId.toLowerCase()].join(':');
}

/** A previous fetch completion must not update a new request or session. */
export function createContractReviewSequence(){
  let revision=0;
  return {
    next:()=>++revision,
    invalidate:()=>{revision+=1;},
    isCurrent:(ticket:number)=>Number.isSafeInteger(ticket)&&
      ticket>0&&ticket===revision,
  };
}
