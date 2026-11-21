import assert from 'node:assert/strict';
import {parseProviderPixCheckout,parseFinancialReceipt} from '../services/pixAutomationBoundary';

const orderId='ORD01HRYFWNYRE1MR1E60MW3X0T2P';
const payId='PAY01HRYFXQ53Q3JPEC48MYWMR0TE';
const operationId='P_'+'a'.repeat(32);
const orders={
  checkout_type:'orders_pix',
  order_id:orderId,payment_id:payId,operation_id:operationId,
  amount_cents:15000,status:'action_required',status_detail:'waiting_transfer',
  qr_code:'00020126580014br.gov.bcb.pix',
  qr_code_base64:'ZmFrZQ==',
  capital_recognized:false,bank_reconciled:false,ledger_written:false,
};
const ok=parseProviderPixCheckout(orders);
assert.equal(ok.order_id,orderId);
assert.equal(ok.payment_id,payId);
assert.equal(ok.status,'action_required');
for(const fields of [
  {order_id:'123456'}, {payment_id:'900001'},
  {status:'processed'}, {status_detail:'accredited'},
  {checkout_type:'legacy'}, {amount_cents:14999.99},
  {capital_recognized:true},{bank_reconciled:true},
  {ledger_written:true},{qr_code:''},
  {ticket_url:'https://attacker.example.invalid/'},
]) {
  assert.throws(()=>parseProviderPixCheckout({...orders,...fields}));
}

const receipt={
  receipt_id:'00000000-0000-4000-8000-0000000000a1',
  ledger_transaction_id:'00000000-0000-4000-8000-0000000000a2',
  order_id:orderId,payment_id:payId,operation_id:operationId,
  amount_cents:15000,status:'CONFIRMADO_CONCILIADO',
  bank_reconciled:true,statement_reference:'BANK_ORDER_PROOF_2027',
};
const confirmed=parseFinancialReceipt(receipt,operationId);
assert.equal(confirmed.order_id,orderId);
for(const fields of [
  {order_id:'ORDdifferent'}, {payment_id:'not-pay'},
  {status:'processed'}, {bank_reconciled:false},
  {statement_reference:''},{ledger_transaction_id:''},
]) assert.throws(()=>parseFinancialReceipt({...receipt,...fields},operationId));
console.log('ORDERS_PIX_FRONTEND_BOUNDARY=PASS');
