/**
 * FR Finance M39900 — exclusive cashbox evidence layout, no account postings.
 * Intent counts and collective-ledger counts are never money amounts.
 * Missing expense/statement/reconciliation evidence stays unavailable.
 */
import type {
  MasterExclusiveCashbox, TenantAdminExclusiveCashbox,
} from './exclusiveCashboxBoundary';

export type CashboxEvidenceItem = Readonly<{
  id: string;
  label: string;
  detail: string;
  kind: 'COUNT_ONLY' | 'NOT_ATTESTED';
  count?: number;
}>;

const pending = (id:string,label:string,detail:string):CashboxEvidenceItem => ({
  id,label,detail,kind:'NOT_ATTESTED',
});
const countOnly = (id:string,label:string,count:number,detail:string):CashboxEvidenceItem => ({
  id,label,count,detail,kind:'COUNT_ONLY',
});

/** Only validated, server-provided metadata is eligible for these panels. */
export function masterCashboxEvidence(
  value:MasterExclusiveCashbox,
):readonly CashboxEvidenceItem[] {
  return [
    countOnly('saas-intents','Cobranças SaaS — intenções registradas',
      value.payment_intents_count,
      'Quantidade de intenções. Não é cobrança liquidada, receita reconhecida ou saldo.'),
    countOnly('saas-preparations','Assinaturas — preparações registradas',
      value.subscription_preparations_count,
      'Quantidade de preparações. Não comprova pagamento, vigência ou recebimento.'),
    pending('platform-expenses','Despesas próprias da plataforma',
      'Não há extrato de despesas da plataforma comprovado por esta API.'),
    pending('platform-history','Histórico de entradas e saídas',
      'Depende de lançamentos auditáveis, documentação e conciliação do caixa da plataforma.'),
    pending('platform-reconciliation','Conciliação e saldo disponível',
      'Aguardando prova do provedor e Livro-Razão da plataforma; nenhuma transferência habilitada.'),
  ];
}

/** Tenant ledger activity belongs to the collective box, not to administrator pay. */
export function adminCashboxEvidence(
  value:TenantAdminExclusiveCashbox,
):readonly CashboxEvidenceItem[] {
  return [
    countOnly('collective-ledger','Livro-Razão coletivo — registros da caixinha',
      value.ledger_transactions_count,
      'Atividade da caixinha, não remuneração pessoal do administrador.'),
    pending('administrator-remuneration','Remuneração própria do administrador',
      'Nenhum valor exigível ou disponível sem percentual contratual validado, fechamento e apuração.'),
    pending('administrator-expenses','Despesas do caixa exclusivo',
      'Nenhuma despesa particular é presumida a partir de lançamentos dos membros.'),
    pending('administrator-history','Histórico da remuneração',
      'Aguardando extrato de remuneração segregado e documentado.'),
    pending('administrator-reconciliation','Conciliação e saque',
      'Sem autorização de fechamento, saldo bancário confirmado ou saque habilitado.'),
  ];
}
