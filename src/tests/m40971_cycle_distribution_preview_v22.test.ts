import assert from "node:assert/strict";
import {
  calculateCycleDistributionPreviewV22,
  createCycleDistributionPreviewEnvelopeV22,
  CycleDistributionPreviewV22Error,
  type AcceptedCycleDistributionPolicyV22,
  type CycleDistributionPreviewInputV22,
} from "../services/cycleDistributionPreviewV22";
import type {ProfitBasisLineV22} from "../services/eligibleProfitBasisV22";

const scope = {tenantId: "tenant-m40971", cycleId: "cycle-2025"};
const cycleStart = "2025-01-01";
const cycleEndExclusive = "2026-01-01";
const policy: AcceptedCycleDistributionPolicyV22 = {
  scope,
  cycleStart,
  cycleEndExclusive,
  versionId: "policy-v7",
  policyDigest: "a".repeat(64),
  adminShareBps: 0,
  accepted: true,
  acceptedAt: "2024-12-01T10:00:00.000Z",
  frozenAt: "2024-12-01T10:05:00.000Z",
  acceptanceEvidenceRef: "acceptance:cycle-2025",
};
const revenue: ProfitBasisLineV22 = {
  ...scope, lineId: "revenue-1", kind: "REALIZED_REVENUE", status: "CONFIRMED",
  currency: "BRL", amountCents: 10001, competenceDate: "2025-06-01",
  recognizedDate: "2025-06-01", financialDate: "2025-06-01",
  reconciled: true, policyAccepted: true, evidenceRef: "receipt:1", authorizationRef: null,
};
function member(membershipId: string, capitalCents: number) {
  return {
    ...scope, membershipId, openingCapitalCents: capitalCents,
    eligibilityPeriods: [{startDate: cycleStart, endDateExclusive: cycleEndExclusive}],
    events: [],
  };
}
function input(overrides: Partial<CycleDistributionPreviewInputV22> = {}): CycleDistributionPreviewInputV22 {
  return {scope, cycleStart, cycleEndExclusive, policy, profitLines: [revenue],
    members: [member("member-c", 1), member("member-a", 1), member("member-b", 1)], ...overrides};
}

const result = calculateCycleDistributionPreviewV22(input());
assert.equal(result.preview, "CYCLE_DISTRIBUTION_SOURCE_ONLY");
assert.equal(result.executionAuthorized, false);
assert.equal(result.policyAttestation, "CALLER_SUPPLIED_NOT_AUTHENTICATED");
assert.equal(result.calculation.profitBasis.distributableNetProfitCents, "10001");
assert.equal(result.calculation.capitalDays.adminShareCents, "0");
assert.equal(result.calculation.capitalDays.memberPoolCents, "10001");
assert.equal(result.calculation.capitalDays.members.reduce(
  (sum, row) => sum + BigInt(row.memberShareCents), 0n), 10001n);
assert.equal(result.calculation.capitalDays.members.find(row => row.membershipId === "member-a")
  ?.residualCentAssigned, true);
assert.equal(result.calculation.capitalDays.members.find(row => row.membershipId === "member-b")
  ?.residualCentAssigned, false);

const emptyWeights = calculateCycleDistributionPreviewV22(input({
  members: [ {...member("no-eligible-capital", 0), eligibilityPeriods: []} ],
}));
assert.equal(emptyWeights.calculation.capitalDays.memberPoolPendingCents, "10001");
assert.equal(emptyWeights.calculation.capitalDays.adminShareCents, "0");
assert.equal(emptyWeights.calculation.capitalDays.members[0].memberShareCents, "0");

assert.throws(() => calculateCycleDistributionPreviewV22(input({
  policy: {...policy, accepted: false} as AcceptedCycleDistributionPolicyV22,
})), (error: unknown) => error instanceof CycleDistributionPreviewV22Error
  && error.code === "POLICY_NOT_ACCEPTED");
assert.throws(() => calculateCycleDistributionPreviewV22(input({
  policy: {...policy, scope: {tenantId: "other", cycleId: scope.cycleId}},
})), (error: unknown) => error instanceof CycleDistributionPreviewV22Error
  && error.code === "POLICY_SCOPE_MISMATCH");
assert.throws(() => calculateCycleDistributionPreviewV22(input({
  policy: {...policy, cycleEndExclusive: "2027-01-01"},
})), (error: unknown) => error instanceof CycleDistributionPreviewV22Error
  && error.code === "POLICY_CYCLE_MISMATCH");
assert.throws(() => calculateCycleDistributionPreviewV22(input({
  policy: {...policy, adminShareBps: 10001},
})), (error: unknown) => error instanceof CycleDistributionPreviewV22Error
  && error.code === "INVALID_ADMIN_SHARE_BPS");
assert.throws(() => calculateCycleDistributionPreviewV22(input({
  policy: {...policy, frozenAt: "2024-11-30T10:00:00.000Z"},
})), (error: unknown) => error instanceof CycleDistributionPreviewV22Error
  && error.code === "INVALID_POLICY_ACCEPTANCE_WINDOW");

const mismatchedLine = {...revenue, tenantId: "another-tenant"};
assert.throws(() => calculateCycleDistributionPreviewV22(input({profitLines: [mismatchedLine]})),
  /LINE_SCOPE_MISMATCH/);

const firstEnvelope = await createCycleDistributionPreviewEnvelopeV22(input());
const repeatedEnvelope = await createCycleDistributionPreviewEnvelopeV22(input());
assert.equal(firstEnvelope.digestAlgorithm, "SHA-256");
assert.match(firstEnvelope.digest, /^[a-f0-9]{64}$/);
assert.equal(firstEnvelope.digest, repeatedEnvelope.digest);
assert.equal(firstEnvelope.result.executionAuthorized, false);
const changedEnvelope = await createCycleDistributionPreviewEnvelopeV22(input({
  profitLines: [{...revenue, amountCents: 10002}],
}));
assert.notEqual(firstEnvelope.digest, changedEnvelope.digest);

console.log("M40971_CYCLE_DISTRIBUTION_PREVIEW_SOURCE_ONLY=PASS");
