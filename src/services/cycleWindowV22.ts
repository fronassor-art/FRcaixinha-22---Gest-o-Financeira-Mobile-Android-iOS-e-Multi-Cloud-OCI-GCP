/**
 * Validates the date window used by source-only cycle previews.
 * Twelve-month anniversary remains the default. Alternative dates require an
 * explicit, frozen, caller-supplied acceptance record bound to scope and policy.
 * This check does not authenticate that record or authorize financial execution.
 */
export type CycleWindowModeV22 = "ANNIVERSARY_12_MONTH" | "EXPLICIT_ACCEPTED_WINDOW";

export interface ExplicitCycleWindowAcceptanceV22 {
  mode: "EXPLICIT_ACCEPTED_WINDOW";
  scope: {tenantId: string; cycleId: string};
  cycleStart: string;
  cycleEndExclusive: string;
  versionId: string;
  policyDigest: string;
  accepted: boolean;
  acceptedAt: string;
  frozenAt: string;
  acceptanceEvidenceRef: string;
}

export class CycleWindowV22Error extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "CycleWindowV22Error";
  }
}

const DAY_MS = 86400000;
const DATE_ONLY = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;

function fail(code: string): never {
  throw new CycleWindowV22Error(code);
}

function validId(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 128
    && value === value.trim();
}

function validInstant(value: unknown): value is string {
  if (typeof value !== "string"
      || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}Z$/.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value;
}

export function civilDateDayNumberV22(value: unknown): number {
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

export function validateCycleWindowV22(
  scope: {tenantId: string; cycleId: string},
  cycleStart: unknown,
  cycleEndExclusive: unknown,
  acceptance?: ExplicitCycleWindowAcceptanceV22,
): {start: number; end: number} {
  if (scope === null || typeof scope !== "object"
      || !validId(scope.tenantId) || !validId(scope.cycleId)) return fail("INVALID_SCOPE");
  const start = civilDateDayNumberV22(cycleStart);
  const end = civilDateDayNumberV22(cycleEndExclusive);
  if (end <= start) return fail("INVALID_CYCLE_WINDOW");

  if (acceptance === undefined) {
    const year = Number(String(cycleStart).slice(0, 4)) + 1;
    if (year > 9999) return fail("INVALID_CYCLE_WINDOW");
    const month = Number(String(cycleStart).slice(5, 7)) - 1;
    const day = Number(String(cycleStart).slice(8, 10));
    const anniversaryDay = Math.min(day, new Date(Date.UTC(year, month + 1, 0)).getUTCDate());
    const anniversary = Date.UTC(year, month, anniversaryDay) / DAY_MS;
    if (end !== anniversary) return fail("INVALID_CYCLE_WINDOW");
    return {start, end};
  }

  if (acceptance === null || typeof acceptance !== "object"
      || acceptance.mode !== "EXPLICIT_ACCEPTED_WINDOW"
      || !acceptance.scope || acceptance.scope.tenantId !== scope.tenantId
      || acceptance.scope.cycleId !== scope.cycleId
      || acceptance.cycleStart !== cycleStart
      || acceptance.cycleEndExclusive !== cycleEndExclusive
      || !validId(acceptance.versionId)
      || typeof acceptance.policyDigest !== "string"
      || !/^[a-f0-9]{64}$/.test(acceptance.policyDigest)
      || acceptance.accepted !== true
      || !validInstant(acceptance.acceptedAt)
      || !validInstant(acceptance.frozenAt)
      || Date.parse(acceptance.acceptedAt) > Date.parse(acceptance.frozenAt)
      || typeof acceptance.acceptanceEvidenceRef !== "string"
      || acceptance.acceptanceEvidenceRef.length === 0
      || acceptance.acceptanceEvidenceRef.length > 512
      || acceptance.acceptanceEvidenceRef !== acceptance.acceptanceEvidenceRef.trim()) {
    return fail("INVALID_CYCLE_WINDOW_ACCEPTANCE");
  }
  return {start, end};
}
