import assert from "node:assert/strict";
import {
  calculateCapitalDaysFromProfitBasisV22,
  calculateEligibleProfitBasisV22,
  EligibleProfitBasisV22Error,
  type EligibleProfitBasisInputV22,
  type ProfitBasisLineV22,
} from "../services/eligibleProfitBasisV22";

const scope = {tenantId: "tenant-profit", cycleId: "cycle-profit"};
const cycleStart = "2025-01-01";
const cycleEndExclusive = "2026-01-01";

function line(
  lineId: string,
  kind: ProfitBasisLineV22["kind"],
  amountCents: number,
  overrides: Partial<ProfitBasisLineV22> = {},
): ProfitBasisLineV22 {
  return {
    ...scope,
    lineId,
    kind,
    status: "CONFIRMED",
    currency: "BRL",
    amountCents,
    competenceDate: "2025-06-01",
    recognizedDate: "2025-06-02",
    financialDate: "2025-06-03",
    reconciled: true,
    policyAccepted: true,
    evidenceRef: "evidence:"+lineId,
    authorizationRef: kind.startsWith("AUTHORIZED_ADJUSTMENT") ? "approval:"+lineId : null,
    ...overrides,
  };
}

function basis(lines: ProfitBasisLineV22[]) {
  const input: EligibleProfitBasisInputV22 = {scope, cycleStart, cycleEndExclusive, lines};
  return calculateEligibleProfitBasisV22(input);
}

const entries = [
  line("revenue", "REALIZED_REVENUE", 2000),
  line("expense", "RECOGNIZED_EXPENSE", 300),
  line("loss", "REALIZED_LOSS", 100),
  line("adjust-credit", "AUTHORIZED_ADJUSTMENT_CREDIT", 50),
  line("adjust-debit", "AUTHORIZED_ADJUSTMENT_DEBIT", 25),
  line("capital", "CAPITAL_PRINCIPAL", 9000),
  line("loan-principal", "LOAN_PRINCIPAL", 8000),
  line("receivable", "UNPAID_RECEIVABLE", 7000),
  line("future-interest", "FUTURE_INTEREST", 6000),
  line("lottery", "EXTERNAL_LOTTERY_AWARD", 5000),
  line("pending-revenue", "REALIZED_REVENUE", 500, {status: "PENDING"}),
  line("unreconciled-revenue", "REALIZED_REVENUE", 400, {reconciled: false}),
  line("out-of-cycle-revenue", "REALIZED_REVENUE", 300, {financialDate: "2026-01-01"}),
  line("unauthorized-adjustment", "AUTHORIZED_ADJUSTMENT_CREDIT", 200, {authorizationRef: null}),
];
const result = basis(entries);
assert.equal(result.basis, "REALIZED_NET_PROFIT_SOURCE_ONLY");
assert.equal(result.realizedRevenueCents, "2000");
assert.equal(result.recognizedExpenseCents, "300");
assert.equal(result.realizedLossCents, "100");
assert.equal(result.adjustmentCreditCents, "50");
assert.equal(result.adjustmentDebitCents, "25");
assert.equal(result.rawNetResultCents, "1625");
assert.equal(result.distributableNetProfitCents, "1625");
assert.equal(result.lines.length, entries.length);
assert.deepEqual(result.lines.map(x => x.lineId), [...result.lines.map(x=>x.lineId)].sort());
assert.equal(result.lines.find(x=>x.lineId==="capital")?.reason, "EXCLUDED_BY_PROFIT_BASIS_RULE");
assert.equal(result.lines.find(x=>x.lineId==="pending-revenue")?.reason, "LINE_NOT_CONFIRMED");
assert.equal(result.lines.find(x=>x.lineId==="unreconciled-revenue")?.reason, "REVENUE_NOT_RECONCILED");
assert.equal(result.lines.find(x=>x.lineId==="out-of-cycle-revenue")?.reason, "FINANCIAL_DATE_OUTSIDE_CYCLE");
assert.equal(result.lines.find(x=>x.lineId==="unauthorized-adjustment")?.reason, "MISSING_ADJUSTMENT_AUTHORIZATION");

const reordered = basis([...entries].reverse());
assert.deepEqual(reordered, result);

const lossOnly = basis([
  line("expense", "RECOGNIZED_EXPENSE", 700),
  line("revenue", "REALIZED_REVENUE", 200),
]);
assert.equal(lossOnly.rawNetResultCents, "-500");
assert.equal(lossOnly.distributableNetProfitCents, "0");

const empty = basis([]);
assert.equal(empty.distributableNetProfitCents, "0");

assert.throws(() => basis([line("x", "REALIZED_REVENUE", 10, {tenantId: "tenant-other"})]),
  (error: unknown) => error instanceof EligibleProfitBasisV22Error && error.code === "LINE_SCOPE_MISMATCH");
assert.throws(() => basis([line("x", "REALIZED_REVENUE", 10), line("x", "REALIZED_REVENUE", 10)]),
  (error: unknown) => error instanceof EligibleProfitBasisV22Error && error.code === "INVALID_PROFIT_BASIS_LINE");
assert.throws(() => basis([line("x", "REALIZED_REVENUE", Number.MAX_SAFE_INTEGER + 1)]),
  (error: unknown) => error instanceof EligibleProfitBasisV22Error && error.code === "INVALID_PROFIT_BASIS_LINE");
assert.throws(() => basis([line("x", "REALIZED_REVENUE", 10, {currency: "USD" as "BRL"})]),
  (error: unknown) => error instanceof EligibleProfitBasisV22Error && error.code === "INVALID_PROFIT_BASIS_LINE");

const scopedMember: CapitalDaysFromProfitBasisInputV22["members"][number] = {
  ...scope,
  membershipId: "member-profit",
  openingCapitalCents: 1000,
  eligibilityPeriods: [{startDate: cycleStart, endDateExclusive: cycleEndExclusive}],
  events: [],
};
const integrated = calculateCapitalDaysFromProfitBasisV22({
  scope, cycleStart, cycleEndExclusive, adminShareBps: 2000,
  members: [scopedMember], profitLines: entries,
});
assert.equal(integrated.profitBasis.distributableNetProfitCents, "1625");
assert.equal(integrated.capitalDays.netProfitCents, "1625");
assert.equal(integrated.capitalDays.adminShareCents, "325");
assert.equal(integrated.capitalDays.memberPoolCents, "1300");

assert.throws(() => calculateCapitalDaysFromProfitBasisV22({
  scope, cycleStart, cycleEndExclusive, adminShareBps: 0,
  members: [scopedMember],
  profitLines: [line("large-a", "REALIZED_REVENUE", Number.MAX_SAFE_INTEGER),
    line("large-b", "REALIZED_REVENUE", Number.MAX_SAFE_INTEGER)],
}), (error: unknown) => error instanceof EligibleProfitBasisV22Error && error.code === "NET_PROFIT_CENTS_OUT_OF_RANGE");

console.log("M40970_REALIZED_NET_PROFIT_BASIS_SOURCE_ONLY=PASS");
