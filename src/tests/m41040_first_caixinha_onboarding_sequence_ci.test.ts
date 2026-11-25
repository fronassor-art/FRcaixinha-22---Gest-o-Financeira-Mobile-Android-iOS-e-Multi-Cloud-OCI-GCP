import assert from "node:assert/strict";
import React from "react";
import {readFileSync} from "node:fs";
import {renderToStaticMarkup} from "react-dom/server";
import {FirstCaixinhaCalendarDraftPanel} from "../components/FirstCaixinhaCalendarDraftPanel";
import {
  FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1,
  FIRST_CAIXINHA_REQUIREMENT_STAGES_V1,
} from "../services/firstCaixinhaOnboardingSequenceV1";

const expectedStepIds = [
  "MASTER_INVITES_ADMIN",
  "ADMIN_REGISTERS",
  "ADMIN_ACCEPTS_CONTRACT_A",
  "ADMIN_PAYS_SAAS",
  "ADMIN_CONFIGURES_AND_ACCEPTS_CONTRACT_B",
  "ADMIN_INVITES_MEMBERS",
  "MEMBERS_REGISTER_AND_ACCEPT_CONTRACT_B",
  "MEMBERS_PAY_CONTRIBUTIONS",
  "ADMIN_CLOSES_CYCLE",
] as const;
assert.deepEqual(FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1.map((step) => step.id), expectedStepIds);
assert.deepEqual(FIRST_CAIXINHA_REQUIREMENT_STAGES_V1, [
  "01_SCOPE", "02_CODE", "03_UNIT", "04_SECURITY", "05_E2E", "06_EXTERNAL", "07_SIGNOFF",
]);
assert.equal(Object.isFrozen(FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1), true);

for (const step of FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1) {
  assert.equal(step.status, "BLOCKED_SOURCE_ONLY");
  assert.equal(step.actionEnabled, false);
  assert.equal(step.acceptanceRecorded, false);
  assert.equal(step.persisted, false);
  assert.ok(step.requirementIds.length > 0);
  assert.ok(step.releaseGateIds.length > 0);
  assert.ok(step.blocker.length > 0);
  assert.equal(Object.isFrozen(step), true);
  assert.equal(Object.isFrozen(step.requirementIds), true);
  assert.equal(Reflect.set(step, "status", "READY"), false);
  assert.equal(step.requirementIds.every((id) => /^CP26-\d{4}$/.test(id)), true);
}

const matrix = JSON.parse(readFileSync(
  "docs/FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.json", "utf8",
));
assert.equal(matrix.counts.expanded_total, 330);
assert.equal(matrix.items.length, 330);
type MatrixRequirementRow = {
  check_id: string;
  production_verified: boolean;
  acceptance_state: string;
};
const rows = new Map<string, MatrixRequirementRow>();
for (const row of matrix.items as MatrixRequirementRow[]) {
  rows.set(row.check_id, row);
}
const referencedRequirements = new Set(
  FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1.flatMap((step) => step.requirementIds),
);
for (const requirementId of referencedRequirements) {
  const row = rows.get(requirementId);
  assert.ok(row, `Missing stable requirement ID: ${requirementId}`);
  assert.equal(row.production_verified, false, `${requirementId} cannot be promoted by this package`);
  assert.equal(row.acceptance_state, "PENDING_INDEPENDENT_EVIDENCE");
}

const byId = new Map(FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1.map((step) => [step.id, step]));
assert.ok(expectedStepIds.indexOf("MASTER_INVITES_ADMIN") < expectedStepIds.indexOf("ADMIN_REGISTERS"));
assert.ok(expectedStepIds.indexOf("ADMIN_REGISTERS") < expectedStepIds.indexOf("ADMIN_ACCEPTS_CONTRACT_A"));
assert.ok(expectedStepIds.indexOf("ADMIN_ACCEPTS_CONTRACT_A") < expectedStepIds.indexOf("ADMIN_PAYS_SAAS"));
assert.ok(expectedStepIds.indexOf("ADMIN_PAYS_SAAS") < expectedStepIds.indexOf("ADMIN_CONFIGURES_AND_ACCEPTS_CONTRACT_B"));
assert.ok(expectedStepIds.indexOf("ADMIN_CONFIGURES_AND_ACCEPTS_CONTRACT_B") < expectedStepIds.indexOf("ADMIN_INVITES_MEMBERS"));
assert.ok(expectedStepIds.indexOf("ADMIN_INVITES_MEMBERS") < expectedStepIds.indexOf("MEMBERS_REGISTER_AND_ACCEPT_CONTRACT_B"));
assert.ok(expectedStepIds.indexOf("MEMBERS_REGISTER_AND_ACCEPT_CONTRACT_B") < expectedStepIds.indexOf("MEMBERS_PAY_CONTRIBUTIONS"));
assert.equal(byId.get("ADMIN_PAYS_SAAS")?.requirementIds.includes("CP26-0006"), true);
assert.equal(byId.get("ADMIN_PAYS_SAAS")?.requirementIds.includes("CP26-0007"), false);
assert.equal(byId.get("MEMBERS_PAY_CONTRIBUTIONS")?.requirementIds.includes("CP26-0007"), true);

const html = renderToStaticMarkup(React.createElement(FirstCaixinhaCalendarDraftPanel));
assert.match(html, /Ver as 9 etapas e os bloqueios/);
assert.match(html, /Master: Convidar o administrador/);
assert.match(html, /Revisar e aceitar o Contrato A/);
assert.match(html, /Pagar a licença SaaS/);
assert.match(html, /aceitar o Contrato B/);
assert.match(html, /Convidar os membros/);
assert.match(html, /Pagar as cotas da caixinha/);
assert.match(html, /20\/12\/2027/);
assert.match(html, /Bloqueado nesta versão/);
assert.doesNotMatch(html, /<button\b|<form\b/i);

const panelSource = readFileSync("src/components/FirstCaixinhaCalendarDraftPanel.tsx", "utf8");
const sequenceSource = readFileSync(
  "src/services/firstCaixinhaOnboardingSequenceV1.ts", "utf8",
);
assert.doesNotMatch(
  panelSource + sequenceSource,
  /fetch\s*\(|localStorage|financialApi|createCycle|createInvite|sendInvite|createPayment/i,
);
assert.doesNotMatch(JSON.stringify(FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1), /15%|85%/);
console.log("M41040_FIRST_CAIXINHA_ONBOARDING_SEQUENCE=PASS_SOURCE_ONLY_NO_GO");
