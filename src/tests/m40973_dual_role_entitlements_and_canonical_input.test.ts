import assert from "node:assert/strict";
import {
  calculateCycleDistributionPreviewV22,
  createCycleDistributionPreviewEnvelopeV22,
  CycleDistributionPreviewV22Error,
  type AcceptedCycleDistributionPolicyV22,
  type CycleDistributionPreviewInputV22,
} from "../services/cycleDistributionPreviewV22";
import type {ProfitBasisLineV22} from "../services/eligibleProfitBasisV22";

const scope = {tenantId: "tenant-m40973", cycleId: "cycle-m40973"};
const cycleStart = "2025-01-01";
const cycleEndExclusive = "2026-01-01";
const policy: AcceptedCycleDistributionPolicyV22 = {
  scope, administratorId: "admin-user", administratorMembershipId: "member-a",
  cycleStart, cycleEndExclusive, versionId: "policy-m40973",
  policyDigest: "c".repeat(64), adminShareBps: 2000, accepted: true,
  acceptedAt: "2024-12-01T10:00:00.000Z", frozenAt: "2024-12-01T10:05:00.000Z",
  acceptanceEvidenceRef: "acceptance:m40973",
};
const revenue: ProfitBasisLineV22 = {
  ...scope, lineId: "revenue-m40973", kind: "REALIZED_REVENUE", status: "CONFIRMED",
  currency: "BRL", amountCents: 2500, competenceDate: "2025-06-01",
  recognizedDate: "2025-06-01", financialDate: "2025-06-01",
  reconciled: true, policyAccepted: true, evidenceRef: "receipt:m40973", authorizationRef: null,
};
function member(membershipId: string, openingCapitalCents: number) {
  return {
    ...scope, membershipId, openingCapitalCents,
    eligibilityPeriods: [{startDate: cycleStart, endDateExclusive: cycleEndExclusive}],
    events: [],
  };
}
function makeInput(overrides: Partial<CycleDistributionPreviewInputV22> = {}): CycleDistributionPreviewInputV22 {
  return {
    scope, cycleStart, cycleEndExclusive, policy, profitLines: [revenue],
    members: [member("member-a", 100), member("member-b", 100)], ...overrides,
  };
}

const dualRole = calculateCycleDistributionPreviewV22(makeInput());
assert.equal(dualRole.executionAuthorized, false);
assert.equal(dualRole.policyAttestation, "CALLER_SUPPLIED_NOT_AUTHENTICATED");
assert.equal(dualRole.calculation.profitBasis.distributableNetProfitCents, "2500");
assert.equal(dualRole.calculation.capitalDays.adminShareCents, "500");
assert.equal(dualRole.calculation.capitalDays.memberPoolCents, "2000");
const adminRows = dualRole.entitlements.filter(row => row.beneficiaryId === "admin-user");
assert.equal(adminRows.length, 1);
assert.deepEqual(adminRows[0], {
  kind: "ADMINISTRATOR_COMPENSATION", beneficiaryId: "admin-user",
  membershipId: "member-a", amountCents: "500",
});
const adminMemberRow = dualRole.entitlements.find(row =>
  row.kind === "MEMBER_PROFIT" && row.membershipId === "member-a");
assert.ok(adminMemberRow);
assert.equal(adminMemberRow.amountCents, "1000");
assert.notEqual(adminRows[0].kind, adminMemberRow.kind);
assert.equal(dualRole.entitlements.reduce((sum, row) => sum + BigInt(row.amountCents), 0n), 2500n);

const nonMemberAdmin = calculateCycleDistributionPreviewV22(makeInput({
  policy: {...policy, administratorMembershipId: null},
}));
assert.equal(nonMemberAdmin.entitlements[0].kind, "ADMINISTRATOR_COMPENSATION");
assert.equal(nonMemberAdmin.entitlements[0].membershipId, null);
assert.equal(nonMemberAdmin.entitlements.filter(row => row.kind === "MEMBER_PROFIT").length, 2);

assert.throws(() => calculateCycleDistributionPreviewV22(makeInput({
  policy: {...policy, administratorMembershipId: "membership-from-another-cycle"},
})), (error: unknown) => error instanceof CycleDistributionPreviewV22Error
  && error.code === "ADMINISTRATOR_MEMBERSHIP_NOT_IN_CYCLE");

const noWeights = calculateCycleDistributionPreviewV22(makeInput({
  members: [member("member-a", 0), member("member-b", 0)],
}));
assert.equal(noWeights.entitlements.find(row => row.kind === "PENDING_MEMBER_POOL")?.amountCents, "2000");
assert.equal(noWeights.calculation.capitalDays.adminShareCents, "500");
assert.equal(noWeights.entitlements.reduce((sum, row) => sum + BigInt(row.amountCents), 0n), 2500n);

const nonFinite = makeInput();
Object.assign(nonFinite, {diagnosticMetadata: Number.NaN});
await assert.rejects(() => createCycleDistributionPreviewEnvelopeV22(nonFinite),
  (error: unknown) => error instanceof CycleDistributionPreviewV22Error
    && error.code === "NON_CANONICAL_INPUT");

const cyclic = makeInput();
Object.assign(cyclic, {diagnosticMetadata: cyclic});
await assert.rejects(() => createCycleDistributionPreviewEnvelopeV22(cyclic),
  (error: unknown) => error instanceof CycleDistributionPreviewV22Error
    && error.code === "CYCLIC_CANONICAL_INPUT");

console.log("M40973_DUAL_ROLE_ENTITLEMENTS_AND_CANONICAL_INPUT_GUARDS=PASS");
