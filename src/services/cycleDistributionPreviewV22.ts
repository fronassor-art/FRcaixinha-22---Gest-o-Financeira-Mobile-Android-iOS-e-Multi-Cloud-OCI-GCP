import {
  calculateCapitalDaysFromProfitBasisV22,
  EligibleProfitBasisV22Error,
  type CapitalDaysFromProfitBasisInputV22,
  type CapitalDaysWithProfitBasisResultV22,
  type ProfitBasisLineV22,
} from "./eligibleProfitBasisV22";
import {
  CycleWindowV22Error,
  validateCycleWindowV22,
  type CycleWindowModeV22,
  type ExplicitCycleWindowAcceptanceV22,
} from "./cycleWindowV22";

export interface AcceptedCycleDistributionPolicyV22 {
  scope: {tenantId: string; cycleId: string};
  administratorId: string;
  administratorMembershipId: string | null;
  cycleStart: string;
  cycleEndExclusive: string;
  versionId: string;
  policyDigest: string;
  adminShareBps: number;
  accepted: boolean;
  acceptedAt: string;
  frozenAt: string;
  acceptanceEvidenceRef: string;
  cycleWindowMode?: CycleWindowModeV22;
}

export type CycleDistributionPreviewInputV22 =
  Omit<CapitalDaysFromProfitBasisInputV22,
    "adminShareBps" | "profitLines" | "cycleWindowAcceptance"> & {
    policy: AcceptedCycleDistributionPolicyV22;
    profitLines: ProfitBasisLineV22[];
  };

export type CycleDistributionEntitlementKindV22 =
  | "ADMINISTRATOR_COMPENSATION"
  | "MEMBER_PROFIT"
  | "PENDING_MEMBER_POOL";

export interface CycleDistributionEntitlementV22 {
  kind: CycleDistributionEntitlementKindV22;
  beneficiaryId: string | null;
  membershipId: string | null;
  amountCents: string;
}

export interface CycleDistributionPreviewV22 {
  preview: "CYCLE_DISTRIBUTION_SOURCE_ONLY";
  policyAttestation: "CALLER_SUPPLIED_NOT_AUTHENTICATED";
  executionAuthorized: false;
  policy: AcceptedCycleDistributionPolicyV22;
  entitlements: CycleDistributionEntitlementV22[];
  calculation: CapitalDaysWithProfitBasisResultV22;
}

export interface CycleDistributionPreviewEnvelopeV22 {
  envelope: "CYCLE_DISTRIBUTION_PREVIEW_ONLY";
  digestAlgorithm: "SHA-256";
  digest: string;
  result: CycleDistributionPreviewV22;
}

export class CycleDistributionPreviewV22Error extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "CycleDistributionPreviewV22Error";
  }
}

function fail(code: string): never {
  throw new CycleDistributionPreviewV22Error(code);
}

function validId(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 128
    && value === value.trim();
}

function validInstant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value;
}

function canonicalJson(value: unknown, ancestors: Set<object> = new Set()): string {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    const encoded = JSON.stringify(value);
    if (encoded === undefined) return fail("NON_CANONICAL_INPUT");
    return encoded;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return fail("NON_CANONICAL_INPUT");
    return JSON.stringify(value);
  }
  if (typeof value !== "object") return fail("NON_CANONICAL_INPUT");
  if (ancestors.has(value)) return fail("CYCLIC_CANONICAL_INPUT");
  ancestors.add(value);
  try {
    if (Array.isArray(value)) {
      return "[" + Array.from(value, item => item === undefined ? "null"
        : canonicalJson(item, ancestors)).join(",") + "]";
    }
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record).filter(key => record[key] !== undefined).sort();
    return "{" + keys
      .map(key => JSON.stringify(key) + ":" + canonicalJson(record[key], ancestors))
      .join(",") + "}";
  } finally {
    ancestors.delete(value);
  }
}

function validatePolicy(
  input: CycleDistributionPreviewInputV22,
): ExplicitCycleWindowAcceptanceV22 | undefined {
  const policy = input.policy;
  if (policy === null || typeof policy !== "object") return fail("INVALID_POLICY");
  if (!policy.scope || policy.scope.tenantId !== input.scope?.tenantId
      || policy.scope.cycleId !== input.scope?.cycleId) return fail("POLICY_SCOPE_MISMATCH");
  if (policy.cycleStart !== input.cycleStart
      || policy.cycleEndExclusive !== input.cycleEndExclusive) return fail("POLICY_CYCLE_MISMATCH");
  if (!validId(policy.administratorId)) return fail("INVALID_ADMINISTRATOR_ID");
  if (policy.administratorMembershipId !== null
      && !validId(policy.administratorMembershipId)) return fail("INVALID_ADMINISTRATOR_MEMBERSHIP_ID");
  if (!validId(policy.versionId)) return fail("INVALID_POLICY_VERSION");
  if (typeof policy.policyDigest !== "string" || !/^[a-f0-9]{64}$/.test(policy.policyDigest)) {
    return fail("INVALID_POLICY_DIGEST");
  }
  if (policy.accepted !== true) return fail("POLICY_NOT_ACCEPTED");
  if (!validInstant(policy.acceptedAt) || !validInstant(policy.frozenAt)
      || Date.parse(policy.acceptedAt) > Date.parse(policy.frozenAt)) {
    return fail("INVALID_POLICY_ACCEPTANCE_WINDOW");
  }
  if (typeof policy.adminShareBps !== "number" || !Number.isInteger(policy.adminShareBps)
      || policy.adminShareBps < 0 || policy.adminShareBps > 10000) {
    return fail("INVALID_ADMIN_SHARE_BPS");
  }
  if (typeof policy.acceptanceEvidenceRef !== "string"
      || policy.acceptanceEvidenceRef.trim().length === 0
      || policy.acceptanceEvidenceRef.length > 512
      || policy.acceptanceEvidenceRef !== policy.acceptanceEvidenceRef.trim()) {
    return fail("MISSING_POLICY_ACCEPTANCE_EVIDENCE");
  }
  if (policy.cycleWindowMode !== undefined
      && policy.cycleWindowMode !== "ANNIVERSARY_12_MONTH"
      && policy.cycleWindowMode !== "EXPLICIT_ACCEPTED_WINDOW") {
    return fail("INVALID_CYCLE_WINDOW_MODE");
  }
  const cycleWindowAcceptance = policy.cycleWindowMode === "EXPLICIT_ACCEPTED_WINDOW"
    ? {
      mode: "EXPLICIT_ACCEPTED_WINDOW" as const,
      scope: policy.scope,
      cycleStart: policy.cycleStart,
      cycleEndExclusive: policy.cycleEndExclusive,
      versionId: policy.versionId,
      policyDigest: policy.policyDigest,
      accepted: policy.accepted,
      acceptedAt: policy.acceptedAt,
      frozenAt: policy.frozenAt,
      acceptanceEvidenceRef: policy.acceptanceEvidenceRef,
    }
    : undefined;
  try {
    validateCycleWindowV22(
      input.scope, input.cycleStart, input.cycleEndExclusive, cycleWindowAcceptance,
    );
  } catch (error) {
    if (error instanceof CycleWindowV22Error) return fail(error.code);
    return fail("INVALID_CYCLE_WINDOW");
  }
  return cycleWindowAcceptance;
}

/**
 * Computes a review-only, source-only distribution preview. Policy evidence and
 * input records are caller-supplied; this function does not authenticate them,
 * persist a closing snapshot, authorize a beneficiary, or execute settlement.
 */
export function calculateCycleDistributionPreviewV22(
  input: CycleDistributionPreviewInputV22,
): CycleDistributionPreviewV22 {
  if (input === null || typeof input !== "object" || !Array.isArray(input.profitLines)
      || !Array.isArray(input.members)) return fail("INVALID_INPUT");
  const cycleWindowAcceptance = validatePolicy(input);
  const calculation = calculateCapitalDaysFromProfitBasisV22({
    scope: input.scope,
    cycleStart: input.cycleStart,
    cycleEndExclusive: input.cycleEndExclusive,
    cycleWindowAcceptance,
    adminShareBps: input.policy.adminShareBps,
    members: input.members,
    profitLines: input.profitLines,
  });
  const capital = calculation.capitalDays;
  const profit = BigInt(calculation.profitBasis.distributableNetProfitCents);
  const admin = BigInt(capital.adminShareCents);
  const memberPool = BigInt(capital.memberPoolCents);
  const pending = BigInt(capital.memberPoolPendingCents);
  const assigned = capital.members.reduce((sum, member) => sum + BigInt(member.memberShareCents), 0n);
  if (admin + memberPool !== profit || assigned + pending !== memberPool) {
    return fail("DISTRIBUTION_CONSERVATION_FAILED");
  }
  if ((BigInt(capital.eligibleCapitalDaysTotal) === 0n && pending !== memberPool)
      || (BigInt(capital.eligibleCapitalDaysTotal) > 0n && pending !== 0n)) {
    return fail("PENDING_POOL_INVARIANT_FAILED");
  }
  const membershipIds = new Set(capital.members.map(member => member.membershipId));
  if (input.policy.administratorMembershipId !== null
      && !membershipIds.has(input.policy.administratorMembershipId)) {
    return fail("ADMINISTRATOR_MEMBERSHIP_NOT_IN_CYCLE");
  }
  const entitlements: CycleDistributionEntitlementV22[] = [
    {
      kind: "ADMINISTRATOR_COMPENSATION",
      beneficiaryId: input.policy.administratorId,
      membershipId: input.policy.administratorMembershipId,
      amountCents: capital.adminShareCents,
    },
    ...capital.members.map(member => ({
      kind: "MEMBER_PROFIT" as const,
      beneficiaryId: member.membershipId,
      membershipId: member.membershipId,
      amountCents: member.memberShareCents,
    })),
  ];
  if (pending > 0n) {
    entitlements.push({
      kind: "PENDING_MEMBER_POOL",
      beneficiaryId: null,
      membershipId: null,
      amountCents: pending.toString(),
    });
  }
  const entitlementTotal = entitlements.reduce((sum, row) => sum + BigInt(row.amountCents), 0n);
  if (entitlementTotal !== profit) return fail("ENTITLEMENT_CONSERVATION_FAILED");
  return {
    preview: "CYCLE_DISTRIBUTION_SOURCE_ONLY",
    policyAttestation: "CALLER_SUPPLIED_NOT_AUTHENTICATED",
    executionAuthorized: false,
    policy: {...input.policy, scope: {...input.policy.scope}},
    entitlements,
    calculation,
  };
}

export async function createCycleDistributionPreviewEnvelopeV22(
  input: CycleDistributionPreviewInputV22,
): Promise<CycleDistributionPreviewEnvelopeV22> {
  const result = calculateCycleDistributionPreviewV22(input);
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return fail("CRYPTO_UNAVAILABLE");
  const digestInput = canonicalJson({algorithm: result.preview, input, result});
  const digestBytes = await subtle.digest("SHA-256", new TextEncoder().encode(digestInput));
  const digest = Array.from(new Uint8Array(digestBytes),
    byte => byte.toString(16).padStart(2, "0")).join("");
  return {envelope: "CYCLE_DISTRIBUTION_PREVIEW_ONLY", digestAlgorithm: "SHA-256", digest, result};
}
