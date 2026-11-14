/** FR Finance M39070: APK pricing and SaaS promotions source contract.
 * Offline validation only. Does not activate production accounts or payments.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const main = readFileSync('src/components/MasterLicensingView.tsx', 'utf8');
const campaigns = readFileSync('src/components/SaasPromotionsPanel.tsx', 'utf8');
const client = readFileSync('src/services/financialApiService.ts', 'utf8');
const backend = readFileSync('backend/app/routers/saas_promotions.py', 'utf8');
const master = readFileSync('backend/app/routers/master.py', 'utf8');

assert.match(main, /MasterSaasPromotionsPanel/);
assert.match(main, /NewAdminSaasOffersPanel/);
assert.match(main, /master-license-annual-price/);
assert.match(main, /setNewAnnualPrice/);
assert.match(main, /editingVersionId/);
assert.doesNotMatch(main, /roundCents\(newMonthlyPrice \* 10\)/);

assert.match(campaigns, /Criar rascunho \(sem publicar\)/);
assert.match(campaigns, /Publicar campanha no aplicativo/);
assert.match(campaigns, /Cancelar publicação/);
assert.match(campaigns, /fetchTenantSaasPromotions/);
assert.match(campaigns, /billing!=='OFF_NO_PROVIDER_NO_CHARGE'/);
assert.match(campaigns, /state\.currentTenantId|tenantId/);
assert.doesNotMatch(campaigns, /mercadopago|sendEmail|sendSMS|sendWhatsApp|sendPush/i);

assert.match(client, /createMasterSaasPromotionDraft/);
assert.match(client, /transitionMasterSaasPromotion/);
assert.match(client, /expected_version_id/);
assert.match(client, /\/api\/v1\/master\/saas-promotions/);
assert.match(client, /\/saas-promotions\`/);

assert.match(backend, /Depends\(require_master\)/);
assert.match(backend, /require_tenant_access\(tenant_id,session\)/);
assert.match(backend, /state='PUBLISHED'/);
assert.match(backend, /pg_advisory_xact_lock/);
assert.match(master, /status_code=409/);
assert.match(master, /annual_price: Decimal = Field/);
assert.match(master, /billing_status": "OFF_NO_PROVIDER_NO_CHARGE"/);
console.log('M39070_ANDROID_SAAS_MASTER_PRICE_PROMOTION_CONTRACT=PASS');
