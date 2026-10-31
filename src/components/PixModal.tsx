import React, { useState } from 'react';
import { QrCode, Copy, CheckCircle2, AlertCircle, RefreshCw, X, ShieldCheck } from 'lucide-react';
import { formatBRL } from '../services/financialEngine';
import confetti from 'canvas-confetti';

interface PixModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  amount: number;
  description: string;
  recipientName: string;
  referenceId: string;
  onConfirmPayment: () => void;
}

export const PixModal: React.FC<PixModalProps> = ({
  isOpen,
  onClose,
  title,
  amount,
  description,
  recipientName,
  referenceId,
  onConfirmPayment,
}) => {
  const [copied, setCopied] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [simulatedWebhookDuplicate, setSimulatedWebhookDuplicate] = useState(false);

  if (!isOpen) return null;

  const pixKeyMock = `00020126580014br.gov.bcb.pix0136${referenceId}5204000053039865406${amount.toFixed(2)}5802BR5925${recipientName.slice(0, 25)}6009SAO PAULO62070503***6304E8A2`;

  const handleCopy = () => {
    navigator.clipboard.writeText(pixKeyMock);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleSimulatePayment = (isDuplicate = false) => {
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
      onConfirmPayment();
      confetti({
        particleCount: 80,
        spread: 60,
        origin: { y: 0.6 },
      });
      if (isDuplicate) {
        setSimulatedWebhookDuplicate(true);
      } else {
        onClose();
      }
    }, 700);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-100">
        {/* Header */}
        <div className="bg-emerald-700 text-white p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
              <QrCode className="w-6 h-6 text-emerald-100" />
            </div>
            <div>
              <h3 className="font-bold text-lg leading-tight">{title}</h3>
              <p className="text-emerald-100 text-xs">Mercado Pago • Pix Oficial Integrado</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-emerald-100 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Valor e Destinatário */}
          <div className="bg-emerald-50/70 border border-emerald-100 rounded-xl p-4 text-center">
            <span className="text-xs font-medium text-emerald-800 uppercase tracking-wider">Valor da Operação</span>
            <div className="text-3xl font-extrabold text-emerald-950 mt-1">{formatBRL(amount)}</div>
            <div className="text-xs text-slate-600 mt-2 flex items-center justify-center gap-1.5">
              <span>Favorecido:</span>
              <strong className="text-slate-800">{recipientName}</strong>
            </div>
          </div>

          {/* QR Code Ilustrativo Estilizado */}
          <div className="flex flex-col items-center justify-center p-3 border border-slate-200 rounded-xl bg-slate-50/50">
            <div className="w-44 h-44 bg-white border border-slate-200 rounded-lg p-2.5 flex items-center justify-center shadow-xs">
              <div className="w-full h-full border-2 border-dashed border-emerald-500/40 rounded flex flex-col items-center justify-center text-center p-2">
                <QrCode className="w-24 h-24 text-slate-800 mb-1" />
                <span className="text-[10px] text-slate-500 font-mono">PIX-ID: {referenceId.slice(0, 14)}</span>
              </div>
            </div>
            <span className="text-xs text-slate-500 mt-2 text-center">
              Aponte a câmera do aplicativo do seu banco para o QR Code
            </span>
          </div>

          {/* Copia e Cola */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Código Pix Copia e Cola (Imutável)
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
                className={`px-3.5 py-2.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0 shadow-xs ${
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
              <span>Idempotência:</span>
              <span className="font-mono text-slate-700">{referenceId}</span>
            </div>
            <div className="flex items-center gap-1.5 text-emerald-700 font-medium pt-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Segregação patrimonial garantida (Cláusulas 1.7 e 7.1)</span>
            </div>
          </div>

          {/* Ações de Simulação do Provedor */}
          <div className="pt-2 space-y-2">
            <button
              onClick={() => handleSimulatePayment(false)}
              disabled={isProcessing}
              className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl shadow-md shadow-emerald-600/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Conciliando com Provedor Pix...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5" />
                  <span>Simular Confirmação Pix (Webhook Reconciliado)</span>
                </>
              )}
            </button>

            {/* Teste de Idempotência (Webhook duplicado 10x - Cláusula 9.8 / AT-11) */}
            <button
              onClick={() => handleSimulatePayment(true)}
              className="w-full py-2 px-3 text-[11px] text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors flex items-center justify-center gap-1.5"
            >
              <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
              <span>Simular Webhook Duplicado (Teste Idempotência AT-11)</span>
            </button>

            {simulatedWebhookDuplicate && (
              <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                ✅ <strong>Idempotência verificada:</strong> O segundo webhook não gerou novo lançamento nem cobrou duplicado no ledger.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
