/**
 * M41030 — intervalo civil entre a última contribuição e o encerramento
 * informado para a primeira caixinha. É uma prévia sem efeitos financeiros.
 */
import {
  buildFirstCaixinhaCalendarDraftV1,
  type FirstCaixinhaCalendarDraftV1,
} from "./firstCaixinhaCalendarDraftV1";

export interface FirstCaixinhaCloseIntervalPreviewV22 {
  readonly scope: "OWNER_FIRST_CAIXINHA_ONLY";
  readonly status: "READ_ONLY_CALENDAR_INTERVAL";
  readonly lastContributionDate: string;
  readonly closeAndFinalPaymentDate: string;
  /** Difference between date-only values, independent of local clock/DST. */
  readonly elapsedCalendarDaysBetweenDates: number;
  readonly capitalDaysCutoffResolved: false;
  readonly acceptanceRecorded: false;
  readonly persisted: false;
  readonly cycleOpeningEnabled: false;
  readonly financialCalculationEnabled: false;
}

const DAY_MS = 86400000;
const canonical = buildFirstCaixinhaCalendarDraftV1();

function isCanonicalDraft(value: unknown): value is FirstCaixinhaCalendarDraftV1 {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  try {
    const draft = value as Record<string, unknown>;
    const dates = draft.contributionDates;
    if (!Array.isArray(dates) || dates.length !== canonical.contributionDates.length) return false;
    const flags = [
      "cycleOpeningEnabled",
      "contractAcceptanceEnabled",
      "realInvitationsEnabled",
      "saasBillingEnabled",
      "memberContributionsEnabled",
      "financialExecutionEnabled",
    ];
    return draft.scope === canonical.scope
      && draft.status === canonical.status
      && draft.cycleStart === canonical.cycleStart
      && draft.firstContributionDate === canonical.firstContributionDate
      && draft.lastContributionDate === canonical.lastContributionDate
      && draft.closeAndFinalPaymentDate === canonical.closeAndFinalPaymentDate
      && draft.contributionDueDay === canonical.contributionDueDay
      && draft.contributionCount === canonical.contributionCount
      && draft.timezone === canonical.timezone
      && draft.capitalDaysEndExclusive === null
      && draft.capitalDaysCutoffResolved === false
      && canonical.contributionDates.every((date, index) => dates[index] === date)
      && flags.every((key) => draft[key] === false);
  } catch {
    return false;
  }
}

function dayNumber(value: unknown): number {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error("INVALID_FIRST_CAIXINHA_INTERVAL_DATE");
  }
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  if (year < 1000 || month < 1 || month > 12 || day < 1 || day > 31) {
    throw new Error("INVALID_FIRST_CAIXINHA_INTERVAL_DATE");
  }
  const stamp = Date.UTC(year, month - 1, day);
  if (!Number.isFinite(stamp) || new Date(stamp).toISOString().slice(0, 10) !== value) {
    throw new Error("INVALID_FIRST_CAIXINHA_INTERVAL_DATE");
  }
  return stamp / DAY_MS;
}

/**
 * Only describes the difference between the two supplied civil dates.
 * It does not interpret Capital-Days inclusion or create payment events.
 */
export function previewFirstCaixinhaCloseIntervalV22(
  draftInput: unknown,
): FirstCaixinhaCloseIntervalPreviewV22 {
  if (!isCanonicalDraft(draftInput)) {
    throw new Error("INVALID_FIRST_CAIXINHA_DRAFT");
  }
  const start = dayNumber(draftInput.lastContributionDate);
  const end = dayNumber(draftInput.closeAndFinalPaymentDate);
  if (end <= start) throw new Error("INVALID_FIRST_CAIXINHA_INTERVAL_RANGE");

  return {
    scope: "OWNER_FIRST_CAIXINHA_ONLY",
    status: "READ_ONLY_CALENDAR_INTERVAL",
    lastContributionDate: draftInput.lastContributionDate,
    closeAndFinalPaymentDate: draftInput.closeAndFinalPaymentDate,
    elapsedCalendarDaysBetweenDates: end - start,
    capitalDaysCutoffResolved: false,
    acceptanceRecorded: false,
    persisted: false,
    cycleOpeningEnabled: false,
    financialCalculationEnabled: false,
  };
}
