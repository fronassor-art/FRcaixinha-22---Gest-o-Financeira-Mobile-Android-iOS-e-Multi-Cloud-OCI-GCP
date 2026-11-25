/**
 * M40965 — source-only Capital-Dias V2 calculation.
 * Pure integer-cent preview for one cycle. It does not authorize or settle money.
 */
export type CapitalEventKindV22 = "CONTRIBUTION" | "RESTITUTION";
export type CapitalEventStatusV22 = "CONFIRMED" | "PENDING" | "REVERSED";

export interface CapitalEventV22 {
  eventId: string;
  effectiveDate: string; // local civil date, YYYY-MM-DD
  kind: CapitalEventKindV22;
  amountCents: number; // positive integer; returns use RESTITUTION
  status: CapitalEventStatusV22;
}

export interface EligibilityPeriodV22 {
  startDate: string; // inclusive local civil date
  endDateExclusive: string; // exclusive local civil date
}

export interface CapitalDaysMemberV22 {
  membershipId: string;
  openingCapitalCents: number; // reconciled capital at the close before cycleStart
  eligibilityPeriods: EligibilityPeriodV22[]; // supplied by the accepted cycle policy
  events: CapitalEventV22[]; // event dates must belong to this cycle
}

export interface CapitalDaysInputV22 {
  cycleStart: string; // inclusive
  cycleEndExclusive: string; // exclusive
  netProfitCents: number; // realized cycle net result; losses are capped at zero
  adminShareBps: number; // explicit accepted policy, integer basis points, no default
  members: CapitalDaysMemberV22[];
}

export interface CapitalDaysMemberResultV22 {
  membershipId: string;
  eligibleCapitalDays: string; // exact integer cents × eligible days
  baseShareCents: string;
  remainderNumerator: string;
  residualCentAssigned: boolean;
  memberShareCents: string;
}

export interface CapitalDaysResultV22 {
  calculation: "CAPITAL_DAYS_V2_SOURCE_ONLY";
  cycleStart: string;
  cycleEndExclusive: string;
  netProfitCents: string;
  adminShareBps: number;
  adminShareCents: string;
  memberPoolCents: string;
  memberPoolPendingCents: string;
  eligibleCapitalDaysTotal: string;
  residualCentsDistributed: string;
  members: CapitalDaysMemberResultV22[];
}

export class CapitalDaysV22Error extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "CapitalDaysV22Error";
  }
}

const DAY_MS = 86_400_000;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

function fail(code: string): never {
  throw new CapitalDaysV22Error(code);
}

function dayNumber(value: string): number {
  if (typeof value !== "string" || !DATE_ONLY.test(value)) return fail("INVALID_DATE");
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  if (year < 1000 || month < 1 || month > 12 || day < 1 || day > 31) return fail("INVALID_DATE");
  const stamp = Date.UTC(year, month - 1, day);
  if (!Number.isFinite(stamp) || new Date(stamp).toISOString().slice(0, 10) !== value) {
    return fail("INVALID_DATE");
  }
  return stamp / DAY_MS;
}

function requireNonNegativeSafeInteger(value: number, code: string): bigint {
  if (!Number.isSafeInteger(value) || value < 0) return fail(code);
  return BigInt(value);
}

function requirePositiveSafeInteger(value: number, code: string): bigint {
  if (!Number.isSafeInteger(value) || value <= 0) return fail(code);
  return BigInt(value);
}

function compareId(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function isInEligibility(day: number, periods: Array<{start: number; end: number}>): boolean {
  for (const period of periods) {
    if (day < period.start) return false;
    if (day < period.end) return true;
  }
  return false;
}

/**
 * Computes daily closing capital in [cycleStart, cycleEndExclusive), then applies
 * daily eligibility windows. CONFIRMED events affect their effective day's close;
 * pending and reversed events do not change capital. Date-only arithmetic avoids
 * host timezone/DST drift. Caller must source eligibility and reconciliation from
 * its validated policy/data layer; this function is not an authenticator.
 */
export function calculateCapitalDaysV22(input: CapitalDaysInputV22): CapitalDaysResultV22 {
  if (input === null || typeof input !== "object" || !Array.isArray(input.members)) {
    return fail("INVALID_INPUT");
  }

  const start = dayNumber(input.cycleStart);
  const end = dayNumber(input.cycleEndExclusive);
  const startDate = new Date(start * DAY_MS);
  const targetYear = startDate.getUTCFullYear() + 1;
  const targetMonth = startDate.getUTCMonth();
  const targetDay = Math.min(
    startDate.getUTCDate(),
    new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate(),
  );
  const expectedEnd = Date.UTC(targetYear, targetMonth, targetDay) / DAY_MS;
  if (end !== expectedEnd || end - start > 366) return fail("INVALID_CYCLE_WINDOW");

  if (!Number.isSafeInteger(input.netProfitCents)) return fail("INVALID_NET_PROFIT_CENTS");
  const profit = BigInt(Math.max(0, input.netProfitCents));
  if (!Number.isInteger(input.adminShareBps) || input.adminShareBps < 0 || input.adminShareBps > 10000) {
    return fail("INVALID_ADMIN_SHARE_BPS");
  }

  const membershipIds = new Set<string>();
  const eventIds = new Set<string>();
  const prepared: Array<{
    membershipId: string;
    weight: bigint;
    deltas: Map<number, bigint>;
  }> = [];

  for (const member of input.members) {
    if (member === null || typeof member !== "object"
        || typeof member.membershipId !== "string"
        || member.membershipId.trim().length === 0
        || member.membershipId.length > 128
        || membershipIds.has(member.membershipId)
        || !Array.isArray(member.events)
        || !Array.isArray(member.eligibilityPeriods)) {
      return fail("INVALID_MEMBER");
    }
    membershipIds.add(member.membershipId);

    let openingBalance = requireNonNegativeSafeInteger(
      member.openingCapitalCents, "INVALID_OPENING_CAPITAL_CENTS",
    );
    const periods = member.eligibilityPeriods.map(period => {
      if (period === null || typeof period !== "object") return fail("INVALID_ELIGIBILITY_PERIOD");
      const periodStart = dayNumber(period.startDate);
      const periodEnd = dayNumber(period.endDateExclusive);
      if (periodStart < start || periodEnd > end || periodEnd <= periodStart) {
        return fail("INVALID_ELIGIBILITY_PERIOD");
      }
      return {start: periodStart, end: periodEnd};
    }).sort((a, b) => a.start - b.start || a.end - b.end);

    for (let i = 1; i < periods.length; i++) {
      if (periods[i].start < periods[i - 1].end) return fail("OVERLAPPING_ELIGIBILITY_PERIODS");
    }

    const deltas = new Map<number, bigint>();
    for (const event of member.events) {
      if (event === null || typeof event !== "object"
          || typeof event.eventId !== "string"
          || event.eventId.trim().length === 0
          || eventIds.has(event.eventId)
          || (event.kind !== "CONTRIBUTION" && event.kind !== "RESTITUTION")
          || (event.status !== "CONFIRMED" && event.status !== "PENDING" && event.status !== "REVERSED")) {
        return fail("INVALID_CAPITAL_EVENT");
      }
      eventIds.add(event.eventId);
      const day = dayNumber(event.effectiveDate);
      if (day < start || day >= end) return fail("CAPITAL_EVENT_OUTSIDE_CYCLE");
      const amount = requirePositiveSafeInteger(event.amountCents, "INVALID_CAPITAL_EVENT_AMOUNT");
      if (event.status === "CONFIRMED") {
        const signed = event.kind === "CONTRIBUTION" ? amount : -amount;
        deltas.set(day, (deltas.get(day) ?? 0n) + signed);
      }
    }

    let weight = 0n;
    for (let day = start; day < end; day++) {
      openingBalance += deltas.get(day) ?? 0n;
      if (openingBalance < 0n) return fail("RESTITUTION_EXCEEDS_CONFIRMED_CAPITAL");
      if (isInEligibility(day, periods)) weight += openingBalance;
    }
    prepared.push({membershipId: member.membershipId, weight, deltas});
  }

  const eligible = prepared.filter(member => member.weight > 0n);
  const totalWeight = eligible.reduce((sum, member) => sum + member.weight, 0n);
  const adminShare = (profit * BigInt(input.adminShareBps) + 5000n) / 10000n;
  const memberPool = profit - adminShare;
  const pendingPool = totalWeight === 0n ? memberPool : 0n;
  const shares = new Map<string, {base: bigint; remainder: bigint; bonus: boolean}>();

  for (const member of prepared) shares.set(member.membershipId, {base: 0n, remainder: 0n, bonus: false});

  if (totalWeight > 0n && memberPool > 0n) {
    for (const member of eligible) {
      const numerator = memberPool * member.weight;
      shares.set(member.membershipId, {
        base: numerator / totalWeight,
        remainder: numerator % totalWeight,
        bonus: false,
      });
    }
    const assigned = [...eligible].sort((a, b) => {
      const remA = shares.get(a.membershipId)!.remainder;
      const remB = shares.get(b.membershipId)!.remainder;
      return remA > remB ? -1 : remA < remB ? 1 : compareId(a.membershipId, b.membershipId);
    });
    const baseSum = assigned.reduce((sum, member) => sum + shares.get(member.membershipId)!.base, 0n);
    const residual = memberPool - baseSum;
    if (residual >= BigInt(assigned.length)) return fail("RESIDUAL_ALLOCATION_INVARIANT");
    for (let i = 0; i < Number(residual); i++) {
      const member = assigned[i];
      const share = shares.get(member.membershipId)!;
      shares.set(member.membershipId, {...share, bonus: true});
    }
  }

  const memberResults = prepared.map(member => {
    const share = shares.get(member.membershipId)!;
    const amount = share.base + (share.bonus ? 1n : 0n);
    return {
      membershipId: member.membershipId,
      eligibleCapitalDays: member.weight.toString(),
      baseShareCents: share.base.toString(),
      remainderNumerator: share.remainder.toString(),
      residualCentAssigned: share.bonus,
      memberShareCents: amount.toString(),
    };
  });

  const distributedMemberCents = memberResults.reduce((sum, member) => sum + BigInt(member.memberShareCents), 0n);
  if (adminShare + distributedMemberCents + pendingPool !== profit) return fail("DISTRIBUTION_CONSERVATION_FAILED");

  const residualCents = totalWeight > 0n && memberPool > 0n
    ? BigInt(memberResults.filter(member => member.residualCentAssigned).length)
    : 0n;

  return {
    calculation: "CAPITAL_DAYS_V2_SOURCE_ONLY",
    cycleStart: input.cycleStart,
    cycleEndExclusive: input.cycleEndExclusive,
    netProfitCents: profit.toString(),
    adminShareBps: input.adminShareBps,
    adminShareCents: adminShare.toString(),
    memberPoolCents: memberPool.toString(),
    memberPoolPendingCents: pendingPool.toString(),
    eligibleCapitalDaysTotal: totalWeight.toString(),
    residualCentsDistributed: residualCents.toString(),
    members: memberResults,
  };
}
