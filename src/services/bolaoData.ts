/**
 * FRcaixinha 2.2 - Módulo de Bolões Oficiais (Versão de Revisão 1.1 - 30/10/2026)
 * Dados iniciais das 3 campanhas especiais:
 * - Quina de São João (9 jogos de 6 dezenas)
 * - Lotofácil da Independência (3 jogos de 16 dezenas)
 * - Mega da Virada (10 jogos de 7 dezenas)
 * Transcrição fiel dos prints enviados pelo proprietário em 30/10/2026.
 */

import { BolaoCampaign, BolaoMemberParticipation, BolaoGame } from '../types';
import { allocateBolaoCentsDeterministically, calculateBolaoPricing } from './financialEngine';

// Jogos da Quina de São João (9 apostas de 6 dezenas conforme prints de 30/10/2026)
const SEED_QUINA_GAMES: BolaoGame[] = [
  {
    id: 'game-q-1',
    game_number: 1,
    numbers: [1, 8, 18, 42, 51, 62],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:00:00Z',
  },
  {
    id: 'game-q-2',
    game_number: 2,
    numbers: [4, 31, 47, 50, 69, 71],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:05:00Z',
  },
  {
    id: 'game-q-3',
    game_number: 3,
    numbers: [5, 12, 28, 39, 58, 77],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:10:00Z',
  },
  {
    id: 'game-q-4',
    game_number: 4,
    numbers: [7, 19, 33, 44, 60, 80],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:15:00Z',
  },
  {
    id: 'game-q-5',
    game_number: 5,
    numbers: [2, 16, 27, 49, 63, 75],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:20:00Z',
  },
  {
    id: 'game-q-6',
    game_number: 6,
    numbers: [10, 22, 35, 52, 66, 74],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:25:00Z',
  },
  {
    id: 'game-q-7',
    game_number: 7,
    numbers: [3, 14, 29, 41, 57, 70],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:30:00Z',
  },
  {
    id: 'game-q-8',
    game_number: 8,
    numbers: [9, 21, 38, 48, 65, 78],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:35:00Z',
  },
  {
    id: 'game-q-9',
    game_number: 9,
    numbers: [6, 17, 30, 46, 61, 79],
    numbers_count: 6,
    unit_cost: 18.00,
    created_at: '2027-01-10T10:40:00Z',
  },
];

// Jogos da Lotofácil da Independência (3 apostas de 16 dezenas conforme prints de 30/10/2026)
const SEED_LOTOFACIL_GAMES: BolaoGame[] = [
  {
    id: 'game-lot-1',
    game_number: 1,
    numbers: [1, 2, 4, 5, 7, 11, 12, 13, 15, 16, 17, 20, 21, 22, 23, 25],
    numbers_count: 16,
    unit_cost: 56.00,
    created_at: '2027-01-12T11:00:00Z',
  },
  {
    id: 'game-lot-2',
    game_number: 2,
    numbers: [1, 3, 4, 6, 8, 9, 10, 12, 14, 15, 17, 18, 19, 21, 24, 25],
    numbers_count: 16,
    unit_cost: 56.00,
    created_at: '2027-01-12T11:10:00Z',
  },
  {
    id: 'game-lot-3',
    game_number: 3,
    numbers: [2, 3, 5, 6, 7, 8, 10, 11, 13, 14, 16, 18, 19, 20, 22, 23],
    numbers_count: 16,
    unit_cost: 56.00,
    created_at: '2027-01-12T11:20:00Z',
  },
];

// Jogos da Mega da Virada (10 apostas de 7 dezenas conforme prints de 30/10/2026)
const SEED_MEGA_GAMES: BolaoGame[] = [
  {
    id: 'game-meg-1',
    game_number: 1,
    numbers: [1, 12, 31, 50, 53, 54, 55],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:00:00Z',
  },
  {
    id: 'game-meg-2',
    game_number: 2,
    numbers: [2, 15, 20, 25, 43, 47, 60],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:05:00Z',
  },
  {
    id: 'game-meg-3',
    game_number: 3,
    numbers: [4, 11, 23, 34, 42, 51, 58],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:10:00Z',
  },
  {
    id: 'game-meg-4',
    game_number: 4,
    numbers: [7, 14, 26, 38, 45, 52, 59],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:15:00Z',
  },
  {
    id: 'game-meg-5',
    game_number: 5,
    numbers: [3, 18, 22, 35, 41, 48, 56],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:20:00Z',
  },
  {
    id: 'game-meg-6',
    game_number: 6,
    numbers: [5, 16, 29, 33, 44, 49, 57],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:25:00Z',
  },
  {
    id: 'game-meg-7',
    game_number: 7,
    numbers: [8, 13, 27, 36, 40, 50, 60],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:30:00Z',
  },
  {
    id: 'game-meg-8',
    game_number: 8,
    numbers: [9, 17, 24, 37, 46, 53, 58],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:35:00Z',
  },
  {
    id: 'game-meg-9',
    game_number: 9,
    numbers: [10, 19, 28, 32, 47, 54, 59],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:40:00Z',
  },
  {
    id: 'game-meg-10',
    game_number: 10,
    numbers: [6, 21, 30, 39, 43, 51, 55],
    numbers_count: 7,
    unit_cost: 42.00,
    created_at: '2027-01-15T09:45:00Z',
  },
];

export const SEED_BOLAO_CAMPAIGNS: BolaoCampaign[] = [
  // 1. Quina de São João (Junho / 2027)
  {
    id: 'bol-quina-2027',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    campaign_name: 'Quina de São João 2027',
    modality: 'QUINA',
    special_edition: 'Concurso Especial de São João',
    contest_number: 6750,
    contest_date: '2027-06-24',
    internal_deadline: '2027-06-20',
    estimated_prize: 220000000.00, // R$ 220 Milhões
    total_valid_quotas: 25,
    numbers_per_game: 6,
    max_games_per_receipt: 10,
    games: SEED_QUINA_GAMES,
    cost_official_bets: 162.00, // 9 x R$ 18,00
    external_fee: 0.00, // Organização própria presencial = R$ 0,00
    box_additional_fee: 32.40, // 20% sobre R$ 162,00
    total_budget: 194.40,
    price_per_quota_base: 7.776, // 10 a R$ 7,77 e 15 a R$ 7,78
    internal_status: 'PRONTO_PARA_IMPRESSAO',
    draw_status: 'AGUARDANDO_RESULTADO',
    prize_gross_amount: 0,
    prize_member_share_pct: 96,
    prize_admin_fee_pct: 4,
    version: 1,
    created_at: '2027-01-10T00:00:00Z',
    updated_at: '2027-01-10T12:00:00Z',
  },

  // 2. Lotofácil da Independência (Setembro / 2027)
  {
    id: 'bol-lotofacil-2027',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    campaign_name: 'Lotofácil da Independência 2027',
    modality: 'LOTOFACIL',
    special_edition: 'Concurso Especial da Independência',
    contest_number: 3200,
    contest_date: '2027-09-10',
    internal_deadline: '2027-09-05',
    estimated_prize: 200000000.00, // R$ 200 Milhões
    total_valid_quotas: 25,
    numbers_per_game: 16,
    max_games_per_receipt: 10,
    games: SEED_LOTOFACIL_GAMES,
    cost_official_bets: 168.00, // 3 x R$ 56,00
    external_fee: 0.00,
    box_additional_fee: 33.60, // 20% sobre R$ 168,00
    total_budget: 201.60,
    price_per_quota_base: 8.064, // 16 a R$ 8,06 e 9 a R$ 8,07
    internal_status: 'RASCUNHO',
    draw_status: 'AGUARDANDO_RESULTADO',
    prize_gross_amount: 0,
    prize_member_share_pct: 96,
    prize_admin_fee_pct: 4,
    version: 1,
    created_at: '2027-01-12T00:00:00Z',
    updated_at: '2027-01-12T12:00:00Z',
  },

  // 3. Mega da Virada (Dezembro / 2027 - 31/12)
  {
    id: 'bol-mega-2027',
    tenant_id: 'tenant-inaugural',
    cycle_id: 'cycle-2027-inaugural',
    campaign_name: 'Mega da Virada 2027',
    modality: 'MEGA_SENA',
    special_edition: 'Concurso Especial de Fim de Ano',
    contest_number: 2950,
    contest_date: '2027-12-31',
    internal_deadline: '2027-12-26',
    estimated_prize: 600000000.00, // R$ 600 Milhões
    total_valid_quotas: 25,
    numbers_per_game: 7,
    max_games_per_receipt: 10,
    games: SEED_MEGA_GAMES,
    cost_official_bets: 420.00, // 10 x R$ 42,00
    external_fee: 0.00,
    box_additional_fee: 84.00, // 20% sobre R$ 420,00
    total_budget: 504.00,
    price_per_quota_base: 20.16, // Exatos R$ 20,16 por cota
    internal_status: 'RASCUNHO',
    draw_status: 'AGUARDANDO_RESULTADO',
    prize_gross_amount: 0,
    prize_member_share_pct: 96,
    prize_admin_fee_pct: 4,
    version: 1,
    created_at: '2027-01-15T00:00:00Z',
    updated_at: '2027-01-15T12:00:00Z',
  },
];

/**
 * Gera as participações das 25 cotas válidas para os membros da caixinha (Seção 3 do documento)
 * Membros com 1 cota: 15 membros
 * Membros com 2 cotas: 5 membros (ex: Maria Oliveira detém 2 cotas)
 * Total: 20 membros, 25 cotas.
 */
export function generateSeedBolaoParticipations(): BolaoMemberParticipation[] {
  const participations: BolaoMemberParticipation[] = [];

  // Alocação determinística para a Quina (R$ 194,40 em 25 cotas):
  const quinaAlloc = allocateBolaoCentsDeterministically(194.40, 25);

  // Membro 1: João Silva (1 cota - Cota #1)
  participations.push({
    id: 'part-q-joao',
    campaign_id: 'bol-quina-2027',
    membership_id: 'mem-joao',
    member_name: 'João Silva',
    quotas_count: 1,
    assigned_quota_numbers: [1],
    amount_official_share: 6.48, // 162 / 25
    amount_fee_share: 0,
    amount_box_share: 1.296, // 32.40 / 25
    total_due: quinaAlloc[0].amount, // R$ 7,77
    amount_paid: quinaAlloc[0].amount,
    amount_pending: 0,
    days_overdue: 0,
    mora_interest: 0,
    payment_status: 'BAIXADO',
    paid_at: '2027-06-15T10:00:00Z',
    pix_reference_id: 'pix-bol-joao-01',
  });

  // Membro 2: Maria Oliveira (2 cotas - Cotas #2 e #3) -> Seção 9.1: R$ 15,55 (7,77 + 7,78)
  const mariaDue = quinaAlloc[1].amount + quinaAlloc[2].amount;
  participations.push({
    id: 'part-q-maria',
    campaign_id: 'bol-quina-2027',
    membership_id: 'mem-maria',
    member_name: 'Maria Oliveira',
    quotas_count: 2,
    assigned_quota_numbers: [2, 3],
    amount_official_share: 12.96,
    amount_fee_share: 0,
    amount_box_share: 2.592,
    total_due: mariaDue, // R$ 15,55
    amount_paid: 0,
    amount_pending: mariaDue,
    days_overdue: 0,
    mora_interest: 0,
    payment_status: 'NAO_PAGO',
    paid_at: null,
  });

  // Membro 3: Pedro Santos (1 cota - Cota #4)
  participations.push({
    id: 'part-q-pedro',
    campaign_id: 'bol-quina-2027',
    membership_id: 'mem-pedro',
    member_name: 'Pedro Santos',
    quotas_count: 1,
    assigned_quota_numbers: [4],
    amount_official_share: 6.48,
    amount_fee_share: 0,
    amount_box_share: 1.296,
    total_due: quinaAlloc[3].amount,
    amount_paid: quinaAlloc[3].amount,
    amount_pending: 0,
    days_overdue: 0,
    mora_interest: 0,
    payment_status: 'BAIXADO',
    paid_at: '2027-06-18T14:00:00Z',
    pix_reference_id: 'pix-bol-pedro-01',
  });

  // Membro 4: Ana Costa (1 cota - Cota #5) -> Teste de Mora (10 dias de atraso)
  const anaDue = quinaAlloc[4].amount; // R$ 7,77
  const anaMora = Math.round(anaDue * 0.20 * (10 / 30) * 100) / 100; // R$ 0,52
  participations.push({
    id: 'part-q-ana',
    campaign_id: 'bol-quina-2027',
    membership_id: 'mem-ana',
    member_name: 'Ana Costa',
    quotas_count: 1,
    assigned_quota_numbers: [5],
    amount_official_share: 6.48,
    amount_fee_share: 0,
    amount_box_share: 1.296,
    total_due: anaDue,
    amount_paid: 0,
    amount_pending: anaDue,
    days_overdue: 10,
    mora_interest: anaMora,
    payment_status: 'VENCIDO',
    paid_at: null,
  });

  // Demais 20 cotas simuladas (Cotas 6 a 25) distribuídas entre membros do grupo
  for (let q = 5; q < 25; q++) {
    const quotaVal = quinaAlloc[q].amount;
    participations.push({
      id: `part-q-cot-${q + 1}`,
      campaign_id: 'bol-quina-2027',
      membership_id: `mem-grupo-${Math.floor(q / 2)}`,
      member_name: `Membro Participante ${q + 1}`,
      quotas_count: 1,
      assigned_quota_numbers: [q + 1],
      amount_official_share: 6.48,
      amount_fee_share: 0,
      amount_box_share: 1.296,
      total_due: quotaVal,
      amount_paid: q % 2 === 0 ? quotaVal : 0,
      amount_pending: q % 2 === 0 ? 0 : quotaVal,
      days_overdue: 0,
      mora_interest: 0,
      payment_status: q % 2 === 0 ? 'BAIXADO' : 'COBRANCA_GERADA',
      paid_at: q % 2 === 0 ? '2027-06-19T11:00:00Z' : null,
      pix_reference_id: q % 2 === 0 ? `pix-bol-grp-${q + 1}` : undefined,
    });
  }

  return participations;
}

export const SEED_BOLAO_PARTICIPATIONS = generateSeedBolaoParticipations();
