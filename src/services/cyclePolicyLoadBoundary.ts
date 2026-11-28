/** M37449: ONLY the policy endpoint's 404 denotes no active cycle.
 * Never hide unauthorized, incompatible-price or offline failures.
 */
import {FinancialApiHttpError,FinancialBackendUnavailableError,SessionBoundaryError} from './financialApiService';

export type CyclePolicyLoadOutcome={kind:'empty'|'blocked'|'unavailable';message:string};

export function classifyCyclePolicyLoadFailure(error:unknown):CyclePolicyLoadOutcome{
 if(error instanceof FinancialApiHttpError && error.status===404)
   return {
     kind:'empty',
     message:'Nenhum ciclo aberto nesta caixinha. Não existem cobranças do ciclo antigo. Para preparar um novo ciclo, confira a prévia abaixo; a abertura continua sujeita à autorização do servidor.'
   };
 if(error instanceof FinancialApiHttpError && error.status===409)
   return {
     kind:'blocked',
     message:'Política de ciclo incompatível com o mínimo contratual. É necessária revisão auditada antes de exibir cobranças.'
   };
 if(error instanceof SessionBoundaryError ||
    (error instanceof FinancialApiHttpError && [401,403].includes(error.status)))
   return {
     kind:'blocked',
     message:'Consulta não autorizada para esta sessão. Verifique o perfil e entre novamente.'
   };
 if(error instanceof FinancialBackendUnavailableError ||
    (error instanceof FinancialApiHttpError && error.status>=500))
   return {
     kind:'unavailable',
     message:'A política do ciclo não pôde ser consultada. Verifique a conexão com o FastAPI e tente Atualizar.'
   };
 return {
   kind:'unavailable',
   message:'Falha ao consultar a política do ciclo. Não foi possível comprovar o estado financeiro; tente novamente.'
 };
}
