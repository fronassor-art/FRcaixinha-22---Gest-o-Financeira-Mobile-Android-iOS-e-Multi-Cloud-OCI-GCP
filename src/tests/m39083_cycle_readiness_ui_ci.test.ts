/** M39083 — no-current-cycle campaign UX, static/offline boundary regression. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const read=(path:string)=>readFileSync(path,'utf8');
const ui=read('src/components/SpecialCreditView.tsx');
const api=read('src/services/specialCreditApi.ts');
const boundary=read('src/services/specialCreditRequestBoundary.ts');
const backend=read('backend/app/routers/special_credit.py');
const routes=read('src/services/roleScope.ts');

assert(ui.includes('specialCreditApi.cycleReadiness(tenant)'));
assert(ui.includes('setCycleReady(readiness.current_open_cycle)'));
assert(ui.includes('setEnabled(false);setCycleReady(false)'));
assert(ui.includes('Nenhum ciclo vigente e aberto nesta caixinha.'));
assert(ui.includes('Revogações e cancelamentos continuam disponíveis.'));
assert(ui.includes("disabled={busy||!cycleReady||selectedMembers.length===0"));
assert(ui.includes("disabled={busy||!cycleReady||!grants.some("));
assert(ui.includes("c.status==='DRAFT'&&<button disabled={busy||!cycleReady}"));
assert(ui.includes("onClick={()=>void run(()=>specialCreditApi.revoke("));
assert(ui.includes("onClick={()=>void run(()=>specialCreditApi.cancel("));
assert(api.includes("'/cycle-readiness'"));
assert(api.includes('real_credit_enabled:false'));
assert(api.includes('external_dispatch:false'));
assert(!boundary.includes('import { authService }')); // transport stays session-injected.
assert(boundary.includes('transport.isCurrent(snapshot)'));
assert(backend.includes('@router.get("/cycle-readiness")'));
assert(backend.includes('_authorize(tenant_id, session, "TENANT_ADMIN")'));
assert(backend.includes("start_date<=CURRENT_DATE AND end_date>=CURRENT_DATE"));
assert(!routes.includes("'CAMPANHAS_MEMBROS','MINHAS_OPORTUNIDADES'"));
console.log('M39083_CYCLE_READINESS_ADMIN_UI=PASS_STATIC');
console.log('M39083_DATABASE_WRITES=NONE');
console.log('M39083_REAL_CREDIT=OFF');
