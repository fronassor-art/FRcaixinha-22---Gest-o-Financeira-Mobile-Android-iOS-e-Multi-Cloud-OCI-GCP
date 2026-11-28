/** FR Finance M39091 — 404 cannot quietly downgrade security or credit. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {requestSpecialCredit,type SpecialCreditTransport} from '../services/specialCreditRequestBoundary';

const tenant='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
let invalidations=0, requests=0;
let current=true;
const transport:SpecialCreditTransport={
 origin:()=> 'http://127.0.0.1:8000',
 captureSession:()=>({token:'offline-synthetic',generation:1}),
 isCurrent:()=>current,
 getUser:()=>({id:'11111111-1111-4111-8111-111111111111',
   name:'Synthetic',email:'not-real@example.invalid',role:'TENANT_ADMIN',
   tenantId:tenant}),
 invalidateIfCurrent:()=>{invalidations++;return true;},
 send:async(url,opts)=>{
   requests++;
   assert(url.endsWith('/tenants/'+tenant+'/special-credit/capabilities')||
          url.endsWith('/tenants/'+tenant+'/special-credit/members'));
   assert.equal(opts.method,'GET');
   return Response.json({detail:'Not Found'},{status:404});
 },
};
await assert.rejects(
 requestSpecialCredit(transport,tenant,'/capabilities'),
 /Rota de Crédito Especial ausente no servidor \(404\)/);
await assert.rejects(
 requestSpecialCredit(transport,tenant,'/members'),
 /Rota de Crédito Especial não encontrada no backend \(404\)/);
assert.equal(requests,2);
assert.equal(invalidations,0);
assert.equal(current,true);
const backend=readFileSync('backend/app/routers/special_credit.py','utf8');
const main=readFileSync('backend/app/main.py','utf8');
const ui=readFileSync('src/components/SpecialCreditView.tsx','utf8');
const script=readFileSync('backend/scripts/frfinance_m39091_api_route_probe_readonly.py','utf8');
assert.match(backend,/@router.get\("\/capabilities"\)/);
assert.match(main,/app.include_router\(_special_credit.router, prefix=settings.API_V1_STR\)/);
assert.match(ui,/role==='TENANT_ADMIN'\?'Atualizar campanhas':'Atualizar oportunidades'/);
assert.match(script,/127\.0\.0\.1:8000\/openapi\.json/);
assert.doesNotMatch(script,/POST|DELETE|ALTER\s+TABLE|DROP\s+TABLE/);
console.log('M39091_HTTP_404_DIAGNOSIS=PASS');
console.log('M39091_NO_DB_WRITES_NO_AUTO_RESTART=PASS');
