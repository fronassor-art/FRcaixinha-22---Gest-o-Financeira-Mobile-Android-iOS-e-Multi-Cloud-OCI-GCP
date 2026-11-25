import assert from "node:assert/strict";
import {buildFirstCaixinhaCalendarDraftV1,buildMonthlyDueDates} from "../services/firstCaixinhaCalendarDraftV1";

const draft=buildFirstCaixinhaCalendarDraftV1();
assert.equal(draft.scope,"OWNER_FIRST_CAIXINHA_ONLY");
assert.equal(draft.status,"DRAFT_UNBOUND_TO_TENANT");
assert.equal(draft.cycleStart,"2026-12-10");
assert.equal(draft.firstContributionDate,"2026-12-10");
assert.equal(draft.lastContributionDate,"2027-11-10");
assert.equal(draft.closeAndFinalPaymentDate,"2027-12-20");
assert.equal(draft.contributionDueDay,10);
assert.equal(draft.contributionCount,12);
assert.deepEqual(draft.contributionDates,[
  "2026-12-10","2027-01-10","2027-02-10","2027-03-10",
  "2027-04-10","2027-05-10","2027-06-10","2027-07-10",
  "2027-08-10","2027-09-10","2027-10-10","2027-11-10",
]);
assert.equal(draft.capitalDaysEndExclusive,null);
assert.equal(draft.capitalDaysCutoffResolved,false);
for(const gate of [draft.cycleOpeningEnabled,draft.contractAcceptanceEnabled,draft.realInvitationsEnabled,
  draft.saasBillingEnabled,draft.memberContributionsEnabled,draft.financialExecutionEnabled]) {
  assert.equal(gate,false);
}
assert.equal(buildMonthlyDueDates("2026-12-10","2027-10-10",10).length,11);
assert.throws(()=>buildMonthlyDueDates("2026-12-10","2027-10-11",10),/INVALID_DUE_DATE_RANGE/);
assert.throws(()=>buildMonthlyDueDates("2026-12-11","2027-11-10",10),/INVALID_DUE_DATE_RANGE/);
assert.throws(()=>buildMonthlyDueDates("2027-02-29","2027-11-10",10),/INVALID_CIVIL_DATE/);
assert.throws(()=>buildMonthlyDueDates("2026-12-10","2027-11-10",0),/INVALID_DUE_DAY/);
console.log("M41000_FIRST_CAIXINHA_CALENDAR_DRAFT=PASS_SOURCE_ONLY");
