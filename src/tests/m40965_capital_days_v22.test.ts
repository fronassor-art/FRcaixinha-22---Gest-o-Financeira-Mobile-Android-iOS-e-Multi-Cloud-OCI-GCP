import assert from "node:assert/strict";
import {
  calculateCapitalDaysV22,
  createCapitalDaysPreviewEnvelopeV22,
  CapitalDaysV22Error,
  type CapitalDaysInputV22,
  type CapitalEventV22,
} from "../services/capitalDaysV22";
import type {ExplicitCycleWindowAcceptanceV22} from "../services/cycleWindowV22";

const scope = {tenantId: "tenant-demo", cycleId: "cycle-demo"} as const;

function event(
  membershipId: string,
  value: Omit<CapitalEventV22, "tenantId" | "cycleId" | "membershipId">,
): CapitalEventV22 {
  return {...scope, membershipId, ...value};
}

function rejected(input: CapitalDaysInputV22, code: string) {
  assert.throws(() => calculateCapitalDaysV22(input), (error: unknown) =>
    error instanceof CapitalDaysV22Error && error.code === code,
  );
}

function explicitWindowAcceptance(
  cycleStart: string,
  cycleEndExclusive: string,
  overrides: Partial<ExplicitCycleWindowAcceptanceV22> = {},
): ExplicitCycleWindowAcceptanceV22 {
  return {
    mode: "EXPLICIT_ACCEPTED_WINDOW",
    scope,
    cycleStart,
    cycleEndExclusive,
    versionId: "policy-custom-v1",
    policyDigest: "b".repeat(64),
    accepted: true,
    acceptedAt: "2026-11-25T12:00:00.000Z",
    frozenAt: "2026-11-25T12:05:00.000Z",
    acceptanceEvidenceRef: "acceptance:custom-cycle-window",
    ...overrides,
  };
}

const base: CapitalDaysInputV22 = {
  scope,
  cycleStart: "2026-12-31",
  cycleEndExclusive: "2027-12-31",
  netProfitCents: 1000,
  adminShareBps: 1500,
  members: [
    {
      ...scope,
      membershipId: "mem-a",
      openingCapitalCents: 10000,
      eligibilityPeriods: [{startDate: "2026-12-31", endDateExclusive: "2027-12-31"}],
      events: [
        event("mem-a", {eventId: "a1", effectiveDate: "2027-01-01", kind: "CONTRIBUTION", amountCents: 5000, status: "CONFIRMED"}),
        event("mem-a", {eventId: "a2", effectiveDate: "2027-01-02", kind: "RESTITUTION", amountCents: 2000, status: "CONFIRMED"}),
      ],
    },
    {
      ...scope,
      membershipId: "mem-b",
      openingCapitalCents: 0,
      eligibilityPeriods: [{startDate: "2027-01-02", endDateExclusive: "2027-01-04"}],
      events: [
        event("mem-b", {eventId: "b1", effectiveDate: "2027-01-01", kind: "CONTRIBUTION", amountCents: 5000, status: "CONFIRMED"}),
      ],
    },
  ],
};

const result = calculateCapitalDaysV22(base);
assert.equal(result.calculation, "CAPITAL_DAYS_V2_SOURCE_ONLY");
assert.deepEqual(result.scope, scope);
assert.equal(result.eligibleCapitalDaysTotal, "4754000");
assert.equal(result.adminShareCents, "150");
assert.equal(result.memberPoolCents, "850");
assert.equal(result.memberPoolPendingCents, "0");
assert.deepEqual(result.members.map(m => m.eligibleCapitalDays), ["4744000", "10000"]);
assert.equal(result.members.reduce((sum, member) => sum + BigInt(member.memberShareCents), 0n), 850n);
assert.equal(result.members.reduce((sum, member) => sum + BigInt(member.memberShareCents), 0n)
  + BigInt(result.adminShareCents), 1000n);
assert.deepEqual(base.members[0].events.map(e => e.amountCents), [5000, 2000]);

const statusInput: CapitalDaysInputV22 = {
  scope,
  cycleStart: "2025-01-01",
  cycleEndExclusive: "2026-01-01",
  netProfitCents: 100,
  adminShareBps: 0,
  members: [{
    ...scope,
    membershipId: "mem-status",
    openingCapitalCents: 0,
    eligibilityPeriods: [{startDate: "2025-01-01", endDateExclusive: "2026-01-01"}],
    events: [
      event("mem-status", {eventId: "pending", effectiveDate: "2025-01-01", kind: "CONTRIBUTION", amountCents: 1000, status: "PENDING"}),
      event("mem-status", {eventId: "reversed", effectiveDate: "2025-01-01", kind: "CONTRIBUTION", amountCents: 900, status: "REVERSED"}),
      event("mem-status", {eventId: "confirmed", effectiveDate: "2025-01-02", kind: "CONTRIBUTION", amountCents: 1000, status: "CONFIRMED"}),
      event("mem-status", {eventId: "return", effectiveDate: "2025-01-03", kind: "RESTITUTION", amountCents: 300, status: "CONFIRMED"}),
    ],
  }],
};
assert.equal(calculateCapitalDaysV22(statusInput).members[0].eligibleCapitalDays, "255100");

const tieInput: CapitalDaysInputV22 = {
  scope,
  cycleStart: "2025-02-01",
  cycleEndExclusive: "2026-02-01",
  netProfitCents: 1,
  adminShareBps: 0,
  members: ["mem-z", "mem-b", "mem-a"].map(membershipId => ({
    ...scope,
    membershipId,
    openingCapitalCents: 1,
    eligibilityPeriods: [{startDate: "2025-02-01", endDateExclusive: "2026-02-01"}],
    events: [],
  })),
};
const tie = calculateCapitalDaysV22(tieInput);
assert.equal(tie.residualCentsDistributed, "1");
assert.equal(tie.members.find(m => m.membershipId === "mem-a")?.memberShareCents, "1");
assert.equal(tie.members.find(m => m.membershipId === "mem-b")?.memberShareCents, "0");

const noWeights = calculateCapitalDaysV22({
  ...tieInput,
  adminShareBps: 1500,
  members: tieInput.members.map(member => ({...member, eligibilityPeriods: []})),
});
assert.equal(noWeights.memberPoolPendingCents, "1");
assert.equal(noWeights.adminShareCents, "0");

const halfUp = calculateCapitalDaysV22({...tieInput, adminShareBps: 5000, members: []});
assert.equal(halfUp.adminShareCents, "1");
assert.equal(halfUp.memberPoolCents, "0");

const loss = calculateCapitalDaysV22({...tieInput, netProfitCents: -250, members: []});
assert.equal(loss.netProfitCents, "0");
assert.equal(loss.adminShareCents, "0");

rejected({...base, cycleStart: "2027-02-29"}, "INVALID_DATE");
rejected({...base, cycleEndExclusive: "2026-12-30"}, "INVALID_CYCLE_WINDOW");
rejected({...base, cycleEndExclusive: "2028-01-01"}, "INVALID_CYCLE_WINDOW");
assert.equal(calculateCapitalDaysV22({...tieInput, cycleStart: "2027-12-31", cycleEndExclusive: "2028-12-31", members: []}).cycleEndExclusive, "2028-12-31");
assert.equal(calculateCapitalDaysV22({...tieInput, cycleStart: "2028-02-29", cycleEndExclusive: "2029-02-28", members: []}).cycleEndExclusive, "2029-02-28");
rejected({...base, cycleStart: "2028-02-29", cycleEndExclusive: "2029-03-01"}, "INVALID_CYCLE_WINDOW");

const customStart = "2026-12-10";
const includeFinalDateEnd = "2027-12-21";
const customIncluded = calculateCapitalDaysV22({
  scope, cycleStart: customStart, cycleEndExclusive: includeFinalDateEnd,
  cycleWindowAcceptance: explicitWindowAcceptance(customStart, includeFinalDateEnd),
  netProfitCents: 0, adminShareBps: 0,
  members: [{
    ...scope, membershipId: "member-final-date", openingCapitalCents: 10000,
    eligibilityPeriods: [{startDate: customStart, endDateExclusive: includeFinalDateEnd}],
    events: [event("member-final-date", {
      eventId: "final-date-contribution", effectiveDate: "2027-12-20",
      kind: "CONTRIBUTION", amountCents: 100, status: "CONFIRMED",
    })],
  }],
});
assert.equal(customIncluded.members[0].eligibleCapitalDays, "3760100");
assert.equal(customIncluded.cycleEndExclusive, includeFinalDateEnd);

const excludeFinalDateEnd = "2027-12-20";
const customExcluded = calculateCapitalDaysV22({
  scope, cycleStart: customStart, cycleEndExclusive: excludeFinalDateEnd,
  cycleWindowAcceptance: explicitWindowAcceptance(customStart, excludeFinalDateEnd),
  netProfitCents: 0, adminShareBps: 0,
  members: [{
    ...scope, membershipId: "member-before-final-date", openingCapitalCents: 10000,
    eligibilityPeriods: [{startDate: customStart, endDateExclusive: excludeFinalDateEnd}],
    events: [],
  }],
});
assert.equal(customExcluded.members[0].eligibleCapitalDays, "3750000");
rejected({
  scope, cycleStart: customStart, cycleEndExclusive: excludeFinalDateEnd,
  cycleWindowAcceptance: explicitWindowAcceptance(customStart, excludeFinalDateEnd),
  netProfitCents: 0, adminShareBps: 0,
  members: [{
    ...scope, membershipId: "member-after-cutoff", openingCapitalCents: 10000,
    eligibilityPeriods: [{startDate: customStart, endDateExclusive: excludeFinalDateEnd}],
    events: [event("member-after-cutoff", {
      eventId: "after-cutoff", effectiveDate: "2027-12-20",
      kind: "CONTRIBUTION", amountCents: 1, status: "CONFIRMED",
    })],
  }],
}, "CAPITAL_EVENT_OUTSIDE_CYCLE");
rejected({
  scope, cycleStart: customStart, cycleEndExclusive: includeFinalDateEnd,
  cycleWindowAcceptance: explicitWindowAcceptance(customStart, includeFinalDateEnd, {
    scope: {tenantId: "tenant-other", cycleId: scope.cycleId},
  }),
  netProfitCents: 0, adminShareBps: 0, members: [],
}, "INVALID_CYCLE_WINDOW_ACCEPTANCE");
rejected({
  ...base, cycleStart: customStart, cycleEndExclusive: includeFinalDateEnd, members: [],
}, "INVALID_CYCLE_WINDOW");
rejected({
  scope, cycleStart: customStart, cycleEndExclusive: includeFinalDateEnd,
  cycleWindowAcceptance: explicitWindowAcceptance(customStart, includeFinalDateEnd, {accepted: false}),
  netProfitCents: 0, adminShareBps: 0, members: [],
}, "INVALID_CYCLE_WINDOW_ACCEPTANCE");
const endOnlyInput: CapitalDaysInputV22 = {
  scope, cycleStart: customStart, cycleEndExclusive: excludeFinalDateEnd,
  cycleWindowAcceptance: explicitWindowAcceptance(customStart, excludeFinalDateEnd),
  netProfitCents: 0, adminShareBps: 0, members: [],
};
const includeFinalDateInput: CapitalDaysInputV22 = {
  scope, cycleStart: customStart, cycleEndExclusive: includeFinalDateEnd,
  cycleWindowAcceptance: explicitWindowAcceptance(customStart, includeFinalDateEnd),
  netProfitCents: 0, adminShareBps: 0, members: [],
};
const endOnlyEnvelope = await createCapitalDaysPreviewEnvelopeV22(endOnlyInput, "policy-v1", "nonce-1");
const includeFinalEnvelope = await createCapitalDaysPreviewEnvelopeV22(
  includeFinalDateInput, "policy-v1", "nonce-1",
);
assert.notEqual(endOnlyEnvelope.digest, includeFinalEnvelope.digest);
rejected({...base, netProfitCents: 1.5}, "INVALID_NET_PROFIT_CENTS");
rejected({...base, adminShareBps: 10001}, "INVALID_ADMIN_SHARE_BPS");
rejected({...base, members: [base.members[0], {...base.members[1], membershipId: "mem-a"}]}, "INVALID_MEMBER");
rejected({...base, members: [{...base.members[0], events: [...base.members[0].events, {...base.members[0].events[0]}]}]}, "INVALID_CAPITAL_EVENT");
rejected({...base, members: [{...base.members[0], openingCapitalCents: 0, events: [
  event("mem-a", {eventId: "return", effectiveDate: "2027-01-01", kind: "RESTITUTION", amountCents: 1, status: "CONFIRMED"}),
]}]}, "RESTITUTION_EXCEEDS_CONFIRMED_CAPITAL");
rejected({...base, members: [{...base.members[0], eligibilityPeriods: [
  {startDate: "2026-12-31", endDateExclusive: "2027-01-03"},
  {startDate: "2027-01-02", endDateExclusive: "2027-01-04"},
]}]}, "OVERLAPPING_ELIGIBILITY_PERIODS");
rejected({...base, members: [{...base.members[0], events: [
  event("mem-a", {eventId: "outside", effectiveDate: "2027-12-31", kind: "CONTRIBUTION", amountCents: 1, status: "CONFIRMED"}),
]}]}, "CAPITAL_EVENT_OUTSIDE_CYCLE");
rejected({...base, members: [{...base.members[0], openingCapitalCents: -1}]}, "INVALID_OPENING_CAPITAL_CENTS");

console.log("M40965_CAPITAL_DAYS_V22_INTEGER_LEDGER_PREVIEW=PASS");
