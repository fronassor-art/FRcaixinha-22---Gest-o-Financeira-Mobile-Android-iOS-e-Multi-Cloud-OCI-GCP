import {
  calculateCapitalDaysFromProfitBasisV22,
  EligibleProfitBasisV22Error,
  type CapitalDaysFromProfitBasisInputV22,
  type CapitalDaysWithProfitBasisResultV22,
  type ProfitBasisLineV22,
} from "./eligibleProfitBasisV22";

export interface AcceptedCycleDistributionPolicyV22 {
  scope: {tenantId: string; cycleId: string};
  cycleStart: string;
  cycleEndExclusive: string;
  versionId: string;
  policyDigest: string;
  adminShareBps: number;
  accepted: boolean;
  acceptedAt: string;
  frozenAt: string;
  acceptanceEvidenceRef: string;
}

export type CycleDistributionPreviewInputV22 =
  Omit<CapitalDaysFromProfitBasisInputV22, "adminShareBps" | "profitLines"> & {
    policy: AcceptedCycleDistributionPolicyV22;
    profitLines: ProfitBasisLineV22[];
  };

export interface CycleDistributionPreviewV22 {
  preview: "CYCLE_DISTRIBUTION_SOURCE_ONLY";
  policyAttestation: "CALLER_SUPPLIED_NOT_AUTHENTICATED";
  executionAuthorized: false;
  policy: AcceptedCycleDistributionPolicyV22;
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

function canonicalJson(value: unknown): string {
  if (value === null || typeof value === "string" || typeof value === "boolean"
      || typeof value === "number") {
    const encoded = JSON.stringify(value);
    if (encoded === undefined) return fail("NON_CANONICAL_INPUT");
    return encoded;
  }
  if (typeof value === "number" && !Number.isFinite(value)) return fail("NON_CANONICAL_INPUT");
  if (Array.isArray(value)) {
    return "[" + Array.from(value, item => item === undefined ? "null" : canonicalJson(item)).join(",") + "]";
  }
  if (typeof value !== "object") return fail("NON_CANONICAL_INPUT");
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).filter(key => record[key] !== undefined).sort();
  return "{" + keys
    .map(key => JSON.stringify(key) + ":" + canonicalJson(record[key]))
    .join(",") + "}";
}

function validatePolicy(input: CycleDistributionPreviewInputV22): void {
  const policy = input.policy;
  if (policy === null || typeof policy !== "object") return fail("INVALID_POLICY");
  if (!policy.scope || policy.scope.tenantId !== input.scope?.tenantId
      || policy.scope.cycleId !== input.scope?.cycleId) return fail("POLICY_SCOPE_MISMATCH");
  if (policy.cycleStart !== input.cycleStart
      || policy.cycleEndExclusive !== input.cycleEndExclusive) return fail("POLICY_CYCLE_MISMATCH");
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
  validatePolicy(input);
  const calculation = calculateCapitalDaysFromProfitBasisV22({
    scope: input.scope,
    cycleStart: input.cycleStart,
    cycleEndExclusive: input.cycleEndExclusive,
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
  return {
    preview: "CYCLE_DISTRIBUTION_SOURCE_ONLY",
    policyAttestation: "CALLER_SUPPLIED_NOT_AUTHENTICATED",
    executionAuthorized: false,
    policy: {...input.policy, scope: {...input.policy.scope}},
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
