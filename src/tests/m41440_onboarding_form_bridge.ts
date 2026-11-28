/** Only CI subprocess stdin/stdout, no network or logging of fixture credentials. */
import {readFileSync} from 'node:fs';
import {parseAdminReauthentication,parseAdministratorReadiness} from '../services/administratorReadinessV23';
import {preliminaryContext,parsePreliminaryJourney} from '../services/preliminaryJourneyV23';
import {webcrypto} from 'node:crypto';
import {masterInviteForm,adminBForm,memberInviteForm,invitationProofForm,registrationForm,checkoutForm} from '../services/onboardingFormsV23';
if(!globalThis.crypto)Object.defineProperty(globalThis,'crypto',{value:webcrypto});
try{
 if(process.env.GITHUB_ACTIONS!=='true'||process.env.FRCAIXINHA_CI_ISOLATED!=='1'||['PIX_REAL','PAGAMENTOS_REAIS','ATIVACAO_REAL'].some(k=>process.env[k]!=='OFF'))throw Error();
 const x=JSON.parse(readFileSync(0,'utf8'));
 let request:unknown;
 switch(x.op){
  case 'MASTER':request=await masterInviteForm(x.scope,x.raw,x.id,x.form);break;
  case 'B':request=await adminBForm(x.scope,x.raw,x.id,x.accepted);break;
  case 'MEMBER_INVITE':request=memberInviteForm(x.scope,x.cycle,x.form);break;
  case 'PROOFS':request={path:'/invitation-terms',body:invitationProofForm(x.proofs)};break;
  case 'REGISTER':request=(await registrationForm(x.raw,x.proofs)).prepare(x.form);break;
  case 'CHECKOUT':request=checkoutForm(x.scope,x.raw,x.id,x.period,x.accepted);break;
  case 'PRELIMINARY_LOGIN_VIEW':{const c=preliminaryContext(x.raw);request=c.initial;c.discard();break;}
  case 'PRELIMINARY_JOURNEY_VIEW':request=parsePreliminaryJourney(x.raw,x.scope);break;
  case 'ADMIN_REAUTH_VIEW':{const c=parseAdminReauthentication(x.raw,x.scope);request=c.identity;c.discard();break;}
  case 'ADMIN_READINESS_VIEW':request=await parseAdministratorReadiness(x.raw,x.scope,x.id);break;
  default:throw Error();
 }
 process.stdout.write(JSON.stringify(request));
}catch{process.exitCode=2;}
