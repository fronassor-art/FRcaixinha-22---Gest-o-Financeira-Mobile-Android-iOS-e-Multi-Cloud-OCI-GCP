/** FR Finance M39070: APK pricing and SaaS promotions source contract.
 * Offline validation only. Does not activate production accounts or payments.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import { MASTER_CAMPAIGN_WRITES_RELEASED, campaignScheduleLabel } from '../services/masterSaasCampaignSchedule';

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

const scheduled = {state:'PUBLISHED', starts_at:'2026-12-01T12:00:00Z', ends_at:'2026-12-02T12:00:00Z'};
const start = Date.parse(scheduled.starts_at), end = Date.parse(scheduled.ends_at);
assert.equal(MASTER_CAMPAIGN_WRITES_RELEASED, false);
assert.equal(campaignScheduleLabel(scheduled,start-1),'Agendada');
assert.equal(campaignScheduleLabel(scheduled,start),'Dentro da vigência');
assert.equal(campaignScheduleLabel(scheduled,end-1),'Dentro da vigência');
assert.equal(campaignScheduleLabel(scheduled,end),'Encerrada');
assert.equal(campaignScheduleLabel({...scheduled,state:'DRAFT'},start),'Rascunho');
assert.equal(campaignScheduleLabel({...scheduled,state:'CANCELED'},start),'Cancelada');
assert.equal(campaignScheduleLabel({...scheduled,state:'UNKNOWN'},start),'Não confirmada');
assert.equal(campaignScheduleLabel({...scheduled,ends_at:scheduled.starts_at},start),'Não confirmada');
assert.equal(campaignScheduleLabel({...scheduled,starts_at:'2026-12-01T12:00:00'},start),'Não confirmada');
assert.equal(campaignScheduleLabel(scheduled,NaN),'Não confirmada');
assert.match(campaigns,/if \(!MASTER_CAMPAIGN_WRITES_RELEASED\)/);
assert.match(campaigns,/if \(!MASTER_CAMPAIGN_WRITES_RELEASED \|\| !actorId/);
assert.equal((campaigns.match(/disabled=\{!MASTER_CAMPAIGN_WRITES_RELEASED/g)||[]).length,3);
assert.match(campaigns,/relógio do aparelho; não confirma elegibilidade/);
console.log('M40952_MASTER_CAMPAIGN_LOCAL_READ_ONLY=PASS');
