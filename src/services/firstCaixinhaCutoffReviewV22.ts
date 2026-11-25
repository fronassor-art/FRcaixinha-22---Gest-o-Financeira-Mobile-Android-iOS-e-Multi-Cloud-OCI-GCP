import type {FirstCaixinhaCalendarDraftV1} from "./firstCaixinhaCalendarDraftV1";

export type FirstCaixinhaCutoffChoiceV22 =
  | "EXCLUDE_FINAL_PAYMENT_DATE"
  | "INCLUDE_FINAL_PAYMENT_DATE";

export interface FirstCaixinhaCutoffReviewV22 {
  readonly scope: "OWNER_FIRST_CAIXINHA_ONLY";
  readonly status: "NO_OPTION_SELECTED" | "TEMPORARY_PREVIEW_ONLY";
  readonly choice: FirstCaixinhaCutoffChoiceV22 | null;
  readonly capitalDaysStartInclusive: string;
  readonly capitalDaysEndExclusive: string | null;
  readonly capitalDaysCalendarDays: number | null;
  readonly finalPaymentDate: string;
  readonly finalPaymentDateIncluded: boolean | null;
  readonly acceptanceRecorded: false;
  readonly persisted: false;
  readonly financialCalculationEnabled: false;
  readonly cycleOpeningEnabled: false;
}

const DAY_MS = 86400000;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

function dayNumber(value: unknown): number {
  if (typeof value !== "string" || !DATE_ONLY.test(value)) {
    throw new Error("INVALID_FIRST_CAIXINHA_REVIEW_DATE");
  }
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  if (year < 1000 || month < 1 || month > 12 || day < 1 || day > 31) {
    throw new Error("INVALID_FIRST_CAIXINHA_REVIEW_DATE");
  }
  const stamp = Date.UTC(year, month - 1, day);
  if (!Number.isFinite(stamp) || new Date(stamp).toISOString().slice(0, 10) !== value) {
    throw new Error("INVALID_FIRST_CAIXINHA_REVIEW_DATE");
  }
  return stamp / DAY_MS;
}

function addCivilDay(value: string): string {
  return new Date((dayNumber(value) + 1) * DAY_MS).toISOString().slice(0, 10);
}

function isFirstCaixinhaDraft(value: unknown): value is FirstCaixinhaCalendarDraftV1 {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const draft = value as Record<string, unknown>;
  const disabled = [
    "cycleOpeningEnabled",
    "contractAcceptanceEnabled",
    "realInvitationsEnabled",
    "saasBillingEnabled",
    "memberContributionsEnabled",
    "financialExecutionEnabled",
  ];
  return draft.scope === "OWNER_FIRST_CAIXINHA_ONLY"
    && draft.status === "DRAFT_UNBOUND_TO_TENANT"
    && draft.cycleStart === "2026-12-10"
    && draft.firstContributionDate === "2026-12-10"
    && draft.lastContributionDate === "2027-11-10"
    && draft.closeAndFinalPaymentDate === "2027-12-20"
    && draft.contributionDueDay === 10
    && draft.contributionCount === 12
    && Array.isArray(draft.contributionDates)
    && draft.contributionDates.length === 12
    && draft.timezone === "America/Belem"
    && draft.capitalDaysEndExclusive === null
    && draft.capitalDaysCutoffResolved === false
    && disabled.every(key => draft[key] === false);
}

/**
 * M41020: compare the two possible interval boundaries for the first cashbox.
 * The choice is ephemeral and cannot accept, persist, open, or calculate finance.
 */
export function previewFirstCaixinhaCutoffV22(
  draftInput: unknown,
  choiceInput: unknown,
): FirstCaixinhaCutoffReviewV22 {
  if (!isFirstCaixinhaDraft(draftInput)) {
    throw new Error("INVALID_FIRST_CAIXINHA_DRAFT");
  }
  if (choiceInput !== null
      && choiceInput !== "EXCLUDE_FINAL_PAYMENT_DATE"
      && choiceInput !== "INCLUDE_FINAL_PAYMENT_DATE") {
    throw new Error("INVALID_FIRST_CAIXINHA_CUTOFF_CHOICE");
  }

  const start = draftInput.cycleStart;
  const finalPaymentDate = draftInput.closeAndFinalPaymentDate;
  const startDay = dayNumber(start);
  const paymentDay = dayNumber(finalPaymentDate);
  if (paymentDay <= startDay) throw new Error("INVALID_FIRST_CAIXINHA_REVIEW_RANGE");

  if (choiceInput === null) {
    return {
      scope: "OWNER_FIRST_CAIXINHA_ONLY",
      status: "NO_OPTION_SELECTED",
      choice: null,
      capitalDaysStartInclusive: start,
      capitalDaysEndExclusive: null,
      capitalDaysCalendarDays: null,
      finalPaymentDate,
      finalPaymentDateIncluded: null,
      acceptanceRecorded: false,
      persisted: false,
      financialCalculationEnabled: false,
      cycleOpeningEnabled: false,
    };
  }

  const finalPaymentDateIncluded = choiceInput === "INCLUDE_FINAL_PAYMENT_DATE";
  const endExclusive = finalPaymentDateIncluded ? addCivilDay(finalPaymentDate) : finalPaymentDate;
  const endDay = dayNumber(endExclusive);
  if (endDay <= startDay) throw new Error("INVALID_FIRST_CAIXINHA_REVIEW_RANGE");

  return {
    scope: "OWNER_FIRST_CAIXINHA_ONLY",
    status: "TEMPORARY_PREVIEW_ONLY",
    choice: choiceInput,
    capitalDaysStartInclusive: start,
    capitalDaysEndExclusive: endExclusive,
    capitalDaysCalendarDays: endDay - startDay,
    finalPaymentDate,
    finalPaymentDateIncluded,
    acceptanceRecorded: false,
    persisted: false,
    financialCalculationEnabled: false,
    cycleOpeningEnabled: false,
  };
}
