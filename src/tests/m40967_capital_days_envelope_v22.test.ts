import assert from "node:assert/strict";
import {
  calculateCapitalDaysV22,
  CapitalDaysV22Error,
  createCapitalDaysPreviewEnvelopeV22,
  type CapitalDaysInputV22,
} from "../services/capitalDaysV22";

const scope = {tenantId: "tenant-envelope", cycleId: "cycle-envelope"};
const input: CapitalDaysInputV22 = {
  scope,
  cycleStart: "2025-01-01",
  cycleEndExclusive: "2026-01-01",
  netProfitCents: 101,
  adminShareBps: 1500,
  members: [
    {
      ...scope,
      membershipId: "member-b",
      openingCapitalCents: 2500,
      eligibilityPeriods: [{startDate: "2025-01-01", endDateExclusive: "2026-01-01"}],
      events: [
        {tenantId: scope.tenantId, cycleId: scope.cycleId, membershipId: "member-b", eventId: "b2", effectiveDate: "2025-03-02", kind: "RESTITUTION", amountCents: 200, status: "CONFIRMED"},
        {tenantId: scope.tenantId, cycleId: scope.cycleId, membershipId: "member-b", eventId: "b1", effectiveDate: "2025-02-01", kind: "CONTRIBUTION", amountCents: 500, status: "CONFIRMED"},
      ],
    },
    {
      ...scope,
      membershipId: "member-a",
      openingCapitalCents: 1500,
      eligibilityPeriods: [{startDate: "2025-01-01", endDateExclusive: "2026-01-01"}],
      events: [],
    },
  ],
};

const before = structuredClone(input);
const first = await createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-cycle-7", "nonce-preview-001");
assert.equal(first.envelope, "CAPITAL_DAYS_V2_PREVIEW_ONLY");
assert.equal(first.digestAlgorithm, "SHA-256");
assert.equal(first.nonce, "nonce-preview-001");
assert.match(first.digest, /^[a-f0-9]{64}$/);
assert.equal(first.result.calculation, "CAPITAL_DAYS_V2_SOURCE_ONLY");
assert.deepEqual(input, before);

const reordered: CapitalDaysInputV22 = {
  ...input,
  members: [...input.members].reverse().map(member => ({
    ...member,
    eligibilityPeriods: [...member.eligibilityPeriods].reverse(),
    events: [...member.events].reverse(),
  })),
};
const same = await createCapitalDaysPreviewEnvelopeV22(reordered, "policy-v2.2-cycle-7", "nonce-preview-001");
assert.equal(same.digest, first.digest);
assert.deepEqual(same.result.members.map(member => member.membershipId), ["member-a", "member-b"]);

const otherPolicy = await createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-cycle-8", "nonce-preview-001");
assert.notEqual(otherPolicy.digest, first.digest);
const otherNonce = await createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-cycle-7", "nonce-preview-002");
assert.notEqual(otherNonce.digest, first.digest);
const otherInput = structuredClone(input);
otherInput.members[0].openingCapitalCents += 1;
const changed = await createCapitalDaysPreviewEnvelopeV22(otherInput, "policy-v2.2-cycle-7", "nonce-preview-001");
assert.notEqual(changed.digest, first.digest);

await assert.rejects(
  createCapitalDaysPreviewEnvelopeV22(input, " "),
  (error: unknown) => error instanceof CapitalDaysV22Error && error.code === "INVALID_POLICY_VERSION",
);

const calculated = calculateCapitalDaysV22(input);
assert.deepEqual(first.result, calculated);
assert.equal(
  BigInt(first.result.adminShareCents)
    + BigInt(first.result.memberPoolPendingCents)
    + first.result.members.reduce((sum, member) => sum + BigInt(member.memberShareCents), 0n),
  101n,
);
console.log("M40967_CAPITAL_DAYS_CANONICAL_PREVIEW_ENVELOPE=PASS");
