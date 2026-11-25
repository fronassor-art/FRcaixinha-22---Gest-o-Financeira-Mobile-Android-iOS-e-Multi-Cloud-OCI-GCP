import assert from "node:assert/strict";
import {calculateCapitalDaysV22, CapitalDaysV22Error, type CapitalDaysInputV22, type CapitalEventV22} from "../services/capitalDaysV22";

const scope = {tenantId: "tenant-reversal", cycleId: "cycle-reversal"};
const start = "2025-01-01";
const end = "2026-01-01";

function ev(
  eventId: string,
  kind: CapitalEventV22["kind"],
  effectiveDate: string,
  amountCents: number,
  reversesEventId?: string,
  status: CapitalEventV22["status"] = "CONFIRMED",
  membershipId = "member-a",
): CapitalEventV22 {
  return {
    ...scope, membershipId, eventId, kind, effectiveDate, amountCents, status,
    ...(reversesEventId === undefined ? {} : {reversesEventId}),
  };
}

function input(events: CapitalEventV22[], openingCapitalCents = 0): CapitalDaysInputV22 {
  return {
    scope, cycleStart: start, cycleEndExclusive: end,
    netProfitCents: 100, adminShareBps: 0,
    members: [{
      ...scope, membershipId: "member-a", openingCapitalCents,
      eligibilityPeriods: [{startDate: start, endDateExclusive: end}],
      events,
    }],
  };
}

function rejects(events: CapitalEventV22[], code: string, openingCapitalCents = 0) {
  assert.throws(() => calculateCapitalDaysV22(input(events, openingCapitalCents)), (error: unknown) =>
    error instanceof CapitalDaysV22Error && error.code === code,
  );
}

const contributionAndReversal = calculateCapitalDaysV22(input([
  ev("contribution", "CONTRIBUTION", "2025-01-01", 1000),
  ev("reversal", "REVERSAL", "2025-01-03", 1000, "contribution"),
]));
assert.equal(contributionAndReversal.members[0].eligibleCapitalDays, "2000");
assert.equal(contributionAndReversal.members[0].memberShareCents, "100");

const restitutionAndReversal = calculateCapitalDaysV22(input([
  ev("restitution", "RESTITUTION", "2025-01-02", 200),
  ev("reversal", "REVERSAL", "2025-01-03", 200, "restitution"),
], 1000));
assert.equal(restitutionAndReversal.members[0].eligibleCapitalDays, "364800");

const reversalOfReversal = calculateCapitalDaysV22(input([
  ev("contribution", "CONTRIBUTION", "2025-01-01", 100),
  ev("reversal-1", "REVERSAL", "2025-01-02", 100, "contribution"),
  ev("reversal-2", "REVERSAL", "2025-01-03", 100, "reversal-1"),
]));
assert.equal(reversalOfReversal.members[0].eligibleCapitalDays, "36400");

const permuted = calculateCapitalDaysV22(input([
  ev("reversal-2", "REVERSAL", "2025-01-03", 100, "reversal-1"),
  ev("reversal-1", "REVERSAL", "2025-01-02", 100, "contribution"),
  ev("contribution", "CONTRIBUTION", "2025-01-01", 100),
]));
assert.equal(permuted.members[0].eligibleCapitalDays, reversalOfReversal.members[0].eligibleCapitalDays);

rejects([ev("reversal", "REVERSAL", "2025-01-03", 100, "missing")], "REVERSAL_TARGET_NOT_FOUND");
rejects([
  ev("contribution", "CONTRIBUTION", "2025-01-01", 100),
  ev("reversal", "REVERSAL", "2025-01-02", 99, "contribution"),
], "REVERSAL_AMOUNT_MISMATCH");
rejects([
  ev("contribution", "CONTRIBUTION", "2025-01-01", 100),
  ev("reversal-1", "REVERSAL", "2025-01-02", 100, "contribution"),
  ev("reversal-2", "REVERSAL", "2025-01-03", 100, "contribution"),
], "DUPLICATE_EVENT_REVERSAL");
rejects([
  ev("contribution", "CONTRIBUTION", "2025-01-02", 100),
  ev("reversal", "REVERSAL", "2025-01-01", 100, "contribution"),
], "REVERSAL_BEFORE_TARGET");
rejects([
  ev("pending", "CONTRIBUTION", "2025-01-01", 100, undefined, "PENDING"),
  ev("reversal", "REVERSAL", "2025-01-02", 100, "pending"),
], "REVERSAL_TARGET_NOT_CONFIRMED");
rejects([
  ev("contribution", "CONTRIBUTION", "2025-01-01", 100),
  ev("reversal", "REVERSAL", "2025-01-02", 100, "contribution", "CONFIRMED", "member-b"),
], "EVENT_MEMBERSHIP_MISMATCH");
rejects([
  ev("a", "REVERSAL", "2025-01-01", 100, "b"),
  ev("b", "REVERSAL", "2025-01-01", 100, "a"),
], "REVERSAL_CYCLE");

const pendingReversal = calculateCapitalDaysV22(input([
  ev("contribution", "CONTRIBUTION", "2025-01-01", 100),
  ev("reversal", "REVERSAL", "2025-01-02", 100, "contribution", "PENDING"),
]));
assert.equal(pendingReversal.members[0].eligibleCapitalDays, "36500");

assert.throws(() => calculateCapitalDaysV22(input([
  {...ev("contribution", "CONTRIBUTION", "2025-01-01", 100), reversesEventId: "unexpected"},
])), (error: unknown) => error instanceof CapitalDaysV22Error && error.code === "UNEXPECTED_REVERSAL_REFERENCE");

console.log("M40969_CAPITAL_DAYS_EXPLICIT_REVERSAL_LINEAGE=PASS");
