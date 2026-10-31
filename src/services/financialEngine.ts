/**
 * FRcaixinha 2.2 - Motor Financeiro e Contábil Regulatório
 * Fórmulas aprovadas: Price com 1º período irregular, Imputação Parcial em 4 etapas,
 * Capital-Dias V2 e Método dos Maiores Restos para centavos residuais.
 */

export interface PriceSimulationParams {
  principal: number; // PV
  monthlyRate: number; // Taxa decimal mensal (ex: 0.20 para 20% a.m.)
  termMonths: number; // n parcelas (1 a 12)
  disbursementDate?: Date; // Data da efetiva liberação Pix
  cycleYear?: number; // Ano do ciclo atual (ex: 2027)
  useIrregularFirstPeriod?: boolean; // Se false (padrão): períodos mensais completos sem juros proporcionais
}

export interface InstallmentSimulation {
  sequence: number;
  dueDate: string;
  isFirstPeriod: boolean;
  periodDays: number;
  periodRate: number;
  payment: number;
  principalDue: number;
  interestDue: number;
  remainingBalance: number;
}

export interface PriceSimulationResult {
  principal: number;
  monthlyRate: number;
  termMonths: number;
  disbursementDate: string;
  firstDueDate: string;
  firstPeriodDays: number;
  firstPeriodRate: number;
  uniformPayment: number;
  lastPayment: number;
  totalInterest: number;
  totalPayment: number;
  isValidCycle: boolean;
  validationError?: string;
  useIrregularFirstPeriod: boolean;
  installments: InstallmentSimulation[];
}

/** Arredondamento monetário bancário ROUND_HALF_UP para centavos */
export function roundCents(amount: number): number {
  return Math.round((amount + Number.EPSILON) * 100) / 100;
}

/** Formata valor em BRL */
export function formatBRL(amount: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(amount);
}

/** Formata data padrão dd/mm/aaaa */
export function formatDateBR(dateStrOrObj: string | Date): string {
  if (!dateStrOrObj) return '-';
  const d = typeof dateStrOrObj === 'string' ? new Date(dateStrOrObj) : dateStrOrObj;
  if (isNaN(d.getTime())) return '-';
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

/**
 * Simulação Price oficial (sem taxa adicional de qualquer natureza).
 * - Padrão solicitado: Períodos mensais completos, sem juros proporcionais de primeiro período irregular.
 *   Fórmula clássica: PMT = PV * (i / (1 - (1 + i)^(-n)))
 *   Juros calculados a cada mês sobre o saldo devedor restante (i * Saldo Devedor).
 *   Amortização = PMT - Juros.
 *   Última parcela ajustada para zerar o saldo devedor por centavos.
 * - Suporta opcionalmente useIrregularFirstPeriod = true para cenários de auditoria específica.
 */
export function calculatePriceSimulation(params: PriceSimulationParams): PriceSimulationResult {
  const {
    principal,
    monthlyRate,
    termMonths,
    disbursementDate = new Date(),
    cycleYear = 2027,
    useIrregularFirstPeriod = false,
  } = params;

  const disb = new Date(disbursementDate);
  const firstDue = new Date(disb.getFullYear(), disb.getMonth() + 1, 10);

  // Calcular dias corridos entre desembolso e primeiro vencimento
  const diffMs = firstDue.getTime() - disb.getTime();
  const firstPeriodDays = Math.max(1, Math.round(diffMs / (1000 * 60 * 60 * 24)));
  const firstPeriodRate = useIrregularFirstPeriod ? monthlyRate * (firstPeriodDays / 30) : monthlyRate;

  // Validar se todas as parcelas cabem no ciclo financeiro anual (até 31/12)
  const lastDueDate = new Date(firstDue.getFullYear(), firstDue.getMonth() + (termMonths - 1), 10);
  const cycleEnd = new Date(cycleYear, 11, 31, 23, 59, 59);

  let isValidCycle = true;
  let validationError: string | undefined;

  if (lastDueDate > cycleEnd) {
    isValidCycle = false;
    validationError = `A última parcela venceria em ${formatDateBR(lastDueDate)}, ultrapassando o término do ciclo anual em 31/12/${cycleYear}. Reduza o prazo para caber no ciclo.`;
  }

  let uniformPayment: number;

  if (useIrregularFirstPeriod) {
    // Fatores de desconto com primeiro período irregular
    let sumDiscount = 0;
    let currentProd = 1;
    for (let j = 1; j <= termMonths; j++) {
      const rateForPeriod = j === 1 ? firstPeriodRate : monthlyRate;
      currentProd *= (1 + rateForPeriod);
      sumDiscount += 1 / currentProd;
    }
    const exactPMT = monthlyRate === 0 ? principal / termMonths : principal / sumDiscount;
    uniformPayment = roundCents(exactPMT);
  } else {
    // Tabela Price padrão para períodos mensais completos: PMT = PV * (i / (1 - (1 + i)^(-n)))
    if (monthlyRate === 0) {
      uniformPayment = roundCents(principal / termMonths);
    } else {
      const discountFactor = 1 - Math.pow(1 + monthlyRate, -termMonths);
      const exactPMT = principal * (monthlyRate / discountFactor);
      uniformPayment = roundCents(exactPMT);
    }
  }

  // Cronograma de amortização
  const installments: InstallmentSimulation[] = [];
  let remainingBalance = principal;
  let totalInterest = 0;
  let totalPayment = 0;

  for (let k = 1; k <= termMonths; k++) {
    const rateForPeriod = (k === 1 && useIrregularFirstPeriod) ? firstPeriodRate : monthlyRate;
    const dueDate = new Date(firstDue.getFullYear(), firstDue.getMonth() + (k - 1), 10);
    const dueDateStr = dueDate.toISOString().split('T')[0];

    const interestDue = roundCents(remainingBalance * rateForPeriod);
    let principalDue = 0;
    let payment = uniformPayment;

    if (k === termMonths) {
      // Ajuste final na última parcela para zerar centavos
      principalDue = roundCents(remainingBalance);
      payment = roundCents(principalDue + interestDue);
      remainingBalance = 0;
    } else {
      principalDue = roundCents(uniformPayment - interestDue);
      remainingBalance = roundCents(remainingBalance - principalDue);
    }

    totalInterest = roundCents(totalInterest + interestDue);
    totalPayment = roundCents(totalPayment + payment);

    installments.push({
      sequence: k,
      dueDate: dueDateStr,
      isFirstPeriod: k === 1 && useIrregularFirstPeriod,
      periodDays: (k === 1 && useIrregularFirstPeriod) ? firstPeriodDays : 30,
      periodRate: rateForPeriod,
      payment,
      principalDue,
      interestDue,
      remainingBalance,
    });
  }

  return {
    principal,
    monthlyRate,
    termMonths,
    disbursementDate: disb.toISOString().split('T')[0],
    firstDueDate: firstDue.toISOString().split('T')[0],
    firstPeriodDays,
    firstPeriodRate,
    uniformPayment,
    lastPayment: installments[installments.length - 1]?.payment || uniformPayment,
    totalInterest,
    totalPayment,
    isValidCycle,
    validationError,
    useIrregularFirstPeriod,
    installments,
  };
}

/**
 * Cláusula 8.6 e 16.2: Ordem obrigatória para pagamentos parciais confirmados e conciliados.
 * Dentro da parcela vencida mais antiga:
 * (1) juros remuneratórios vencidos (paid_interest)
 * (2) mora simples acumulada (paid_mora)
 * (3) multa única exigível de R$ 10 (paid_fine)
 * (4) principal vencido (paid_principal)
 * Retorna os componentes pagos e o saldo restante.
 */
export interface ImputationInput {
  paymentAmount: number;
  interestDue: number;
  moraDue: number;
  fineDue: number;
  principalDue: number;
}

export interface ImputationOutput {
  paidInterest: number;
  paidMora: number;
  paidFine: number;
  paidPrincipal: number;
  remainingOverpaid: number;
  unpaidInterest: number;
  unpaidMora: number;
  unpaidFine: number;
  unpaidPrincipal: number;
  isFullySettled: boolean;
}

export function calculateImputationHierarchy(input: ImputationInput): ImputationOutput {
  let available = roundCents(input.paymentAmount);

  // 1. Juros remuneratórios
  const paidInterest = Math.min(available, input.interestDue);
  available = roundCents(available - paidInterest);

  // 2. Mora simples acumulada
  const paidMora = Math.min(available, input.moraDue);
  available = roundCents(available - paidMora);

  // 3. Multa única
  const paidFine = Math.min(available, input.fineDue);
  available = roundCents(available - paidFine);

  // 4. Principal vencido
  const paidPrincipal = Math.min(available, input.principalDue);
  available = roundCents(available - paidPrincipal);

  const unpaidInterest = roundCents(input.interestDue - paidInterest);
  const unpaidMora = roundCents(input.moraDue - paidMora);
  const unpaidFine = roundCents(input.fineDue - paidFine);
  const unpaidPrincipal = roundCents(input.principalDue - paidPrincipal);

  const isFullySettled = unpaidInterest === 0 && unpaidMora === 0 && unpaidFine === 0 && unpaidPrincipal === 0;

  return {
    paidInterest,
    paidMora,
    paidFine,
    paidPrincipal,
    remainingOverpaid: available,
    unpaidInterest,
    unpaidMora,
    unpaidFine,
    unpaidPrincipal,
    isFullySettled,
  };
}

/**
 * Cláusula 10.3, 10.4 e 16.2: Rateio Capital-Dias V2 e Método dos Maiores Restos (Hamilton/Hare-Niemeyer).
 * W_i = sum_d(C_{i,d} * E_{i,d})
 * R_i_exact = member_pool * (W_i / sum(W))
 * Trunca ao centavo e distribui os centavos residuais aos maiores restos com desempate por membership_id.
 */
export interface MemberCapitalDiasInput {
  membershipId: string;
  memberName: string;
  isProfitEligible: boolean; // E_i (0 se 3 meses inadimplente na caixinha do proprietário)
  totalCapitalConfirmed: number;
  capitalDiasWeight: number; // W_i somado ao longo do ano
}

export interface MemberDistributionOutput {
  membershipId: string;
  memberName: string;
  isEligible: boolean;
  capitalDiasWeight: number;
  weightPercentage: number;
  exactShare: number;
  truncatedShare: number;
  remainderFraction: number;
  bonusCentavos: number;
  finalProfitShare: number;
}

export interface CycleClosingCalculationResult {
  totalNetProfitRealized: number;
  adminPct: number;
  memberPct: number;
  adminPool: number;
  memberPool: number;
  totalWeights: number;
  sumTruncatedShares: number;
  residualCentavosToDistribute: number;
  memberDistributions: MemberDistributionOutput[];
}

export function calculateCycleClosingSettlement(
  netProfitRealized: number,
  adminPct: number,
  memberPct: number,
  members: MemberCapitalDiasInput[]
): CycleClosingCalculationResult {
  const profit = Math.max(0, roundCents(netProfitRealized));
  const adminPool = roundCents(profit * (adminPct / 100));
  const memberPool = roundCents(profit * (memberPct / 100));

  // Filtrar apenas elegíveis com peso > 0
  const eligibleMembers = members.filter(m => m.isProfitEligible && m.capitalDiasWeight > 0);
  const totalWeights = eligibleMembers.reduce((acc, m) => acc + m.capitalDiasWeight, 0);

  if (totalWeights === 0 || memberPool === 0) {
    const rawOutputs: MemberDistributionOutput[] = members.map(m => ({
      membershipId: m.membershipId,
      memberName: m.memberName,
      isEligible: m.isProfitEligible,
      capitalDiasWeight: m.capitalDiasWeight,
      weightPercentage: 0,
      exactShare: 0,
      truncatedShare: 0,
      remainderFraction: 0,
      bonusCentavos: 0,
      finalProfitShare: 0,
    }));

    return {
      totalNetProfitRealized: profit,
      adminPct,
      memberPct,
      adminPool,
      memberPool,
      totalWeights: 0,
      sumTruncatedShares: 0,
      residualCentavosToDistribute: 0,
      memberDistributions: rawOutputs,
    };
  }

  // 1. Calcular quotas exatas e truncadas
  const distributions: MemberDistributionOutput[] = members.map(m => {
    if (!m.isProfitEligible || m.capitalDiasWeight <= 0) {
      return {
        membershipId: m.membershipId,
        memberName: m.memberName,
        isEligible: m.isProfitEligible,
        capitalDiasWeight: m.capitalDiasWeight,
        weightPercentage: 0,
        exactShare: 0,
        truncatedShare: 0,
        remainderFraction: 0,
        bonusCentavos: 0,
        finalProfitShare: 0,
      };
    }

    const weightPercentage = (m.capitalDiasWeight / totalWeights) * 100;
    const exactShare = memberPool * (m.capitalDiasWeight / totalWeights);
    // Truncar para 2 casas decimais (centavos exatos)
    const truncatedShare = Math.floor(exactShare * 100) / 100;
    const remainderFraction = exactShare - truncatedShare;

    return {
      membershipId: m.membershipId,
      memberName: m.memberName,
      isEligible: true,
      capitalDiasWeight: m.capitalDiasWeight,
      weightPercentage: roundCents(weightPercentage),
      exactShare,
      truncatedShare,
      remainderFraction,
      bonusCentavos: 0,
      finalProfitShare: truncatedShare,
    };
  });

  // 2. Somar parcelas truncadas
  const sumTruncated = roundCents(
    distributions.reduce((acc, d) => acc + d.truncatedShare, 0)
  );

  // 3. Determinar os centavos residuais
  let residualCents = Math.round((memberPool - sumTruncated) * 100);

  // 4. Ordenar elegíveis pelo Método dos Maiores Restos (Hare-Niemeyer)
  // Critério de desempate contratual: membership_id em ordem ascendente (Cláusula 10.4)
  const sortedEligible = [...distributions]
    .filter(d => d.isEligible && d.capitalDiasWeight > 0)
    .sort((a, b) => {
      if (Math.abs(b.remainderFraction - a.remainderFraction) > 0.0000001) {
        return b.remainderFraction - a.remainderFraction; // Maior resto primeiro
      }
      return a.membershipId.localeCompare(b.membershipId); // Desempate determinístico
    });

  // Atribuir 1 centavo por vez aos maiores restos até esgotar a diferença
  let idx = 0;
  while (residualCents > 0 && idx < sortedEligible.length) {
    const target = distributions.find(d => d.membershipId === sortedEligible[idx].membershipId);
    if (target) {
      target.bonusCentavos += 0.01;
      target.finalProfitShare = roundCents(target.finalProfitShare + 0.01);
      residualCents--;
    }
    idx++;
  }

  return {
    totalNetProfitRealized: profit,
    adminPct,
    memberPct,
    adminPool,
    memberPool,
    totalWeights,
    sumTruncatedShares: sumTruncated,
    residualCentavosToDistribute: Math.round((memberPool - sumTruncated) * 100),
    memberDistributions: distributions,
  };
}

/**
 * Cláusula 3.10: Upgrade de licença proporcional.
 * max(0, novo_preco - antigo_preco) * segundos_restantes / segundos_totais
 */
export function calculateLicenseUpgradeProRata(
  oldMonthlyPrice: number,
  newMonthlyPrice: number,
  startsAt: Date,
  endsAt: Date,
  currentDate: Date = new Date()
): { priceDifference: number; proRataAmount: number; daysRemaining: number; totalDays: number } {
  const priceDifference = Math.max(0, roundCents(newMonthlyPrice - oldMonthlyPrice));
  const totalMs = endsAt.getTime() - startsAt.getTime();
  const remainingMs = Math.max(0, endsAt.getTime() - currentDate.getTime());

  const totalDays = Math.max(1, Math.round(totalMs / (1000 * 60 * 60 * 24)));
  const daysRemaining = Math.max(0, Math.round(remainingMs / (1000 * 60 * 60 * 24)));

  const ratio = Math.min(1, Math.max(0, remainingMs / totalMs));
  const proRataAmount = roundCents(priceDifference * ratio);

  return {
    priceDifference,
    proRataAmount,
    daysRemaining,
    totalDays,
  };
}

/**
 * MÓDULO DE RIFAS - FRCAIXINHA 2.2
 * Seção 9: Regra de inadimplência com mora simples de 20% ao mês proporcional aos dias de atraso.
 * - Vencimento: dia 20. Início do atraso: dia 21.
 * - Taxa mensal: 20% (0.20). Mês financeiro: 30 dias.
 * - Taxa diária: 20% / 30 = 0.666666...%
 * - Base de cálculo: somente o principal não quitado (sem juros sobre juros).
 * Fórmula: Juros = Valor pendente × 0,20 × (dias de atraso ÷ 30)
 * Total atualizado = Valor pendente + Juros
 */
export function calculateRaffleMoraInterest(pendingAmount: number, daysOverdue: number): {
  pendingPrincipal: number;
  daysOverdue: number;
  monthlyRate: number;
  dailyRate: number;
  moraInterest: number;
  totalUpdated: number;
  interestAmount: number;
  totalWithInterest: number;
} {
  const principal = Math.max(0, roundCents(pendingAmount));
  const days = Math.max(0, Math.floor(daysOverdue));

  if (principal === 0 || days === 0) {
    return {
      pendingPrincipal: principal,
      daysOverdue: days,
      monthlyRate: 0.20,
      dailyRate: 0.20 / 30,
      moraInterest: 0,
      totalUpdated: principal,
      interestAmount: 0,
      totalWithInterest: principal,
    };
  }

  // Juros = Valor pendente × 0,20 × (dias de atraso ÷ 30)
  const rawInterest = principal * 0.20 * (days / 30);
  const moraInterest = roundCents(rawInterest);
  const totalUpdated = roundCents(principal + moraInterest);

  return {
    pendingPrincipal: principal,
    daysOverdue: days,
    monthlyRate: 0.20,
    dailyRate: 0.20 / 30,
    moraInterest,
    totalUpdated,
    interestAmount: moraInterest,
    totalWithInterest: totalUpdated,
  };
}

/**
 * Seção 3 e 5: Arrecadação variável e resultado financeiro por campanha
 */
export function calculateRaffleCampaignFinancials(
  activeQuotas: number,
  prizeAmount: number = 200.00,
  otherExpenses: number = 0
): {
  activeQuotas: number;
  totalTickets: number;
  expectedRevenue: number;
  prizeAmount: number;
  otherExpenses: number;
  netBalanceBeforeExpenses: number;
  netResult: number;
  netBalance: number;
  isPrizeHigherThanRevenue: boolean;
} {
  const quotas = Math.max(0, activeQuotas);
  const totalTickets = quotas * 10;
  const expectedRevenue = roundCents(quotas * 50.00);
  const prize = roundCents(prizeAmount);
  const expenses = roundCents(otherExpenses);
  const netBalanceBeforeExpenses = roundCents(expectedRevenue - prize);
  const netResult = roundCents(expectedRevenue - prize - expenses);
  const isPrizeHigherThanRevenue = prize > expectedRevenue;

  return {
    activeQuotas: quotas,
    totalTickets,
    expectedRevenue,
    prizeAmount: prize,
    otherExpenses: expenses,
    netBalanceBeforeExpenses,
    netResult,
    netBalance: netResult,
    isPrizeHigherThanRevenue,
  };
}

/**
 * Seção 14: Projeção Anual de 3 Campanhas de Rifas (Março, Junho, Setembro)
 */
export function calculateRaffleAnnualFinancials(
  activeQuotas: number = 20,
  prizePerCampaign: number = 200.00,
  memberPct: number = 85,
  adminPct: number = 15
): {
  campaignsCount: number;
  activeQuotas: number;
  annualObligationPerQuota: number;
  totalAnnualRevenue: number;
  totalAnnualPrizes: number;
  annualNetResult: number;
  membersShare: number;
  adminShare: number;
  totalExpectedRevenue: number;
  totalPrizeAmount: number;
  netBalance: number;
  memberShareAmount: number;
  adminShareAmount: number;
} {
  const campaignsCount = 3;
  const annualObligationPerQuota = roundCents(campaignsCount * 50.00); // R$ 150,00
  const totalAnnualRevenue = roundCents(activeQuotas * annualObligationPerQuota); // 20 cotas = R$ 3.000,00
  const totalAnnualPrizes = roundCents(campaignsCount * prizePerCampaign); // 3 * R$ 200 = R$ 600,00
  const annualNetResult = roundCents(totalAnnualRevenue - totalAnnualPrizes); // R$ 2.400,00

  const membersShare = roundCents(annualNetResult * (memberPct / 100)); // R$ 2.040,00
  const adminShare = roundCents(annualNetResult * (adminPct / 100)); // R$ 360,00

  return {
    campaignsCount,
    activeQuotas,
    annualObligationPerQuota,
    totalAnnualRevenue,
    totalAnnualPrizes,
    annualNetResult,
    membersShare,
    adminShare,
    totalExpectedRevenue: totalAnnualRevenue,
    totalPrizeAmount: totalAnnualPrizes,
    netBalance: annualNetResult,
    memberShareAmount: membersShare,
    adminShareAmount: adminShare,
  };
}

// ==========================================
// Fórmulas Financeiras - Bolões Oficiais (Versão 1.1)
// ==========================================

export interface BolaoPricingOutput {
  costOfficialA: number; // A: apostas oficiais
  externalFeeB: number; // B: tarifa externa
  acquisitionCost: number; // A + B
  boxAdditionalC: number; // C: 20% sobre (A + B)
  totalBudget: number; // A + B + C
  pricePerQuotaBase: number;
}

export function calculateBolaoPricing(
  costOfficialA: number,
  externalFeeB: number = 0,
  quotasCount: number = 25
): BolaoPricingOutput {
  const A = Math.max(0, roundCents(costOfficialA));
  const B = Math.max(0, roundCents(externalFeeB));
  const acquisition = roundCents(A + B);
  const C = roundCents(acquisition * 0.20);
  const total = roundCents(acquisition + C);
  const basePerQuota = quotasCount > 0 ? total / quotasCount : 0;

  return {
    costOfficialA: A,
    externalFeeB: B,
    acquisitionCost: acquisition,
    boxAdditionalC: C,
    totalBudget: total,
    pricePerQuotaBase: basePerQuota,
  };
}

/**
 * Seção 8.2: Critério determinístico auditável de centavos por cota.
 * Distribui a diferença de centavos entre as cotas para que a soma seja exata.
 * Exemplo Quina (R$ 194,40 em 25 cotas): 10 cotas a R$ 7,77 e 15 cotas a R$ 7,78.
 */
export function allocateBolaoCentsDeterministically(
  totalAmount: number,
  quotasCount: number
): { quotaIndex: number; quotaNumber: number; amount: number }[] {
  if (quotasCount <= 0) return [];
  const totalCents = Math.round(totalAmount * 100);
  const baseCents = Math.floor(totalCents / quotasCount);
  const remainderCents = totalCents - baseCents * quotasCount;

  const result: { quotaIndex: number; quotaNumber: number; amount: number }[] = [];
  for (let i = 0; i < quotasCount; i++) {
    // As últimas 'remainderCents' cotas recebem +1 centavo
    const extraCent = i >= (quotasCount - remainderCents) ? 1 : 0;
    const quotaAmount = (baseCents + extraCent) / 100;
    result.push({
      quotaIndex: i,
      quotaNumber: i + 1,
      amount: roundCents(quotaAmount),
    });
  }
  return result;
}

/**
 * Seção 12: Rateio Diferenciado de Prêmios para Bolões Oficiais
 * 96% para o lucro da caixinha (distribuído aos titulares das cotas oficiais)
 * 4% para a taxa de administração da caixinha
 * Política exclusiva do bolão oficial
 */
export function calculateBolaoPrizeSplit(
  grossPrizeAmount: number,
  totalQuotas: number = 25
): {
  grossPrize: number;
  memberSharePct: number;
  adminFeePct: number;
  memberShareTotal: number;
  adminFeeTotal: number;
  prizePerQuota: number;
} {
  const gross = Math.max(0, roundCents(grossPrizeAmount));
  const memberSharePct = 96;
  const adminFeePct = 4;

  const memberShareTotal = roundCents(gross * 0.96);
  const adminFeeTotal = roundCents(gross * 0.04);
  const prizePerQuota = totalQuotas > 0 ? roundCents(memberShareTotal / totalQuotas) : 0;

  return {
    grossPrize: gross,
    memberSharePct,
    adminFeePct,
    memberShareTotal,
    adminFeeTotal,
    prizePerQuota,
  };
}

/**
 * Seção 11: Mora simples de 20% ao mês pró-rata dia
 * Juros = Principal pendente × 0,20 × (dias de atraso ÷ 30)
 */
export function calculateBolaoMora(
  pendingPrincipal: number,
  daysOverdue: number
): {
  pendingPrincipal: number;
  daysOverdue: number;
  moraInterest: number;
  totalWithMora: number;
} {
  const principal = Math.max(0, roundCents(pendingPrincipal));
  const days = Math.max(0, Math.floor(daysOverdue));

  if (principal === 0 || days === 0) {
    return {
      pendingPrincipal: principal,
      daysOverdue: days,
      moraInterest: 0,
      totalWithMora: principal,
    };
  }

  const rawMora = principal * 0.20 * (days / 30);
  const moraInterest = roundCents(rawMora);
  const totalWithMora = roundCents(principal + moraInterest);

  return {
    pendingPrincipal: principal,
    daysOverdue: days,
    moraInterest,
    totalWithMora,
  };
}

