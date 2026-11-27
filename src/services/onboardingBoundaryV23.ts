/** M41420. Public capability only. No token, PII, mutation or demo fallback. */
import {classifyApiOrigin} from './apiOriginPolicy';
const keys=['available','invites_enabled','registration_enabled','checkout_enabled','contract_acceptance_enabled','real_payments_enabled','production_authorized'] as const;
export function parseOnboardingGate(value:unknown):'BLOCKED'{
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Contrato de contratação indisponível.');
 const obj=value as Record<string,unknown>;
 if(Object.keys(obj).length!==keys.length+1||obj.contract!=='FR_FINANCE_V23_ONBOARDING_V1'||keys.some(k=>obj[k]!==false))
   throw Error('Contrato de contratação incompatível. Nenhuma operação autorizada.');
 return 'BLOCKED';
}
export async function readOnboardingGate(originValue:string,send:(url:string,options:RequestInit)=>Promise<Response>){
 const origin=classifyApiOrigin(originValue);
 if(origin.kind==='BLOCKED')throw Error('Servidor FR Finance não configurado.');
 const response=await send(origin.origin+'/api/v1/v23/onboarding/capabilities',{method:'GET',headers:{Accept:'application/json'},cache:'no-store',credentials:'omit',redirect:'error'});
 if(!response.ok)throw Error('Contratação indisponível no servidor.');
 return parseOnboardingGate(await response.json());
}
export type OnboardingAudience='MASTER'|'INVITED'|'TENANT_ADMIN'|'TENANT_MEMBER';
export const onboardingSteps:Record<OnboardingAudience,readonly string[]>={
 MASTER:['Convite nominal do administrador','Revisão independente e confirmação de entrega'],
 INVITED:['Confirmação de titularidade','Cadastro individual e aceite do documento aplicável','Entrar novamente após validação'],
 TENANT_ADMIN:['Contrato A e oferta mensal ou anual','Pagamento SaaS conciliado','Contrato B e política do ciclo','Convites nominais e adesões dos membros'],
 TENANT_MEMBER:['Convite nominal e verificação de identidade','Contrato B e política do ciclo','Adesão confirmada pelo administrador'],
};
