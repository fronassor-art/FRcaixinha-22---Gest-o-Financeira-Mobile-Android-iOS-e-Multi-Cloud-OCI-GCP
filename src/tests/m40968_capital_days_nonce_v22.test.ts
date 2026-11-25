import assert from "node:assert/strict";
import {
  CapitalDaysV22Error,
  createCapitalDaysPreviewEnvelopeV22,
  type CapitalDaysInputV22,
} from "../services/capitalDaysV22";

const scope = {tenantId: "tenant-nonce", cycleId: "cycle-nonce"};
const input: CapitalDaysInputV22 = {
  scope,
  cycleStart: "2025-01-01",
  cycleEndExclusive: "2026-01-01",
  netProfitCents: 500,
  adminShareBps: 0,
  members: [{
    ...scope,
    membershipId: "member-nonce",
    openingCapitalCents: 100,
    eligibilityPeriods: [{startDate: "2025-01-01", endDateExclusive: "2026-01-01"}],
    events: [],
  }],
};

const one = await createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-nonce", "request-001");
const same = await createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-nonce", "request-001");
const fresh = await createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-nonce", "request-002");
assert.equal(one.nonce, "request-001");
assert.equal(one.digest, same.digest);
assert.notEqual(one.digest, fresh.digest);

await assert.rejects(
  createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-nonce", ""),
  (error: unknown) => error instanceof CapitalDaysV22Error && error.code === "INVALID_PREVIEW_NONCE",
);
await assert.rejects(
  createCapitalDaysPreviewEnvelopeV22(input, "policy-v2.2-nonce", " request-003 "),
  (error: unknown) => error instanceof CapitalDaysV22Error && error.code === "INVALID_PREVIEW_NONCE",
);

console.log("M40968_CAPITAL_DAYS_PREVIEW_NONCE_BINDING=PASS");
