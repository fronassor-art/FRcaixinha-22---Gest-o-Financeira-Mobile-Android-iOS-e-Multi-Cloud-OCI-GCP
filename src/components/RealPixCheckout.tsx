import React, { useState } from 'react';
import { financialApi } from '../services/financialApiService';
import { authService } from '../services/authService';
import type { ProviderPixCheckout, FinancialReceipt } from '../services/pixAutomationBoundary';
import { parseFinancialReceipt } from '../services/pixAutomationBoundary';

interface Props {
  checkout: ProviderPixCheckout;
  tenantId: string;
  onClose: () => void;
}

const money = (cents: number) => new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'BRL',
}).format(cents / 100);

export const RealPixCheckout: React.FC<Props> = ({ checkout, tenantId, onClose }) => {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [receipt, setReceipt] = useState<FinancialReceipt | null>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(checkout.qr_code);
      setNotice('Código Pix oficial copiado.');
    } catch {
      setNotice('Não foi possível copiar automaticamente. Selecione o código.');
    }
  }

  async function checkReceipt() {
    const snapshot = authService.captureSession();
    setBusy(true);
    setNotice('Consultando comprovante conciliado no servidor...');
    try {
      const data = await financialApi.getPixAutomationReceipt(tenantId, checkout.operation_id);
      if (!authService.isSessionSnapshotCurrent(snapshot)) return;
      const verified = parseFinancialReceipt(data, checkout.operation_id);
      if (verified.payment_id !== checkout.payment_id ||
          verified.amount_cents !== checkout.amount_cents ||
          (checkout.checkout_type === 'orders_pix' &&
           verified.order_id !== checkout.order_id)) {
        throw new Error('Comprovante não corresponde a esta cobrança.');
      }
      setReceipt(verified);
      setNotice('Pagamento confirmado e conciliado pelo servidor.');
    } catch (error) {
      if (authService.isSessionSnapshotCurrent(snapshot)) {
        setNotice(error instanceof Error ? error.message :
          'Aguarde a conciliação bancária. Não confirme manualmente.');
      }
    } finally {
      if (authService.isSessionSnapshotCurrent(snapshot)) setBusy(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Pix Mercado Pago"
         className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3">
      <section className="max-h-[94vh] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-5 shadow-xl space-y-4">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Pix Mercado Pago</h3>
            <p className="text-xs text-slate-600">
              Cobrança identificada • Aguardando confirmação bancária
            </p>
          </div>
          <button type="button" onClick={onClose}
                  className="rounded-lg border px-3 py-2 text-sm">Fechar</button>
        </header>
        <p className="text-2xl font-extrabold text-emerald-800">
          {money(checkout.amount_cents)}
        </p>
        {checkout.qr_code_base64 && (
          <img alt="QR Code Pix retornado pelo provedor"
               className="mx-auto h-52 w-52 object-contain"
               src={`data:image/png;base64,${checkout.qr_code_base64}`} />
        )}
        <div>
          <label htmlFor="real-pix-copy" className="block text-sm font-semibold text-slate-800">
            Pix Copia e Cola
          </label>
          <textarea id="real-pix-copy" readOnly value={checkout.qr_code} rows={3}
                    className="mt-2 w-full rounded-lg border p-2 font-mono text-xs" />
          <button type="button" onClick={copy}
                  className="mt-2 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">
            Copiar código
          </button>
        </div>
        <p className="break-all text-xs text-slate-600">
          Operação: {checkout.operation_id}
          {checkout.order_id ? ` • Order: ${checkout.order_id}` : ''}
          • Pagamento: {checkout.payment_id}
        </p>
        {!receipt ? (
          <button type="button" disabled={busy} onClick={checkReceipt}
                  className="w-full rounded-lg bg-emerald-800 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60">
            {busy ? 'Verificando...' : 'Consultar confirmação e comprovante'}
          </button>
        ) : (
          <section className="rounded-xl border border-emerald-300 p-3 text-sm"
                   aria-label="Comprovante conciliado">
            <p className="font-semibold text-emerald-900">Pagamento conciliado</p>
            <p>Comprovante: {receipt.receipt_id}</p>
            <p>Valor: {money(receipt.amount_cents)}</p>
            <p className="break-all">Referência bancária: {receipt.statement_reference}</p>
            <p className="break-all">Livro-Razão: {receipt.ledger_transaction_id}</p>
          </section>
        )}
        {notice && <p role="status" className="text-sm text-slate-800">{notice}</p>}
        <p className="text-xs text-amber-900">
          O botão acima consulta a evidência do servidor. Não dá baixa manual
          nem transforma uma cobrança pendente em pagamento confirmado.
        </p>
      </section>
    </div>
  );
};
