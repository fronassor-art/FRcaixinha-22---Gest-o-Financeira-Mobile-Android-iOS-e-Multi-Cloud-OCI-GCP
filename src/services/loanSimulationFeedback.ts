/** Tratamento de falhas Price: mensagens seguras sem liberar operações.
 * Falha na verificação de ciclo/política NUNCA autoriza fallback local.
 */
import {
  FinancialApiHttpError,FinancialBackendUnavailableError,SessionBoundaryError
} from './financialApiService';
import {ApiResponseIntegrityError} from './apiResponsePolicy';

const suffix=' Nenhuma operação financeira foi realizada.';
const cycleNotOpen='Não há ciclo aberto autorizado para simulação.';
const missingPolicy='A política financeira vigente não está configurada.';
const limit='Prazo excede o limite da política vigente da caixinha.';

export function loanSimulationFailureMessage(error:unknown):string{
  if(error instanceof SessionBoundaryError)
    return 'Sua sessão não está válida. Entre novamente para consultar o servidor.'+suffix;
  if(error instanceof FinancialBackendUnavailableError)
    return 'O FastAPI ou PostgreSQL não está disponível para esta consulta.'+suffix;
  if(error instanceof ApiResponseIntegrityError)
    return 'O servidor enviou uma resposta inválida; a simulação foi descartada.'+suffix;
  if(error instanceof FinancialApiHttpError){
    if(error.status===409){
      if(error.message===cycleNotOpen)
        return 'A caixinha ainda não possui um ciclo ABERTO para a simulação.'+suffix;
      if(error.message===missingPolicy)
        return 'O ciclo da caixinha não possui política financeira ACTIVE.'+suffix;
      return 'A simulação está bloqueada por uma condição contratual do ciclo.'+suffix;
    }
    if(error.status===422){
      if(error.message===limit)
        return 'O prazo escolhido excede o máximo permitido pela política vigente.'+suffix;
      return 'Valor, prazo ou calendário não atende à política vigente da caixinha.'+suffix;
    }
    if(error.status===403)
      return 'Este perfil não tem autorização para simular nesta caixinha.'+suffix;
    if(error.status===404)
      return 'A rota da simulação não foi encontrada no servidor.'+suffix;
  }
  return 'Não foi possível confirmar a simulação no FastAPI.'+suffix;
}
