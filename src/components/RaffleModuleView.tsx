import React, { useState } from 'react';
import {
  Ticket,
  Calendar,
  DollarSign,
  AlertCircle,
  CheckCircle2,
  Clock,
  Award,
  Sparkles,
  QrCode,
  Printer,
  ChevronRight,
  TrendingUp,
  User,
  ShieldCheck,
  RefreshCw,
  Edit3,
  History,
  Info,
  Sliders,
  Check,
  X,
  ExternalLink
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { RaffleCampaign, RaffleCard, RaffleTicket, RaffleTicketStatus } from '../types';
import {
  calculateRaffleMoraInterest,
  calculateRaffleCampaignFinancials,
  calculateRaffleAnnualFinancials
} from '../services/financialEngine';

interface RaffleModuleViewProps {
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

export const RaffleModuleView: React.FC<RaffleModuleViewProps> = ({ state, onOpenPixModal }) => {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>(
    state.raffleCampaigns[0]?.id || 'raf-2027-01'
  );
  const [activeTab, setActiveTab] = useState<'CARDS' | 'ADMIN' | 'CALCULATOR' | 'ANNUAL'>('CARDS');

  // Modal para editar prêmio
  const [isEditPrizeModalOpen, setIsEditPrizeModalOpen] = useState(false);
  const [newPrizeInput, setNewPrizeInput] = useState<string>('200.00');
  const [prizeReasonInput, setPrizeReasonInput] = useState<string>('');

  // Modal para inspecionar/imprimir cartela digital
  const [inspectCard, setInspectCard] = useState<RaffleCard | null>(null);

  // Modal para editar bilhete (comprador e status)
  const [editTicket, setEditTicket] = useState<{
    card: RaffleCard;
    ticket: RaffleTicket;
  } | null>(null);
  const [buyerNameInput, setBuyerNameInput] = useState('');
  const [buyerPhoneInput, setBuyerPhoneInput] = useState('');
  const [buyerPixInput, setBuyerPixInput] = useState('');
  const [ticketStatusInput, setTicketStatusInput] = useState<RaffleTicketStatus>('GERADO');

  // Modal para realizar sorteio
  const [isDrawModalOpen, setIsDrawModalOpen] = useState(false);
  const [drawNumberInput, setDrawNumberInput] = useState<string>('');

  // Estado do Simulador de Inadimplência
  const [simPendingAmount, setSimPendingAmount] = useState<number>(50.00);
  const [simDaysOverdue, setSimDaysOverdue] = useState<number>(10);

  // Estado da Simulação Anual
  const [annualQuotasInput, setAnnualQuotasInput] = useState<number>(20);
  const [annualPrizeInput, setAnnualPrizeInput] = useState<number>(200.00);

  const currentCampaign = state.raffleCampaigns.find(c => c.id === selectedCampaignId) || state.raffleCampaigns[0];
  const campaignCards = state.raffleCards.filter(c => c.campaign_id === currentCampaign.id);

  // Se o usuário for membro regular, destacamos ou filtramos suas cartelas
  const userMembership = state.memberships.find(
    m => m.user_id === state.currentUserId && m.tenant_id === state.currentTenantId
  );
  const myCards = userMembership
    ? campaignCards.filter(c => c.membership_id === userMembership.id)
    : [];

  const isAdminOrMaster = state.currentRole === 'TENANT_ADMIN' || state.currentRole === 'MASTER';

  // Cálculos financeiros da campanha selecionada
  const activeQuotasCount = campaignCards.length;
  const campaignFinancials = calculateRaffleCampaignFinancials(
    activeQuotasCount,
    currentCampaign.prize_amount,
    0
  );

  // Arrecadação efetiva real computada a partir das cartelas
  const actualPaidAmount = campaignCards.reduce((acc, c) => acc + c.amount_paid, 0);
  const actualPendingAmount = campaignCards.reduce((acc, c) => acc + c.amount_pending, 0);
  const actualNetBalance = actualPaidAmount - currentCampaign.prize_amount;

  // Auditoria de prêmio da campanha
  const prizeHistory = state.rafflePrizeHistories.filter(h => h.campaign_id === currentCampaign.id);

  // Abertura do modal de edição de prêmio
  const handleOpenEditPrize = () => {
    setNewPrizeInput(currentCampaign.prize_amount.toFixed(2));
    setPrizeReasonInput('');
    setIsEditPrizeModalOpen(true);
  };

  const handleSavePrize = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseFloat(newPrizeInput);
    if (isNaN(parsed) || parsed < 0) {
      alert('Por favor, informe um valor de premiação válido.');
      return;
    }
    appStore.updateRafflePrize(currentCampaign.id, parsed, prizeReasonInput);
    setIsEditPrizeModalOpen(false);
  };

  const handleOpenEditTicket = (card: RaffleCard, ticket: RaffleTicket) => {
    setEditTicket({ card, ticket });
    setBuyerNameInput(ticket.buyer_name || '');
    setBuyerPhoneInput(ticket.buyer_phone || '');
    setBuyerPixInput(ticket.buyer_pix_key || '');
    setTicketStatusInput(ticket.status);
  };

  const handleSaveTicket = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTicket) return;
    appStore.updateRaffleTicketStatus(
      editTicket.ticket.id,
      ticketStatusInput,
      buyerNameInput.trim() || undefined,
      buyerPhoneInput.trim() || undefined,
      buyerPixInput.trim() || undefined
    );
    setEditTicket(null);
  };

  const handlePayTicketDirectly = (card: RaffleCard, ticket: RaffleTicket) => {
    onOpenPixModal({
      title: `Pagamento de Bilhete #${ticket.number.toString().padStart(3, '0')}`,
      amount: ticket.price,
      description: `Rifa ${currentCampaign.title} - Bilhete #${ticket.number} (Cota #${card.quota_number})`,
      recipientName: 'FRcaixinha Gestão Coletiva',
      referenceId: ticket.id,
      onConfirm: () => {
        appStore.payRaffleTicket(ticket.id, ticket.buyer_name || card.member_name);
      },
    });
  };

  const handlePayCardFull = (card: RaffleCard) => {
    onOpenPixModal({
      title: `Quitação Integral de Cartela #${card.id.split('-').pop()}`,
      amount: card.amount_pending,
      description: `Quitação de 10 bilhetes da Cota #${card.quota_number} (${card.member_name}) - ${currentCampaign.title}`,
      recipientName: 'FRcaixinha Gestão Coletiva',
      referenceId: card.id,
      onConfirm: () => {
        appStore.payRaffleCardFull(card.id);
      },
    });
  };

  const handlePerformDraw = (e: React.FormEvent) => {
    e.preventDefault();
    const num = parseInt(drawNumberInput, 10);
    if (isNaN(num) || num < 1 || num > activeQuotasCount * 10) {
      alert(`Informe um número válido entre 001 e ${(activeQuotasCount * 10).toString().padStart(3, '0')}.`);
      return;
    }
    appStore.drawRaffleWinner(currentCampaign.id, num);
    setIsDrawModalOpen(false);
  };

  const handleQuickDrawRandom = () => {
    const maxNumber = activeQuotasCount * 10;
    const randomNum = Math.floor(Math.random() * maxNumber) + 1;
    appStore.drawRaffleWinner(
      currentCampaign.id,
      randomNum,
      'Extração Simulada Oficial (Concurso Loteria Federal)'
    );
  };

  return (
    <div className="space-y-6">
      {/* Banner de Cabeçalho Oficial */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 text-white border border-indigo-900/60 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 bottom-0 w-96 bg-gradient-to-l from-indigo-500/10 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5">
                <Ticket className="w-3.5 h-3.5" /> Módulo de Rifas Homologado
              </span>
              <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full font-mono">
                Regra FRcaixinha 2.2
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white flex items-center gap-2">
              Campanhas de Rifas Vinculadas às Cotas
            </h1>
            <p className="text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
              Distribuição proporcional de 10 bilhetes por cota ativa (R$ 5,00/bilhete = R$ 50,00 por cota),
              arrecadação variável, premiação configurável via Pix e juros simples de mora (20%/mês pró-rata).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setActiveTab('CARDS')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'CARDS'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Cartelas Digitais
            </button>
            <button
              onClick={() => setActiveTab('ADMIN')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'ADMIN'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Painel & Auditoria
            </button>
            <button
              onClick={() => setActiveTab('CALCULATOR')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'CALCULATOR'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Simulador de Mora (20%)
            </button>
            <button
              onClick={() => setActiveTab('ANNUAL')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'ANNUAL'
                  ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              Demonstrativo Anual
            </button>
          </div>
        </div>

        {/* Calendário Central das 3 Campanhas Anuais (Seção 2 do Documento) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-6 pt-5 border-t border-slate-800/80">
          {state.raffleCampaigns.map(camp => {
            const isSelected = camp.id === selectedCampaignId;
            return (
              <div
                key={camp.id}
                onClick={() => setSelectedCampaignId(camp.id)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer text-left ${
                  isSelected
                    ? 'bg-indigo-900/50 border-amber-500/80 ring-2 ring-amber-500/30'
                    : 'bg-slate-800/40 border-slate-700/60 hover:bg-slate-800/70'
                }`}
              >
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-bold text-amber-400 uppercase tracking-wider text-[11px]">
                    {camp.campaign_number}ª Campanha Anual
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      camp.status === 'CONCLUIDA' || camp.status === 'ENCERRADA_SORTEADA'
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : camp.status === 'ATIVA'
                        ? 'bg-blue-500/20 text-blue-300'
                        : 'bg-slate-700 text-slate-400'
                    }`}
                  >
                    {camp.status === 'CONCLUIDA' || camp.status === 'ENCERRADA_SORTEADA'
                      ? 'Sorteio Realizado'
                      : camp.status === 'ATIVA'
                      ? 'Em Andamento'
                      : 'Prevista'}
                  </span>
                </div>
                <div className="font-extrabold text-sm text-white">{camp.month_name}</div>
                <div className="text-xs text-slate-300 mt-1 flex flex-col gap-0.5">
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-amber-400" />
                    Vencimento: <strong>{new Date(camp.due_date + 'T00:00:00').toLocaleDateString('pt-BR')}</strong>
                  </span>
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    Sorteio Loteria: <strong>{new Date(camp.draw_date + 'T00:00:00').toLocaleDateString('pt-BR')}</strong>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cartão de Resumo Financeiro da Campanha Selecionada */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Cotas Ativas
          </span>
          <div className="text-xl font-extrabold text-slate-900 mt-1 flex items-baseline gap-1">
            {activeQuotasCount}
            <span className="text-xs text-slate-500 font-normal">cotas</span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">10 bilhetes/cota</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Bilhetes Totais
          </span>
          <div className="text-xl font-extrabold text-indigo-600 mt-1 flex items-baseline gap-1">
            {campaignFinancials.totalTickets}
            <span className="text-xs text-slate-500 font-normal">unidades</span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">R$ 5,00 cada</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Arrecadação Prevista
          </span>
          <div className="text-xl font-extrabold text-slate-900 mt-1">
            R$ {campaignFinancials.expectedRevenue.toFixed(2)}
          </div>
          <span className="text-[11px] text-emerald-600 font-medium mt-1 block">
            100% adimplente
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Arrecadação Efetiva
          </span>
          <div className="text-xl font-extrabold text-emerald-600 mt-1">
            R$ {actualPaidAmount.toFixed(2)}
          </div>
          <span className="text-[11px] text-amber-600 font-medium mt-1 block">
            Pendente: R$ {actualPendingAmount.toFixed(2)}
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs relative group">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
              Premiação (Pix)
            </span>
            {isAdminOrMaster && (
              <button
                onClick={handleOpenEditPrize}
                className="text-indigo-600 hover:text-indigo-800 p-1 rounded hover:bg-indigo-50 transition-colors"
                title="Editar valor da premiação"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          <div className="text-xl font-extrabold text-amber-600 mt-1">
            R$ {currentCampaign.prize_amount.toFixed(2)}
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">
            {currentCampaign.prize_amount > campaignFinancials.expectedRevenue ? (
              <span className="text-rose-600 font-bold flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Excede arrecadação!
              </span>
            ) : (
              'Configurável pelo admin'
            )}
          </span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
            Saldo Pós-Prêmio
          </span>
          <div
            className={`text-xl font-extrabold mt-1 ${
              actualNetBalance >= 0 ? 'text-emerald-700' : 'text-rose-600'
            }`}
          >
            R$ {actualNetBalance.toFixed(2)}
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">
            Previsto: R$ {campaignFinancials.netBalance.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Seção de Sorteio Concluído / Alerta de Ganhador */}
      {currentCampaign.winning_number !== null && (
        <div className="bg-gradient-to-r from-amber-500/10 via-amber-500/20 to-amber-500/10 border-2 border-amber-500/60 rounded-2xl p-5 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-amber-500 text-slate-950 flex items-center justify-center font-black text-2xl shadow-md">
              <Award className="w-8 h-8" />
            </div>
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-amber-800 bg-amber-200/80 px-2.5 py-0.5 rounded-full">
                Sorteio Oficial Homologado
              </span>
              <h3 className="text-lg font-black text-slate-900 mt-1">
                Bilhete Premiado: #{currentCampaign.winning_number?.toString().padStart(3, '0')}
              </h3>
              <p className="text-xs text-slate-600 mt-0.5">
                Contemplado: <strong>{currentCampaign.winning_member_name}</strong> • Prêmio de{' '}
                <strong>R$ {currentCampaign.prize_amount.toFixed(2)} via Pix</strong> (
                {currentCampaign.draw_source})
              </p>
            </div>
          </div>
          {isAdminOrMaster && (
            <button
              onClick={() => appStore.resetRaffleCampaignDraw(currentCampaign.id)}
              className="px-3.5 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold border border-slate-300 transition-colors shadow-2xs flex items-center gap-1.5 cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Reabrir Sorteio (Simulação)
            </button>
          )}
        </div>
      )}

      {/* Regra de Negócio Crucial: Responsabilidade dos Membros */}
      <div className="bg-amber-50/70 border border-amber-200/80 rounded-xl p-3.5 text-xs text-amber-900 flex items-start gap-3">
        <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <strong>Regra Financeira Proposta (Seção 4 do Documento):</strong> Cada membro é integralmente
          responsável pelo pagamento dos valores correspondentes às suas cotas na campanha (R$ 50,00 por
          cota ativa). <em>A ausência de venda dos bilhetes NÃO elimina a obrigação de pagamento do valor atribuído à cota.</em>{' '}
          Vencimento no dia 20; a partir do dia 21 incide mora simples de 20% ao mês calculada por dia de
          atraso sobre o principal pendente.
        </div>
      </div>

      {/* TAB 1: CARTELAS DIGITAIS */}
      {activeTab === 'CARDS' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200">
            <div>
              <h2 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                <Ticket className="w-5 h-5 text-indigo-600" />
                Cartelas Digitais da Campanha ({campaignCards.length} Cartelas Geradas)
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Cada cota ativa recebe 1 cartela digital com 10 bilhetes numerados sequenciais.
              </p>
            </div>

            {isAdminOrMaster && currentCampaign.winning_number === null && (
              <div className="flex items-center gap-2">
                <button
                  onClick={handleQuickDrawRandom}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition-colors shadow-xs flex items-center gap-1.5 cursor-pointer"
                  title="Simular sorteio aleatório instantâneo"
                >
                  <Sparkles className="w-3.5 h-3.5" /> Sortear Rápido (Loteria Federal)
                </button>
                <button
                  onClick={() => setIsDrawModalOpen(true)}
                  className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-lg transition-colors shadow-xs flex items-center gap-1.5 cursor-pointer"
                >
                  Digitar Número Oficial
                </button>
              </div>
            )}
          </div>

          {/* Grid de Cartelas */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {campaignCards.map(card => {
              const isWinnerCard = card.tickets.some(t => t.number === currentCampaign.winning_number);
              const isCardSettled = card.status === 'QUITADA' || card.status === 'PAGA';
              const cardStatusColor =
                isCardSettled
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                  : card.status === 'PARCIAL'
                  ? 'bg-blue-50 border-blue-300 text-blue-800'
                  : 'bg-rose-50 border-rose-300 text-rose-800';

              return (
                <div
                  key={card.id}
                  className={`bg-white rounded-2xl border-2 transition-all p-5 shadow-xs relative ${
                    isWinnerCard ? 'border-amber-500 ring-2 ring-amber-400/40 bg-amber-50/20' : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  {/* Topo da Cartela */}
                  <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-black bg-slate-900 text-white px-2 py-0.5 rounded font-mono">
                          CARTELA #{card.quota_number.toString().padStart(3, '0')}
                        </span>
                        <span className="text-xs font-bold text-indigo-700">
                          COTA #{card.quota_number}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${cardStatusColor}`}>
                          {isCardSettled
                            ? 'QUITADA (R$ 50,00)'
                            : card.status === 'PARCIAL'
                            ? `PARCIAL (${card.paid_tickets}/10 QUITADOS)`
                            : 'PENDENTE (R$ 50,00)'}
                        </span>
                      </div>
                      <div className="font-extrabold text-base text-slate-900 mt-1 flex items-center gap-1.5">
                        <User className="w-4 h-4 text-slate-400" />
                        {card.member_name}
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] text-slate-400 block font-mono">
                        Números: #{card.tickets[0]?.number.toString().padStart(3, '0')} a #
                        {card.tickets[card.tickets.length - 1]?.number.toString().padStart(3, '0')}
                      </span>
                      <div className="text-sm font-black text-slate-900 mt-0.5">
                        {card.amount_pending > 0 ? (
                          <span className="text-rose-600">Devido: R$ {card.amount_pending.toFixed(2)}</span>
                        ) : (
                          <span className="text-emerald-600">100% Pago</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Grade dos 10 Bilhetes Numerados */}
                  <div className="grid grid-cols-5 gap-2 my-4">
                    {card.tickets.map(ticket => {
                      const isWinningTicket = ticket.number === currentCampaign.winning_number;
                      let ticketBg = 'bg-slate-50 border-slate-200 text-slate-700 hover:border-slate-300';
                      if (ticket.status === 'PAGO') {
                        ticketBg = 'bg-emerald-500/10 border-emerald-400 text-emerald-800 font-bold';
                      } else if (ticket.status === 'PAGAMENTO_PENDENTE') {
                        ticketBg = 'bg-blue-50 border-blue-400 text-blue-800 font-bold';
                      } else if (ticket.status === 'NAO_VENDIDO') {
                        ticketBg = 'bg-slate-100 border-slate-200 text-slate-400 line-through';
                      }

                      if (isWinningTicket) {
                        ticketBg = 'bg-amber-400 border-amber-600 text-slate-950 font-black ring-2 ring-amber-500 animate-pulse';
                      }

                      return (
                        <div
                          key={ticket.id}
                          onClick={() => handleOpenEditTicket(card, ticket)}
                          className={`p-2 rounded-xl border flex flex-col items-center justify-center cursor-pointer transition-all relative group text-center ${ticketBg}`}
                          title={`Clique para gerenciar o bilhete #${ticket.number}`}
                        >
                          <span className="text-sm font-mono font-black">
                            #{ticket.number.toString().padStart(3, '0')}
                          </span>
                          <span className="text-[10px] mt-0.5 truncate max-w-full">
                            {ticket.buyer_name || (ticket.status === 'PAGO' ? 'Pago' : 'R$ 5,00')}
                          </span>
                          {isWinningTicket && (
                            <span className="absolute -top-2 -right-1 text-[9px] bg-amber-600 text-white font-black px-1.5 py-0.2 rounded-full shadow-xs">
                              PREMIADO
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Rodapé da Cartela: Ações e Detalhes */}
                  <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setInspectCard(card)}
                        className="px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold flex items-center gap-1 transition-colors cursor-pointer"
                        title="Visualizar e Imprimir Cartela Digital com Hash e QR Code"
                      >
                        <Printer className="w-3.5 h-3.5" /> Ver Cartela
                      </button>
                      <span className="text-[11px] text-slate-400 font-mono hidden sm:inline">
                        Hash: {card.authenticity_code.substring(0, 10)}...
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {card.amount_pending > 0 && (
                        <button
                          onClick={() => handlePayCardFull(card)}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold transition-colors flex items-center gap-1.5 cursor-pointer shadow-xs"
                        >
                          <QrCode className="w-3.5 h-3.5" /> Quitar R$ {card.amount_pending.toFixed(2)} via Pix
                        </button>
                      )}
                      {card.amount_pending === 0 && (
                        <span className="flex items-center gap-1 text-emerald-600 font-bold">
                          <CheckCircle2 className="w-4 h-4" /> Cartela Paga
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 2: PAINEL DO ADMINISTRADOR E AUDITORIA */}
      {activeTab === 'ADMIN' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Editor e Histórico de Premiação (Seção 6 do Documento) */}
            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                    <Award className="w-5 h-5 text-amber-500" />
                    Premiação Configurável e Auditoria de Alterações
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Histórico imutável de todas as alterações de prêmio (Seção 6.4 do Documento).
                  </p>
                </div>
                {isAdminOrMaster && (
                  <button
                    onClick={handleOpenEditPrize}
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <Edit3 className="w-3.5 h-3.5" /> Reajustar Premiação
                  </button>
                )}
              </div>

              {/* Status Atual do Prêmio */}
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mb-5 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <span className="text-xs text-slate-500">Premiação Homologada Atual:</span>
                  <div className="text-2xl font-black text-slate-900">
                    R$ {currentCampaign.prize_amount.toFixed(2)}
                  </div>
                  <span className="text-xs text-slate-500">Modalidade: Dinheiro via Pix Mercado Pago</span>
                </div>

                <div className="text-right">
                  <span className="text-xs text-slate-500">Saldo Previsto da Caixinha:</span>
                  <div className="text-2xl font-black text-emerald-600">
                    R$ {campaignFinancials.netBalance.toFixed(2)}
                  </div>
                  <span className="text-xs text-slate-400">
                    (Arrecadação R$ {campaignFinancials.expectedRevenue.toFixed(2)} − Prêmio R${' '}
                    {currentCampaign.prize_amount.toFixed(2)})
                  </span>
                </div>
              </div>

              {/* Tabela de Histórico de Auditoria */}
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-slate-400" />
                Trilha de Auditoria do Administrador
              </h4>
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                    <tr>
                      <th className="p-3">Data/Hora</th>
                      <th className="p-3">Administrador</th>
                      <th className="p-3 text-right">Valor Anterior</th>
                      <th className="p-3 text-right">Novo Valor</th>
                      <th className="p-3">Justificativa / Motivo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {prizeHistory.map(h => (
                      <tr key={h.id} className="hover:bg-slate-50">
                        <td className="p-3 text-slate-500 font-mono">
                          {new Date(h.changed_at).toLocaleString('pt-BR')}
                        </td>
                        <td className="p-3 font-semibold text-slate-900">{h.admin_name}</td>
                        <td className="p-3 text-right text-slate-600 font-mono">
                          R$ {h.previous_amount.toFixed(2)}
                        </td>
                        <td className="p-3 text-right font-black text-indigo-700 font-mono">
                          R$ {h.new_amount.toFixed(2)}
                        </td>
                        <td className="p-3 text-slate-600">{h.reason}</td>
                      </tr>
                    ))}
                    {prizeHistory.length === 0 && (
                      <tr>
                        <td colSpan={5} className="p-4 text-center text-slate-400">
                          Nenhuma alteração registrada ainda.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Quadro de Transparência e Pagamentos */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
              <h3 className="text-base font-extrabold text-slate-900 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-600" />
                Prestação de Contas Pix
              </h3>
              <p className="text-xs text-slate-500">
                Todos os pagamentos e premiações são executados diretamente via chave Pix oficial da caixinha
                no Mercado Pago, sem custódia própria.
              </p>

              <div className="space-y-3 pt-2">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
                  <span className="text-slate-600">Total Arrecadado Via Pix:</span>
                  <span className="font-bold text-slate-900 font-mono">
                    R$ {actualPaidAmount.toFixed(2)}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
                  <span className="text-slate-600">Inadimplência Atual:</span>
                  <span className="font-bold text-rose-600 font-mono">
                    R$ {actualPendingAmount.toFixed(2)}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
                  <span className="text-slate-600">Taxa de Adesão/Quitação:</span>
                  <span className="font-bold text-indigo-700 font-mono">
                    {((actualPaidAmount / (campaignFinancials.expectedRevenue || 1)) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Botão de Registro Manual de Conferência */}
              <div className="pt-2">
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800">
                  <strong className="block mb-1">Destinação do Saldo:</strong>
                  O saldo de R$ {actualNetBalance.toFixed(2)} será incorporado ao rateio do fechamento anual
                  da caixinha (Cláusula 10 do Contrato).
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: SIMULADOR DE INADIMPLÊNCIA & MORA (SEÇÃO 10 E 11) */}
      {activeTab === 'CALCULATOR' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-700 border border-rose-200">
              Seção 10 e 11 do Documento
            </span>
            <h2 className="text-lg font-black text-slate-900 mt-2 flex items-center gap-2">
              <Sliders className="w-5 h-5 text-indigo-600" />
              Calculadora Oficial de Mora Diária (20% ao Mês)
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-3xl leading-relaxed">
              Vencimento no dia 20 de cada mês da campanha. Atraso inicia no dia 21. Mora simples de 20% ao
              mês calculada por dia de atraso sobre a base de 30 dias:
              <br />
              <code className="text-indigo-600 font-bold">
                Juros = Valor pendente × 0,20 × (dias de atraso ÷ 30)
              </code>
            </p>
          </div>

          {/* Testes Rápidos Homologados no Documento */}
          <div>
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2">
              Cenários Homologados no Documento (Base R$ 50,00):
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              {[
                { days: 1, label: '1 dia de atraso', expectedJuros: 'R$ 0,33', total: 'R$ 50,33', amount: 50 },
                { days: 10, label: '10 dias de atraso', expectedJuros: 'R$ 3,33', total: 'R$ 53,33', amount: 50 },
                { days: 20, label: '20 dias de atraso', expectedJuros: 'R$ 6,67', total: 'R$ 56,67', amount: 50 },
                { days: 30, label: '30 dias de atraso', expectedJuros: 'R$ 10,00', total: 'R$ 60,00', amount: 50 },
                { days: 45, label: '45 dias de atraso', expectedJuros: 'R$ 15,00', total: 'R$ 65,00', amount: 50 },
                {
                  days: 10,
                  label: 'Parcial (4 pendentes)',
                  expectedJuros: 'R$ 1,33',
                  total: 'R$ 21,33',
                  amount: 20,
                  isPartial: true
                },
              ].map(test => (
                <button
                  key={test.label}
                  type="button"
                  onClick={() => {
                    setSimPendingAmount(test.amount);
                    setSimDaysOverdue(test.days);
                  }}
                  className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                    simPendingAmount === test.amount && simDaysOverdue === test.days
                      ? 'bg-indigo-50 border-indigo-400 ring-2 ring-indigo-300'
                      : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  <div className="text-[11px] font-bold text-indigo-700 truncate">{test.label}</div>
                  <div className="text-xs text-slate-600 mt-1">Juros: {test.expectedJuros}</div>
                  <div className="text-xs font-extrabold text-slate-900 mt-0.5">Total: {test.total}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Simulador Interativo */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-slate-50 rounded-2xl p-5 border border-slate-200">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Valor Principal Pendente (R$)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="5"
                    min="0"
                    max="1000"
                    value={simPendingAmount}
                    onChange={e => setSimPendingAmount(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <span className="text-xs text-slate-400 font-mono whitespace-nowrap">
                    ({(simPendingAmount / 5).toFixed(0)} bilhetes)
                  </span>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-bold text-slate-700">
                    Dias de Atraso (a partir do dia 21)
                  </label>
                  <span className="text-xs font-black text-indigo-600">{simDaysOverdue} dias</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="90"
                  value={simDaysOverdue}
                  onChange={e => setSimDaysOverdue(parseInt(e.target.value, 10))}
                  className="w-full accent-indigo-600"
                />
              </div>
            </div>

            {/* Resultado do Cálculo */}
            {(() => {
              const res = calculateRaffleMoraInterest(simPendingAmount, simDaysOverdue);
              return (
                <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-600">
                      <span>Principal Pendente:</span>
                      <span className="font-bold text-slate-900">R$ {res.pendingPrincipal.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-600">
                      <span>Fórmula Aplicada:</span>
                      <span className="font-mono text-[11px] text-slate-500">
                        R$ {res.pendingPrincipal.toFixed(2)} × 0,20 × ({res.daysOverdue}/30)
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-rose-600 font-bold border-t border-slate-100 pt-2">
                      <span>Juros de Mora (20%/mês):</span>
                      <span className="text-sm font-black">+ R$ {res.interestAmount.toFixed(2)}</span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-200 flex items-baseline justify-between">
                    <span className="text-xs font-bold text-slate-700">Total Atualizado a Pagar:</span>
                    <span className="text-xl font-black text-slate-900 font-mono">
                      R$ {res.totalWithInterest.toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* TAB 4: DEMONSTRATIVO ANUAL CONSOLIDADO (SEÇÃO 12) */}
      {activeTab === 'ANNUAL' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                Seção 12 do Documento
              </span>
              <h2 className="text-lg font-black text-slate-900 mt-2 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-emerald-600" />
                Demonstrativo Anual Consolidado (3 Campanhas)
              </h2>
              <p className="text-xs text-slate-500 mt-1 max-w-2xl">
                Simulação das três rifas anuais (Março, Junho, Setembro) com distribuição proporcional do
                resultado aos membros e taxa de administração.
              </p>
            </div>

            {/* Controles do Simulador Anual */}
            <div className="flex items-center gap-3">
              <div>
                <label className="text-[11px] font-bold text-slate-500 uppercase block mb-1">
                  Cotas Ativas
                </label>
                <select
                  value={annualQuotasInput}
                  onChange={e => setAnnualQuotasInput(parseInt(e.target.value, 10))}
                  className="px-3 py-1.5 bg-slate-50 border border-slate-300 rounded-lg text-xs font-bold text-slate-900 cursor-pointer"
                >
                  <option value={10}>10 cotas (100 bilhetes)</option>
                  <option value={20}>20 cotas (200 bilhetes - Padrão)</option>
                  <option value={30}>30 cotas (300 bilhetes)</option>
                  <option value={40}>40 cotas (400 bilhetes)</option>
                  <option value={50}>50 cotas (500 bilhetes)</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-bold text-slate-500 uppercase block mb-1">
                  Prêmio/Campanha
                </label>
                <input
                  type="number"
                  step="50"
                  value={annualPrizeInput}
                  onChange={e => setAnnualPrizeInput(parseFloat(e.target.value) || 0)}
                  className="w-24 px-3 py-1.5 bg-slate-50 border border-slate-300 rounded-lg text-xs font-bold text-slate-900"
                />
              </div>
            </div>
          </div>

          {/* Tabela de Arrecadação Variável Conforme Seção 5 do Documento */}
          <div className="overflow-x-auto border border-slate-200 rounded-xl">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                <tr>
                  <th className="p-3">Cotas Ativas</th>
                  <th className="p-3 text-right">Bilhetes Totais</th>
                  <th className="p-3 text-right">Arrecadação Prevista (1 Rifa)</th>
                  <th className="p-3 text-right">Prêmio Estimado</th>
                  <th className="p-3 text-right">Saldo Líquido (1 Rifa)</th>
                  <th className="p-3 text-right">Arrecadação Anual (3 Rifas)</th>
                  <th className="p-3 text-right bg-emerald-50 text-emerald-900 font-bold">
                    Saldo Anual Consolidado
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[10, 20, 30, 40, 50].map(q => {
                  const oneCamp = calculateRaffleCampaignFinancials(q, annualPrizeInput, 0);
                  const annual = calculateRaffleAnnualFinancials(q, annualPrizeInput, 85, 15);
                  const isCurrent = q === annualQuotasInput;
                  return (
                    <tr
                      key={q}
                      className={isCurrent ? 'bg-indigo-50/60 font-bold' : 'hover:bg-slate-50'}
                    >
                      <td className="p-3 text-slate-900">
                        {q} cotas {isCurrent && <span className="text-indigo-600 text-[10px]">(Selecionado)</span>}
                      </td>
                      <td className="p-3 text-right font-mono text-slate-700">{q * 10}</td>
                      <td className="p-3 text-right font-mono text-slate-900">
                        R$ {oneCamp.expectedRevenue.toFixed(2)}
                      </td>
                      <td className="p-3 text-right font-mono text-amber-600">
                        R$ {annualPrizeInput.toFixed(2)}
                      </td>
                      <td className="p-3 text-right font-mono text-emerald-600">
                        R$ {oneCamp.netBalance.toFixed(2)}
                      </td>
                      <td className="p-3 text-right font-mono text-slate-900">
                        R$ {annual.totalExpectedRevenue.toFixed(2)}
                      </td>
                      <td className="p-3 text-right font-mono text-emerald-700 font-black bg-emerald-50/50">
                        R$ {annual.netBalance.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Cards do Split Demonstrativo (85% Membros / 15% Administração) */}
          {(() => {
            const annual = calculateRaffleAnnualFinancials(annualQuotasInput, annualPrizeInput, 85, 15);
            return (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-xs text-slate-500 font-semibold block">
                    Saldo Consolidado Anual
                  </span>
                  <div className="text-2xl font-black text-slate-900 mt-1 font-mono">
                    R$ {annual.netBalance.toFixed(2)}
                  </div>
                  <span className="text-[11px] text-slate-400 mt-1 block">
                    Total arrecadado R$ {annual.totalExpectedRevenue.toFixed(2)} − R${' '}
                    {annual.totalPrizeAmount.toFixed(2)} prêmios
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200">
                  <span className="text-xs text-emerald-800 font-semibold block">
                    Repasse aos Membros (85%)
                  </span>
                  <div className="text-2xl font-black text-emerald-700 mt-1 font-mono">
                    R$ {annual.memberShareAmount.toFixed(2)}
                  </div>
                  <span className="text-[11px] text-emerald-600 mt-1 block">
                    R$ {(annual.memberShareAmount / annualQuotasInput).toFixed(2)} por cota ativa no ano
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-indigo-50 border border-indigo-200">
                  <span className="text-xs text-indigo-800 font-semibold block">
                    Taxa de Administração (15%)
                  </span>
                  <div className="text-2xl font-black text-indigo-700 mt-1 font-mono">
                    R$ {annual.adminShareAmount.toFixed(2)}
                  </div>
                  <span className="text-[11px] text-indigo-600 mt-1 block">
                    Destinado à manutenção e gestão da caixinha
                  </span>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* MODAL: EDITAR PREMIAÇÃO (SEÇÃO 6) */}
      {isEditPrizeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-extrabold text-base text-slate-900 flex items-center gap-2">
                <Edit3 className="w-5 h-5 text-indigo-600" />
                Configurar Premiação da Rifa
              </h3>
              <button
                onClick={() => setIsEditPrizeModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSavePrize} className="space-y-4 mt-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Novo Valor da Premiação (R$)
                </label>
                <input
                  type="number"
                  step="10"
                  min="0"
                  value={newPrizeInput}
                  onChange={e => setNewPrizeInput(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-base font-black text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
                <span className="text-[11px] text-slate-400 mt-1 block">
                  Valor atual: R$ {currentCampaign.prize_amount.toFixed(2)} • Arrecadação prevista: R${' '}
                  {campaignFinancials.expectedRevenue.toFixed(2)}
                </span>
              </div>

              {parseFloat(newPrizeInput) > campaignFinancials.expectedRevenue && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Atenção:</strong> O prêmio informado (R$ {newPrizeInput}) é maior do que a
                    arrecadação prevista da caixinha (R$ {campaignFinancials.expectedRevenue.toFixed(2)}).
                  </span>
                </div>
              )}

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Justificativa / Motivo da Alteração
                </label>
                <textarea
                  rows={2}
                  value={prizeReasonInput}
                  onChange={e => setPrizeReasonInput(e.target.value)}
                  placeholder="Ex: Aprovação em assembleia de aumento do prêmio para estimular vendas..."
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
                <span className="text-[10px] text-slate-400 block mt-0.5">
                  Esta alteração será gravada permanentemente na trilha de auditoria com seu usuário e carimbo de tempo.
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsEditPrizeModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer"
                >
                  Confirmar e Gravar Auditoria
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: GERENCIAR/EDITAR BILHETE INDIVIDUAL */}
      {editTicket && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <span className="text-[11px] font-bold text-indigo-600 uppercase">
                  Cartela #{editTicket.card.quota_number} • Cota {editTicket.card.member_name}
                </span>
                <h3 className="font-extrabold text-lg text-slate-900 mt-0.5">
                  Bilhete #{editTicket.ticket.number.toString().padStart(3, '0')}
                </h3>
              </div>
              <button
                onClick={() => setEditTicket(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveTicket} className="space-y-4 mt-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Status do Bilhete (Seção 7.8)
                </label>
                <select
                  value={ticketStatusInput}
                  onChange={e => setTicketStatusInput(e.target.value as RaffleTicketStatus)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs font-bold text-slate-900"
                >
                  <option value="GERADO">Gerado (Disponível)</option>
                  <option value="PAGAMENTO_PENDENTE">Vendido - Pagamento Pendente</option>
                  <option value="PAGO">Pago (Quitado via Pix)</option>
                  <option value="NAO_VENDIDO">Não Vendido</option>
                  <option value="CANCELADO">Cancelado</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Nome do Comprador / Titular do Bilhete
                </label>
                <input
                  type="text"
                  value={buyerNameInput}
                  onChange={e => setBuyerNameInput(e.target.value)}
                  placeholder="Nome completo do comprador"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs text-slate-900"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Telefone / WhatsApp para Notificação de Prêmio
                </label>
                <input
                  type="text"
                  value={buyerPhoneInput}
                  onChange={e => setBuyerPhoneInput(e.target.value)}
                  placeholder="(91) 98888-7777"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs text-slate-900"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Chave Pix do Comprador (Para Pagamento Direto se Contemplado)
                </label>
                <input
                  type="text"
                  value={buyerPixInput}
                  onChange={e => setBuyerPixInput(e.target.value)}
                  placeholder="CPF, Telefone ou E-mail Pix"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs text-slate-900"
                />
              </div>

              <div className="pt-2 flex items-center justify-between gap-2 border-t border-slate-100">
                {editTicket.ticket.status !== 'PAGO' ? (
                  <button
                    type="button"
                    onClick={() => {
                      const c = editTicket.card;
                      const t = editTicket.ticket;
                      setEditTicket(null);
                      handlePayTicketDirectly(c, t);
                    }}
                    className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                  >
                    <QrCode className="w-3.5 h-3.5" /> Pagar R$ 5,00 via Pix
                  </button>
                ) : (
                  <span className="text-xs font-bold text-emerald-600 flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Pago em{' '}
                    {editTicket.ticket.paid_at
                      ? new Date(editTicket.ticket.paid_at).toLocaleDateString('pt-BR')
                      : 'Data confirmada'}
                  </span>
                )}

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setEditTicket(null)}
                    className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg cursor-pointer shadow-xs"
                  >
                    Salvar
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: INSPEÇÃO E IMPRESSÃO DA CARTELA DIGITAL (SEÇÃO 8) */}
      {inspectCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
          <div className="bg-white rounded-3xl max-w-xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 relative animate-in fade-in zoom-in-95">
            <button
              onClick={() => setInspectCard(null)}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-600 p-1"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Cabeçalho da Cartela Impressa */}
            <div className="border-b-2 border-dashed border-slate-200 pb-5 text-center">
              <span className="text-[11px] font-black tracking-widest uppercase bg-slate-900 text-white px-3 py-1 rounded-full">
                CARTELA DIGITAL OFICIAL • FRCAIXINHA 2.2
              </span>
              <h2 className="text-xl font-black text-slate-900 mt-2">
                {currentCampaign.title}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Cota #{inspectCard.quota_number.toString().padStart(3, '0')} • Titular:{' '}
                <strong>{inspectCard.member_name}</strong>
              </p>
            </div>

            {/* Conteúdo da Cartela */}
            <div className="py-5 space-y-4">
              <div className="flex items-center justify-between text-xs bg-slate-50 p-3 rounded-xl border border-slate-200">
                <div>
                  <span className="text-slate-500 block">Data de Vencimento:</span>
                  <strong className="text-slate-900">
                    {new Date(currentCampaign.due_date + 'T00:00:00').toLocaleDateString('pt-BR')}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-500 block">Data Prevista do Sorteio:</span>
                  <strong className="text-slate-900">
                    {new Date(currentCampaign.draw_date + 'T00:00:00').toLocaleDateString('pt-BR')}
                  </strong>
                </div>
                <div className="text-right">
                  <span className="text-slate-500 block">Premiação via Pix:</span>
                  <strong className="text-emerald-600 text-sm">
                    R$ {currentCampaign.prize_amount.toFixed(2)}
                  </strong>
                </div>
              </div>

              {/* Bilhetes em Destaque */}
              <div>
                <span className="text-xs font-bold text-slate-700 block mb-2">
                  10 Números Exclusivos Atribuídos à Cota (R$ 5,00 cada):
                </span>
                <div className="grid grid-cols-5 gap-2">
                  {inspectCard.tickets.map(t => (
                    <div
                      key={t.id}
                      className={`p-2.5 rounded-xl border text-center font-mono ${
                        t.status === 'PAGO'
                          ? 'bg-emerald-50 border-emerald-400 text-emerald-900 font-black'
                          : 'bg-slate-50 border-slate-300 text-slate-800 font-bold'
                      }`}
                    >
                      <div className="text-base font-black">
                        #{t.number.toString().padStart(3, '0')}
                      </div>
                      <div className="text-[9px] text-slate-500 uppercase mt-0.5">
                        {t.status === 'PAGO' ? 'Pago' : 'Pendente'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* QR Code Digital e Hash Criptográfico */}
              <div className="flex items-center gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div className="w-16 h-16 bg-white border border-slate-300 rounded-lg flex items-center justify-center p-1 shrink-0">
                  <QrCode className="w-14 h-14 text-slate-900" />
                </div>
                <div className="text-xs space-y-1 overflow-hidden">
                  <div className="font-bold text-slate-900">Código de Autenticidade Digital:</div>
                  <div className="font-mono text-[10px] text-slate-600 truncate bg-white px-2 py-1 rounded border border-slate-200">
                    {inspectCard.authenticity_code}
                  </div>
                  <p className="text-[10px] text-slate-400 leading-tight">
                    Validação em conformidade com as regras financeiras da FRcaixinha 2.2. Modalidade interna
                    autorizada com prestação de contas no livro-razão.
                  </p>
                </div>
              </div>
            </div>

            {/* Rodapé / Botão de Fechar */}
            <div className="flex items-center justify-between border-t border-slate-200 pt-4">
              <span className="text-xs text-slate-400 font-mono">
                Emitida eletronicamente pelo applet FRcaixinha
              </span>
              <button
                onClick={() => setInspectCard(null)}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold rounded-xl transition-colors cursor-pointer"
              >
                Concluir Visualização
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: SORTEIO COM NÚMERO ESPECÍFICO */}
      {isDrawModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="font-extrabold text-base text-slate-900 flex items-center gap-2">
              <Award className="w-5 h-5 text-indigo-600" />
              Inserir Resultado do Sorteio
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Informe os dígitos finais extraídos do 1º Prêmio da Loteria Federal Oficial.
            </p>

            <form onSubmit={handlePerformDraw} className="space-y-4 mt-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Número Premiado (001 a {(activeQuotasCount * 10).toString().padStart(3, '0')})
                </label>
                <input
                  type="number"
                  min="1"
                  max={activeQuotasCount * 10}
                  value={drawNumberInput}
                  onChange={e => setDrawNumberInput(e.target.value)}
                  placeholder="Ex: 27"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-lg font-black text-slate-900 text-center font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsDrawModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer"
                >
                  Homologar Resultado
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
