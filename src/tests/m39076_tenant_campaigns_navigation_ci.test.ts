/** FR Finance M39076 — integração segura de campanhas do administrador e oportunidades do membro.
 * Teste totalmente offline: não abre PG18, API, sessões nem cria crédito/Pix.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {initialRoleTab, isRoleTabAllowed, tabsAllowedToRole} from '../services/roleScope';
import {startTabHistory, visitTab} from '../services/tabHistory';

const app=readFileSync('src/App.tsx','utf8');
const dash=readFileSync('src/components/DashboardView.tsx','utf8');
const form=readFileSync('src/components/SpecialCreditView.tsx','utf8');
const api=readFileSync('backend/app/routers/special_credit.py','utf8');
const manifest=readFileSync('backend/migrations/110_fr_finance_special_credit_offline.sql','utf8');
const integrity=readFileSync('backend/migrations/111_frfinance_special_credit_integrity_guards.sql','utf8');
const config=readFileSync('.github/workflows/frfinance-android-debug-m39050.yml','utf8');

const admin='CAMPANHAS_MEMBROS';
const member='MINHAS_OPORTUNIDADES';

assert(isRoleTabAllowed('TENANT_ADMIN',admin));
assert(!isRoleTabAllowed('TENANT_ADMIN',member));
assert(isRoleTabAllowed('TENANT_MEMBER',member));
assert(!isRoleTabAllowed('TENANT_MEMBER',admin));
assert(!isRoleTabAllowed('MASTER',admin));
assert(!isRoleTabAllowed('MASTER',member));
assert(!tabsAllowedToRole('MASTER').includes(admin));
assert(!tabsAllowedToRole('MASTER').includes(member));
assert.equal(initialRoleTab('TENANT_ADMIN'),'DASHBOARD');
assert.equal(initialRoleTab('TENANT_MEMBER'),'MEU_PAINEL');
for(const role of ['MASTER','TENANT_ADMIN','TENANT_MEMBER'] as const){
  const permitted=role==='TENANT_ADMIN'?admin:role==='TENANT_MEMBER'?member:'LICENCAS';
  const forbidden=role==='TENANT_ADMIN'?member:admin;
  const first=startTabHistory(initialRoleTab(role));
  assert.equal(visitTab(first,permitted,tab=>isRoleTabAllowed(role,tab)).entries.length,2);
  assert.equal(visitTab(first,forbidden,tab=>isRoleTabAllowed(role,tab)),first);
}

assert(app.includes("import { SpecialCreditView } from './components/SpecialCreditView';"));
assert(app.includes("{ id: 'CAMPANHAS_MEMBROS', label: 'Campanhas para Membros'"));
assert(app.includes("{ id: 'MINHAS_OPORTUNIDADES', label: 'Minhas Oportunidades'"));
assert.match(app,/visibleTab === 'CAMPANHAS_MEMBROS' && state\.currentRole === 'TENANT_ADMIN' && \(\s*<SpecialCreditView state=\{state\}\/>/);
assert.match(app,/visibleTab === 'MINHAS_OPORTUNIDADES' && state\.currentRole === 'TENANT_MEMBER' && \(\s*<SpecialCreditView state=\{state\}\/>/);
assert.match(app,/isRoleTabAllowed\(state\.currentRole, activeTab\)/);
assert.match(app,/navItems\.slice\(3\)\.map/);
assert.match(app,/setMoreOpen\(false\); if\(item\.id === 'AUDITORIA'\)/);
assert.match(app,/resumeValidationPending && \(/);
assert.match(app,/inert=\{resumeValidationPending\}/);

assert.match(dash,/onNavigateTab\(member \? 'MINHAS_OPORTUNIDADES' : 'CAMPANHAS_MEMBROS'\)/);
assert(dash.includes("member ? 'Minhas oportunidades' : 'Campanhas para membros'"));
assert.match(form,/if\(role==='MASTER'\) return null;/);
assert.match(form,/role==='TENANT_ADMIN'\?'Crédito Especial • Campanhas':'Minhas Oportunidades de Crédito'/);
assert.match(form,/role==='TENANT_ADMIN'&&tenant/);
assert.match(form,/role==='TENANT_MEMBER'&&tenant/);
assert.match(form,/if\(!cap\.sandbox_enabled\) throw new Error/);
assert.match(form,/specialCreditApi\.grant\(/);
assert.match(form,/specialCreditApi\.createCampaign\(/);
assert.match(form,/specialCreditApi\.opportunities\(/);
assert.match(form,/specialCreditApi\.reply\(/);
assert.match(form,/Push, e-mail, WhatsApp, SMS e Pix reais não são enviados/);
assert.match(api,/FR_FINANCE_SPECIAL_CREDIT_SANDBOX/);
assert.match(api,/os\.getenv\("FR_FINANCE_SPECIAL_CREDIT_SANDBOX"\) == "YES"/);
assert.match(api,/_authorize\(tenant_id, session, "TENANT_ADMIN"\)/);
assert.match(api,/_authorize\(tenant_id, session, "TENANT_MEMBER"\)/);
assert.match(api,/pix_real_enabled": False/);
assert(manifest.includes('FORCE ROW LEVEL SECURITY'));
assert(integrity.includes('special_credit_campaigns'));
assert(config.includes('FR_FINANCE_SPECIAL_CREDIT_SANDBOX: "NO"'));
assert(config.includes('FR_FINANCE_PIX_REAL: "OFF"'));

console.log('M39076_ADMIN_MEMBER_CAMPAIGNS_NAVIGATION=PASS');
console.log('M39076_MASTER_TENANT_ISOLATION=PASS');
console.log('M39076_CREDIT_SANDBOX_GATE_NOT_BYPASSED=PASS');
console.log('M39076_DATABASE_WRITES=NONE');
console.log('M39076_REAL_PIX=OFF');
