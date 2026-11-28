import assert from "node:assert/strict";
import {
  calculateCapitalDaysV22,
  CapitalDaysV22Error,
  type CapitalDaysInputV22,
} from "../services/capitalDaysV22";

const scope = {tenantId: "tenant-alpha", cycleId: "cycle-alpha"};
const base: CapitalDaysInputV22 = {
  scope,
  cycleStart: "2026-01-01",
  cycleEndExclusive: "2027-01-01",
  netProfitCents: 0,
  adminShareBps: 0,
  members: [{
    ...scope,
    membershipId: "membership-alpha",
    openingCapitalCents: 0,
    eligibilityPeriods: [],
    events: [],
  }],
};

function expectScopeRejection(input: CapitalDaysInputV22, code: string) {
  assert.throws(() => calculateCapitalDaysV22(input), (error: unknown) =>
    error instanceof CapitalDaysV22Error && error.code === code,
  );
}

const valid = calculateCapitalDaysV22(base);
assert.deepEqual(valid.scope, scope);
assert.equal(valid.calculation, "CAPITAL_DAYS_V2_SOURCE_ONLY");

expectScopeRejection({
  ...base,
  members: [{...base.members[0], tenantId: "tenant-beta"}],
}, "MEMBER_SCOPE_MISMATCH");

expectScopeRejection({
  ...base,
  members: [{...base.members[0], cycleId: "cycle-beta"}],
}, "MEMBER_SCOPE_MISMATCH");

const eventBase = {
  eventId: "event-alpha",
  effectiveDate: "2026-04-01",
  kind: "CONTRIBUTION" as const,
  amountCents: 1,
  status: "CONFIRMED" as const,
  membershipId: "membership-alpha",
  tenantId: "tenant-alpha",
  cycleId: "cycle-alpha",
};

expectScopeRejection({
  ...base,
  members: [{...base.members[0], events: [{...eventBase, tenantId: "tenant-beta"}]}],
}, "EVENT_SCOPE_MISMATCH");

expectScopeRejection({
  ...base,
  members: [{...base.members[0], events: [{...eventBase, cycleId: "cycle-beta"}]}],
}, "EVENT_SCOPE_MISMATCH");

expectScopeRejection({
  ...base,
  members: [{...base.members[0], events: [{...eventBase, membershipId: "membership-beta"}]}],
}, "EVENT_MEMBERSHIP_MISMATCH");

expectScopeRejection({
  ...base,
  scope: {tenantId: " tenant-alpha ", cycleId: "cycle-alpha"},
}, "INVALID_SCOPE");

expectScopeRejection({
  ...base,
  scope: {tenantId: "", cycleId: "cycle-alpha"},
}, "INVALID_SCOPE");

console.log("M40966_CAPITAL_DAYS_TENANT_CYCLE_MEMBERSHIP_FENCE=PASS");
