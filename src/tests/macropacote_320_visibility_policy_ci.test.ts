import assert from 'node:assert/strict';
import {ledgerReadMode} from '../services/ledgerVisibilityPolicy';
import type {LedgerIntegrityPreview} from '../services/ledgerIntegrityPreview';
const base:LedgerIntegrityPreview={
 source:'POSTGRESQL_RLS',scope:'TENANT_ADMIN_READ_ONLY',
 tenant_id:'00000000-0000-4000-8000-000000000001',
 checked_transactions:0,balanced_transactions:0,review_required_transactions:0,
 status:'NO_TRANSACTIONS',bank_reconciled:false,financial_closing_authorized:false,
};
assert.equal(ledgerReadMode(base),'DIRECTORY_WITHOUT_BALANCES');
assert.equal(ledgerReadMode({...base,status:'BALANCED'}),'INTEGRITY_REVIEW_BLOCKED');
assert.equal(ledgerReadMode({...base,status:'NO_TRANSACTIONS',checked_transactions:1}),
 'INTEGRITY_REVIEW_BLOCKED');
assert.equal(ledgerReadMode({...base,status:'BALANCED',checked_transactions:2,
 balanced_transactions:2}),'DETAIL_PREVIEW');
assert.equal(ledgerReadMode({...base,status:'BALANCED',checked_transactions:2,
 balanced_transactions:1}),'INTEGRITY_REVIEW_BLOCKED');
assert.equal(ledgerReadMode({...base,status:'REVIEW_REQUIRED',checked_transactions:2,
 balanced_transactions:1,review_required_transactions:1}),'INTEGRITY_REVIEW_BLOCKED');
console.log('FR_CAIXINHA_M320_VISIBILITY_STATE_MACHINE=PASS');
