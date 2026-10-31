import React, { useState } from 'react';
import {
  Ticket,
  AlertTriangle,
  ShieldCheck,
  CheckCircle2,
  FileText,
  DollarSign,
  Info,
  ExternalLink,
  Award,
  Lock
} from 'lucide-react';
import { AppState } from '../services/store';
import { formatBRL } from '../services/financialEngine';

interface LotteryDemoViewProps {
  state: AppState;
}

export const LotteryDemoView: React.FC<LotteryDemoViewProps> = ({ state }) => {
  const campaign = state.lotteryCampaign;
  const [showMandateModal, setShowMandateModal] = useState(false);
  const [showTicketModal, setShowTicketModal] = useState(false);

  return (
    <div className="space-y-6">
      {/* Banner Obrigatório de Conformidade Regulatória (Seção 14 / Cláusula 14.5 e 14.6) */}
      <div className="p-5 rounded-2xl bg-amber-500/10 border-2 border-amber-500/40 text-amber-950 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-700 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <strong className="text-sm font-extrabold uppercase tracking-wide text-amber-900">
                Modo Demonstração Regulatória • Dados Fictícios
              </strong>
              <span className="bg-amber-200 text-amber-900 text-[10px] font-bold px-2 py-0.5 rounded-full">
                Dinheiro Real Estritamente Bloqueado
              </span>
            </div>
            <p className="text-xs text-amber-800/90 mt-0.5">
              Cláusula 14.5: Proibido operar com dinheiro real, vender cotas ou registrar apostas antes de parecer jurídico brasileiro sobre mandato oneroso e aprovação expressa da CAIXA.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono bg-white/80 border border-amber-300 text-amber-900 px-3 py-1.5 rounded-lg font-bold">
            SEÇÃO 14 HOMOLOGADA
          </span>
        </div>
      </div>

      {/* Card da Campanha Simulada */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-slate-900">{campaign.title}</h3>
              <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full">
                Concurso Oficial #{campaign.contest_number}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Até 4 campanhas anuais por caixinha sob responsabilidade mandatária do administrador (Cláusula 14.1).
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowMandateModal(true)}
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 cursor-pointer flex items-center gap-1.5"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Ver Mandato Específico</span>
            </button>
            <button
              onClick={() => setShowTicketModal(true)}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg cursor-pointer flex items-center gap-1.5 shadow-xs"
            >
              <Ticket className="w-3.5 h-3.5" />
              <span>Comprovante Fictício CAIXA</span>
            </button>
          </div>
        </div>

        {/* Decomposição Econômica Transparente (Cláusula 14.2 / AT-15 / AT-27) */}
        <div>
          <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">
            Decomposição de Preço e Margem Transparente (Cláusula 14.2)
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Custo Oficial por Cota</span>
              <div className="text-xl font-black text-slate-900 font-mono">
                {formatBRL(campaign.official_cost_per_quota)}
              </div>
              <p className="text-[10px] text-slate-500">R$ 150,00 ÷ 20 cotas oficiais</p>
            </div>

            <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200 space-y-1">
              <span className="text-[10px] font-bold text-emerald-800 uppercase">Preço Final por Cota</span>
              <div className="text-xl font-black text-emerald-900 font-mono">
                {formatBRL(campaign.final_price_per_quota)}
              </div>
              <p className="text-[10px] text-emerald-700">Preço público total contratado</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase">Arrecadação Esperada</span>
              <div className="text-xl font-black text-slate-900 font-mono">
                {formatBRL(campaign.total_revenue_expected)}
              </div>
              <p className="text-[10px] text-slate-500">20 cotas × R$ 25,00</p>
            </div>

            <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 space-y-1">
              <span className="text-[10px] font-bold text-teal-800 uppercase">Margem Bruta de Gestão</span>
              <div className="text-xl font-black text-teal-900 font-mono">
                {formatBRL(campaign.gross_margin)}
              </div>
              <p className="text-[10px] text-teal-700">R$ 17,50 por cota incluída</p>
            </div>
          </div>
        </div>

        {/* Alerta de Segregação de Prêmios */}
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-2">
          <div className="flex items-center gap-2 font-bold text-slate-900">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Destinação dos Recursos e Segregação de Prêmios (Cláusula 14.3)</span>
          </div>
          <p className="leading-relaxed">
            A margem líquida realizada (se aprovada pelos órgãos competentes) compõe o resultado da caixinha (ex: 85% para membros e 15% para o administrador).{' '}
            <strong>Prêmios lotéricos eventualmente sorteados pertencem exclusivamente aos titulares reais das cotas adquiridas, não configurando patrimônio nem lucro comum da caixinha.</strong>
          </p>
        </div>
      </div>

      {/* Modal de Mandato Fictício */}
      {showMandateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 border border-slate-200">
            <h3 className="font-bold text-slate-900 text-base">Contrato de Mandato Específico para Bolão</h3>
            <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-950 font-mono text-[11px] font-bold text-center">
              DADOS FICTÍCIOS — MODO DEMONSTRAÇÃO
            </div>
            <div className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-200 max-h-60 overflow-y-auto">
              "Pelo presente mandato, o aderente confere poderes especiais ao organizador {state.tenants[0]?.display_name} para, em seu nome, adquirir e registrar cotas de bilhete oficial das Loterias CAIXA correspondentes ao Concurso 2850, ficando o mandatário obrigado a prestar contas, custodiar o bilhete físico original e transferir integralmente os eventuais prêmios proporcionais aos compradores das cotas (Arts. 653 e seguintes do Código Civil)."
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowMandateModal(false)}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-xs font-semibold cursor-pointer"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Comprovante de Bilhete Fictício */}
      {showTicketModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-slate-200">
            <h3 className="font-bold text-slate-900 text-base">Registro de Bilhete Simulado (Demonstrador)</h3>
            <div className="p-4 bg-slate-900 text-emerald-400 font-mono rounded-xl text-xs space-y-2 border border-slate-800">
              <div className="text-center font-bold text-amber-300">*** DADOS FICTÍCIOS DE DEMONSTRAÇÃO ***</div>
              <div className="text-center">LOTERIAS CAIXA - SIMULAÇÃO</div>
              <div className="border-t border-slate-700 my-1"></div>
              <div>CONCURSO: 2850 • MODALIDADE: MEGA-SENA</div>
              <div>DEZENAS: 04 - 11 - 23 - 34 - 42 - 58</div>
              <div>TOTAL DE COTAS: 20 • COTA REGISTRADA: #01 a #20</div>
              <div>VALOR PAGO OFICIAL: R$ 150,00</div>
              <div>HASH REGISTRO: D6A4-91BF-TEST-SIMULATION</div>
              <div className="border-t border-slate-700 my-1"></div>
              <div className="text-[10px] text-slate-400 text-center">
                Jamais rotular um registro fictício como bilhete válido da Caixa (Cláusula 11.0-A)
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowTicketModal(false)}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-xs font-semibold cursor-pointer"
              >
                Fechar Comprovante
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
