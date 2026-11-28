import assert from 'node:assert/strict';
import {reuseOrCreateCyclePriceAttempt} from '../services/cyclePriceAttempt';
import {parseCyclePriceInput} from '../services/cyclePriceBoundary';

let generated=0;
const uuid=()=>{generated++;return '00000000-0000-4000-8000-'+String(generated).padStart(12,'0');};
const input={scope:'admin:A:tenant:A',cycleId:'cycle-2027',amountCents:15000,
  reason:'Atualização da contribuição com justificativa formal'};
const first=reuseOrCreateCyclePriceAttempt(null,input,uuid);
assert.equal(generated,1);
assert.equal(first.amountCents,parseCyclePriceInput('150,00'));
// Same payload after a network timeout reuses the exact key, not a second write request.
assert.strictEqual(reuseOrCreateCyclePriceAttempt(first,{...input},uuid),first);
assert.equal(generated,1);
// Every identity, role, tenant, cycle and payload boundary must rotate the key.
for(const changed of [
  {...input,scope:'admin:B:tenant:B'},
  {...input,scope:'member:A:tenant:A'},
  {...input,cycleId:'cycle-2028'},
  {...input,amountCents:20000},
  {...input,reason:'Outra justificativa documentada'},
]){
  const next=reuseOrCreateCyclePriceAttempt(first,changed,uuid);
  assert.notEqual(next.idempotencyKey,first.idempotencyKey);
  assert.equal(next.scope,changed.scope);
}
assert.equal(generated,6);
const afterSuccess=reuseOrCreateCyclePriceAttempt(null,input,uuid);
assert.notEqual(afterSuccess.idempotencyKey,first.idempotencyKey);
assert.equal(generated,7);
console.log('M20500_IDEMPOTENT_RETRY_SCOPE_AND_PAYLOAD_PASS');
