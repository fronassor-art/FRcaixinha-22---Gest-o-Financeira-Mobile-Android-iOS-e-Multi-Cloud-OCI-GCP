import React, { useState } from 'react';
import {
  Ticket,
  Printer,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  QrCode,
  DollarSign,
  Info,
  Calendar,
  Layers,
  FileText,
  ChevronRight,
  TrendingUp,
  Percent,
  Award,
  RefreshCw,
  Plus,
  Trash2,
  Edit,
  ShieldCheck,
  X,
  ExternalLink,
  Lock,
  Eye
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import {
  BolaoCampaign,
  BolaoGame,
  BolaoMemberParticipation,
  BolaoInternalStatus,
  BolaoPaymentStatus
} from '../types';
import {
  calculateBolaoPricing,
  calculateBolaoPrizeSplit,
  calculateBolaoMora,
  allocateBolaoCentsDeterministically,
  formatBRL
} from '../services/financialEngine';

interface BolaoModuleViewProps {
  state: AppState;
  onOpenPixModal: (params: {
    title: string;
    amount: number;
    description: string;
    recipientName: string;
    referenceId: string;
    onConfirm: () => void;
  }) => void;
}

export const BolaoModuleView: React.FC<BolaoModuleViewProps> = ({ state, onOpenPixModal }) => {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>(
    state.bolaoCampaigns[0]?.id || 'bol-quina-2027'
  );
  const [activeTab, setActiveTab] = useState<'GAMES' | 'MEMBERS' | 'RECEIPT' | 'MORA' | 'PRIZE_SPLIT'>('GAMES');

  // Modal para criar/adicionar aposta
  const [isAddGameModalOpen, setIsAddGameModalOpen] = useState(false);
  const [selectedNumbers, setSelectedNumbers] = useState<number[]>([]);

  // Modal de Impressão do Roteiro para a Lotérica (Seção 7.1)
  const [isPrintRoteiroOpen, setIsPrintRoteiroOpen] = useState(false);

  // Modal de Retorno e Registro do Recibo Oficial CAIXA (Seção 7.2)
  const [isReceiptModalOpen, setIsReceiptModalOpen] = useState(false);
  const [receiptCodeInput, setReceiptCodeInput] = useState('');
  const [receiptDateInput, setReceiptDateInput] = useState(new Date().toISOString().split('T')[0]);

  // Modal de Sorteio e Apuração de Prêmio (Seção 12 - 96% / 4%)
  const [isDrawModalOpen, setIsDrawModalOpen] = useState(false);
  const [simDrawnNumbersInput, setSimDrawnNumbersInput] = useState<string>('');
  const [simGrossPrizeInput, setSimGrossPrizeInput] = useState<number>(1000000.00); // R$ 1.000.000,00 clássico

  // Simulador de Mora Simples
  const [moraPendingInput, setMoraPendingInput] = useState<number>(9.60); // Exemplo do documento (2 cotas)
  const [moraDaysInput, setMoraDaysInput] = useState<number>(10);

  const visibleCampaigns = state.bolaoCampaigns.filter(c => c.tenant_id === state.currentTenantId);
  const currentCampaign = visibleCampaigns.find(c => c.id === selectedCampaignId) || visibleCampaigns[0];
  if (!currentCampaign) return <div role="status" className="p-4 text-sm">Nenhum bolão demonstrativo nesta caixinha.</div>;
  const participations = state.bolaoParticipations.filter(p => p.campaign_id === currentCampaign.id);

  const isAdminOrMaster = state.currentRole === 'TENANT_ADMIN' || state.currentRole === 'MASTER';

  // Identificar cotas do membro logado
  const currentMember = state.memberships.find(
    m => m.user_id === state.currentUserId && m.tenant_id === state.currentTenantId
  );
  const myParticipation = participations.find(p => p.membership_id === currentMember?.id);

  // Dezenas utilizadas no bolão (união de todas as dezenas dos jogos)
  const allUsedNumbers = Array.from(
    new Set(currentCampaign.games.flatMap(g => g.numbers))
  ).sort((a, b) => a - b);

  // Configuração visual da modalidade conforme prints oficiais
  const modalityTheme = {
    QUINA: {
      name: 'Quina de São João',
      primaryColor: 'from-blue-900 to-indigo-950',
      badgeBg: 'bg-blue-600',
      borderColor: 'border-blue-700/60',
      tagColor: 'bg-blue-50 text-blue-900 border-blue-200',
      circleColor: 'bg-blue-600 text-white',
      maxGrid: 80,
      minRequired: 5,
      maxAllowed: 15,
    },
    LOTOFACIL: {
      name: 'Lotofácil da Independência',
      primaryColor: 'from-fuchsia-950 via-purple-950 to-slate-950',
      badgeBg: 'bg-fuchsia-700',
      borderColor: 'border-fuchsia-700/60',
      tagColor: 'bg-fuchsia-50 text-fuchsia-900 border-fuchsia-200',
      circleColor: 'bg-fuchsia-700 text-white',
      maxGrid: 25,
      minRequired: 15,
      maxAllowed: 20,
    },
    MEGA_SENA: {
      name: 'Mega da Virada',
      primaryColor: 'from-emerald-950 via-teal-950 to-slate-950',
      badgeBg: 'bg-emerald-600',
      borderColor: 'border-emerald-700/60',
      tagColor: 'bg-emerald-50 text-emerald-900 border-emerald-200',
      circleColor: 'bg-emerald-600 text-white',
      maxGrid: 60,
      minRequired: 6,
      maxAllowed: 20,
    },
  }[currentCampaign.modality];

  // Alternar dezena na grade
  const toggleNumberSelection = (num: number) => {
    if (selectedNumbers.includes(num)) {
      setSelectedNumbers(selectedNumbers.filter(n => n !== num));
    } else {
      if (selectedNumbers.length >= currentCampaign.numbers_per_game) {
        alert(`Este bolão está configurado para exatamente ${currentCampaign.numbers_per_game} dezenas por jogo.`);
        return;
      }
      setSelectedNumbers([...selectedNumbers, num].sort((a, b) => a - b));
    }
  };

  // Surpresinha Inteligente (Gera dezenas aleatórias válidas)
  const handleGenerateSurpresinha = () => {
    const pool: number[] = [];
    for (let i = 1; i <= modalityTheme.maxGrid; i++) pool.push(i);
    // Shuffle
    const shuffled = pool.sort(() => 0.5 - Math.random());
    const picked = shuffled.slice(0, currentCampaign.numbers_per_game).sort((a, b) => a - b);
    setSelectedNumbers(picked);
  };

  const handleSaveNewGame = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedNumbers.length !== currentCampaign.numbers_per_game) {
      alert(`Selecione exatamente ${currentCampaign.numbers_per_game} dezenas.`);
      return;
    }
    try {
      appStore.addBolaoGame(currentCampaign.id, selectedNumbers);
      setSelectedNumbers([]);
      setIsAddGameModalOpen(false);
    } catch (err: any) {
      alert(err.message || 'Erro ao adicionar aposta');
    }
  };

  const handleRegisterReceipt = (e: React.FormEvent) => {
    e.preventDefault();
    if (!receiptCodeInput.trim()) {
      alert('Informe o número ou código de segurança do recibo oficial da CAIXA.');
      return;
    }
    appStore.registerBolaoOfficialReceipt(
      currentCampaign.id,
      receiptCodeInput.trim(),
      receiptDateInput
    );
    setIsReceiptModalOpen(false);
    setReceiptCodeInput('');
  };

  const handlePayParticipationDirectly = (p: BolaoMemberParticipation) => {
    onOpenPixModal({
      title: `Pagamento Bolão - ${currentCampaign.campaign_name}`,
      amount: p.amount_pending,
      description: `Participação de ${p.member_name} (${p.quotas_count} cota(s)) no Bolão ${currentCampaign.campaign_name}`,
      recipientName: 'FR Finance Gestão Coletiva',
      referenceId: p.id,
      onConfirm: () => {
        appStore.payBolaoParticipation(p.id);
      },
    });
  };

  const handleSimulateDraw = (e: React.FormEvent) => {
    e.preventDefault();
    let numbers: number[] = [];
    if (simDrawnNumbersInput.trim()) {
      numbers = simDrawnNumbersInput
        .split(/[ ,;-]+/)
        .map(n => parseInt(n, 10))
        .filter(n => !isNaN(n) && n >= 1 && n <= modalityTheme.maxGrid);
    } else {
      // Gerar aleatórios se vazio
      const pool: number[] = [];
      for (let i = 1; i <= modalityTheme.maxGrid; i++) pool.push(i);
      const shuffled = pool.sort(() => 0.5 - Math.random());
      const drawCount = currentCampaign.modality === 'MEGA_SENA' ? 6 : currentCampaign.modality === 'QUINA' ? 5 : 15;
      numbers = shuffled.slice(0, drawCount).sort((a, b) => a - b);
    }

    appStore.simulateBolaoDraw(currentCampaign.id, numbers, simGrossPrizeInput);
    setIsDrawModalOpen(false);
  };

  return (
    <div className="space-y-6">
      <div role="note" className="rounded-xl border border-amber-400 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-950">
        DEMONSTRAÇÃO — dados fictícios e ações locais. Não há bilhete, aposta, sorteio, cobrança ou pagamento real neste módulo.
      </div>
      {/* Banner Principal com Identidade dos Prints de 30/10/2026 */}
      <div
        className={`bg-gradient-to-r ${modalityTheme.primaryColor} rounded-2xl p-6 text-white border ${modalityTheme.borderColor} shadow-xl relative overflow-hidden`}
      >
        <div className="absolute right-0 top-0 bottom-0 w-96 bg-gradient-to-l from-white/5 to-transparent pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5">
                <Ticket className="w-3.5 h-3.5" /> Bolões — demonstração
              </span>
              <span className="text-xs bg-slate-800/80 text-emerald-400 font-bold px-2 py-0.5 rounded-full border border-emerald-500/40">
                DEMONSTRAÇÃO SEM APOSTA
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white flex items-center gap-2">
              {currentCampaign.campaign_name}
            </h1>
            <p className="text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
              Criação integral dos jogos no FR Finance, impressão do roteiro de preenchimento,
              registro oficial presencial na CAIXA, adicional de 20% à caixinha e rateio exclusivo de prêmio (96% membros / 4% caixinha).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setActiveTab('GAMES')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'GAMES'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Composição & Jogos
            </button>
            <button
              onClick={() => setActiveTab('MEMBERS')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'MEMBERS'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Cotas & Membros (25 Cotas)
            </button>
            <button
              onClick={() => setActiveTab('PRIZE_SPLIT')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'PRIZE_SPLIT'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Rateio de Prêmio (96% / 4%)
            </button>
            <button
              onClick={() => setActiveTab('MORA')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'MORA'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Simulador de Mora (20%)
            </button>
          </div>
        </div>

        {/* Seletor das 3 Campanhas Especiais do Calendário Anual (Seção 2) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-6 pt-5 border-t border-slate-800/80">
          {visibleCampaigns.map(camp => {
            const isSelected = camp.id === selectedCampaignId;
            return (
              <div
                key={camp.id}
                onClick={() => setSelectedCampaignId(camp.id)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer text-left ${
                  isSelected
                    ? 'bg-white/10 border-amber-400 ring-2 ring-amber-400/40'
                    : 'bg-slate-800/40 border-slate-700/60 hover:bg-slate-800/70'
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-bold text-amber-300 uppercase tracking-wider text-[11px]">
                    {camp.modality.replace('_', ' ')}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-900/60 text-slate-300 border border-slate-700">
                    {camp.internal_status.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="font-extrabold text-sm text-white">{camp.campaign_name}</div>
                <div className="text-xs text-slate-300 mt-1 flex flex-col gap-0.5">
                  <span>Prêmio Estimado: <strong className="text-amber-300">{formatBRL(camp.estimated_prize)}</strong></span>
                  <span>{camp.games.length} apostas de {camp.numbers_per_game} dezenas</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Faixa de Destaque da Modalidade & Barra de Resumo Financeiro (A + B + C) */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-white font-black text-xl shadow-md ${modalityTheme.badgeBg}`}>
              <Ticket className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  {currentCampaign.special_edition}
                </span>
                <span className="text-xs font-mono font-bold bg-slate-100 text-slate-800 px-2 py-0.5 rounded">
                  Concurso de referência #{currentCampaign.contest_number || 'A CONFIRMAR'}
                </span>
              </div>
              <h2 className="text-lg font-black text-slate-900">
                Prêmio Estimado: <span className="text-emerald-600">{formatBRL(currentCampaign.estimated_prize)}</span>
              </h2>
            </div>
          </div>

          {/* Botões de Ação do Roteiro e Comprovante Oficial */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setIsPrintRoteiroOpen(true)}
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition-all flex items-center gap-2 shadow-xs cursor-pointer"
              title="Gerar Roteiro de Preenchimento para a Lotérica (Seção 7.1)"
            >
              <Printer className="w-4 h-4 text-amber-400" />
              <span>Imprimir Roteiro para Lotérica</span>
            </button>

            {isAdminOrMaster && (
              <button
                onClick={() => setIsReceiptModalOpen(true)}
                className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-all flex items-center gap-2 shadow-xs cursor-pointer"
                title="Registrar retorno da lotérica com o comprovante oficial CAIXA"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>
                  {currentCampaign.internal_status === 'REGISTRADO_CONFERIDO'
                    ? 'Recibo CAIXA Confirmado'
                    : 'Registrar Recibo Oficial'}
                </span>
              </button>
            )}

            {isAdminOrMaster && (
              <button
                onClick={() => setIsDrawModalOpen(true)}
                className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl transition-all flex items-center gap-2 shadow-xs cursor-pointer"
              >
                <Sparkles className="w-4 h-4 text-amber-300" />
                <span>Conferir Sorteio / Rateio 96%</span>
              </button>
            )}
          </div>
        </div>

        {/* Decomposição Financeira (Seção 8 do Documento) */}
        <div>
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
            <span>Decomposição Financeira do Bolão (A + B + C)</span>
            <span>25 Cotas Válidas</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[11px] font-semibold">
                (A) Apostas Oficiais CAIXA
              </span>
              <span className="text-base font-black text-slate-900 font-mono mt-0.5 block">
                {formatBRL(currentCampaign.cost_official_bets)}
              </span>
              <span className="text-[10px] text-slate-400">
                {currentCampaign.games.length} jogos × {formatBRL(currentCampaign.games[0]?.unit_cost || 0)}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[11px] font-semibold">
                (B) Tarifa Externa
              </span>
              <span className="text-base font-black text-slate-900 font-mono mt-0.5 block">
                {formatBRL(currentCampaign.external_fee)}
              </span>
              <span className="text-[10px] text-slate-400">Organização direta (R$ 0,00)</span>
            </div>

            <div className="p-3 rounded-xl bg-indigo-50/70 border border-indigo-200">
              <span className="text-indigo-700 block text-[11px] font-bold">
                (C) Adicional Caixinha (20%)
              </span>
              <span className="text-base font-black text-indigo-900 font-mono mt-0.5 block">
                {formatBRL(currentCampaign.box_additional_fee)}
              </span>
              <span className="text-[10px] text-indigo-600">20% sobre (A + B)</span>
            </div>

            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200">
              <span className="text-emerald-800 block text-[11px] font-bold">
                Cobrança Prevista Total
              </span>
              <span className="text-base font-black text-emerald-900 font-mono mt-0.5 block">
                {formatBRL(currentCampaign.total_budget)}
              </span>
              <span className="text-[10px] text-emerald-700">A + B + C</span>
            </div>

            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 col-span-2 sm:col-span-1">
              <span className="text-amber-800 block text-[11px] font-bold">
                Valor por Cota
              </span>
              <span className="text-base font-black text-amber-950 font-mono mt-0.5 block">
                {formatBRL(currentCampaign.price_per_quota_base)}
              </span>
              <span className="text-[10px] text-amber-700">Fechamento auditado centavos</span>
            </div>
          </div>
        </div>
      </div>

      {/* Alerta de Sorteio Concluído & Rateio de 96% / 4% (Seção 12) */}
      {currentCampaign.draw_status === 'RESULTADO_CONFERIDO' && (
        <div className="bg-gradient-to-r from-amber-500/10 via-amber-500/20 to-amber-500/10 border-2 border-amber-500/70 rounded-2xl p-5 shadow-sm space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-amber-500 text-slate-950 flex items-center justify-center font-black shadow-md">
                <Award className="w-7 h-7" />
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-amber-800 bg-amber-200/80 px-2.5 py-0.5 rounded-full">
                  Resultado simulado, sem homologação
                </span>
                <h3 className="text-lg font-black text-slate-900 mt-1">
                  Dezenas Sorteadas: {currentCampaign.drawn_numbers?.map(n => n.toString().padStart(2, '0')).join(' • ')}
                </h3>
                <p className="text-xs text-slate-600 mt-0.5">
                  Prêmio Líquido Confirmado: <strong>{formatBRL(currentCampaign.prize_gross_amount || 0)}</strong>
                </p>
              </div>
            </div>

            <div className="text-right">
              <div className="text-xs text-slate-500">Regra Exclusiva do Bolão (Seção 12):</div>
              <div className="text-sm font-extrabold text-slate-900">
                <span className="text-emerald-700">96% Titulares ({formatBRL(currentCampaign.prize_member_total_amount || 0)})</span>
                {' • '}
                <span className="text-indigo-700">4% Taxa Admin ({formatBRL(currentCampaign.prize_admin_fee_amount || 0)})</span>
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={() => appStore.reopenBolaoDraw(currentCampaign.id)}
              className="text-xs font-semibold text-slate-600 hover:text-slate-900 underline cursor-pointer"
            >
              Reabrir / Simular outro sorteio
            </button>
          </div>
        </div>
      )}

      {/* Regra de Negócio Crucial: Roteiro e Ausência de Custódia */}
      <div className="bg-amber-50/70 border border-amber-200/80 rounded-xl p-3.5 text-xs text-amber-900 flex items-start gap-3">
        <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <strong>Aviso Regulatório Obrigatório (Seções 4, 7 e 14):</strong> O roteiro gerado no aplicativo é
          <em> SOMENTE UM GUIA DE PREENCHIMENTO PARA REGISTRO PRESENCIAL NA LOTÉRICA</em>. A aposta oficial só existe após
          a emissão dos volantes pela CAIXA Econômica Federal. O aplicativo não custodia valores bancários; os
          repasses ocorrem via Pix direto na conta jurídica da caixinha.
        </div>
      </div>

      {/* TAB 1: COMPOSIÇÃO E LISTA DE APOSTAS */}
      {activeTab === 'GAMES' && (
        <div className="space-y-6">
          {/* Seção 1: Dezenas Utilizadas no Bolão (Prints de 30/10/2026) */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-600" />
                  Dezenas Utilizadas no Bolão ({allUsedNumbers.length} Dezenas Diferentes)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  União de todos os prognósticos independentes escolhidos nas apostas deste bolão.
                </p>
              </div>
              <span className="text-xs font-mono font-bold bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg">
                Grade 01 a {modalityTheme.maxGrid.toString().padStart(2, '0')}
              </span>
            </div>

            {/* Grid com as dezenas em círculos estilizados */}
            <div className="flex flex-wrap gap-2 pt-1">
              {allUsedNumbers.map(num => (
                <div
                  key={num}
                  className="w-9 h-9 rounded-full bg-slate-900 text-white font-mono font-black text-xs flex items-center justify-center shadow-xs"
                >
                  {num.toString().padStart(2, '0')}
                </div>
              ))}
              {allUsedNumbers.length === 0 && (
                <span className="text-xs text-slate-400 italic">Nenhuma dezena selecionada ainda.</span>
              )}
            </div>
          </div>

          {/* Seção 2: Lista Integral de Apostas Numeradas (Aposta 01, Aposta 02...) */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-2">
                  <Ticket className="w-4 h-4 text-indigo-600" />
                  Lista Integral de Apostas do Bolão ({currentCampaign.games.length} Apostas)
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Cada aposta com {currentCampaign.numbers_per_game} dezenas em ordem crescente (limite de até 10 jogos no recibo oficial).
                </p>
              </div>

              {isAdminOrMaster && currentCampaign.games.length < currentCampaign.max_games_per_receipt && (
                <button
                  onClick={() => {
                    setSelectedNumbers([]);
                    setIsAddGameModalOpen(true);
                  }}
                  className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Adicionar Nova Aposta
                </button>
              )}
            </div>

            {/* Lista das apostas */}
            <div className="space-y-3">
              {currentCampaign.games.map(game => {
                // Verificar acertos caso haja resultado sorteado
                const hits = currentCampaign.drawn_numbers
                  ? game.numbers.filter(n => currentCampaign.drawn_numbers!.includes(n))
                  : [];

                return (
                  <div
                    key={game.id}
                    className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-slate-50 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-black bg-slate-900 text-white px-2 py-0.5 rounded font-mono">
                          Aposta {game.game_number.toString().padStart(2, '0')}
                        </span>
                        <span className="text-xs font-bold text-slate-600">
                          {game.numbers_count} dezenas
                        </span>
                        <span className="text-xs font-mono text-slate-500">
                          Custo Oficial: {formatBRL(game.unit_cost)}
                        </span>
                        {hits.length > 0 && (
                          <span className="text-xs font-bold bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full">
                            {hits.length} ACERTO(S)!
                          </span>
                        )}
                      </div>

                      {/* Dezenas da Aposta em círculos */}
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {game.numbers.map(num => {
                          const isHit = currentCampaign.drawn_numbers?.includes(num);
                          return (
                            <span
                              key={num}
                              className={`w-8 h-8 rounded-full font-mono font-black text-xs flex items-center justify-center transition-all ${
                                isHit
                                  ? 'bg-amber-400 text-slate-950 ring-2 ring-amber-500 shadow-md font-extrabold animate-bounce'
                                  : 'bg-white border border-slate-300 text-slate-900 shadow-2xs'
                              }`}
                            >
                              {num.toString().padStart(2, '0')}
                            </span>
                          );
                        })}
                      </div>
                    </div>

                    {isAdminOrMaster && currentCampaign.internal_status === 'RASCUNHO' && (
                      <button
                        onClick={() => appStore.removeBolaoGame(currentCampaign.id, game.id)}
                        className="p-2 text-rose-500 hover:text-rose-700 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer shrink-0"
                        title="Remover esta aposta"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: COTAS & PARTICIPAÇÕES DOS MEMBROS (25 COTAS) */}
      {activeTab === 'MEMBERS' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-extrabold text-slate-900 flex items-center gap-2">
                <Award className="w-4 h-4 text-emerald-600" />
                Alocação de Cotas Válidas e Pagamentos ({participations.length} Participações)
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Fechamento exato de centavos auditável (Seção 8.2) e responsabilidade coletiva aprovada.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto border border-slate-200 rounded-xl">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                <tr>
                  <th className="p-3">Membro</th>
                  <th className="p-3 text-center">Cotas</th>
                  <th className="p-3 text-center">Números das Cotas</th>
                  <th className="p-3 text-right">Oficial (A)</th>
                  <th className="p-3 text-right">Caixinha 20% (C)</th>
                  <th className="p-3 text-right">Total Devido</th>
                  <th className="p-3 text-center">Status Pagamento</th>
                  <th className="p-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {participations.map(p => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="p-3 font-semibold text-slate-900">{p.member_name}</td>
                    <td className="p-3 text-center font-bold font-mono">{p.quotas_count}</td>
                    <td className="p-3 text-center font-mono text-slate-500">
                      {p.assigned_quota_numbers.map(n => `#${n}`).join(', ')}
                    </td>
                    <td className="p-3 text-right font-mono text-slate-600">
                      {formatBRL(p.amount_official_share)}
                    </td>
                    <td className="p-3 text-right font-mono text-indigo-600">
                      {formatBRL(p.amount_box_share)}
                    </td>
                    <td className="p-3 text-right font-mono font-black text-slate-900">
                      {formatBRL(p.total_due)}
                    </td>
                    <td className="p-3 text-center">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          p.payment_status === 'BAIXADO'
                            ? 'bg-emerald-100 text-emerald-800'
                            : p.payment_status === 'VENCIDO'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {p.payment_status}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      {p.payment_status !== 'BAIXADO' ? (
                        <button
                          onClick={() => handlePayParticipationDirectly(p)}
                          className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold text-[11px] cursor-pointer"
                        >
                          Ver Pix demonstrativo
                        </button>
                      ) : (
                        <span className="text-emerald-600 font-bold flex items-center justify-end gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Pago
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: RATEIO DE PRÊMIO EXCLUSIVO (96% MEMBROS / 4% CAIXINHA) */}
      {activeTab === 'PRIZE_SPLIT' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">
              Seção 12 do Documento Oficial (30/10/2026)
            </span>
            <h2 className="text-lg font-black text-slate-900 mt-2 flex items-center gap-2">
              <Percent className="w-5 h-5 text-indigo-600" />
              Política Diferenciada de Rateio de Prêmios (96% / 4%)
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl leading-relaxed">
              O prêmio lotérico pertence aos verdadeiros titulares das cotas oficiais do bolão.
              <strong> 96% é destinado aos titulares das cotas e 4% é destinado à taxa de administração da caixinha.</strong>{' '}
              Esta política é exclusiva para o bolão da caixinha e não se confunde com as outras regras da caixinha.
            </p>
          </div>

          {/* Exemplo Clássico do Documento: R$ 1.000.000,00 */}
          <div className="bg-slate-50 rounded-2xl p-5 border border-slate-200 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Simular Valor do Prêmio Líquido da CAIXA (R$)
                </label>
                <input
                  type="number"
                  step="10000"
                  value={simGrossPrizeInput}
                  onChange={e => setSimGrossPrizeInput(parseFloat(e.target.value) || 0)}
                  className="w-64 px-3 py-2 bg-white border border-slate-300 rounded-xl text-lg font-black text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                />
              </div>

              <div className="text-xs text-slate-500">
                Divisão sobre <strong>{currentCampaign.total_valid_quotas} cotas oficiais</strong>
              </div>
            </div>

            {/* Resultado do Split 96% / 4% */}
            {(() => {
              const split = calculateBolaoPrizeSplit(simGrossPrizeInput, currentCampaign.total_valid_quotas);
              return (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                  <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200">
                    <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider block">
                      Repasse aos Titulares das Cotas (96%)
                    </span>
                    <div className="text-2xl font-black text-emerald-950 font-mono mt-1">
                      {formatBRL(split.memberShareTotal)}
                    </div>
                    <span className="text-xs text-emerald-700 mt-1 block">
                      <strong>{formatBRL(split.prizePerQuota)}</strong> por cota oficial
                    </span>
                    <span className="text-[11px] text-slate-500 mt-1 block">
                      (Titular de 2 cotas recebe {formatBRL(split.prizePerQuota * 2)})
                    </span>
                  </div>

                  <div className="p-4 rounded-xl bg-indigo-50 border border-indigo-200">
                    <span className="text-xs font-bold text-indigo-800 uppercase tracking-wider block">
                      Taxa de Administração da Caixinha (4%)
                    </span>
                    <div className="text-2xl font-black text-indigo-950 font-mono mt-1">
                      {formatBRL(split.adminFeeTotal)}
                    </div>
                    <span className="text-xs text-indigo-700 mt-1 block">
                      Receita de gestão exclusiva do bolão
                    </span>
                    <span className="text-[11px] text-slate-500 mt-1 block">
                      Retenção homologada em contrato
                    </span>
                  </div>

                  <div className="p-4 rounded-xl bg-white border border-slate-200">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block">
                      Exemplo Matemático da Seção 12
                    </span>
                    <p className="text-xs text-slate-700 mt-2 leading-relaxed">
                      Em um prêmio de R$ 1.000.000,00 com 20 cotas: R$ 960.000,00 vai aos membros (R$ 48.000/cota)
                      e R$ 40.000,00 para a caixinha. No modelo atual com 25 cotas: R$ 38.400,00 por cota.
                    </p>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* TAB 4: SIMULADOR DE MORA SIMPLES (20% AO MÊS) */}
      {activeTab === 'MORA' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-200">
              Seção 11 do Documento Oficial
            </span>
            <h2 className="text-lg font-black text-slate-900 mt-2 flex items-center gap-2">
              <Clock className="w-5 h-5 text-indigo-600" />
              Calculadora de Mora Diária para Bolões (20% ao Mês)
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl leading-relaxed">
              Mora simples de 20% ao mês calculada por dia de atraso sobre o principal vencido e não quitado:
              <br />
              <code className="text-indigo-600 font-bold">
                Juros = Principal Pendente × 0,20 × (dias de atraso ÷ 30)
              </code>
            </p>
          </div>

          {/* Botões com Exemplos do Documento (Base R$ 9,60) */}
          <div>
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2">
              Exemplo do Documento (2 Cotas = R$ 9,60):
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { days: 1, label: '1 dia de atraso', expectedJuros: 'R$ 0,06', total: 'R$ 9,66', amount: 9.60 },
                { days: 10, label: '10 dias de atraso', expectedJuros: 'R$ 0,64', total: 'R$ 10,24', amount: 9.60 },
                { days: 30, label: '30 dias de atraso', expectedJuros: 'R$ 1,92', total: 'R$ 11,52', amount: 9.60 },
              ].map(test => (
                <button
                  key={test.days}
                  type="button"
                  onClick={() => {
                    setMoraPendingInput(test.amount);
                    setMoraDaysInput(test.days);
                  }}
                  className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
                    moraPendingInput === test.amount && moraDaysInput === test.days
                      ? 'bg-indigo-50 border-indigo-400 ring-2 ring-indigo-300'
                      : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  <div className="text-xs font-bold text-indigo-700">{test.label}</div>
                  <div className="text-xs text-slate-600 mt-1">Juros: {test.expectedJuros}</div>
                  <div className="text-xs font-black text-slate-900 mt-0.5">Total: {test.total}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Simulador Interativo */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-slate-50 rounded-2xl p-5 border border-slate-200">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Principal Pendente (R$)
                </label>
                <input
                  type="number"
                  step="0.10"
                  value={moraPendingInput}
                  onChange={e => setMoraPendingInput(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-sm font-bold text-slate-900"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-bold text-slate-700">
                    Dias de Atraso Corridos
                  </label>
                  <span className="text-xs font-black text-indigo-600">{moraDaysInput} dias</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="60"
                  value={moraDaysInput}
                  onChange={e => setMoraDaysInput(parseInt(e.target.value, 10))}
                  className="w-full accent-indigo-600"
                />
              </div>
            </div>

            {(() => {
              const res = calculateBolaoMora(moraPendingInput, moraDaysInput);
              return (
                <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col justify-between">
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between text-slate-600">
                      <span>Principal Pendente:</span>
                      <span className="font-bold text-slate-900">{formatBRL(res.pendingPrincipal)}</span>
                    </div>
                    <div className="flex justify-between text-slate-600">
                      <span>Fórmula:</span>
                      <span className="font-mono text-[11px] text-slate-500">
                        {formatBRL(res.pendingPrincipal)} × 0,20 × ({res.daysOverdue}/30)
                      </span>
                    </div>
                    <div className="flex justify-between text-rose-600 font-bold border-t border-slate-100 pt-2">
                      <span>Juros de Mora (20%/mês):</span>
                      <span>+ {formatBRL(res.moraInterest)}</span>
                    </div>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-200 flex items-baseline justify-between">
                    <span className="text-xs font-bold text-slate-700">Total Atualizado:</span>
                    <span className="text-xl font-black text-slate-900 font-mono">
                      {formatBRL(res.totalWithMora)}
                    </span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* MODAL 1: ADICIONAR NOVA APOSTA (SELEÇÃO DE DEZENAS EM GRADE) */}
      {isAddGameModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <span className="text-xs font-bold text-indigo-600 uppercase">
                  {currentCampaign.campaign_name}
                </span>
                <h3 className="font-black text-lg text-slate-900 mt-0.5">
                  Montar Aposta #{currentCampaign.games.length + 1} — {currentCampaign.numbers_per_game} dezenas
                </h3>
              </div>
              <button
                onClick={() => setIsAddGameModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Barra de Progresso e Ações da Grade */}
            <div className="py-3 flex items-center justify-between text-xs bg-slate-50 px-3 rounded-xl border border-slate-200 my-2">
              <span className="font-bold text-slate-700">
                Selecionadas:{' '}
                <strong className="text-indigo-600 text-sm">
                  {selectedNumbers.length} de {currentCampaign.numbers_per_game}
                </strong>
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleGenerateSurpresinha}
                  className="px-2.5 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-lg shadow-2xs cursor-pointer flex items-center gap-1"
                >
                  <Sparkles className="w-3.5 h-3.5" /> Surpresinha
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedNumbers([])}
                  className="px-2.5 py-1 text-slate-600 hover:text-slate-900 font-semibold cursor-pointer"
                >
                  Limpar
                </button>
              </div>
            </div>

            {/* Grade Numérica Clicável */}
            <div className="flex-1 overflow-y-auto p-2">
              <div
                className={`grid gap-1.5 ${
                  modalityTheme.maxGrid <= 25
                    ? 'grid-cols-5'
                    : modalityTheme.maxGrid <= 60
                    ? 'grid-cols-6 sm:grid-cols-10'
                    : 'grid-cols-8 sm:grid-cols-10'
                }`}
              >
                {Array.from({ length: modalityTheme.maxGrid }, (_, i) => i + 1).map(num => {
                  const isSelected = selectedNumbers.includes(num);
                  return (
                    <button
                      key={num}
                      type="button"
                      onClick={() => toggleNumberSelection(num)}
                      className={`h-10 rounded-xl font-mono font-black text-xs transition-all cursor-pointer flex items-center justify-center ${
                        isSelected
                          ? `${modalityTheme.circleColor} ring-2 ring-indigo-400 shadow-md scale-105`
                          : 'bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200'
                      }`}
                    >
                      {num.toString().padStart(2, '0')}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Rodapé com Dezenas Escolhidas e Botão de Salvar */}
            <div className="pt-4 border-t border-slate-200 flex items-center justify-between gap-3">
              <div className="text-xs truncate max-w-sm">
                <span className="text-slate-500 font-bold">Escolhidas: </span>
                <span className="font-mono text-indigo-700 font-black">
                  {selectedNumbers.length > 0
                    ? selectedNumbers.map(n => n.toString().padStart(2, '0')).join(' • ')
                    : 'Nenhuma'}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddGameModalOpen(false)}
                  className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleSaveNewGame}
                  disabled={selectedNumbers.length !== currentCampaign.numbers_per_game}
                  className={`px-4 py-2 text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer ${
                    selectedNumbers.length === currentCampaign.numbers_per_game
                      ? 'bg-indigo-600 hover:bg-indigo-700 text-white'
                      : 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  }`}
                >
                  Adicionar Aposta
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: ROTEIRO PARA PREENCHIMENTO NA LOTÉRICA (SEÇÃO 7.1) */}
      {isPrintRoteiroOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto relative animate-in fade-in zoom-in-95">
            <button
              onClick={() => setIsPrintRoteiroOpen(false)}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-600 p-1"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Cabeçalho Obrigatório */}
            <div className="border-b-2 border-dashed border-slate-200 pb-5 text-center space-y-1">
              <span className="text-[11px] font-black tracking-widest uppercase bg-slate-900 text-white px-3 py-1 rounded-full">
                FR FINANCE — ROTEIRO DE APOSTAS PARA REGISTRO PRESENCIAL
              </span>
              <h2 className="text-xl font-black text-slate-900 mt-2">
                {currentCampaign.campaign_name}
              </h2>
              <p className="text-xs text-slate-500">
                Caixinha: <strong>{state.tenants.find(t => t.id === state.currentTenantId)?.display_name}</strong> • Concurso de referência #{currentCampaign.contest_number || 'A CONFIRMAR'}
              </p>
            </div>

            {/* Dados do Roteiro */}
            <div className="py-4 space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-slate-50 p-3 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-500 block">Total de Apostas:</span>
                  <strong>{currentCampaign.games.length} jogos</strong>
                </div>
                <div>
                  <span className="text-slate-500 block">Dezenas/Jogo:</span>
                  <strong>{currentCampaign.numbers_per_game} dezenas</strong>
                </div>
                <div>
                  <span className="text-slate-500 block">Cotas Internas:</span>
                  <strong>{currentCampaign.total_valid_quotas} cotas</strong>
                </div>
                <div>
                  <span className="text-slate-500 block">Custo Oficial Est.:</span>
                  <strong className="text-emerald-700">{formatBRL(currentCampaign.cost_official_bets)}</strong>
                </div>
              </div>

              {/* Lista das Apostas para o Atendente da Lotérica */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-700 block">
                  Jogos a Preencher nos Volantes da CAIXA:
                </span>
                <div className="space-y-2">
                  {currentCampaign.games.map(game => (
                    <div
                      key={game.id}
                      className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs"
                    >
                      <span className="font-black font-mono text-slate-900">
                        Jogo #{game.game_number.toString().padStart(2, '0')}:
                      </span>
                      <span className="font-mono font-bold text-indigo-900 text-sm tracking-wide">
                        {game.numbers.map(n => n.toString().padStart(2, '0')).join(' - ')}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Rodapé Obrigatório (Seção 7.1) */}
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-center font-bold text-amber-950 text-xs">
                DOCUMENTO INTERNO / NÃO É VOLANTE OFICIAL / NÃO É COMPROVANTE DE APOSTA / NÃO DÁ DIREITO A PRÊMIO
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-slate-200 pt-4">
              <span className="text-xs text-slate-400 font-mono">
                Versão do Rascunho: v{currentCampaign.version}
              </span>
              <button
                onClick={() => setIsPrintRoteiroOpen(false)}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-xs font-bold cursor-pointer"
              >
                Fechar Roteiro
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: REGISTRO DE RETORNO DA CAIXA (SEÇÃO 7.2) */}
      {isReceiptModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="font-black text-base text-slate-900 flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              Registrar Recibo Oficial da CAIXA
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Informe os dados do comprovante oficial impresso pela casa lotérica credenciada.
            </p>

            <form onSubmit={handleRegisterReceipt} className="space-y-4 mt-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Código do Recibo Oficial / Terminal Lotérico
                </label>
                <input
                  type="text"
                  value={receiptCodeInput}
                  onChange={e => setReceiptCodeInput(e.target.value)}
                  placeholder="Ex: CAIXA-REC-849204-LOT-BELEM"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs font-bold text-slate-900 font-mono"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Data do Registro Presencial na Lotérica
                </label>
                <input
                  type="date"
                  value={receiptDateInput}
                  onChange={e => setReceiptDateInput(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs font-bold text-slate-900"
                  required
                />
              </div>

              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-xs text-emerald-800">
                Ao registrar o comprovante, o bolão transiciona para o estado <strong>REGISTRADO_CONFERIDO</strong>,
                concedendo plena transparência aos membros participantes.
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsReceiptModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl cursor-pointer shadow-xs"
                >
                  Simular registro de recibo
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: CONFERÊNCIA DE SORTEIO E APURAÇÃO */}
      {isDrawModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="font-black text-base text-slate-900 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-500" />
              Conferir Resultado Oficial CAIXA
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Informe as dezenas sorteadas e o prêmio para aplicação automática do rateio 96% / 4%.
            </p>

            <form onSubmit={handleSimulateDraw} className="space-y-4 mt-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Dezenas Sorteadas (Separe por espaços ou vírgulas)
                </label>
                <input
                  type="text"
                  value={simDrawnNumbersInput}
                  onChange={e => setSimDrawnNumbersInput(e.target.value)}
                  placeholder="Ex: 01 08 18 42 51 (Deixe em branco para aleatório)"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs font-mono font-bold text-slate-900"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Prêmio Líquido a Ratear (R$)
                </label>
                <input
                  type="number"
                  step="1000"
                  value={simGrossPrizeInput}
                  onChange={e => setSimGrossPrizeInput(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm font-black text-slate-900 font-mono"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsDrawModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl cursor-pointer shadow-xs"
                >
                  Apurar e Distribuir (96% / 4%)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
