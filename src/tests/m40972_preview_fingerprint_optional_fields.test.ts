import assert from "node:assert/strict";
import {
  createCycleDistributionPreviewEnvelopeV22,
  type AcceptedCycleDistributionPolicyV22,
  type CycleDistributionPreviewInputV22,
} from "../services/cycleDistributionPreviewV22";
import type {ProfitBasisLineV22} from "../services/eligibleProfitBasisV22";

const scope = {tenantId: "tenant-m40972", cycleId: "cycle-m40972"};
const cycleStart = "2025-01-01";
const cycleEndExclusive = "2026-01-01";
const policy: AcceptedCycleDistributionPolicyV22 = {
  scope,
  cycleStart,
  cycleEndExclusive,
  administratorId: "admin-user",
  administratorMembershipId: null,
  versionId: "policy-optional-fields",
  policyDigest: "b".repeat(64),
  adminShareBps: 0,
  accepted: true,
  acceptedAt: "2024-12-01T10:00:00.000Z",
  frozenAt: "2024-12-01T10:01:00.000Z",
  acceptanceEvidenceRef: "acceptance:m40972",
};
const revenue: ProfitBasisLineV22 = {
  ...scope,
  lineId: "realized-revenue",
  kind: "REALIZED_REVENUE",
  status: "CONFIRMED",
  currency: "BRL",
  amountCents: 2500,
  competenceDate: "2025-04-10",
  recognizedDate: "2025-04-10",
  financialDate: "2025-04-10",
  reconciled: true,
  policyAccepted: true,
  evidenceRef: "receipt:m40972",
  authorizationRef: null,
};
const contribution = {
  tenantId: scope.tenantId,
  cycleId: scope.cycleId,
  membershipId: "member-a",
  eventId: "contribution-1",
  effectiveDate: "2025-02-01",
  kind: "CONTRIBUTION" as const,
  amountCents: 500,
  status: "CONFIRMED" as const,
}; // reversesEventId is intentionally absent: it is optional for contributions.
const input: CycleDistributionPreviewInputV22 = {
  scope,
  cycleStart,
  cycleEndExclusive,
  policy,
  profitLines: [revenue],
  members: [{
    ...scope,
    membershipId: "member-a",
    openingCapitalCents: 0,
    eligibilityPeriods: [{startDate: cycleStart, endDateExclusive: cycleEndExclusive}],
    events: [contribution],
  }],
};

const first = await createCycleDistributionPreviewEnvelopeV22(input);
const replay = await createCycleDistributionPreviewEnvelopeV22(input);
assert.equal(first.envelope, "CYCLE_DISTRIBUTION_PREVIEW_ONLY");
assert.match(first.digest, /^[a-f0-9]{64}$/);
assert.equal(first.digest, replay.digest);
assert.equal(first.result.calculation.capitalDays.memberPoolCents, "2500");
assert.equal(first.result.calculation.capitalDays.memberPoolPendingCents, "0");
assert.equal(first.result.calculation.capitalDays.members[0].membershipId, "member-a");
assert.ok(BigInt(first.result.calculation.capitalDays.members[0].eligibleCapitalDays) > 0n);
assert.equal(first.result.executionAuthorized, false);

// Canonical object-key ordering keeps the same digest for semantically identical input.
const reorderedEvent = Object.fromEntries(Object.entries(contribution).reverse()) as typeof contribution;
const reorderedLine = Object.fromEntries(Object.entries(revenue).reverse()) as ProfitBasisLineV22;
const reorderedPolicy = Object.fromEntries(Object.entries(policy).reverse()) as AcceptedCycleDistributionPolicyV22;
const reorderedInput: CycleDistributionPreviewInputV22 = {
  policy: reorderedPolicy,
  members: [{...input.members[0], events: [reorderedEvent]}],
  profitLines: [reorderedLine],
  cycleEndExclusive,
  cycleStart,
  scope,
};
const reordered = await createCycleDistributionPreviewEnvelopeV22(reorderedInput);
assert.equal(reordered.digest, first.digest);

console.log("M40972_OPTIONAL_EVENT_FINGERPRINT_SOURCE_ONLY=PASS");
