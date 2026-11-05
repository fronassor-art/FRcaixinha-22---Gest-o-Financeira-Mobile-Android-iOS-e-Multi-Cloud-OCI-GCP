/* FR Caixinha AI Studio: official Pix checkout, not demonstrative.
 * Untrusted API JSON only becomes a payable QR after strict validation.
 * No local "confirm" button can mark a monthly fee or loan settled.
 */
export type ProviderPixCheckout = {
  operation_id: string;
  payment_id: string;
  amount_cents: number;
  status: 'pending' | 'in_process';
  qr_code: string;
  qr_code_base64?: string;
  ticket_url?: string;
  capital_recognized: false;
  bank_reconciled: false;
  ledger_written: false;
};

export type FinancialReceipt = {
  receipt_id: string;
  operation_id: string;
  payment_id: string;
  amount_cents: number;
  status: 'CONFIRMADO_CONCILIADO';
  bank_reconciled: true;
  ledger_transaction_id: string;
  statement_reference: string;
};

const hexOrBase64 = /^[A-Za-z0-9+/]+={0,2}$/;
const id = /^[0-9]{1,40}$/;
const operation = /^P_[0-9a-f]{32}$/;

export function parseProviderPixCheckout(raw: unknown): ProviderPixCheckout {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('Cobrança Pix indisponível.');
  }
  const d = raw as Record<string, unknown>;
  if (typeof d.operation_id !== 'string' || !operation.test(d.operation_id)
      || typeof d.payment_id !== 'string' || !id.test(d.payment_id)
      || typeof d.amount_cents !== 'number'
      || !Number.isSafeInteger(d.amount_cents) || d.amount_cents <= 0
      || !['pending','in_process'].includes(String(d.status))
      || typeof d.qr_code !== 'string' || !d.qr_code
      || d.qr_code.length > 4096
      || d.capital_recognized !== false
      || d.bank_reconciled !== false || d.ledger_written !== false) {
    throw new Error('QR Pix sem referência oficial validada.');
  }
  if (d.qr_code_base64 !== undefined &&
      (typeof d.qr_code_base64 !== 'string' ||
       d.qr_code_base64.length > 700000 ||
       !hexOrBase64.test(d.qr_code_base64))) {
    throw new Error('Imagem Pix inválida.');
  }
  if (d.ticket_url !== undefined &&
      (typeof d.ticket_url !== 'string' ||
       !/^https:\/\/(?:www\.)?mercadopago\.com\.br\//.test(d.ticket_url))) {
    throw new Error('Link Pix inválido.');
  }
  return d as ProviderPixCheckout;
}

export function parseFinancialReceipt(raw: unknown, operationId: string): FinancialReceipt {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('Comprovante ainda não confirmado pelo servidor.');
  }
  const d = raw as Record<string, unknown>;
  if (!operation.test(operationId) || d.operation_id !== operationId
      || typeof d.receipt_id !== 'string' || d.receipt_id.length < 20
      || typeof d.payment_id !== 'string' || !id.test(d.payment_id)
      || typeof d.amount_cents !== 'number' ||
      !Number.isSafeInteger(d.amount_cents) || d.amount_cents <= 0
      || d.status !== 'CONFIRMADO_CONCILIADO'
      || d.bank_reconciled !== true
      || typeof d.ledger_transaction_id !== 'string'
      || d.ledger_transaction_id.length < 20
      || typeof d.statement_reference !== 'string'
      || d.statement_reference.length < 8) {
    throw new Error('Comprovante não conciliado; aguarde confirmação externa.');
  }
  return d as FinancialReceipt;
}
