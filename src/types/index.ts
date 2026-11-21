/**
 * FRcaixinha 2.2 - Tipos de Dados e Modelos Contratuais
 * Baseado no Contrato Técnico Mestre e Caderno Mestre (147 Cláusulas)
 */

export type UserRole = 'MASTER' | 'TENANT_ADMIN' | 'TENANT_MEMBER';

export type PartyType = 'PF' | 'PJ';

export type TenantStatus = 'RASCUNHO_INATIVO' | 'ATIVO' | 'SUSPENSO' | 'ENCERRADO';

export type LicenseStatus = 'RASCUNHO_INATIVO' | 'ATIVA' | 'SUSPENSA' | 'CANCELADA';

export type LicensePlanTier = 'ESSENCIAL' | 'INTERMEDIARIO' | 'AMPLIADO';

export type LicensePeriod = 'MENSAL' | 'ANUAL';

export type PaymentFinancialStatus = 'PENDENTE' | 'PARCIAL' | 'QUITADA' | 'REVERTIDA' | 'CANCELADA_JUSTIFICADA';

export type PaymentTemporalStatus = 'A_VENCER' | 'VENCIDA' | 'REGULARIZADA';

export type LoanStatus = 'SIMULADO' | 'SOLICITADO' | 'APROVADO' | 'REJEITADO' | 'RESERVADO' | 'DESEMBOLSADO' | 'QUITADO' | 'INADIMPLENTE';

export type PixStatus = 'SOLICITADO' | 'RESERVADO' | 'ENVIADO' | 'PENDENTE_CONCILIACAO' | 'CONFIRMADO' | 'FALHOU' | 'CANCELADO_COMPROVADO';

export type CycleClosingStatus = 'EM_APURACAO' | 'APROVADO_PARA_LIQUIDACAO' | 'PENDENTE_LIQUIDACAO' | 'FECHADO';

// 12.2 Entidades fundamentais
export interface UserIdentity {
  id: string;
  name: string;
  cpf: string;
  email: string;
  email_verified_at: string | null;
  phone: string;
  phone_verified_at?: string | null;
  profile_photo_ref?: string | null;
  auth_subject: string;
  status: 'ACTIVE' | 'SUSPENDED' | 'PENDING_VERIFICATION';
  created_at: string;
}

export interface ContractingParty {
  id: string;
  party_type: PartyType;
  legal_name: string;
  cpf_or_cnpj: string;
  billing_address?: string;
  representative_user_id?: string;
  fiscal_data?: Record<string, unknown>;
  status: 'ACTIVE' | 'PENDING';
  created_at: string;
}

export interface Tenant {
  id: string;
  admin_user_id: string;
  contracting_party_id: string;
  display_name: string;
  status: TenantStatus;
  is_owner_box?: boolean; // Identifica se é a Caixinha Inaugural do proprietário (Cláusula 4.2: 20% a.m., Price, max 6 parc., 85/15)
  created_at: string;
}

export interface RoleGrant {
  id: string;
  user_id: string;
  tenant_id?: string;
  role: UserRole;
  active_from: string;
  active_until?: string;
  revoked_at?: string | null;
}

export interface Cycle {
  id: string;
  tenant_id: string;
  year: number;
  start_date: string; // '01/01/2027' - Central fixo
  end_date: string;   // '31/12/2027' - Central fixo
  settlement_date: string; // '10/01/2028' - Central fixo
  status: 'ABERTO' | 'CONGELADO' | 'EM_APURACAO' | 'LIQUIDADO';
}

export interface TenantPolicyVersion {
  id: string;
  tenant_id: string;
  cycle_id: string;
  version: number;
  monthly_interest_rate: number; // Ex: 0.20 para 20% a.m.
  max_installments: number; // Ex: 6 (inaugural) ou até 12
  contribution_per_quota: number; // valor escolhido por ciclo: mínimo R$ 150,00
  flat_fine_amount: number; // Ex: 10.00
  daily_mora_rate: number; // Ex: monthly_interest_rate / 30
  admin_pct: number; // Ex: 15 para 15%
  member_pct: number; // Ex: 85 para 85% (admin_pct + member_pct = 100)
  effective_at: string;
  author_id: string;
  status: 'ACTIVE' | 'SUPERSEDED' | 'NEXT_CYCLE_PENDING';
}

export interface TermAcceptance {
  id: string;
  user_id: string;
  tenant_id?: string;
  cycle_id?: string;
  document_version: string;
  document_hash: string;
  accepted_at: string;
  evidence_ref: string;
  scope: 'PLATFORM_LICENSE' | 'TENANT_MEMBERSHIP' | 'LOAN_CONTRACT' | 'SELF_LOAN_CONSENT' | 'LOTTERY_MANDATE';
}

export interface Membership {
  id: string;
  tenant_id: string;
  cycle_id: string;
  user_id: string;
  user_name: string;
  user_cpf: string;
  user_email: string;
  user_phone: string;
  user_photo?: string;
  joined_at: string;
  left_at?: string | null;
  status: 'ATIVA' | 'CONVIDADO_PENDENTE' | 'SAIDA_REGULAR' | 'BLOQUEADO';
  consecutive_unpaid_count: number; // Cláusula 6.5: 3 consecutivas = perda de elegibilidade para lucro
  is_profit_eligible: boolean;
}

export interface Quota {
  id: string;
  tenant_id: string;
  cycle_id: string;
  membership_id: string;
  quota_number: number;
  status: 'ATIVA' | 'CANCELADA';
  effective_from: string;
  effective_to?: string;
}

export interface Contribution {
  id: string;
  tenant_id: string;
  cycle_id: string;
  membership_id: string;
  competence: string; // Ex: '2027-01'
  due_date: string; // '10' de cada mês
  amount_due: number; // Em R$
  amount_paid: number;
  payment_status: PaymentFinancialStatus;
  due_status: PaymentTemporalStatus;
  paid_at?: string | null;
  pix_code?: string;
}

export interface LoanInstallment {
  id: string;
  loan_id: string;
  sequence: number; // 1, 2, ..., n
  due_date: string; // '2027-03-10'
  principal_due: number;
  interest_due: number;
  penalties_due: number; // Multa + Mora
  fine_amount: number;   // Multa única de R$ 10,00
  mora_amount: number;   // Mora diária simples (taxa/30 * principal vencido)
  days_overdue: number;
  paid_amount: number;
  paid_interest: number;
  paid_mora: number;
  paid_fine: number;
  paid_principal: number;
  status: PaymentFinancialStatus;
  due_status: PaymentTemporalStatus;
}

export interface Loan {
  id: string;
  tenant_id: string;
  cycle_id: string;
  borrower_membership_id: string;
  borrower_name: string;
  is_admin_loan: boolean;
  policy_version_id: string;
  principal: number;
  monthly_rate: number;
  term_months: number;
  schedule_type: 'PRICE';
  decision_by?: string;
  status: LoanStatus;
  requested_at: string;
  approved_at?: string;
  disbursed_at?: string;
  pix_transfer_id?: string;
  first_period_days: number;
  first_period_rate: number;
  monthly_payment: number;
  total_interest: number;
  installments: LoanInstallment[];
}

export interface AnnualSelfLoanConsent {
  id: string;
  tenant_id: string;
  cycle_id: string;
  beneficiary_admin_id: string;
  beneficiary_admin_name: string;
  document_version: string;
  status: 'ATIVO' | 'SUSPENSO_REVOGADO' | 'PENDENTE_ASSINATURAS';
  valid_from: string;
  valid_to: string;
  signatures: ConsentSignature[];
}

export interface ConsentSignature {
  id: string;
  consent_id: string;
  signer_membership_id: string;
  signer_name: string;
  signed_at: string;
  evidence_ref: string;
  revoked_at?: string | null;
  revocation_reason?: string | null;
}

export interface LedgerAccount {
  id: string;
  tenant_id: string;
  cycle_id: string;
  account_code: string; // Ex: '1.1.1 Caixa', '2.1.1 Capital', '4.1.1 Juros'
  account_name: string;
  kind: 'ATIVO' | 'PASSIVO' | 'RECEITA' | 'DESPESA' | 'PATRIMONIO_LIQUIDO';
  balance_cents: number; // Exato em centavos
  status: 'ACTIVE' | 'ARCHIVED';
}

export interface LedgerTransaction {
  id: string;
  tenant_id: string;
  cycle_id: string;
  business_type: 'CONTRIBUTION_PAYMENT' | 'LOAN_DISBURSEMENT' | 'LOAN_INSTALLMENT_PAYMENT' | 'LOAN_EARLY_SETTLEMENT' | 'YEAR_END_DISTRIBUTION' | 'EXPENSE' | 'ADJUSTMENT';
  business_id: string;
  posted_at: string;
  reversal_of_id?: string;
  status: 'POSTED' | 'REVERSED';
  description: string;
  entries: LedgerEntry[];
}

export interface LedgerEntry {
  id: string;
  transaction_id: string;
  account_id: string;
  account_name: string;
  direction: 'DEBIT' | 'CREDIT';
  amount_cents: number;
  currency: 'BRL';
}

export interface PixTransfer {
  id: string;
  tenant_id?: string;
  purpose: 'PLATFORM_LICENSE' | 'CONTRIBUTION' | 'LOAN_DISBURSEMENT' | 'LOAN_PAYMENT' | 'YEAR_END_DISTRIBUTION';
  beneficiary_id: string;
  beneficiary_name: string;
  amount: number;
  idempotency_key: string;
  provider_external_id?: string;
  status: PixStatus;
  copia_e_cola: string;
  qr_code_url: string;
  created_at: string;
  confirmed_at?: string | null;
}

export interface CycleClosing {
  id: string;
  tenant_id: string;
  cycle_id: string;
  year: number;
  snapshot_at: string;
  policy_version_id: string;
  total_principal_refundable: number;
  total_net_profit_realized: number;
  admin_pct: number;
  member_pct: number;
  admin_pool: number;
  member_pool: number;
  technical_wallet_residual: number; // Carteira Administrativa Técnica
  largest_remainder_allocated: number;
  status: CycleClosingStatus;
  approved_by: string;
  distributions: Distribution[];
}

export interface Distribution {
  id: string;
  closing_id: string;
  beneficiary_type: 'MEMBER_PRINCIPAL' | 'MEMBER_PROFIT' | 'ADMIN_FEE';
  beneficiary_id: string;
  beneficiary_name: string;
  membership_id?: string;
  capital_dias_weight?: number;
  exact_quota_amount?: number;
  truncated_amount?: number;
  remainder_centavos?: number;
  amount_due: number;
  amount_paid: number;
  pix_transfer_id?: string;
  status: 'PENDENTE' | 'PAGO' | 'CONCILIADO';
}

export interface LicensePlan {
  id: string;
  tier: LicensePlanTier;
  name: string;
  member_limit: number;
  quota_limit: number;
  status: 'ACTIVE' | 'PENDING_CAP_BLOCKED'; // Ampliado é bloqueado até definição de teto
}

export interface LicensePriceVersion {
  id: string;
  plan_tier: LicensePlanTier;
  monthly_price: number;
  annual_price_computed: number; // Formula contratual: monthly_price * 10
  effective_from: string;
  effective_to?: string;
  changed_by: string;
  reason: string;
  created_at: string;
}

export interface LicenseSubscription {
  id: string;
  tenant_id: string;
  contracting_party_id: string;
  plan_tier: LicensePlanTier;
  period: LicensePeriod;
  price_paid: number;
  price_version_id: string;
  anchor_day: number;
  starts_at: string;
  ends_at: string;
  status: LicenseStatus;
  paid_payment_id: string;
}

export interface SupportAccessGrant {
  id: string;
  tenant_id: string;
  granted_by: string;
  granted_to: string;
  type: 'CONSENTED_NORMAL' | 'BREAK_GLASS_EMERGENCY';
  max_minutes: number; // 60 min normal, 30 min emergencial
  scope: string;
  reason: string;
  issued_at: string;
  expires_at: string;
  revoked_at?: string | null;
  status: 'ACTIVE' | 'EXPIRED' | 'REVOKED';
}

export interface AuditEvent {
  id: string;
  actor_id: string;
  actor_role: string;
  tenant_id?: string;
  object_type: string;
  object_id: string;
  action: string;
  timestamp: string;
  reason: string;
  evidence_ref: string;
}

// Bolão Oficial - Demonstrador Regulatório (Seção 14)
export interface LotteryCampaignDemo {
  id: string;
  tenant_id: string;
  cycle_id: string;
  title: string;
  modality: 'MEGA_SENA' | 'LOTOFACIL' | 'QUINA';
  contest_number: number;
  official_cost: number; // R$ 150,00
  quotas_count: number;  // 20
  official_cost_per_quota: number; // R$ 7,50
  final_price_per_quota: number;   // R$ 25,00
  total_revenue_expected: number;  // R$ 500,00
  gross_margin: number;            // R$ 350,00
  status: 'DEMO_PLANEJADA' | 'DEMO_COTAS_RESERVADAS' | 'DEMO_BILHETE_SIMULADO' | 'DEMO_ENCERRADO';
  disclaimer: string;
}

// Módulo de Rifas Consolidado - FRcaixinha 2.2
export type RaffleTicketStatus = 'GERADO' | 'NAO_VENDIDO' | 'PAGAMENTO_PENDENTE' | 'PAGO' | 'CANCELADO';

export interface RaffleCampaign {
  id: string;
  tenant_id: string;
  cycle_id: string;
  campaign_number: 1 | 2 | 3;
  title: string;
  month_name: 'Março' | 'Junho' | 'Setembro';
  due_date: string; // '2027-03-20', '2027-06-20', '2027-09-20'
  draw_date: string; // Data do sorteio (distinta do vencimento)
  value_per_quota: number; // R$ 50,00 fixo
  tickets_per_quota: number; // 10 bilhetes por cota
  ticket_unit_price: number; // R$ 5,00 por bilhete
  prize_amount: number; // Configurável manualmente (ex: R$ 200,00)
  prize_description: string;
  status: 'PLANEJADA' | 'ATIVA' | 'ENCERRADA_SORTEADA' | 'CONCLUIDA';
  winning_number?: number | null;
  winning_member_id?: string | null;
  winning_member_name?: string | null;
  draw_source?: string;
  draw_published_at?: string | null;
  created_at: string;
}

export interface RafflePrizeHistory {
  id: string;
  campaign_id: string;
  admin_id: string;
  admin_name: string;
  previous_amount: number;
  new_amount: number;
  changed_at: string;
  reason: string;
}

export interface RaffleCard {
  id: string;
  campaign_id: string;
  tenant_id: string;
  quota_id: string;
  quota_number: number;
  membership_id: string;
  member_name: string;
  member_cpf: string;
  start_number: number;
  end_number: number;
  total_tickets: number; // 10
  ticket_unit_price: number; // R$ 5,00
  total_card_value: number; // R$ 50,00
  amount_paid: number;
  amount_pending: number;
  paid_tickets: number;
  sold_tickets: number;
  paid_at?: string | null;
  status: 'PENDENTE' | 'PARCIAL' | 'QUITADA' | 'VENCIDA' | 'PAGA';
  authenticity_code: string;
  tickets: RaffleTicket[];
}

export interface RaffleTicket {
  id: string;
  campaign_id: string;
  card_id: string;
  number: number;
  quota_id: string;
  membership_id: string;
  status: RaffleTicketStatus;
  buyer_name?: string;
  buyer_phone?: string;
  buyer_pix_key?: string;
  price: number; // R$ 5,00
  paid_at?: string | null;
}

export interface RafflePayment {
  id: string;
  campaign_id: string;
  membership_id: string;
  card_id?: string;
  amount: number;
  paid_at: string;
  pix_transaction_id: string;
  status: 'CONFIRMADO';
}

// ==========================================
// Módulo de Bolões Oficiais (Versão de Revisão 1.1 - 30/10/2026)
// ==========================================

export type BolaoModality = 'QUINA' | 'LOTOFACIL' | 'MEGA_SENA';

export type BolaoInternalStatus =
  | 'RASCUNHO'
  | 'PRONTO_PARA_IMPRESSAO'
  | 'LEVADO_A_LOTERICA'
  | 'PENDENTE_CONFERENCIA'
  | 'REGISTRADO_CONFERIDO'
  | 'NAO_REGISTRADO';

export type BolaoPaymentStatus =
  | 'NAO_PAGO'
  | 'COBRANCA_GERADA'
  | 'CONFIRMACAO'
  | 'BAIXADO'
  | 'PARCIAL'
  | 'VENCIDO'
  | 'ESTORNADO';

export type BolaoDrawStatus =
  | 'AGUARDANDO_RESULTADO'
  | 'RESULTADO_CONFERIDO'
  | 'PREMIO_PENDENTE'
  | 'RECEBIDO'
  | 'DISTRIBUIDO';

export interface BolaoGame {
  id: string;
  game_number: number; // Aposta 01, Aposta 02...
  numbers: number[]; // Dezenas ordenadas em ordem crescente
  numbers_count: number; // 6 a 20 (Mega), 15 a 20 (Lotofácil), 5 a 15 (Quina)
  unit_cost: number; // Custo oficial pela tabela CAIXA
  created_at: string;
}

export interface BolaoCampaign {
  id: string;
  tenant_id: string;
  cycle_id: string;
  campaign_name: string; // "Quina de São João", "Lotofácil da Independência", "Mega da Virada"
  modality: BolaoModality;
  special_edition: string; // "Edição Especial 2027"
  contest_number: number | null; // Número oficial confirmado
  contest_date: string; // Data do concurso (ex: 2027-06-24, 2027-09-10, 2027-12-31)
  internal_deadline: string; // Data limite interna para arrecadação
  estimated_prize: number; // Prêmio estimado (ex: R$ 220.000.000,00)
  total_valid_quotas: number; // Cotas válidas apuradas (ex: 25 cotas)
  numbers_per_game: number; // Ex: 6 (Quina), 16 (Lotofácil), 7 (Mega)
  max_games_per_receipt: number; // Limite oficial de até 10 jogos por recibo
  games: BolaoGame[];
  cost_official_bets: number; // Componente A: custo efetivo das apostas oficiais
  external_fee: number; // Componente B: tarifa externa comprovada (R$ 0,00 no bolão presencial próprio)
  box_additional_fee: number; // Componente C: adicional de 20% proposto à caixinha
  total_budget: number; // A + B + C
  price_per_quota_base: number; // Média por cota
  internal_status: BolaoInternalStatus;
  draw_status: BolaoDrawStatus;
  drawn_numbers?: number[];
  official_receipt_code?: string;
  official_registered_at?: string | null;
  official_receipt_file_hash?: string;
  prize_gross_amount?: number; // Prêmio líquido total apurado
  prize_member_share_pct: number; // 96% - Exclusivo do bolão (Seção 12)
  prize_admin_fee_pct: number; // 4% - Taxa de administração exclusiva do bolão (Seção 12)
  prize_member_total_amount?: number; // 96%
  prize_admin_fee_amount?: number; // 4%
  version: number;
  created_at: string;
  updated_at: string;
}

export interface BolaoMemberParticipation {
  id: string;
  campaign_id: string;
  membership_id: string;
  member_name: string;
  quotas_count: number; // 1 ou 2 cotas
  assigned_quota_numbers: number[]; // Ex: [1] ou [2, 3]
  amount_official_share: number; // Parcela de A
  amount_fee_share: number; // Parcela de B
  amount_box_share: number; // Parcela de C (20%)
  total_due: number; // Total individual atribuído com ajuste determinístico de centavos
  amount_paid: number;
  amount_pending: number;
  days_overdue: number;
  mora_interest: number; // Mora simples 20%/mês pró-rata dia
  payment_status: BolaoPaymentStatus;
  prize_share_received?: number; // Rateio dos 96%
  paid_at?: string | null;
  pix_reference_id?: string;
}

// ==========================================
// ARQUITETURA MULTI-CLOUD (OCI + GCP) E MOBILE
// ==========================================

export type CloudProvider = 'GCP' | 'OCI';

export type CloudServiceHealth = 'HEALTHY' | 'SYNCED' | 'STANDBY' | 'DEGRADED' | 'ACTIVE_FAILOVER' | 'VERIFIED_LOCKED';

export interface CloudServiceNode {
  id: string;
  provider: CloudProvider;
  name: string;
  roleDescription: string;
  region: string;
  regionCode: string;
  status: CloudServiceHealth;
  latencyMs: number;
  uptimePct: number;
  lastChecked: string;
  details: string;
}

export interface MultiCloudTopology {
  activePrimary: CloudProvider;
  failoverEngaged: boolean;
  failoverTimestamp?: string | null;
  interCloudTunnel: {
    name: string;
    type: string; // "OCI FastConnect <-> GCP Cloud Interconnect"
    bandwidthGbps: number;
    latencyMs: number;
    encryption: string; // "MACsec AES-256 + IPsec IKEv2"
    status: 'ONLINE' | 'DEGRADED';
  };
  metrics: {
    rpoSeconds: number; // 0.0 (Zero data loss)
    rtoSeconds: number; // Sub-15s (8.4s)
    totalTransactionsSynced: number;
    wormAuditEntriesCount: number;
    lastWormHash: string;
    lastReplicationTimestamp: string;
  };
  nodes: CloudServiceNode[];
}

export type MobileDeviceType = 'ANDROID' | 'IOS' | 'DESKTOP';
export type MobilePreviewDevice = 'IPHONE_16' | 'GALAXY_S24' | 'RESPONSIVE';

