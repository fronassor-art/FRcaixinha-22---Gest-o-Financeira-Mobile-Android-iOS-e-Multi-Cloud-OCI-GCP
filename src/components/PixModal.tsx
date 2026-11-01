import React, { useState } from 'react';
import { QrCode, Copy, CheckCircle2, AlertCircle, X, ShieldAlert, Lock } from 'lucide-react';
import { formatBRL } from '../services/financialEngine';

interface PixModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  amount: number;
  description: string;
  recipientName: string;
  referenceId: string;
  onConfirmPayment?: () => void;
}

export const PixModal: React.FC<PixModalProps> = ({
  isOpen,
  onClose,
  title,
  amount,
  description,
  recipientName,
  referenceId,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const pixKeyMock = `00020126580014br.gov.bcb.pix0136${referenceId}5204000053039865406${amount.toFixed(2)}5802BR5925${recipientName.slice(0, 25)}6009SAO PAULO62070503***6304E8A2`;

  const handleCopy = () => {
    navigator.clipboard.writeText(pixKeyMock);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-100">
        {/* Header com Identificação Estrita de Demonstração */}
        <div className="bg-slate-900 text-white p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
              <Lock className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base leading-tight">{title}</h3>
                <span className="text-[10px] font-bold uppercase bg-amber-400/20 text-amber-300 px-2 py-0.5 rounded-full border border-amber-400/30">
                  Demonstração
                </span>
              </div>
              <p className="text-slate-400 text-xs mt-0.5">Sem efeito contábil • Sem custódia financeira</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Aviso Contratual Inviolável */}
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3.5 flex items-start gap-2.5 text-xs text-amber-900">
            <ShieldAlert className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <strong className="block text-amber-950 font-bold mb-0.5">
                Liquidação Financeira e Baixa de Saldo Bloqueadas
              </strong>
              <p className="leading-relaxed">
                Em conformidade com o Contrato Técnico Mestre (Cláusulas 4.5 e 16.4), pagamentos reais só são reconhecidos mediante conciliação via Webhook bancário autenticado (Mercado Pago / BACEN). Neste modo de demonstração, nenhuma movimentação contábil é processada e nenhum saldo é alterado.
              </p>
            </div>
          </div>

          {/* Valor e Destinatário */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-center">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Valor Indicativo da Operação</span>
            <div className="text-3xl font-extrabold text-slate-900 mt-1">{formatBRL(amount)}</div>
            <div className="text-xs text-slate-600 mt-2 flex items-center justify-center gap-1.5">
              <span>Destinatário:</span>
              <strong className="text-slate-800">{recipientName}</strong>
            </div>
          </div>

          {/* QR Code Ilustrativo */}
          <div className="flex flex-col items-center justify-center p-3 border border-slate-200 rounded-xl bg-slate-50/50">
            <div className="w-44 h-44 bg-white border border-slate-200 rounded-lg p-2.5 flex items-center justify-center shadow-xs">
              <div className="w-full h-full border-2 border-dashed border-slate-300 rounded flex flex-col items-center justify-center text-center p-2">
                <QrCode className="w-24 h-24 text-slate-700 mb-1" />
                <span className="text-[10px] text-slate-500 font-mono">PIX-REF: {referenceId.slice(0, 14)}</span>
              </div>
            </div>
            <span className="text-xs text-slate-500 mt-2 text-center">
              QR Code demonstrativo (Geração de intenção em modo sandbox)
            </span>
          </div>

          {/* Copia e Cola */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Código Pix Copia e Cola (Demonstração)
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={pixKeyMock}
                className="w-full text-xs font-mono bg-slate-100 text-slate-600 px-3 py-2.5 rounded-lg border border-slate-200 truncate focus:outline-hidden"
              />
              <button
                type="button"
                onClick={handleCopy}
                className={`px-3.5 py-2.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0 shadow-xs cursor-pointer ${
                  copied
                    ? 'bg-emerald-700 text-white'
                    : 'bg-slate-800 text-white hover:bg-slate-900'
                }`}
              >
                {copied ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copiado!' : 'Copiar'}
              </button>
            </div>
          </div>

          {/* Detalhes contratuais de conformidade */}
          <div className="border-t border-slate-100 pt-3 text-[11px] text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>Finalidade:</span>
              <span className="font-medium text-slate-700">{description}</span>
            </div>
            <div className="flex justify-between">
              <span>Chave de Idempotência:</span>
              <span className="font-mono text-slate-700">{referenceId}</span>
            </div>
            <div className="flex items-center gap-1.5 text-amber-700 font-medium pt-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>Geração de caixa e capital confirmados vedados sem liquidação real</span>
            </div>
          </div>

          {/* Botão de Fechar Exclusivo */}
          <div className="pt-2">
            <button
              onClick={onClose}
              className="w-full py-3 px-4 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Fechar Janela Informativa</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
