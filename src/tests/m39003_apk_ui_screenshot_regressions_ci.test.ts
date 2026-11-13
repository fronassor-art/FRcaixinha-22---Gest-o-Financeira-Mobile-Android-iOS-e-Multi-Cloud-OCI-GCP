/** FR Finance M39003: visual issues observed on installed APK 237e1a5.
 * Pure source-contract checks; does not simulate a real authenticated session,
 * send mail, create invoices, move funds or certify HTTPS/OCI.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const registry=readFileSync('src/components/MasterTenantRegistryView.tsx','utf8');
const licensing=readFileSync('src/components/MasterLicensingView.tsx','utf8');
const backend=readFileSync('backend/app/routers/master.py','utf8');

assert.match(registry,/Convites e alterações de acesso exigem verificação de identidade/);
assert.match(registry,/nenhuma conta é criada, ativada ou suspensa aqui/);
assert.doesNotMatch(registry,/aguardam implementação e aprovação/);
assert.match(registry,/sem acesso a finanças dos membros/);
assert.match(registry,/state\.currentRole!=='MASTER'/);

assert.match(licensing,/htmlFor="master-license-monthly-price"/);
assert.match(licensing,/id="master-license-monthly-price"/);
assert.match(licensing,/inputMode="decimal"/);
assert.match(licensing,/step="0\.01"/);
assert.match(licensing,/min="0\\.01"/);
assert.match(licensing,/aria-describedby="master-license-price-help"/);
assert.match(licensing,/Preço da assinatura da plataforma/);
assert.match(licensing,/cujo mínimo é R\$ 150,00 por ciclo/);
assert.match(licensing,/id="master-license-annual-price"/);
assert.match(licensing,/setNewAnnualPrice/);
assert.doesNotMatch(licensing,/roundCents\\(newMonthlyPrice \\* 10\\)/);
assert.doesNotMatch(licensing,/Valor Anual Calculado Automaticamente/);
assert.match(licensing,/histórico imutável/);
assert.doesNotMatch(licensing,/LicensePriceVersion<\/code>/);
assert.match(licensing,/response\.status !== 'VERSION_PERSISTED_NO_BILLING'/);
assert.match(backend,/decimal_places=2/);

console.log('M39003_APK_VISUAL_COPY_PRICE_BOUNDARIES=PASS');
