import assert from "node:assert/strict";
import {
  calculateCapitalDaysV22,
  CapitalDaysV22Error,
  type CapitalDaysInputV22,
} from "../services/capitalDaysV22";

function rejected(input: CapitalDaysInputV22, code: string) {
  assert.throws(() => calculateCapitalDaysV22(input), (error: unknown) =>
    error instanceof CapitalDaysV22Error && error.code === code,
  );
}

const base: CapitalDaysInputV22 = {
  cycleStart: "2026-12-31",
  cycleEndExclusive: "2027-12-31",
  netProfitCents: 1000,
  adminShareBps: 1500,
  members: [
    {
      membershipId: "mem-a",
      openingCapitalCents: 10000,
      eligibilityPeriods: [{startDate: "2026-12-31", endDateExclusive: "2027-12-31"}],
      events: [
        {eventId: "a1", effectiveDate: "2027-01-01", kind: "CONTRIBUTION", amountCents: 5000, status: "CONFIRMED"},
        {eventId: "a2", effectiveDate: "2027-01-02", kind: "RESTITUTION", amountCents: 2000, status: "CONFIRMED"},
      ],
    },
    {
      membershipId: "mem-b",
      openingCapitalCents: 0,
      eligibilityPeriods: [{startDate: "2027-01-02", endDateExclusive: "2027-01-04"}],
      events: [
        {eventId: "b1", effectiveDate: "2027-01-01", kind: "CONTRIBUTION", amountCents: 5000, status: "CONFIRMED"},
      ],
    },
  ],
};

const result = calculateCapitalDaysV22(base);
assert.equal(result.calculation, "CAPITAL_DAYS_V2_SOURCE_ONLY");
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
  cycleStart: "2025-01-01",
  cycleEndExclusive: "2026-01-01",
  netProfitCents: 100,
  adminShareBps: 0,
  members: [{
    membershipId: "mem-status",
    openingCapitalCents: 0,
    eligibilityPeriods: [{startDate: "2025-01-01", endDateExclusive: "2026-01-01"}],
    events: [
      {eventId: "pending", effectiveDate: "2025-01-01", kind: "CONTRIBUTION", amountCents: 1000, status: "PENDING"},
      {eventId: "reversed", effectiveDate: "2025-01-01", kind: "CONTRIBUTION", amountCents: 900, status: "REVERSED"},
      {eventId: "confirmed", effectiveDate: "2025-01-02", kind: "CONTRIBUTION", amountCents: 1000, status: "CONFIRMED"},
      {eventId: "return", effectiveDate: "2025-01-03", kind: "RESTITUTION", amountCents: 300, status: "CONFIRMED"},
    ],
  }],
};
assert.equal(calculateCapitalDaysV22(statusInput).members[0].eligibleCapitalDays, "255100");

const tieInput: CapitalDaysInputV22 = {
  cycleStart: "2025-02-01",
  cycleEndExclusive: "2026-02-01",
  netProfitCents: 1,
  adminShareBps: 0,
  members: ["mem-z", "mem-b", "mem-a"].map(membershipId => ({
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
rejected({...base, netProfitCents: 1.5}, "INVALID_NET_PROFIT_CENTS");
rejected({...base, adminShareBps: 10001}, "INVALID_ADMIN_SHARE_BPS");
rejected({...base, members: [base.members[0], {...base.members[1], membershipId: "mem-a"}]}, "INVALID_MEMBER");
rejected({...base, members: [{...base.members[0], events: [...base.members[0].events, {...base.members[0].events[0]}]}]}, "INVALID_CAPITAL_EVENT");
rejected({...base, members: [{...base.members[0], openingCapitalCents: 0, events: [
  {eventId: "return", effectiveDate: "2027-01-01", kind: "RESTITUTION", amountCents: 1, status: "CONFIRMED"},
]}]}, "RESTITUTION_EXCEEDS_CONFIRMED_CAPITAL");
rejected({...base, members: [{...base.members[0], eligibilityPeriods: [
  {startDate: "2026-12-31", endDateExclusive: "2027-01-03"},
  {startDate: "2027-01-02", endDateExclusive: "2027-01-04"},
]}]}, "OVERLAPPING_ELIGIBILITY_PERIODS");
rejected({...base, members: [{...base.members[0], events: [
  {eventId: "outside", effectiveDate: "2027-12-31", kind: "CONTRIBUTION", amountCents: 1, status: "CONFIRMED"},
]}]}, "CAPITAL_EVENT_OUTSIDE_CYCLE");
rejected({...base, members: [{...base.members[0], openingCapitalCents: -1}]}, "INVALID_OPENING_CAPITAL_CENTS");

console.log("M40965_CAPITAL_DAYS_V22_INTEGER_LEDGER_PREVIEW=PASS");
