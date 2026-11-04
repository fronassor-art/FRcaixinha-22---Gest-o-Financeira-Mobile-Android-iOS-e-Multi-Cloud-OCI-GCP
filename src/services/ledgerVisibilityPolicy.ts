/** FR Caixinha: decisao de leitura sem autorizar saldos em livro vazio. */
import type {LedgerIntegrityPreview} from './ledgerIntegrityPreview';
export type LedgerReadMode = 'INTEGRITY_REVIEW_BLOCKED'|'DIRECTORY_WITHOUT_BALANCES'|'DETAIL_PREVIEW';
export function ledgerReadMode(integrity:LedgerIntegrityPreview):LedgerReadMode {
  if(integrity.status==='NO_TRANSACTIONS'&&
     integrity.checked_transactions===0&&
     integrity.balanced_transactions===0&&
     integrity.review_required_transactions===0)
    return 'DIRECTORY_WITHOUT_BALANCES';
  if(integrity.status==='BALANCED'&&integrity.checked_transactions>0&&
     integrity.balanced_transactions===integrity.checked_transactions&&
     integrity.review_required_transactions===0)
    return 'DETAIL_PREVIEW';
  return 'INTEGRITY_REVIEW_BLOCKED';
}
