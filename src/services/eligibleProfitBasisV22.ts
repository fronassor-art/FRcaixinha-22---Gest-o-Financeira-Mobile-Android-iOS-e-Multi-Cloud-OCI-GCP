import {
  calculateCapitalDaysV22,
  CapitalDaysV22Error,
  type CapitalDaysInputV22,
  type CapitalDaysResultV22,
} from "./capitalDaysV22";
import {
  civilDateDayNumberV22,
  CycleWindowV22Error,
  validateCycleWindowV22,
  type ExplicitCycleWindowAcceptanceV22,
} from "./cycleWindowV22";

export type ProfitBasisLineKindV22 =
  | "REALIZED_REVENUE"
  | "RECOGNIZED_EXPENSE"
  | "REALIZED_LOSS"
  | "AUTHORIZED_ADJUSTMENT_CREDIT"
  | "AUTHORIZED_ADJUSTMENT_DEBIT"
  | "CAPITAL_PRINCIPAL"
  | "LOAN_PRINCIPAL"
  | "UNPAID_RECEIVABLE"
  | "FUTURE_INTEREST"
  | "EXTERNAL_LOTTERY_AWARD";

export type ProfitBasisLineStatusV22 = "CONFIRMED" | "PENDING" | "REVERSED";

export interface ProfitBasisLineV22 {
  tenantId: string;
  cycleId: string;
  lineId: string;
  kind: ProfitBasisLineKindV22;
  status: ProfitBasisLineStatusV22;
  currency: "BRL";
  amountCents: number;
  competenceDate: string;
  recognizedDate: string | null;
  financialDate: string | null;
  reconciled: boolean;
  policyAccepted: boolean;
  evidenceRef: string | null;
  authorizationRef: string | null;
}

export interface EligibleProfitBasisInputV22 {
  scope: {tenantId: string; cycleId: string};
  cycleStart: string;
  cycleEndExclusive: string;
  cycleWindowAcceptance?: ExplicitCycleWindowAcceptanceV22;
  lines: ProfitBasisLineV22[];
}

export interface EligibleProfitBasisLineResultV22 {
  lineId: string;
  kind: ProfitBasisLineKindV22;
  status: ProfitBasisLineStatusV22;
  competenceDate: string;
  recognizedDate: string | null;
  financialDate: string | null;
  included: boolean;
  reason: string;
  signedImpactCents: string;
}

export interface EligibleProfitBasisResultV22 {
  basis: "REALIZED_NET_PROFIT_SOURCE_ONLY";
  scope: {tenantId: string; cycleId: string};
  cycleStart: string;
  cycleEndExclusive: string;
  currency: "BRL";
  realizedRevenueCents: string;
  recognizedExpenseCents: string;
  realizedLossCents: string;
  adjustmentCreditCents: string;
  adjustmentDebitCents: string;
  rawNetResultCents: string;
  distributableNetProfitCents: string;
  lines: EligibleProfitBasisLineResultV22[];
}

export class EligibleProfitBasisV22Error extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "EligibleProfitBasisV22Error";
  }
}

const MAX_SAFE = BigInt(Number.MAX_SAFE_INTEGER);

function fail(code: string): never {
  throw new EligibleProfitBasisV22Error(code);
}

function dayNumber(value: string): number {
  try {
    return civilDateDayNumberV22(value);
  } catch (error) {
    if (error instanceof CycleWindowV22Error) return fail(error.code);
    return fail("INVALID_DATE");
  }
}

function validId(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 128
    && value === value.trim();
}

function validReference(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 512
    && value === value.trim();
}

function compareId(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function cycleWindow(input: EligibleProfitBasisInputV22): {start: number; end: number} {
  try {
    return validateCycleWindowV22(
      input.scope, input.cycleStart, input.cycleEndExclusive, input.cycleWindowAcceptance,
    );
  } catch (error) {
    if (error instanceof CycleWindowV22Error) return fail(error.code);
    return fail("INVALID_CYCLE_WINDOW");
  }
}

function inCycle(value: string, start: string, endExclusive: string): boolean {
  return value >= start && value < endExclusive;
}

function excluded(
  line: ProfitBasisLineV22,
  reason: string,
): EligibleProfitBasisLineResultV22 {
  return {
    lineId: line.lineId,
    kind: line.kind,
    status: line.status,
    competenceDate: line.competenceDate,
    recognizedDate: line.recognizedDate,
    financialDate: line.financialDate,
    included: false,
    reason,
    signedImpactCents: "0",
  };
}

/**
 * Computes a source-only eligible net-profit preview from explicit, scoped lines.
 * All attestations/references are caller-supplied data and must be authenticated
 * and authorized by a separate server-side ledger before any operational use.
 */
export function calculateEligibleProfitBasisV22(
  input: EligibleProfitBasisInputV22,
): EligibleProfitBasisResultV22 {
  if (input === null || typeof input !== "object" || !Array.isArray(input.lines)) {
    return fail("INVALID_INPUT");
  }
  if (!input.scope || !validId(input.scope.tenantId) || !validId(input.scope.cycleId)) {
    return fail("INVALID_SCOPE");
  }
  const {start, end} = cycleWindow(input);
  const lineIds = new Set<string>();
  const results: EligibleProfitBasisLineResultV22[] = [];
  let revenue = 0n;
  let expenses = 0n;
  let losses = 0n;
  let adjustmentCredits = 0n;
  let adjustmentDebits = 0n;

  for (const line of input.lines) {
    if (line !== null && typeof line === "object"
        && (line.tenantId !== input.scope.tenantId || line.cycleId !== input.scope.cycleId)) {
      return fail("LINE_SCOPE_MISMATCH");
    }
    if (line === null || typeof line !== "object"
        || !validId(line.lineId) || lineIds.has(line.lineId)
        || !["REALIZED_REVENUE", "RECOGNIZED_EXPENSE", "REALIZED_LOSS",
          "AUTHORIZED_ADJUSTMENT_CREDIT", "AUTHORIZED_ADJUSTMENT_DEBIT",
          "CAPITAL_PRINCIPAL", "LOAN_PRINCIPAL", "UNPAID_RECEIVABLE",
          "FUTURE_INTEREST", "EXTERNAL_LOTTERY_AWARD"].includes(line.kind)
        || (line.status !== "CONFIRMED" && line.status !== "PENDING" && line.status !== "REVERSED")
        || line.currency !== "BRL"
        || !Number.isSafeInteger(line.amountCents) || line.amountCents <= 0
        || typeof line.reconciled !== "boolean" || typeof line.policyAccepted !== "boolean"
        || (line.evidenceRef !== null && !validReference(line.evidenceRef))
        || (line.authorizationRef !== null && !validReference(line.authorizationRef))) {
      return fail("INVALID_PROFIT_BASIS_LINE");
    }
    lineIds.add(line.lineId);
    dayNumber(line.competenceDate);
    if (line.recognizedDate !== null) dayNumber(line.recognizedDate);
    if (line.financialDate !== null) dayNumber(line.financialDate);
    const amount = BigInt(line.amountCents);

    if (line.kind === "CAPITAL_PRINCIPAL" || line.kind === "LOAN_PRINCIPAL"
        || line.kind === "UNPAID_RECEIVABLE" || line.kind === "FUTURE_INTEREST"
        || line.kind === "EXTERNAL_LOTTERY_AWARD") {
      results.push(excluded(line, "EXCLUDED_BY_PROFIT_BASIS_RULE"));
      continue;
    }
    if (line.status !== "CONFIRMED") {
      results.push(excluded(line, "LINE_NOT_CONFIRMED"));
      continue;
    }
    if (!inCycle(line.competenceDate, input.cycleStart, input.cycleEndExclusive)) {
      results.push(excluded(line, "COMPETENCE_OUTSIDE_CYCLE"));
      continue;
    }

    let signed = 0n;
    let reason = "INCLUDED";
    switch (line.kind) {
      case "REALIZED_REVENUE":
        if (line.financialDate === null) reason = "MISSING_FINANCIAL_CONFIRMATION_DATE";
        else if (!inCycle(line.financialDate, input.cycleStart, input.cycleEndExclusive)) reason = "FINANCIAL_DATE_OUTSIDE_CYCLE";
        else if (!line.reconciled) reason = "REVENUE_NOT_RECONCILED";
        else if (!validReference(line.evidenceRef)) reason = "MISSING_EVIDENCE";
        else signed = amount;
        break;
      case "RECOGNIZED_EXPENSE":
      case "REALIZED_LOSS":
        if (line.recognizedDate === null) reason = "MISSING_RECOGNITION_DATE";
        else if (!inCycle(line.recognizedDate, input.cycleStart, input.cycleEndExclusive)) reason = "RECOGNITION_DATE_OUTSIDE_CYCLE";
        else if (!line.policyAccepted) reason = "POLICY_NOT_ACCEPTED";
        else if (!validReference(line.evidenceRef)) reason = "MISSING_EVIDENCE";
        else signed = -amount;
        break;
      case "AUTHORIZED_ADJUSTMENT_CREDIT":
      case "AUTHORIZED_ADJUSTMENT_DEBIT":
        if (line.recognizedDate === null) reason = "MISSING_RECOGNITION_DATE";
        else if (!inCycle(line.recognizedDate, input.cycleStart, input.cycleEndExclusive)) reason = "RECOGNITION_DATE_OUTSIDE_CYCLE";
        else if (!line.policyAccepted) reason = "POLICY_NOT_ACCEPTED";
        else if (!validReference(line.evidenceRef)) reason = "MISSING_EVIDENCE";
        else if (!validReference(line.authorizationRef)) reason = "MISSING_ADJUSTMENT_AUTHORIZATION";
        else signed = line.kind === "AUTHORIZED_ADJUSTMENT_CREDIT" ? amount : -amount;
        break;
    }

    if (signed === 0n) {
      results.push(excluded(line, reason));
      continue;
    }
    if (line.kind === "REALIZED_REVENUE") revenue += signed;
    else if (line.kind === "RECOGNIZED_EXPENSE") expenses += amount;
    else if (line.kind === "REALIZED_LOSS") losses += amount;
    else if (line.kind === "AUTHORIZED_ADJUSTMENT_CREDIT") adjustmentCredits += amount;
    else if (line.kind === "AUTHORIZED_ADJUSTMENT_DEBIT") adjustmentDebits += amount;
    results.push({
      lineId: line.lineId,
      kind: line.kind,
      status: line.status,
      competenceDate: line.competenceDate,
      recognizedDate: line.recognizedDate,
      financialDate: line.financialDate,
      included: true,
      reason,
      signedImpactCents: signed.toString(),
    });
  }

  results.sort((a, b) => compareId(a.lineId, b.lineId));
  const raw = revenue - expenses - losses + adjustmentCredits - adjustmentDebits;
  const distributable = raw > 0n ? raw : 0n;
  return {
    basis: "REALIZED_NET_PROFIT_SOURCE_ONLY",
    scope: {...input.scope},
    cycleStart: input.cycleStart,
    cycleEndExclusive: input.cycleEndExclusive,
    currency: "BRL",
    realizedRevenueCents: revenue.toString(),
    recognizedExpenseCents: expenses.toString(),
    realizedLossCents: losses.toString(),
    adjustmentCreditCents: adjustmentCredits.toString(),
    adjustmentDebitCents: adjustmentDebits.toString(),
    rawNetResultCents: raw.toString(),
    distributableNetProfitCents: distributable.toString(),
    lines: results,
  };
}

export type CapitalDaysFromProfitBasisInputV22 =
  Omit<CapitalDaysInputV22, "netProfitCents"> & {profitLines: ProfitBasisLineV22[]};

export interface CapitalDaysWithProfitBasisResultV22 {
  profitBasis: EligibleProfitBasisResultV22;
  capitalDays: CapitalDaysResultV22;
}

export function calculateCapitalDaysFromProfitBasisV22(
  input: CapitalDaysFromProfitBasisInputV22,
): CapitalDaysWithProfitBasisResultV22 {
  const {profitLines, ...calculation} = input;
  const profitBasis = calculateEligibleProfitBasisV22({
    scope: input.scope,
    cycleStart: input.cycleStart,
    cycleEndExclusive: input.cycleEndExclusive,
    cycleWindowAcceptance: input.cycleWindowAcceptance,
    lines: profitLines,
  });
  const distributable = BigInt(profitBasis.distributableNetProfitCents);
  if (distributable > MAX_SAFE) return fail("NET_PROFIT_CENTS_OUT_OF_RANGE");
  const capitalDays = calculateCapitalDaysV22({
    ...calculation,
    netProfitCents: Number(distributable),
  });
  return {profitBasis, capitalDays};
}
