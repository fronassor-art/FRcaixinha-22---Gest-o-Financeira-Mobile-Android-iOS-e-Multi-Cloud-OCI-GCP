import assert from 'node:assert/strict';
import {
  parseProviderPixCheckout, parseFinancialReceipt,
} from '../services/pixAutomationBoundary';

const checkout={
  operation_id:'P_'+'a'.repeat(32),
  payment_id:'900001',
  amount_cents:15000,
  status:'pending',
  qr_code:'00020126-SANDBOX-CI-FAKE-NOT-PAYABLE',
  qr_code_base64:'ZmFrZQ==',
  capital_recognized:false,
  bank_reconciled:false,
  ledger_written:false,
};

const validated=parseProviderPixCheckout(checkout);
assert.equal(validated.amount_cents,15000);
assert.equal(validated.operation_id,checkout.operation_id);
assert.equal(validated.bank_reconciled,false);

for (const overrides of [
  {operation_id:'invalid'}, {payment_id:'x'}, {status:'approved'},
  {amount_cents:14999.5}, {bank_reconciled:true},
  {ledger_written:true}, {capital_recognized:true},
  {qr_code:''}, {ticket_url:'https://evil.example.invalid'},
]) {
  assert.throws(() => parseProviderPixCheckout({...checkout,...overrides}));
}

const receipt={
  receipt_id:'00000000-0000-4000-8000-0000000000a1',
  operation_id:checkout.operation_id,
  payment_id:'900001',
  amount_cents:15000,
  status:'CONFIRMADO_CONCILIADO',
  bank_reconciled:true,
  ledger_transaction_id:'00000000-0000-4000-8000-0000000000a2',
  statement_reference:'BANK_EVIDENCE_2027_001',
};
assert.equal(parseFinancialReceipt(receipt,checkout.operation_id).amount_cents,15000);
for(const overrides of [
  {bank_reconciled:false},{status:'pending'},
  {operation_id:'P_'+'b'.repeat(32)},
  {ledger_transaction_id:''},{statement_reference:''},
]) {
  assert.throws(() => parseFinancialReceipt({...receipt,...overrides},checkout.operation_id));
}
console.log('PIX_AUTOMATION_FRONTEND_BOUNDARY=PASS');
