/**
 * M41000 — calendário planejado da primeira caixinha do proprietário.
 * Datas civis; nenhuma obrigação, ciclo ou pagamento é criado.
 */
export interface FirstCaixinhaCalendarDraftV1 {
  readonly scope: "OWNER_FIRST_CAIXINHA_ONLY";
  readonly status: "DRAFT_UNBOUND_TO_TENANT";
  readonly cycleStart: string;
  readonly firstContributionDate: string;
  readonly lastContributionDate: string;
  readonly closeAndFinalPaymentDate: string;
  readonly contributionDueDay: number;
  readonly contributionDates: readonly string[];
  readonly contributionCount: number;
  readonly timezone: "America/Belem";
  readonly capitalDaysEndExclusive: null;
  readonly capitalDaysCutoffResolved: false;
  readonly cycleOpeningEnabled: false;
  readonly contractAcceptanceEnabled: false;
  readonly realInvitationsEnabled: false;
  readonly saasBillingEnabled: false;
  readonly memberContributionsEnabled: false;
  readonly financialExecutionEnabled: false;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function validateCivilDate(value: string): void {
  if (typeof value !== "string" || !ISO_DATE.test(value)) throw new Error("INVALID_CIVIL_DATE");
  const year=Number(value.slice(0,4)), month=Number(value.slice(5,7)), day=Number(value.slice(8,10));
  if (year<1000||month<1||month>12||day<1||day>31) throw new Error("INVALID_CIVIL_DATE");
  const stamp=Date.UTC(year,month-1,day);
  if (!Number.isFinite(stamp)||new Date(stamp).toISOString().slice(0,10)!==value) {
    throw new Error("INVALID_CIVIL_DATE");
  }
}

/** Generates monthly dates from an explicit anchor without local-time drift. */
export function buildMonthlyDueDates(firstDueDate:string,lastDueDate:string,dueDay:number):string[] {
  validateCivilDate(firstDueDate);
  validateCivilDate(lastDueDate);
  if (!Number.isInteger(dueDay)||dueDay<1||dueDay>28) throw new Error("INVALID_DUE_DAY");
  if (firstDueDate>lastDueDate||Number(firstDueDate.slice(8,10))!==dueDay
      ||Number(lastDueDate.slice(8,10))!==dueDay) throw new Error("INVALID_DUE_DATE_RANGE");

  let year=Number(firstDueDate.slice(0,4)),month=Number(firstDueDate.slice(5,7));
  const dates:string[]=[];
  for(let index=0;index<24;index+=1){
    const candidate=String(year).padStart(4,"0")+"-"+String(month).padStart(2,"0")
      +"-"+String(dueDay).padStart(2,"0");
    if(candidate>lastDueDate)break;
    dates.push(candidate);
    if(month===12){year+=1;month=1;}else month+=1;
  }
  if(dates.length===0||dates[dates.length-1]!==lastDueDate) {
    throw new Error("LAST_DUE_DATE_NOT_ON_MONTHLY_CADENCE");
  }
  return dates;
}

/**
 * Exact dates requested for the owner's first caixinha.
 * 20/12 is not converted into an exclusive Capital-Days cutoff.
 */
export function buildFirstCaixinhaCalendarDraftV1():FirstCaixinhaCalendarDraftV1 {
  const cycleStart="2026-12-10";
  const firstContributionDate="2026-12-10";
  const lastContributionDate="2027-11-10";
  const closeAndFinalPaymentDate="2027-12-20";
  for(const value of [cycleStart,firstContributionDate,lastContributionDate,closeAndFinalPaymentDate]) {
    validateCivilDate(value);
  }
  if(cycleStart>firstContributionDate||firstContributionDate>lastContributionDate
      ||lastContributionDate>=closeAndFinalPaymentDate) throw new Error("INVALID_FIRST_CAIXINHA_ORDER");
  const contributionDates=buildMonthlyDueDates(firstContributionDate,lastContributionDate,10);
  if(contributionDates.length!==12)throw new Error("FIRST_CAIXINHA_REQUIRES_TWELVE_CONTRIBUTION_DATES");
  return {
    scope:"OWNER_FIRST_CAIXINHA_ONLY",status:"DRAFT_UNBOUND_TO_TENANT",
    cycleStart,firstContributionDate,lastContributionDate,closeAndFinalPaymentDate,
    contributionDueDay:10,contributionDates,contributionCount:contributionDates.length,
    timezone:"America/Belem",capitalDaysEndExclusive:null,capitalDaysCutoffResolved:false,
    cycleOpeningEnabled:false,contractAcceptanceEnabled:false,realInvitationsEnabled:false,
    saasBillingEnabled:false,memberContributionsEnabled:false,financialExecutionEnabled:false,
  };
}
