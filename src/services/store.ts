/**
 * FRcaixinha 2.2 - Estado Central e Regras de Negócio
 * Implementa persistência local, troca de papéis/tenants e validações do Contrato Mestre.
 */

import {
  UserIdentity,
  Tenant,
  RoleGrant,
  Cycle,
  TenantPolicyVersion,
  Membership,
  Quota,
  Contribution,
  Loan,
  AnnualSelfLoanConsent,
  LedgerAccount,
  LedgerTransaction,
  LedgerEntry,
  PixTransfer,
  LicensePlan,
  LicensePriceVersion,
  LicenseSubscription,
  SupportAccessGrant,
  AuditEvent,
  LotteryCampaignDemo,
  UserRole,
  RaffleCampaign,
  RaffleCard,
  RaffleTicket,
  RafflePrizeHistory,
  RafflePayment,
  RaffleTicketStatus,
  BolaoCampaign,
  BolaoMemberParticipation,
  BolaoGame,
  BolaoInternalStatus,
  BolaoPaymentStatus
} from '../types';
import {
  calculatePriceSimulation,
  calculateImputationHierarchy,
  calculateEarlySettlement,
  calculateLoanOverdueCharges,
  roundCents,
  calculateRaffleMoraInterest,
  calculateBolaoPricing,
  allocateBolaoCentsDeterministically,
  calculateBolaoPrizeSplit
} from './financialEngine';
import {
  SEED_RAFFLE_CAMPAIGNS,
  SEED_RAFFLE_CARDS,
  SEED_RAFFLE_PRIZE_HISTORIES,
  SEED_RAFFLE_PAYMENTS
} from './raffleData';
import {
  SEED_BOLAO_CAMPAIGNS,
  SEED_BOLAO_PARTICIPATIONS
} from './bolaoData';
import { financialApi, FinancialBackendUnavailableError } from './financialApiService';

// Chave para persistência local
const STORAGE_KEY = 'frcaixinha_2_2_app_state_v1';

// Dados iniciais (Seed)
const SEED_USERS: UserIdentity[] = [
  {
    id: 'usr-master',
    name: 'Carlos Master (Plataforma)',
    cpf: '000.111.222-33',
    email: 'master@frcaixinha.com.br',
    email_verified_at: '2026-01-01T10:00:00Z',
    phone: '(91) 98111-0001',
    auth_subject: 'auth|master',
    status: 'ACTIVE',
    created_at: '2026-01-01T10:00:00Z',
  },
  {
    id: 'usr-admin-joao',
    name: 'João Silva (Admin & Membro)',
    cpf: '111.222.333-44',
    email: 'joao.silva@exemplo.com.br',
    email_verified_at: '2026-10-16T12:00:00Z',
    phone: '(91) 98222-1111',
    profile_photo_ref: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80',
    auth_subject: 'auth|joao',
    status: 'ACTIVE',
    created_at: '2026-10-16T12:00:00Z',
  },
  {
    id: 'usr-maria',
    name: 'Maria Oliveira (Membro 2 Cotas)',
    cpf: '222.333.444-55',
    email: 'maria.oliveira@exemplo.com.br',
    email_verified_at: '2026-11-01T14:30:00Z',
    phone: '(91) 98333-2222',
    profile_photo_ref: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=120&auto=format&fit=crop&q=80',
    auth_subject: 'auth|maria',
    status: 'ACTIVE',
    created_at: '2026-11-01T14:30:00Z',
  },
  {
    id: 'usr-pedro',
    name: 'Pedro Santos (Membro 1 Cota)',
    cpf: '333.444.555-66',
    email: 'pedro.santos@exemplo.com.br',
    email_verified_at: '2026-11-05T09:15:00Z',
    phone: '(91) 98444-3333',
    auth_subject: 'auth|pedro',
    status: 'ACTIVE',
    created_at: '2026-11-05T09:15:00Z',
  },
  {
    id: 'usr-ana',
    name: 'Ana Costa (Membro Teste Inadimplência)',
    cpf: '444.555.666-77',
    email: 'ana.costa@exemplo.com.br',
    email_verified_at: '2026-11-10T16:00:00Z',
    phone: '(91) 98555-4444',
    auth_subject: 'auth|ana',
    status: 'ACTIVE',
    created_at: '2026-11-10T16:00:00Z',
  },
  {
    id: 'usr-admin-renata',
    name: 'Renata Martins (Admin Caixinha Tech)',
    cpf: '555.666.777-88',
    email: 'renata.martins@techsolucoes.com.br',
    email_verified_at: '2026-12-01T10:00:00Z',
    phone: '(11) 99777-5555',
    auth_subject: 'auth|renata',
    status: 'ACTIVE',
    created_at: '2026-12-01T10:00:00Z',
  },
];

const SEED_TENANTS: Tenant[] = [
  {
    id: 'tenant-inaugural',
    admin_user_id: 'usr-admin-joao',
    contracting_party_id: 'cp-joao',
    display_name: 'Caixinha Modelo Inaugural (Família & Negócios)',
    status: 'ATIVO',
    is_owner_box: true,
    created_at: '2026-10-16T15:00:00Z',
  },
  {
    id: 'tenant-tech',
    admin_user_id: 'usr-admin-renata',
    contracting_party_id: 'cp-renata',
    display_name: 'Caixinha dos Colegas de TI',
    status: 'ATIVO',
    is_owner_box: false,
    created_at: '2026-12-05T11:00:00Z',
  },
];

const SEED_ROLE_GRANTS: RoleGrant[] = [
  { id: 'rg-1', user_id: 'usr-master', role: 'MASTER', active_from: '2026-01-01' },
  { id: 'rg-2', user_id: 'usr-admin-joao', tenant_id: 'tenant-inaugural', role: 'TENANT_ADMIN', active_from: '2026-10-16' },
  { id: 'rg-3', user_id: 'usr-admin-joao', tenant_id: 'tenant-inaugural', role: 'TENANT_MEMBER', active_from: '2026-10-16' },
  { id: 'rg-4', user_id: 'usr-maria', tenant_id: 'tenant-inaugural', role: 'TENANT_MEMBER', active_from: '2026-11-01' },
  { id: 'rg-5', user_id: 'usr-pedro', tenant_id: 'tenant-inaugural', role: 'TENANT_MEMBER', active_from: '2026-11-05' },
  { id: 'rg-6', user_id: 'usr-ana', tenant_id: 'tenant-inaugural', role: 'TENANT_MEMBER', active_from: '2026-11-10' },
  { id: 'rg-7', user_id: 'usr-admin-renata', tenant_id: 'tenant-tech', role: 'TENANT_ADMIN', active_from: '2026-12-05' },
];

const SEED_CYCLES: Cycle[] = [
  {
    id: 'cycle-2027-inaugural',
    tenant_id: 'tenant-inaugural',
    year: 2027,
    start_date: '2027-01-01',
    end_date: '2027-12-31',
    settlement_date: '2028-01-10',
    status: 'ABERTO',
  },
  {
    id: 'cycle-2027-tech',
    tenant_id: 'tenant-tech',
    year: 2027,
    start_date: '2027-01-01',
    end_date: '2027-12-31',
    settlement_date: '2028-01-10',
    status: 'ABERTO',
  },
];

const SEED_POLICIES: TenantPolicyVersion[] = [
  {
    id: 'pol-inaugural-v1',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    version: 1,
    monthly_interest_rate: 0.20, // 20% a.m. (Cláusula 4.2)
    max_installments: 6,         // Máximo de 6 parcelas
    contribution_per_quota: 150.00, // apenas exemplo de teste; preço real definido pelo administrador
    flat_fine_amount: 10.00,     // Multa única R$ 10,00
    daily_mora_rate: 0.20 / 30,  // 20%/30 ao dia sobre principal vencido
    admin_pct: 15,               // 15% administrador
    member_pct: 85,              // 85% membros
    effective_at: '2026-10-16T00:00:00Z',
    author_id: 'usr-admin-joao',
    status: 'ACTIVE',
  },
  {
    id: 'pol-tech-v1',
    tenant_id: 'tenant-tech',
    cycle_id: 'cycle-2027-tech',
    version: 1,
    monthly_interest_rate: 0.10, // 10% a.m.
    max_installments: 10,
    contribution_per_quota: 150.00,
    flat_fine_amount: 10.00,
    daily_mora_rate: 0.10 / 30,
    admin_pct: 20,               // 20% administrador
    member_pct: 80,              // 80% membros
    effective_at: '2026-12-05T00:00:00Z',
    author_id: 'usr-admin-renata',
    status: 'ACTIVE',
  },
];

const SEED_MEMBERSHIPS: Membership[] = [
  {
    id: 'mem-joao',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    user_id: 'usr-admin-joao',
    user_name: 'João Silva',
    user_cpf: '111.222.333-44',
    user_email: 'joao.silva@exemplo.com.br',
    user_phone: '(91) 98222-1111',
    joined_at: '2027-01-01',
    status: 'ATIVA',
    consecutive_unpaid_count: 0,
    is_profit_eligible: true,
  },
  {
    id: 'mem-maria',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    user_id: 'usr-maria',
    user_name: 'Maria Oliveira',
    user_cpf: '222.333.444-55',
    user_email: 'maria.oliveira@exemplo.com.br',
    user_phone: '(91) 98333-2222',
    joined_at: '2027-01-01',
    status: 'ATIVA',
    consecutive_unpaid_count: 0,
    is_profit_eligible: true,
  },
  {
    id: 'mem-pedro',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    user_id: 'usr-pedro',
    user_name: 'Pedro Santos',
    user_cpf: '333.444.555-66',
    user_email: 'pedro.santos@exemplo.com.br',
    user_phone: '(91) 98444-3333',
    joined_at: '2027-01-01',
    status: 'ATIVA',
    consecutive_unpaid_count: 0,
    is_profit_eligible: true,
  },
  {
    id: 'mem-ana',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    user_id: 'usr-ana',
    user_name: 'Ana Costa',
    user_cpf: '444.555.666-77',
    user_email: 'ana.costa@exemplo.com.br',
    user_phone: '(91) 98555-4444',
    joined_at: '2027-01-01',
    status: 'ATIVA',
    consecutive_unpaid_count: 3, // 3 consecutivas vencidas (Cláusula 6.5)
    is_profit_eligible: false,   // Bloqueada para lucro, principal preservado!
  },
];

const SEED_QUOTAS: Quota[] = [
  { id: 'q-joao-1', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-joao', quota_number: 1, status: 'ATIVA', effective_from: '2027-01-01' },
  { id: 'q-maria-1', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-maria', quota_number: 2, status: 'ATIVA', effective_from: '2027-01-01' },
  { id: 'q-maria-2', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-maria', quota_number: 3, status: 'ATIVA', effective_from: '2027-01-01' },
  { id: 'q-pedro-1', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-pedro', quota_number: 4, status: 'ATIVA', effective_from: '2027-01-01' },
  { id: 'q-ana-1', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-ana', quota_number: 5, status: 'ATIVA', effective_from: '2027-01-01' },
];

const SEED_PLANS: LicensePlan[] = [
  { id: 'plan-essencial', tier: 'ESSENCIAL', name: 'Plano Essencial', member_limit: 20, quota_limit: 40, status: 'ACTIVE' },
  { id: 'plan-intermediario', tier: 'INTERMEDIARIO', name: 'Plano Intermediário', member_limit: 50, quota_limit: 50, status: 'ACTIVE' },
  { id: 'plan-ampliado', tier: 'AMPLIADO', name: 'Plano Ampliado (Teto Pendente)', member_limit: 9999, quota_limit: 9999, status: 'PENDING_CAP_BLOCKED' },
];

const SEED_PRICE_VERSIONS: LicensePriceVersion[] = [
  {
    id: 'lpv-essencial-v1',
    plan_tier: 'ESSENCIAL',
    monthly_price: 89.90,
    annual_price_computed: 899.00, // 10 x mensal
    effective_from: '2026-10-16',
    changed_by: 'usr-master',
    reason: 'Tabela inaugural aprovada no Contrato Técnico Mestre (Cláusula 3.2)',
    created_at: '2026-10-16T10:00:00Z',
  },
  {
    id: 'lpv-intermediario-v1',
    plan_tier: 'INTERMEDIARIO',
    monthly_price: 109.90,
    annual_price_computed: 1099.00,
    effective_from: '2026-10-16',
    changed_by: 'usr-master',
    reason: 'Tabela inaugural aprovada no Contrato Técnico Mestre',
    created_at: '2026-10-16T10:00:00Z',
  },
  {
    id: 'lpv-ampliado-v1',
    plan_tier: 'AMPLIADO',
    monthly_price: 129.90,
    annual_price_computed: 1299.00,
    effective_from: '2026-10-16',
    changed_by: 'usr-master',
    reason: 'Preço indicativo (checkout travado até definição de teto de membros e cotas)',
    created_at: '2026-10-16T10:00:00Z',
  },
];

const SEED_SUBSCRIPTIONS: LicenseSubscription[] = [
  {
    id: 'sub-inaugural',
    tenant_id: 'tenant-inaugural',
    contracting_party_id: 'cp-joao',
    plan_tier: 'INTERMEDIARIO',
    period: 'ANUAL',
    price_paid: 1099.00,
    price_version_id: 'lpv-intermediario-v1',
    anchor_day: 16,
    starts_at: '2026-10-16T00:00:00Z',
    ends_at: '2027-10-16T00:00:00Z',
    status: 'ATIVA',
    paid_payment_id: 'pay-lic-001',
  },
  {
    id: 'sub-tech',
    tenant_id: 'tenant-tech',
    contracting_party_id: 'cp-renata',
    plan_tier: 'ESSENCIAL',
    period: 'MENSAL',
    price_paid: 89.90,
    price_version_id: 'lpv-essencial-v1',
    anchor_day: 5,
    starts_at: '2026-12-05T00:00:00Z',
    ends_at: '2027-01-05T00:00:00Z',
    status: 'ATIVA',
    paid_payment_id: 'pay-lic-002',
  },
];

const SEED_CONTRIBUTIONS: Contribution[] = [
  // Competência Janeiro 2027 (Vencimento 10/01/2027)
  { id: 'c-1', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-joao', competence: '2027-01', due_date: '2027-01-10', amount_due: 150.00, amount_paid: 150.00, payment_status: 'QUITADA', due_status: 'REGULARIZADA', paid_at: '2027-01-09T14:00:00Z' },
  { id: 'c-2', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-maria', competence: '2027-01', due_date: '2027-01-10', amount_due: 300.00, amount_paid: 300.00, payment_status: 'QUITADA', due_status: 'REGULARIZADA', paid_at: '2027-01-10T11:00:00Z' },
  { id: 'c-3', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-pedro', competence: '2027-01', due_date: '2027-01-10', amount_due: 150.00, amount_paid: 150.00, payment_status: 'QUITADA', due_status: 'REGULARIZADA', paid_at: '2027-01-08T16:20:00Z' },
  { id: 'c-4', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-ana', competence: '2027-01', due_date: '2027-01-10', amount_due: 150.00, amount_paid: 0, payment_status: 'PENDENTE', due_status: 'VENCIDA' },

  // Competência Fevereiro 2027 (Vencimento 10/02/2027)
  { id: 'c-5', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-joao', competence: '2027-02', due_date: '2027-02-10', amount_due: 150.00, amount_paid: 150.00, payment_status: 'QUITADA', due_status: 'REGULARIZADA', paid_at: '2027-02-09T10:00:00Z' },
  { id: 'c-6', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-maria', competence: '2027-02', due_date: '2027-02-10', amount_due: 300.00, amount_paid: 150.00, payment_status: 'PARCIAL', due_status: 'VENCIDA' }, // Exemplo AT-12: Parcial e Vencida simultaneamente!
  { id: 'c-7', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-pedro', competence: '2027-02', due_date: '2027-02-10', amount_due: 150.00, amount_paid: 150.00, payment_status: 'QUITADA', due_status: 'REGULARIZADA', paid_at: '2027-02-10T09:00:00Z' },
  { id: 'c-8', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-ana', competence: '2027-02', due_date: '2027-02-10', amount_due: 150.00, amount_paid: 0, payment_status: 'PENDENTE', due_status: 'VENCIDA' },

  // Competência Março 2027 (Vencimento 10/03/2027)
  { id: 'c-9', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-joao', competence: '2027-03', due_date: '2027-03-10', amount_due: 150.00, amount_paid: 150.00, payment_status: 'QUITADA', due_status: 'REGULARIZADA', paid_at: '2027-03-10T15:00:00Z' },
  { id: 'c-10', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-maria', competence: '2027-03', due_date: '2027-03-10', amount_due: 300.00, amount_paid: 0, payment_status: 'PENDENTE', due_status: 'A_VENCER' },
  { id: 'c-11', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-pedro', competence: '2027-03', due_date: '2027-03-10', amount_due: 150.00, amount_paid: 0, payment_status: 'PENDENTE', due_status: 'A_VENCER' },
  { id: 'c-12', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', membership_id: 'mem-ana', competence: '2027-03', due_date: '2027-03-10', amount_due: 150.00, amount_paid: 0, payment_status: 'PENDENTE', due_status: 'VENCIDA' },
];

// Seed de autorização anual para crédito do administrador (Cláusula 2.5 e 8.8)
const SEED_ADMIN_SELF_CONSENTS: AnnualSelfLoanConsent[] = [
  {
    id: 'consent-joao-2027',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    beneficiary_admin_id: 'usr-admin-joao',
    beneficiary_admin_name: 'João Silva',
    document_version: 'TERMO_AUTORIZACAO_ANUAL_CREDITO_PROPRIO_V1',
    status: 'ATIVO', // Todos assinaram unanimemente
    valid_from: '2027-01-01',
    valid_to: '2027-12-31',
    signatures: [
      {
        id: 'sig-maria',
        consent_id: 'consent-joao-2027',
        signer_membership_id: 'mem-maria',
        signer_name: 'Maria Oliveira',
        signed_at: '2027-01-02T10:00:00Z',
        evidence_ref: 'EVID-SIG-MARIA-SHA256-OK',
      },
      {
        id: 'sig-pedro',
        consent_id: 'consent-joao-2027',
        signer_membership_id: 'mem-pedro',
        signer_name: 'Pedro Santos',
        signed_at: '2027-01-03T11:30:00Z',
        evidence_ref: 'EVID-SIG-PEDRO-SHA256-OK',
      },
    ],
  },
];

// Seed de Empréstimos com simulação Price oficial (sem taxa, períodos mensais completos)
const initialLoanSim = calculatePriceSimulation({
  principal: 500.00,
  monthlyRate: 0.20,
  termMonths: 5,
  cycleYear: 2027,
  useIrregularFirstPeriod: false,
});

const SEED_LOANS: Loan[] = [
  {
    id: 'loan-pedro-01',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    borrower_membership_id: 'mem-pedro',
    borrower_name: 'Pedro Santos',
    is_admin_loan: false,
    policy_version_id: 'pol-inaugural-v1',
    principal: 500.00,
    monthly_rate: 0.20,
    term_months: 5,
    schedule_type: 'PRICE',
    decision_by: 'usr-admin-joao',
    status: 'DESEMBOLSADO',
    requested_at: '2027-01-27T10:00:00Z',
    approved_at: '2027-01-28T09:00:00Z',
    disbursed_at: '2027-01-28T14:20:00Z',
    pix_transfer_id: 'pix-disb-pedro-01',
    first_period_days: 30,
    first_period_rate: 0.20,
    monthly_payment: initialLoanSim.uniformPayment,
    total_interest: initialLoanSim.totalInterest,
    installments: initialLoanSim.installments.map((inst, index) => {
      // 1ª parcela paga em 10/02
      if (index === 0) {
        return {
          id: `inst-pedro-1`,
          loan_id: 'loan-pedro-01',
          sequence: 1,
          due_date: inst.dueDate,
          principal_due: inst.principalDue,
          interest_due: inst.interestDue,
          penalties_due: 0,
          fine_amount: 0,
          mora_amount: 0,
          days_overdue: 0,
          paid_amount: inst.payment,
          paid_interest: inst.interestDue,
          paid_mora: 0,
          paid_fine: 0,
          paid_principal: inst.principalDue,
          status: 'QUITADA',
          due_status: 'REGULARIZADA',
        };
      }
      return {
        id: `inst-pedro-${index + 1}`,
        loan_id: 'loan-pedro-01',
        sequence: index + 1,
        due_date: inst.dueDate,
        principal_due: inst.principalDue,
        interest_due: inst.interestDue,
        penalties_due: 0,
        fine_amount: 0,
        mora_amount: 0,
        days_overdue: 0,
        paid_amount: 0,
        paid_interest: 0,
        paid_mora: 0,
        paid_fine: 0,
        paid_principal: 0,
        status: 'PENDENTE',
        due_status: 'A_VENCER',
      };
    }),
  },
];

// Seed de Contas do Ledger Contábil (Centavos exatos)
const SEED_LEDGER_ACCOUNTS: LedgerAccount[] = [
  { id: 'la-caixa', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', account_code: '1.1.1', account_name: 'Caixa Financeiro Reconciliado', kind: 'ATIVO', balance_cents: 145000, status: 'ACTIVE' }, // R$ 1.450,00
  { id: 'la-credito', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', account_code: '1.2.1', account_name: 'Crédito Interno a Receber (Principal)', kind: 'ATIVO', balance_cents: 65000, status: 'ACTIVE' }, // R$ 650,00
  { id: 'la-capital', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', account_code: '2.1.1', account_name: 'Capital Confirmado dos Membros', kind: 'PASSIVO', balance_cents: 190000, status: 'ACTIVE' }, // R$ 1.900,00
  { id: 'la-receita-juros', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', account_code: '4.1.1', account_name: 'Receita Realizada de Juros e Multas', kind: 'RECEITA', balance_cents: 20000, status: 'ACTIVE' }, // R$ 200,00
  { id: 'la-reserva-saida', tenant_id: 'tenant-inaugural', cycle_id: 'cycle-2027-inaugural', account_code: '2.2.1', account_name: 'Reserva Atômica de Desembolsos Pendentes', kind: 'PASSIVO', balance_cents: 0, status: 'ACTIVE' },
];

const SEED_LEDGER_TXS: LedgerTransaction[] = [
  {
    id: 'ltx-001',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    business_type: 'CONTRIBUTION_PAYMENT',
    business_id: 'c-1',
    posted_at: '2027-01-09T14:00:00Z',
    status: 'POSTED',
    description: 'Contribuição confirmada Jan/2027 João Silva',
    entries: [
      { id: 'le-1', transaction_id: 'ltx-001', account_id: 'la-caixa', account_name: 'Caixa Financeiro Reconciliado', direction: 'DEBIT', amount_cents: 10000, currency: 'BRL' },
      { id: 'le-2', transaction_id: 'ltx-001', account_id: 'la-capital', account_name: 'Capital Confirmado dos Membros', direction: 'CREDIT', amount_cents: 10000, currency: 'BRL' },
    ],
  },
  {
    id: 'ltx-002',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    business_type: 'LOAN_DISBURSEMENT',
    business_id: 'loan-pedro-01',
    posted_at: '2027-01-28T14:20:00Z',
    status: 'POSTED',
    description: 'Desembolso de empréstimo aprovado Pedro Santos',
    entries: [
      { id: 'le-3', transaction_id: 'ltx-002', account_id: 'la-credito', account_name: 'Crédito Interno a Receber (Principal)', direction: 'DEBIT', amount_cents: 80000, currency: 'BRL' },
      { id: 'le-4', transaction_id: 'ltx-002', account_id: 'la-caixa', account_name: 'Caixa Financeiro Reconciliado', direction: 'CREDIT', amount_cents: 80000, currency: 'BRL' },
    ],
  },
];

const SEED_LOTTERY: LotteryCampaignDemo = {
  id: 'lot-demo-01',
  tenant_id: 'tenant-inaugural',
  cycle_id: 'cycle-2027-inaugural',
  title: 'Mega-Sena Especial da Virada (Demonstrador Regulatório)',
  modality: 'MEGA_SENA',
  contest_number: 2850,
  official_cost: 150.00,
  quotas_count: 20,
  official_cost_per_quota: 7.50,
  final_price_per_quota: 25.00,
  total_revenue_expected: 500.00,
  gross_margin: 350.00,
  status: 'DEMO_COTAS_RESERVADAS',
  disclaimer: 'DADOS FICTÍCIOS — MODO DEMONSTRAÇÃO REGULATÓRIA. Proibido dinheiro real ou apostas verdadeiras até aprovação expressa da CAIXA e conformidade legal.',
};

export interface AppState {
  currentUserId: string;
  currentRole: UserRole;
  currentTenantId: string;
  activeCycleId: string;
  users: UserIdentity[];
  tenants: Tenant[];
  roleGrants: RoleGrant[];
  cycles: Cycle[];
  policies: TenantPolicyVersion[];
  memberships: Membership[];
  quotas: Quota[];
  contributions: Contribution[];
  loans: Loan[];
  adminSelfConsents: AnnualSelfLoanConsent[];
  ledgerAccounts: LedgerAccount[];
  ledgerTransactions: LedgerTransaction[];
  pixTransfers: PixTransfer[];
  plans: LicensePlan[];
  priceVersions: LicensePriceVersion[];
  subscriptions: LicenseSubscription[];
  supportGrants: SupportAccessGrant[];
  auditEvents: AuditEvent[];
  lotteryCampaign: LotteryCampaignDemo;
  raffleCampaigns: RaffleCampaign[];
  raffleCards: RaffleCard[];
  rafflePrizeHistories: RafflePrizeHistory[];
  rafflePayments: RafflePayment[];
  bolaoCampaigns: BolaoCampaign[];
  bolaoParticipations: BolaoMemberParticipation[];
  backendStatus: 'CONNECTED' | 'UNCONFIGURED' | 'UNAVAILABLE';
  isDataLoadedFromServer: boolean;
  lastFinancialError: { message: string; code?: string; detail?: string } | null;
}

export class AppStore {
  private state: AppState;
  private listeners: (() => void)[] = [];

  constructor() {
    this.state = this.loadState();
  }

  private loadState(): AppState {
    return structuredClone({
      currentUserId: '',
      currentRole: 'TENANT_MEMBER',
      currentTenantId: '',
      activeCycleId: 'cycle-2027-inaugural',
      users: SEED_USERS,
      tenants: SEED_TENANTS,
      roleGrants: SEED_ROLE_GRANTS,
      cycles: SEED_CYCLES,
      policies: SEED_POLICIES,
      memberships: SEED_MEMBERSHIPS,
      quotas: SEED_QUOTAS,
      contributions: SEED_CONTRIBUTIONS,
      loans: SEED_LOANS,
      adminSelfConsents: SEED_ADMIN_SELF_CONSENTS,
      ledgerAccounts: SEED_LEDGER_ACCOUNTS,
      ledgerTransactions: SEED_LEDGER_TXS,
      pixTransfers: [],
      plans: SEED_PLANS,
      priceVersions: SEED_PRICE_VERSIONS,
      subscriptions: SEED_SUBSCRIPTIONS,
      supportGrants: [],
      auditEvents: [
        {
          id: 'aud-001',
          actor_id: 'usr-master',
          actor_role: 'MASTER',
          object_type: 'CONTRACT',
          object_id: 'FRCAIXINHA-2.2',
          action: 'APROVACAO_DOCUMENTAL_G1',
          timestamp: '2026-10-16T12:00:00Z',
          reason: 'Homologação e aprovação das 147 cláusulas do Contrato Técnico Mestre',
          evidence_ref: 'DOC-HASH-G1-CONCLUIDO',
        },
      ],
      lotteryCampaign: SEED_LOTTERY,
      raffleCampaigns: SEED_RAFFLE_CAMPAIGNS,
      raffleCards: SEED_RAFFLE_CARDS,
      rafflePrizeHistories: SEED_RAFFLE_PRIZE_HISTORIES,
      rafflePayments: SEED_RAFFLE_PAYMENTS,
      bolaoCampaigns: SEED_BOLAO_CAMPAIGNS,
      bolaoParticipations: SEED_BOLAO_PARTICIPATIONS,
      backendStatus: 'UNCONFIGURED',
      isDataLoadedFromServer: false,
      lastFinancialError: null,
    });
  }

  public async refreshFinancialDataFromServer(tenantId: string): Promise<boolean> {
    try {
      await Promise.all([
        financialApi.fetchQuotas(tenantId),
        financialApi.fetchContributions(tenantId),
        financialApi.fetchLoans(tenantId),
        financialApi.fetchLedgerAccounts(tenantId),
      ]);
      this.state.backendStatus = 'CONNECTED';
      // A API respondeu, mas seus resultados ainda não substituem os dados locais.
      this.state.isDataLoadedFromServer = false;
      this.notify();
      return true;
    } catch {
      this.state.backendStatus = 'UNAVAILABLE';
      this.state.isDataLoadedFromServer = false;
      this.notify();
      return false;
    }
  }

  private persist() {
    // CONFORMIDADE CONTRATUAL ESTREITA:
    // O localStorage NUNCA deve gravar ou restaurar saldos, identidades, cotas, amortizações
    // ou dados financeiros como se fossem autoritativos do servidor.
    // A fonte única autoritativa é o backend PostgreSQL.
    this.notify();
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify() {
    this.listeners.forEach(l => l());
  }

  public getState(): AppState {
    return this.state;
  }

  // --- Gestão de Contexto e Papéis Autorizados pelo Servidor ---
  public setAuthenticatedContext(user: { id: string; role: UserRole; tenantId?: string }) {
    this.state = this.loadState();
    this.state.currentUserId = user.id;
    this.state.currentRole = user.role;
    this.state.currentTenantId = user.tenantId || '';
    if (user.tenantId) {
      const cycle = this.state.cycles.find(c => c.tenant_id === user.tenantId);
      if (cycle) {
        this.state.activeCycleId = cycle.id;
      }
    }
    this.addAudit('LOGIN_SUCCESS', `Autenticação confirmada pelo servidor para papel ${user.role}`);
    this.notify();
  }

  public clearAuthenticatedContext() {
    this.state = this.loadState();
    this.state.currentUserId = '';
    this.state.currentRole = 'TENANT_MEMBER';
    this.state.currentTenantId = '';
    this.addAudit('LOGOUT_SUCCESS', 'Sessão encerrada com sucesso');
    this.notify();
  }

  // Bloqueio explícito de troca de contexto sem autenticação
  public switchContext(_userId: string, _role: UserRole, _tenantId?: string) {
    console.warn('Ação bloqueada: alteração de papel no cliente rejeitada por política de RBAC.');
  }

  public addAudit(action: string, reason: string, objectType = 'SYSTEM', objectId = 'GENERAL') {
    const event: AuditEvent = {
      id: `aud-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      actor_id: this.state.currentUserId,
      actor_role: this.state.currentRole,
      tenant_id: this.state.currentRole === 'MASTER' ? undefined : this.state.currentTenantId,
      object_type: objectType,
      object_id: objectId,
      action,
      timestamp: new Date().toISOString(),
      reason,
      evidence_ref: `REF-${Date.now().toString(16).toUpperCase()}`,
    };
    this.state.auditEvents.unshift(event);
  }

  // --- Contabilidade e Ledger ---
  public getTenantCashBalance(tenantId: string): number {
    const account = this.state.ledgerAccounts.find(
      a => a.tenant_id === tenantId && a.account_code === '1.1.1'
    );
    return account ? account.balance_cents / 100 : 0;
  }

  public getTenantFreeCash(tenantId: string): number {
    const cash = this.getTenantCashBalance(tenantId);
    const reserveAcc = this.state.ledgerAccounts.find(
      a => a.tenant_id === tenantId && a.account_code === '2.2.1'
    );
    const reserved = reserveAcc ? reserveAcc.balance_cents / 100 : 0;
    return Math.max(0, roundCents(cash - reserved));
  }

  public getTenantTotalCapital(tenantId: string): number {
    const account = this.state.ledgerAccounts.find(
      a => a.tenant_id === tenantId && a.account_code === '2.1.1'
    );
    return account ? account.balance_cents / 100 : 0;
  }

  public getTenantOutstandingCredit(tenantId: string): number {
    const account = this.state.ledgerAccounts.find(
      a => a.tenant_id === tenantId && a.account_code === '1.2.1'
    );
    return account ? account.balance_cents / 100 : 0;
  }

  public getTenantRealizedProfit(tenantId: string): number {
    const account = this.state.ledgerAccounts.find(
      a => a.tenant_id === tenantId && a.account_code === '4.1.1'
    );
    return account ? account.balance_cents / 100 : 0;
  }

  // --- Contribuições & Pagamentos ---
  public async registerContributionPayment(contributionId: string, amount: number) {
    const contrib = this.state.contributions.find(c => c.id === contributionId);
    if (!contrib) throw new Error('Contribuição não encontrada.');

    // 1. Chamar o backend oficial FastAPI + PostgreSQL
    try {
      await financialApi.payContribution(contrib.tenant_id, contributionId, amount);
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    // A API criou apenas uma intenção pendente; não houve conciliação bancária.
    // Não altere status, pagamentos, saldos ou lançamentos locais.
    this.state.lastFinancialError = null;
    this.notify();
  }

  // --- Empréstimos: Pedido, Aprovação e Desembolso ---
  public async requestLoan(params: {
    membershipId: string;
    principal: number;
    termMonths: number;
  }) {
    const policy = this.state.policies.find(p => p.tenant_id === this.state.currentTenantId && p.status === 'ACTIVE');
    const membership = this.state.memberships.find(m => m.id === params.membershipId);
    if (!policy || !membership) throw new Error('Política ou membro não encontrado');

    const isAdmin = membership.user_id === this.state.tenants.find(t => t.id === this.state.currentTenantId)?.admin_user_id;

    // Se for administrador, verificar se há autorização coletiva unânime anual (Cláusula 2.5 e 8.8)
    if (isAdmin) {
      const consent = this.state.adminSelfConsents.find(c => c.tenant_id === this.state.currentTenantId && c.cycle_id === this.state.activeCycleId);
      const otherActiveMembers = this.state.memberships.filter(m => m.tenant_id === this.state.currentTenantId && m.status === 'ATIVA' && m.id !== membership.id);
      
      const hasUnanimous = consent && consent.status === 'ATIVO' && otherActiveMembers.every(om => 
        consent.signatures.some(sig => sig.signer_membership_id === om.id && !sig.revoked_at)
      );

      if (!hasUnanimous) {
        throw new Error('Autoempréstimo de administrador bloqueado: requer autorização coletiva unânime de todos os demais membros ativos no ciclo.');
      }
    }

    // 1. Chamar backend oficial FastAPI
    try {
      await financialApi.requestLoan(this.state.currentTenantId, {
        principal: params.principal,
        term_months: params.termMonths,
        is_admin_loan: isAdmin,
      });
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    const sim = calculatePriceSimulation({
      principal: params.principal,
      monthlyRate: policy.monthly_interest_rate,
      termMonths: params.termMonths,
      disbursementDate: new Date(),
      cycleYear: 2027,
    });

    if (!sim.isValidCycle) {
      throw new Error(sim.validationError || 'Prazo incompatível com o ciclo financeiro');
    }

    const freeCash = this.getTenantFreeCash(this.state.currentTenantId);
    if (params.principal > freeCash) {
      throw new Error(`Saldo livre insuficiente no caixa da caixinha (Disponível: R$ ${freeCash.toFixed(2)}, Solicitado: R$ ${params.principal.toFixed(2)})`);
    }

    const newLoan: Loan = {
      id: `loan-${Date.now()}`,
      tenant_id: this.state.currentTenantId,
      cycle_id: this.state.activeCycleId,
      borrower_membership_id: membership.id,
      borrower_name: membership.user_name,
      is_admin_loan: isAdmin,
      policy_version_id: policy.id,
      principal: params.principal,
      monthly_rate: policy.monthly_interest_rate,
      term_months: params.termMonths,
      schedule_type: 'PRICE',
      status: 'SOLICITADO',
      requested_at: new Date().toISOString(),
      first_period_days: sim.firstPeriodDays,
      first_period_rate: sim.firstPeriodRate,
      monthly_payment: sim.uniformPayment,
      total_interest: sim.totalInterest,
      installments: sim.installments.map(inst => ({
        id: `inst-${Date.now()}-${inst.sequence}`,
        loan_id: `loan-${Date.now()}`,
        sequence: inst.sequence,
        due_date: inst.dueDate,
        principal_due: inst.principalDue,
        interest_due: inst.interestDue,
        penalties_due: 0,
        fine_amount: 0,
        mora_amount: 0,
        days_overdue: 0,
        paid_amount: 0,
        paid_interest: 0,
        paid_mora: 0,
        paid_fine: 0,
        paid_principal: 0,
        status: 'PENDENTE',
        due_status: 'A_VENCER',
      })),
    };

    this.state.loans.unshift(newLoan);
    this.addAudit('LOAN_REQUESTED', `Empréstimo de R$ ${params.principal.toFixed(2)} solicitado por ${membership.user_name}`, 'LOAN', newLoan.id);
    this.persist();
    return newLoan;
  }

  public async approveLoan(loanId: string) {
    const loan = this.state.loans.find(l => l.id === loanId);
    if (!loan) throw new Error('Empréstimo não encontrado.');

    // 1. Chamar backend oficial FastAPI
    try {
      await financialApi.approveLoan(loan.tenant_id, loanId);
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    loan.status = 'APROVADO';
    loan.approved_at = new Date().toISOString();
    this.addAudit('LOAN_APPROVED', `Empréstimo ${loan.id} aprovado pelo administrador`, 'LOAN', loan.id);
    this.persist();
  }

  public async disburseLoanPix(loanId: string) {
    const loan = this.state.loans.find(l => l.id === loanId);
    if (!loan || loan.status !== 'APROVADO') throw new Error('Empréstimo deve estar aprovado.');

    // 1. Chamar backend oficial FastAPI
    try {
      await financialApi.disburseLoan(loan.tenant_id, loanId);
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    // Verificar liquidez em tempo real
    const freeCash = this.getTenantFreeCash(loan.tenant_id);
    if (loan.principal > freeCash) {
      throw new Error('Falha no desembolso: caixa livre insuficiente');
    }

    loan.status = 'DESEMBOLSADO';
    loan.disbursed_at = new Date().toISOString();
    loan.pix_transfer_id = `pix-disb-${Date.now()}`;

    // Lançamento contábil de partidas dobradas
    const principalCents = Math.round(loan.principal * 100);
    const caixaAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '1.1.1');
    const creditoAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '1.2.1');

    if (caixaAcc && creditoAcc) {
      caixaAcc.balance_cents -= principalCents;
      creditoAcc.balance_cents += principalCents;

      const tx: LedgerTransaction = {
        id: `ltx-${Date.now()}`,
        tenant_id: loan.tenant_id,
        cycle_id: loan.cycle_id,
        business_type: 'LOAN_DISBURSEMENT',
        business_id: loan.id,
        posted_at: new Date().toISOString(),
        status: 'POSTED',
        description: `Desembolso Pix de empréstimo para ${loan.borrower_name}`,
        entries: [
          { id: `le-${Date.now()}-1`, transaction_id: `ltx-${Date.now()}`, account_id: creditoAcc.id, account_name: creditoAcc.account_name, direction: 'DEBIT', amount_cents: principalCents, currency: 'BRL' },
          { id: `le-${Date.now()}-2`, transaction_id: `ltx-${Date.now()}`, account_id: caixaAcc.id, account_name: caixaAcc.account_name, direction: 'CREDIT', amount_cents: principalCents, currency: 'BRL' },
        ],
      };
      this.state.ledgerTransactions.unshift(tx);
    }

    this.addAudit('LOAN_DISBURSED', `Desembolso Pix efetivado com sucesso: R$ ${loan.principal.toFixed(2)} para ${loan.borrower_name}`, 'LOAN', loan.id);
    this.persist();
  }

  // --- Pagamento de Parcela de Empréstimo com Imputação em 4 etapas ---
  public async payLoanInstallment(loanId: string, installmentSeq: number, paymentAmount: number) {
    const loan = this.state.loans.find(l => l.id === loanId);
    if (!loan) throw new Error('Empréstimo não encontrado.');
    const installment = loan.installments.find(i => i.sequence === installmentSeq);
    if (!installment) throw new Error('Parcela não encontrada.');

    // 1. Chamar backend oficial FastAPI
    try {
      await financialApi.repayLoan(loan.tenant_id, loanId, paymentAmount);
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    // Calcular imputação contratual obrigatória
    const impResult = calculateImputationHierarchy({
      paymentAmount,
      interestDue: installment.interest_due - installment.paid_interest,
      moraDue: installment.mora_amount - installment.paid_mora,
      fineDue: installment.fine_amount - installment.paid_fine,
      principalDue: installment.principal_due - installment.paid_principal,
    });

    installment.paid_interest += impResult.paidInterest;
    installment.paid_mora += impResult.paidMora;
    installment.paid_fine += impResult.paidFine;
    installment.paid_principal += impResult.paidPrincipal;
    installment.paid_amount = roundCents(
      installment.paid_interest + installment.paid_mora + installment.paid_fine + installment.paid_principal
    );

    if (impResult.isFullySettled) {
      installment.status = 'QUITADA';
      installment.due_status = 'REGULARIZADA';
    } else {
      installment.status = 'PARCIAL';
    }

    // Verificar se todo o empréstimo foi quitado
    if (loan.installments.every(i => i.status === 'QUITADA')) {
      loan.status = 'QUITADO';
    }

    // Lançamentos no Ledger contábil
    const caixaAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '1.1.1');
    const creditoAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '1.2.1');
    const receitaAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '4.1.1');

    const totalPaidCents = Math.round(paymentAmount * 100);
    const principalPaidCents = Math.round(impResult.paidPrincipal * 100);
    const revenuePaidCents = Math.round((impResult.paidInterest + impResult.paidMora + impResult.paidFine) * 100);

    if (caixaAcc && creditoAcc && receitaAcc) {
      caixaAcc.balance_cents += totalPaidCents;
      creditoAcc.balance_cents -= principalPaidCents;
      receitaAcc.balance_cents += revenuePaidCents;

      const entries: LedgerEntry[] = [
        { id: `le-${Date.now()}-1`, transaction_id: `ltx-${Date.now()}`, account_id: caixaAcc.id, account_name: caixaAcc.account_name, direction: 'DEBIT', amount_cents: totalPaidCents, currency: 'BRL' },
      ];
      if (principalPaidCents > 0) {
        entries.push({ id: `le-${Date.now()}-2`, transaction_id: `ltx-${Date.now()}`, account_id: creditoAcc.id, account_name: creditoAcc.account_name, direction: 'CREDIT', amount_cents: principalPaidCents, currency: 'BRL' });
      }
      if (revenuePaidCents > 0) {
        entries.push({ id: `le-${Date.now()}-3`, transaction_id: `ltx-${Date.now()}`, account_id: receitaAcc.id, account_name: receitaAcc.account_name, direction: 'CREDIT', amount_cents: revenuePaidCents, currency: 'BRL' });
      }

      const tx: LedgerTransaction = {
        id: `ltx-${Date.now()}`,
        tenant_id: loan.tenant_id,
        cycle_id: loan.cycle_id,
        business_type: 'LOAN_INSTALLMENT_PAYMENT',
        business_id: loan.id,
        posted_at: new Date().toISOString(),
        status: 'POSTED',
        description: `Recebimento parcela ${installmentSeq} de ${loan.borrower_name}`,
        entries,
      };
      this.state.ledgerTransactions.unshift(tx);
    }

    this.addAudit('LOAN_INSTALLMENT_PAID', `Parcela ${installmentSeq} do empréstimo ${loan.id} amortizada em R$ ${paymentAmount.toFixed(2)}`, 'LOAN', loan.id);
    this.persist();
  }

  // --- Quitação Antecipada sem Juros Futuros (Cláusula 8.6) ---
  public async settleLoanEarly(loanId: string): Promise<{ totalPaid: number; principalPaid: number; futureInterestWaived: number }> {
    const loan = this.state.loans.find(l => l.id === loanId);
    if (!loan) throw new Error('Empréstimo não encontrado');
    if (loan.status === 'QUITADO') throw new Error('Empréstimo já se encontra quitado');

    // 1. Chamar backend oficial FastAPI
    try {
      await financialApi.settleLoanEarly(loan.tenant_id, loanId);
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    // Apurar principal em aberto de todas as parcelas
    let remainingPrincipal = 0;
    let overdueInterest = 0;
    let overdueMora = 0;
    let overdueFine = 0;
    let futureUnaccruedInterest = 0;

    const now = new Date();

    loan.installments.forEach(inst => {
      if (inst.status !== 'QUITADA') {
        const unpaidPrincipal = roundCents(inst.principal_due - inst.paid_principal);
        remainingPrincipal = roundCents(remainingPrincipal + unpaidPrincipal);

        const dueDate = new Date(inst.due_date);
        const isPastDue = dueDate < now;

        if (isPastDue) {
          // Encargos já vencidos e legítimos
          overdueInterest = roundCents(overdueInterest + (inst.interest_due - inst.paid_interest));
          overdueMora = roundCents(overdueMora + (inst.mora_amount - inst.paid_mora));
          overdueFine = roundCents(overdueFine + (inst.fine_amount - inst.paid_fine));
        } else {
          // Juros futuros vincendos NÃO incorridos -> 100% abatidos
          futureUnaccruedInterest = roundCents(futureUnaccruedInterest + (inst.interest_due - inst.paid_interest));
        }
      }
    });

    const earlyRes = calculateEarlySettlement(
      remainingPrincipal,
      overdueInterest,
      overdueMora,
      overdueFine,
      futureUnaccruedInterest
    );

    // Marcar todas as parcelas como quitadas
    loan.installments.forEach(inst => {
      inst.status = 'QUITADA';
      inst.due_status = 'REGULARIZADA';
      inst.paid_principal = inst.principal_due;
      inst.paid_amount = roundCents(inst.principal_due + inst.paid_interest + inst.paid_mora + inst.paid_fine);
    });
    loan.status = 'QUITADO';

    // Lançamento contábil no Ledger
    const caixaAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '1.1.1');
    const creditoAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '1.2.1');
    const receitaAcc = this.state.ledgerAccounts.find(a => a.tenant_id === loan.tenant_id && a.account_code === '4.1.1');

    const totalPaidCents = Math.round(earlyRes.totalSettlementAmount * 100);
    const principalPaidCents = Math.round(earlyRes.remainingPrincipal * 100);
    const overdueRevenueCents = Math.round(earlyRes.totalOverdueCharges * 100);

    if (caixaAcc && creditoAcc) {
      caixaAcc.balance_cents += totalPaidCents;
      creditoAcc.balance_cents -= principalPaidCents;
      if (receitaAcc && overdueRevenueCents > 0) {
        receitaAcc.balance_cents += overdueRevenueCents;
      }

      const entries: LedgerEntry[] = [
        { id: `le-${Date.now()}-1`, transaction_id: `ltx-${Date.now()}`, account_id: caixaAcc.id, account_name: caixaAcc.account_name, direction: 'DEBIT', amount_cents: totalPaidCents, currency: 'BRL' },
        { id: `le-${Date.now()}-2`, transaction_id: `ltx-${Date.now()}`, account_id: creditoAcc.id, account_name: creditoAcc.account_name, direction: 'CREDIT', amount_cents: principalPaidCents, currency: 'BRL' },
      ];
      if (receitaAcc && overdueRevenueCents > 0) {
        entries.push({ id: `le-${Date.now()}-3`, transaction_id: `ltx-${Date.now()}`, account_id: receitaAcc.id, account_name: receitaAcc.account_name, direction: 'CREDIT', amount_cents: overdueRevenueCents, currency: 'BRL' });
      }

      const tx: LedgerTransaction = {
        id: `ltx-${Date.now()}`,
        tenant_id: loan.tenant_id,
        cycle_id: loan.cycle_id,
        business_type: 'LOAN_EARLY_SETTLEMENT',
        business_id: loan.id,
        posted_at: new Date().toISOString(),
        status: 'POSTED',
        description: `Quitação antecipada integral do empréstimo de ${loan.borrower_name} (sem juros futuros)`,
        entries,
      };
      this.state.ledgerTransactions.unshift(tx);
    }

    this.addAudit(
      'LOAN_EARLY_SETTLED',
      `Empréstimo ${loan.id} quitado antecipadamente por R$ ${earlyRes.totalSettlementAmount.toFixed(2)} (Juros futuros abatidos: R$ ${earlyRes.futureInterestWaived.toFixed(2)})`,
      'LOAN',
      loan.id
    );
    this.persist();

    return {
      totalPaid: earlyRes.totalSettlementAmount,
      principalPaid: earlyRes.remainingPrincipal,
      futureInterestWaived: earlyRes.futureInterestWaived,
    };
  }

  // --- Autorização Anual para Administrador ---
  public async toggleAdminConsentSignature(signerMembershipId: string) {
    const consent = this.state.adminSelfConsents.find(c => c.tenant_id === this.state.currentTenantId);
    if (!consent) throw new Error('Registro de consentimento não encontrado.');

    // 1. Chamar backend oficial FastAPI
    try {
      await financialApi.voteAdminConsent(this.state.currentTenantId, 'annual-cycle', 'FAVORAVEL');
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    const existingSig = consent.signatures.find(s => s.signer_membership_id === signerMembershipId);
    if (existingSig) {
      if (existingSig.revoked_at) {
        existingSig.revoked_at = null;
        existingSig.revocation_reason = null;
        existingSig.signed_at = new Date().toISOString();
      } else {
        existingSig.revoked_at = new Date().toISOString();
        existingSig.revocation_reason = 'Revogação manual pelo membro';
      }
    } else {
      const member = this.state.memberships.find(m => m.id === signerMembershipId);
      if (member) {
        consent.signatures.push({
          id: `sig-${Date.now()}`,
          consent_id: consent.id,
          signer_membership_id: member.id,
          signer_name: member.user_name,
          signed_at: new Date().toISOString(),
          evidence_ref: `REF-SIG-${Date.now().toString(16)}`,
        });
      }
    }

    // Reavaliar status de unanimidade
    const otherMembers = this.state.memberships.filter(
      m => m.tenant_id === this.state.currentTenantId && m.status === 'ATIVA' && m.user_id !== consent.beneficiary_admin_id
    );
    const isUnanimous = otherMembers.every(om => 
      consent.signatures.some(s => s.signer_membership_id === om.id && !s.revoked_at)
    );
    consent.status = isUnanimous ? 'ATIVO' : 'SUSPENSO_REVOGADO';

    this.addAudit('SELF_LOAN_CONSENT_UPDATED', `Assinatura de autorização de autoempréstimo alterada por ${signerMembershipId}. Status: ${consent.status}`, 'CONSENT', consent.id);
    this.persist();
  }

  // --- Fechamento de Ciclo Anual (Capital-Dias V2) ---
  public async closeCycle(cycleId: string) {
    try {
      await financialApi.closeCycle(this.state.currentTenantId, cycleId);
    } catch (err: any) {
      this.state.lastFinancialError = {
        message: err.message,
        code: err.code || 'FINANCIAL_BACKEND_UNAVAILABLE',
        detail: err.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.',
      };
      this.notify();
      throw err;
    }

    const cycle = this.state.cycles.find(c => c.id === cycleId);
    if (cycle) {
      cycle.status = 'LIQUIDADO';
    }
    this.addAudit('CYCLE_CLOSED', `Fechamento anual do ciclo ${cycleId} homologado via FastAPI`, 'CYCLE', cycleId);
    this.persist();
  }

  // --- Master: Edição Dinâmica de Preço ---
  public updateLicenseMonthlyPrice(planTier: LicensePlan['tier'], newMonthlyPrice: number, reason: string) {
    if (this.state.currentUserId) {
      throw new Error('Preço real exige registro de nova versão no FastAPI/PostgreSQL; atualização local bloqueada.');
    }
    if (this.state.currentRole !== 'MASTER') {
      throw new Error('Apenas o Master pode alterar preços de licença');
    }

    const computedAnnual = roundCents(newMonthlyPrice * 10);
    const newVersion: LicensePriceVersion = {
      id: `lpv-${planTier.toLowerCase()}-v${Date.now()}`,
      plan_tier: planTier,
      monthly_price: roundCents(newMonthlyPrice),
      annual_price_computed: computedAnnual,
      effective_from: new Date().toISOString().split('T')[0],
      changed_by: this.state.currentUserId,
      reason,
      created_at: new Date().toISOString(),
    };

    this.state.priceVersions.unshift(newVersion);
    this.addAudit('PRICE_VERSION_UPDATED', `Plano ${planTier} reajustado para R$ ${newMonthlyPrice.toFixed(2)}/mês e R$ ${computedAnnual.toFixed(2)}/ano`, 'PRICING', newVersion.id);
    this.persist();
  }

  // --- Suporte Excepcional & Break-Glass ---
  public grantSupportAccess(tenantId: string, type: 'CONSENTED_NORMAL' | 'BREAK_GLASS_EMERGENCY', reason: string) {
    if (this.state.currentUserId) {
      throw new Error('Suporte real indisponível sem autorização transacional e consentimento no servidor.');
    }
    const maxMinutes = type === 'CONSENTED_NORMAL' ? 60 : 30;
    const now = new Date();
    const expiresAt = new Date(now.getTime() + maxMinutes * 60 * 1000);

    const grant: SupportAccessGrant = {
      id: `sup-${Date.now()}`,
      tenant_id: tenantId,
      granted_by: type === 'CONSENTED_NORMAL' ? 'usr-admin-joao' : 'SYSTEM_EMERGENCY_AUDIT',
      granted_to: 'usr-master',
      type,
      max_minutes: maxMinutes,
      scope: 'DIAGNOSTICO_TECNICO_RECONCILIACAO_SEM_PIX_SEM_APROVACAO',
      reason,
      issued_at: now.toISOString(),
      expires_at: expiresAt.toISOString(),
      status: 'ACTIVE',
    };

    this.state.supportGrants.unshift(grant);
    this.addAudit('SUPPORT_ACCESS_GRANTED', `Acesso ${type} (${maxMinutes}m) concedido com restrições invioláveis`, 'SUPPORT', grant.id);
    this.persist();
    return grant;
  }

  public revokeSupportAccess(grantId: string) {
    if (this.state.currentUserId) {
      throw new Error('Revogação de suporte real exige confirmação do FastAPI; alteração local bloqueada.');
    }
    const grant = this.state.supportGrants.find(g => g.id === grantId);
    if (!grant) return;
    grant.status = 'REVOKED';
    grant.revoked_at = new Date().toISOString();
    this.addAudit('SUPPORT_ACCESS_REVOKED', `Acesso de suporte ${grant.id} revogado imediatamente`, 'SUPPORT', grant.id);
    this.persist();
  }

  // --- Módulo de Rifas (Proposta Consolidada FRcaixinha 2.2) ---
  public updateRafflePrize(campaignId: string, newAmount: number, reason: string) {
    const campaign = this.state.raffleCampaigns.find(c => c.id === campaignId);
    if (!campaign) throw new Error('Campanha de rifa não encontrada');

    const previousAmount = campaign.prize_amount;
    const roundedNewAmount = roundCents(newAmount);

    const currentUser = this.state.users.find(u => u.id === this.state.currentUserId);
    const adminName = currentUser ? currentUser.name : 'Administrador';

    const historyEntry: RafflePrizeHistory = {
      id: `rph-${Date.now()}`,
      campaign_id: campaignId,
      admin_id: this.state.currentUserId,
      admin_name: adminName,
      previous_amount: previousAmount,
      new_amount: roundedNewAmount,
      changed_at: new Date().toISOString(),
      reason: reason || 'Revisão orçamentária pelo administrador',
    };

    campaign.prize_amount = roundedNewAmount;
    campaign.prize_description = `Prêmio em Dinheiro: R$ ${roundedNewAmount.toFixed(2)} via Pix Oficial`;
    this.state.rafflePrizeHistories.unshift(historyEntry);

    this.addAudit(
      'RAFFLE_PRIZE_UPDATED',
      `Premiação da campanha "${campaign.title}" alterada de R$ ${previousAmount.toFixed(2)} para R$ ${roundedNewAmount.toFixed(2)}. Motivo: ${reason}`,
      'RAFFLE_CAMPAIGN',
      campaign.id
    );
    this.persist();
  }

  public updateRaffleTicketStatus(
    ticketId: string,
    status: RaffleTicketStatus,
    buyerName?: string,
    buyerPhone?: string,
    buyerPixKey?: string
  ) {
    for (const card of this.state.raffleCards) {
      const ticket = card.tickets.find(t => t.id === ticketId);
      if (ticket) {
        ticket.status = status;
        if (buyerName !== undefined) ticket.buyer_name = buyerName;
        if (buyerPhone !== undefined) ticket.buyer_phone = buyerPhone;
        if (buyerPixKey !== undefined) ticket.buyer_pix_key = buyerPixKey;
        if (status === 'PAGO' && !ticket.paid_at) {
          ticket.paid_at = new Date().toISOString();
        } else if (status !== 'PAGO') {
          ticket.paid_at = null;
        }

        // Recalcular totais da cartela
        this.recalculateCardTotals(card);
        this.addAudit('RAFFLE_TICKET_UPDATED', `Bilhete #${ticket.number} atualizado para status "${status}" na cartela ${card.id}`, 'RAFFLE_TICKET', ticket.id);
        this.persist();
        return;
      }
    }
  }

  public payRaffleTicket(ticketId: string, buyerName?: string) {
    for (const card of this.state.raffleCards) {
      const ticket = card.tickets.find(t => t.id === ticketId);
      if (ticket) {
        ticket.status = 'PAGO';
        if (buyerName) ticket.buyer_name = buyerName;
        ticket.paid_at = new Date().toISOString();

        this.recalculateCardTotals(card);

        // Registrar pagamento
        const payment: RafflePayment = {
          id: `pay-raf-${Date.now()}`,
          campaign_id: card.campaign_id,
          membership_id: card.membership_id,
          card_id: card.id,
          amount: ticket.price,
          paid_at: ticket.paid_at,
          pix_transaction_id: `pix-mp-${Date.now()}`,
          status: 'CONFIRMADO',
        };
        this.state.rafflePayments.unshift(payment);

        this.addAudit('RAFFLE_TICKET_PAID', `Bilhete #${ticket.number} pago (R$ ${ticket.price.toFixed(2)}) via Pix`, 'RAFFLE_TICKET', ticket.id);
        this.persist();
        return;
      }
    }
  }

  public payRaffleCardFull(cardId: string) {
    const card = this.state.raffleCards.find(c => c.id === cardId);
    if (!card) throw new Error('Cartela não encontrada');

    const pendingBefore = card.amount_pending;
    const now = new Date().toISOString();

    card.tickets.forEach(ticket => {
      ticket.status = 'PAGO';
      if (!ticket.paid_at) ticket.paid_at = now;
      if (!ticket.buyer_name) ticket.buyer_name = card.member_name;
    });

    card.paid_tickets = 10;
    card.sold_tickets = 10;
    card.amount_paid = 50.00;
    card.amount_pending = 0.00;
    card.status = 'PAGA';

    if (pendingBefore > 0) {
      const payment: RafflePayment = {
        id: `pay-raf-full-${Date.now()}`,
        campaign_id: card.campaign_id,
        membership_id: card.membership_id,
        card_id: card.id,
        amount: pendingBefore,
        paid_at: now,
        pix_transaction_id: `pix-mp-full-${Date.now()}`,
        status: 'CONFIRMADO',
      };
      this.state.rafflePayments.unshift(payment);
    }

    this.addAudit('RAFFLE_CARD_PAID_FULL', `Cartela ${card.id} (Cota #${card.quota_number}) quitada integralmente por ${card.member_name} (R$ 50,00)`, 'RAFFLE_CARD', card.id);
    this.persist();
  }

  public drawRaffleWinner(campaignId: string, winningNumber: number, drawSource?: string) {
    const campaign = this.state.raffleCampaigns.find(c => c.id === campaignId);
    if (!campaign) throw new Error('Campanha não encontrada');

    // Localizar o bilhete e cota correspondente
    let winningTicket: RaffleTicket | null = null;
    let winningCard: RaffleCard | null = null;

    for (const card of this.state.raffleCards.filter(c => c.campaign_id === campaignId)) {
      const t = card.tickets.find(tk => tk.number === winningNumber);
      if (t) {
        winningTicket = t;
        winningCard = card;
        break;
      }
    }

    campaign.winning_number = winningNumber;
    campaign.winning_member_id = winningCard ? winningCard.membership_id : null;
    campaign.winning_member_name = winningCard ? (winningTicket?.buyer_name ? `${winningTicket.buyer_name} (Cota de ${winningCard.member_name})` : winningCard.member_name) : null;
    campaign.status = 'CONCLUIDA';
    if (drawSource) campaign.draw_source = drawSource;

    this.addAudit(
      'RAFFLE_WINNER_DRAWN',
      `Sorteio da campanha "${campaign.title}" realizado. Número sorteado: #${winningNumber}. Contemplado: ${campaign.winning_member_name || 'Bilhete não atribuído'}. Prêmio: R$ ${campaign.prize_amount.toFixed(2)} via Pix`,
      'RAFFLE_CAMPAIGN',
      campaign.id
    );
    this.persist();
  }

  public resetRaffleCampaignDraw(campaignId: string) {
    const campaign = this.state.raffleCampaigns.find(c => c.id === campaignId);
    if (!campaign) return;
    campaign.status = 'ATIVA';
    campaign.winning_number = null;
    campaign.winning_member_id = null;
    campaign.winning_member_name = null;
    this.addAudit('RAFFLE_DRAW_RESET', `Sorteio da campanha ${campaign.title} reaberto para simulação`, 'RAFFLE_CAMPAIGN', campaign.id);
    this.persist();
  }

  private recalculateCardTotals(card: RaffleCard) {
    const paidCount = card.tickets.filter(t => t.status === 'PAGO').length;
    const soldCount = card.tickets.filter(t => t.status === 'PAGO' || t.status === 'PAGAMENTO_PENDENTE').length;

    card.paid_tickets = paidCount;
    card.sold_tickets = soldCount;
    card.amount_paid = roundCents(paidCount * 5.00);
    card.amount_pending = roundCents(Math.max(0, 50.00 - card.amount_paid));

    if (card.amount_pending === 0) {
      card.status = 'PAGA';
    } else if (card.amount_paid > 0) {
      card.status = 'PARCIAL';
    } else {
      card.status = 'PENDENTE';
    }
  }

  // --- Módulo de Bolões Oficiais (Versão de Revisão 1.1) ---
  public addBolaoGame(campaignId: string, numbers: number[]): BolaoGame {
    const campaign = this.state.bolaoCampaigns.find(c => c.id === campaignId);
    if (!campaign) throw new Error('Campanha de bolão não encontrada');

    if (campaign.games.length >= campaign.max_games_per_receipt) {
      throw new Error(`Limite oficial da CAIXA atingido: máximo de ${campaign.max_games_per_receipt} jogos por recibo.`);
    }

    const sortedNumbers = [...new Set(numbers)].sort((a, b) => a - b);
    if (sortedNumbers.length !== campaign.numbers_per_game) {
      throw new Error(`Aposta deve conter exatamente ${campaign.numbers_per_game} dezenas.`);
    }

    // Calcular custo unitário oficial da aposta
    let unitCost = 0;
    if (campaign.modality === 'MEGA_SENA') {
      const costs: Record<number, number> = { 6: 5.00, 7: 42.00, 8: 140.00, 9: 420.00, 10: 1050.00 };
      unitCost = costs[campaign.numbers_per_game] || 42.00;
    } else if (campaign.modality === 'LOTOFACIL') {
      const costs: Record<number, number> = { 15: 3.50, 16: 56.00, 17: 476.00, 18: 2856.00 };
      unitCost = costs[campaign.numbers_per_game] || 56.00;
    } else if (campaign.modality === 'QUINA') {
      const costs: Record<number, number> = { 5: 3.00, 6: 18.00, 7: 63.00, 8: 168.00 };
      unitCost = costs[campaign.numbers_per_game] || 18.00;
    }

    const newGame: BolaoGame = {
      id: `game-${campaign.modality.toLowerCase()}-${Date.now()}`,
      game_number: campaign.games.length + 1,
      numbers: sortedNumbers,
      numbers_count: campaign.numbers_per_game,
      unit_cost: unitCost,
      created_at: new Date().toISOString(),
    };

    campaign.games.push(newGame);
    this.recalculateBolaoCampaignFinancials(campaign);
    this.addAudit(
      'BOLAO_GAME_ADDED',
      `Aposta #${newGame.game_number} adicionada ao bolão ${campaign.campaign_name}: [${sortedNumbers.join(', ')}]`,
      'BOLAO_CAMPAIGN',
      campaign.id
    );
    this.persist();
    return newGame;
  }

  public removeBolaoGame(campaignId: string, gameId: string) {
    const campaign = this.state.bolaoCampaigns.find(c => c.id === campaignId);
    if (!campaign) throw new Error('Campanha não encontrada');

    campaign.games = campaign.games.filter(g => g.id !== gameId);
    // Renumerar jogos
    campaign.games.forEach((g, idx) => {
      g.game_number = idx + 1;
    });

    this.recalculateBolaoCampaignFinancials(campaign);
    this.addAudit('BOLAO_GAME_REMOVED', `Aposta removida do bolão ${campaign.campaign_name}`, 'BOLAO_CAMPAIGN', campaign.id);
    this.persist();
  }

  public updateBolaoInternalStatus(campaignId: string, status: BolaoInternalStatus, notes?: string) {
    const campaign = this.state.bolaoCampaigns.find(c => c.id === campaignId);
    if (!campaign) throw new Error('Campanha não encontrada');

    const previousStatus = campaign.internal_status;
    campaign.internal_status = status;
    campaign.updated_at = new Date().toISOString();

    this.addAudit(
      'BOLAO_STATUS_CHANGED',
      `Status do bolão ${campaign.campaign_name} alterado de ${previousStatus} para ${status}. ${notes || ''}`,
      'BOLAO_CAMPAIGN',
      campaign.id
    );
    this.persist();
  }

  public registerBolaoOfficialReceipt(
    campaignId: string,
    receiptCode: string,
    registeredAt: string,
    costOfficialBets?: number,
    externalFee: number = 0
  ) {
    const campaign = this.state.bolaoCampaigns.find(c => c.id === campaignId);
    if (!campaign) throw new Error('Campanha não encontrada');

    campaign.official_receipt_code = receiptCode;
    campaign.official_registered_at = registeredAt || new Date().toISOString();
    campaign.internal_status = 'REGISTRADO_CONFERIDO';

    if (costOfficialBets !== undefined && costOfficialBets > 0) {
      campaign.cost_official_bets = costOfficialBets;
    }
    campaign.external_fee = externalFee;

    this.recalculateBolaoCampaignFinancials(campaign);
    this.addAudit(
      'BOLAO_OFFICIAL_RECEIPT_REGISTERED',
      `Comprovante oficial CAIXA #${receiptCode} registrado para o bolão ${campaign.campaign_name}. Status: REGISTRADO_CONFERIDO`,
      'BOLAO_CAMPAIGN',
      campaign.id
    );
    this.persist();
  }

  public payBolaoParticipation(participationId: string) {
    const part = this.state.bolaoParticipations.find(p => p.id === participationId);
    if (!part) throw new Error('Participação não encontrada');

    part.amount_paid = part.total_due;
    part.amount_pending = 0;
    part.payment_status = 'BAIXADO';
    part.paid_at = new Date().toISOString();
    part.pix_reference_id = `pix-bol-${Date.now()}`;

    this.addAudit(
      'BOLAO_PARTICIPATION_PAID',
      `Participação de ${part.member_name} no bolão quitada (R$ ${part.total_due.toFixed(2)}) via Pix Oficial`,
      'BOLAO_PARTICIPATION',
      part.id
    );
    this.persist();
  }

  public simulateBolaoDraw(campaignId: string, drawnNumbers: number[], grossPrize: number) {
    const campaign = this.state.bolaoCampaigns.find(c => c.id === campaignId);
    if (!campaign) throw new Error('Campanha não encontrada');

    const roundedPrize = roundCents(grossPrize);
    campaign.drawn_numbers = [...drawnNumbers].sort((a, b) => a - b);
    campaign.draw_status = 'RESULTADO_CONFERIDO';
    campaign.prize_gross_amount = roundedPrize;

    // Seção 12: Regra diferenciada 96% para membros e 4% taxa de administração exclusiva dos bolões
    const split = calculateBolaoPrizeSplit(roundedPrize, campaign.total_valid_quotas);
    campaign.prize_member_total_amount = split.memberShareTotal;
    campaign.prize_admin_fee_amount = split.adminFeeTotal;

    // Atualizar cada participação com o rateio proporcional às suas cotas
    for (const part of this.state.bolaoParticipations.filter(p => p.campaign_id === campaignId)) {
      part.prize_share_received = roundCents(split.prizePerQuota * part.quotas_count);
    }

    this.addAudit(
      'BOLAO_DRAW_SIMULATED',
      `Resultado oficial apurado para ${campaign.campaign_name}: dezenas [${campaign.drawn_numbers.join(', ')}]. Prêmio líquido: R$ ${roundedPrize.toFixed(2)} (96% membros: R$ ${split.memberShareTotal.toFixed(2)} | 4% caixinha: R$ ${split.adminFeeTotal.toFixed(2)})`,
      'BOLAO_CAMPAIGN',
      campaign.id
    );
    this.persist();
  }

  public reopenBolaoDraw(campaignId: string) {
    const campaign = this.state.bolaoCampaigns.find(c => c.id === campaignId);
    if (!campaign) return;

    campaign.draw_status = 'AGUARDANDO_RESULTADO';
    campaign.drawn_numbers = undefined;
    campaign.prize_gross_amount = 0;
    campaign.prize_member_total_amount = 0;
    campaign.prize_admin_fee_amount = 0;

    for (const part of this.state.bolaoParticipations.filter(p => p.campaign_id === campaignId)) {
      part.prize_share_received = 0;
    }

    this.addAudit('BOLAO_DRAW_REOPENED', `Conferência do bolão ${campaign.campaign_name} reaberta para nova simulação`, 'BOLAO_CAMPAIGN', campaign.id);
    this.persist();
  }

  private recalculateBolaoCampaignFinancials(campaign: BolaoCampaign) {
    const totalOfficialBets = campaign.games.reduce((acc, g) => acc + g.unit_cost, 0);
    campaign.cost_official_bets = roundCents(totalOfficialBets);

    const pricing = calculateBolaoPricing(
      campaign.cost_official_bets,
      campaign.external_fee,
      campaign.total_valid_quotas
    );

    campaign.box_additional_fee = pricing.boxAdditionalC;
    campaign.total_budget = pricing.totalBudget;
    campaign.price_per_quota_base = pricing.pricePerQuotaBase;

    // Reconciliar centavos determinísticos entre participações da campanha
    const alloc = allocateBolaoCentsDeterministically(campaign.total_budget, campaign.total_valid_quotas);
    const campaignParts = this.state.bolaoParticipations.filter(p => p.campaign_id === campaign.id);

    let quotaCursor = 0;
    campaignParts.forEach(p => {
      let partDue = 0;
      for (let k = 0; k < p.quotas_count; k++) {
        if (quotaCursor < alloc.length) {
          partDue += alloc[quotaCursor].amount;
          quotaCursor++;
        }
      }
      p.total_due = roundCents(partDue);
      p.amount_official_share = roundCents((campaign.cost_official_bets / campaign.total_valid_quotas) * p.quotas_count);
      p.amount_box_share = roundCents((campaign.box_additional_fee / campaign.total_valid_quotas) * p.quotas_count);
      p.amount_pending = roundCents(Math.max(0, p.total_due - p.amount_paid));
    });
  }

  public resetAllToSeed() {
    localStorage.removeItem(STORAGE_KEY);
    this.state = this.loadState();
    this.notify();
  }
}

export const appStore = new AppStore();
