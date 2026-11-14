import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const ui=readFileSync('src/components/MasterLicensingView.tsx','utf8');
const sql=readFileSync('backend/migrations/017_saas_payment_activation.sql','utf8');
const catalog=readFileSync('backend/migrations/011_platform_license_catalog.sql','utf8');
for(const x of [
 'currentEssencialPrice?.monthly_price',
 'currentInterPrice?.monthly_price',
 'Number.isFinite(essentialMonthly)',
 'Number.isFinite(intermediateMonthly)',
 'illustrativeMonthlyDelta',
 'catálogo PostgreSQL',
 'não é uma proposta de cobrança',
 'Valor pro-rata a pagar: não calculado',
 'Sem esses documentos, nenhum valor devido',
])
 assert(ui.includes(x),x);
for(const x of ["calculateLicenseUpgradeProRata(", "new Date('2026-10-16')",
 "new Date('2027-10-16')", "Valor Pro-Rata Devido:", "useState<number>(89.90)"])
 assert(!ui.includes(x),x);
assert(sql.includes("saas_license_entitlements"));
assert(catalog.includes("platform_license_price_versions"));
assert(ui.includes("Nenhuma cobrança ou assinatura foi alterada."));
console.log('M37451_MASTER_NO_FICTITIOUS_PRORATA_LICENSE=PASS');
