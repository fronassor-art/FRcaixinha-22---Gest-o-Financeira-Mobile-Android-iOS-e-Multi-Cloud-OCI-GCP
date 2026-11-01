/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  Users,
  Wallet,
  TrendingUp,
  ShieldCheck,
  BookOpen,
  LifeBuoy,
  FileSpreadsheet,
  Coins,
  Ticket,
  Sliders,
  DollarSign,
  AlertTriangle,
  RotateCcw,
  Cloud,
  Smartphone,
  Apple,
  Menu
} from 'lucide-react';
import { appStore, AppState } from './services/store';
import { Navbar } from './components/Navbar';
import { PixModal } from './components/PixModal';
import { AdminManualModal } from './components/AdminManualModal';
import { AuditSuiteModal } from './components/AuditSuiteModal';
import { DashboardView } from './components/DashboardView';
import { MembersView } from './components/MembersView';
import { ContributionsView } from './components/ContributionsView';
import { LoansView } from './components/LoansView';
import { ConsentView } from './components/ConsentView';
import { LedgerView } from './components/LedgerView';
import { CycleClosingView } from './components/CycleClosingView';
import { MasterLicensingView } from './components/MasterLicensingView';
import { SupportSessionView } from './components/SupportSessionView';
import { LotteryDemoView } from './components/LotteryDemoView';
import { RaffleModuleView } from './components/RaffleModuleView';
import { BolaoModuleView } from './components/BolaoModuleView';
import { MultiCloudView } from './components/MultiCloudView';
import { MobileInstallModal } from './components/MobileInstallModal';
import { MobileDevicePreviewModal } from './components/MobileDevicePreviewModal';
import { GitHubSyncModal } from './components/GitHubSyncModal';
import { LoginView } from './components/LoginView';
import { authService, AuthenticatedUser } from './services/authService';

export default function App() {
  const [state, setState] = useState<AppState>(() => appStore.getState());
  const [activeTab, setActiveTab] = useState<string>('DASHBOARD');
  const [authenticatedUser, setAuthenticatedUser] = useState<AuthenticatedUser | null>(() => authService.getUser());
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState<boolean>(false);

  // Modais globais
  const [isManualOpen, setIsManualOpen] = useState(false);
  const [isAuditOpen, setIsAuditOpen] = useState(false);
  const [isMobileInstallOpen, setIsMobileInstallOpen] = useState(false);
  const [isMobilePreviewOpen, setIsMobilePreviewOpen] = useState(false);
  const [isGitHubSyncOpen, setIsGitHubSyncOpen] = useState(false);
  const [pixModalData, setPixModalData] = useState<{
    isOpen: boolean;
    title: string;
    amount: number;
    description: string;
    recipientName: string;
    referenceId: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    amount: 0,
    description: '',
    recipientName: '',
    referenceId: '',
    onConfirm: () => {},
  });

  // Reagir a mudanças no store
  useEffect(() => {
    const unsubscribe = appStore.subscribe(() => {
      setState({ ...appStore.getState() });
    });
    return () => unsubscribe();
  }, []);

  // Monitorar ciclo de vida de autenticação e expiração de sessão
  useEffect(() => {
    // Validação compulsória contra o servidor em /api/auth/me na inicialização
    authService.checkCurrentUser().then(user => {
      if (user) {
        setAuthenticatedUser(user);
        appStore.setAuthenticatedContext(user);
      } else {
        setAuthenticatedUser(null);
        appStore.clearAuthenticatedContext();
      }
    });

    const unsubscribeAuth = authService.subscribe(() => {
      const user = authService.getUser();
      setAuthenticatedUser(user);
      if (!user) {
        appStore.clearAuthenticatedContext();
      }
    });

    const handleExpired = () => {
      setSessionExpiredNotice(true);
    };
    window.addEventListener('frcaixinha:session-expired', handleExpired);

    return () => {
      unsubscribeAuth();
      window.removeEventListener('frcaixinha:session-expired', handleExpired);
    };
  }, []);

  const handleLoginSuccess = (user: AuthenticatedUser) => {
    setAuthenticatedUser(user);
    setSessionExpiredNotice(false);
    appStore.setAuthenticatedContext(user);
    if (user.role === 'MASTER') {
      setActiveTab('DASHBOARD');
    } else if (user.role === 'TENANT_ADMIN') {
      setActiveTab('DASHBOARD');
    } else {
      setActiveTab('MEU_PAINEL');
    }
  };

  const handleLogout = async () => {
    await authService.logout();
    setAuthenticatedUser(null);
    appStore.clearAuthenticatedContext();
  };

  // Ajustar aba ativa caso o papel mude
  useEffect(() => {
    if (state.currentRole === 'MASTER') {
      if (!['DASHBOARD', 'LICENCAS', 'NUVEM', 'SUPORTE', 'AUDITORIA'].includes(activeTab)) {
        setActiveTab('DASHBOARD');
      }
    } else if (state.currentRole === 'TENANT_ADMIN') {
      if (!['DASHBOARD', 'MEMBROS', 'CONTRIBUICOES', 'EMPRESTIMOS', 'NUVEM', 'CONSENTIMENTO', 'LEDGER', 'FECHAMENTO', 'LICENCA', 'RIFAS', 'BOLOES'].includes(activeTab)) {
        setActiveTab('DASHBOARD');
      }
    } else {
      if (!['MEU_PAINEL', 'MINHAS_CONTRIBUICOES', 'MEU_EMPRESTIMO', 'NUVEM', 'AUTORIZACAO_ADMIN', 'MEU_RESULTADO', 'MINHAS_RIFAS', 'MEUS_BOLOES'].includes(activeTab)) {
        setActiveTab('MEU_PAINEL');
      }
    }
  }, [state.currentRole]);

  const openPixModal = (params: {
    title: string;
    amount: number;
    description: string;
    recipientName: string;
    referenceId: string;
    onConfirm: () => void;
  }) => {
    setPixModalData({
      isOpen: true,
      ...params,
    });
  };

  // Se não estiver autenticado, exibe EXCLUSIVAMENTE a tela de login com segurança server-side
  if (!authenticatedUser) {
    return (
      <LoginView
        onLoginSuccess={handleLoginSuccess}
        sessionExpiredNotice={sessionExpiredNotice}
      />
    );
  }

  // Itens de navegação conforme papel autenticado (Cláusula 11.1)
  const renderNavTabs = () => {
    if (state.currentRole === 'MASTER') {
      return [
        { id: 'DASHBOARD', label: 'Painel Master (SaaS)', icon: LayoutDashboard },
        { id: 'LICENCAS', label: 'Licenças e Preços', icon: DollarSign },
        { id: 'NUVEM', label: 'Multi-Cloud OCI + GCP', icon: Cloud },
        { id: 'SUPORTE', label: 'Suporte e Break-Glass', icon: LifeBuoy },
        { id: 'AUDITORIA', label: 'Suíte AT-01 a AT-50', icon: ShieldCheck },
      ];
    }

    if (state.currentRole === 'TENANT_ADMIN') {
      return [
        { id: 'DASHBOARD', label: 'Visão Geral', icon: LayoutDashboard },
        { id: 'MEMBROS', label: 'Membros e Cotas', icon: Users },
        { id: 'CONTRIBUICOES', label: 'Contribuições (Dia 10)', icon: Wallet },
        { id: 'EMPRESTIMOS', label: 'Crédito Price', icon: TrendingUp },
        { id: 'RIFAS', label: 'Rifas da Caixinha', icon: Ticket },
        { id: 'BOLOES', label: 'Bolões Oficiais', icon: Ticket },
        { id: 'NUVEM', label: 'Multi-Cloud OCI + GCP', icon: Cloud },
        { id: 'CONSENTIMENTO', label: 'Autorização Anual Admin', icon: ShieldCheck },
        { id: 'LEDGER', label: 'Livro-Razão (Partidas Dobradas)', icon: FileSpreadsheet },
        { id: 'FECHAMENTO', label: 'Fechamento e Capital-Dias', icon: Coins },
        { id: 'LICENCA', label: 'Políticas & Licença', icon: Sliders },
      ];
    }

    // TENANT_MEMBER
    return [
      { id: 'MEU_PAINEL', label: 'Meu Painel', icon: LayoutDashboard },
      { id: 'MINHAS_CONTRIBUICOES', label: 'Minhas Contribuições', icon: Wallet },
      { id: 'MEU_EMPRESTIMO', label: 'Meu Empréstimo', icon: TrendingUp },
      { id: 'MINHAS_RIFAS', label: 'Minhas Rifas & Cartelas', icon: Ticket },
      { id: 'MEUS_BOLOES', label: 'Meus Bolões', icon: Ticket },
      { id: 'NUVEM', label: 'Nuvem & Segurança (OCI + GCP)', icon: Cloud },
      { id: 'AUTORIZACAO_ADMIN', label: 'Termo Coletivo Admin', icon: ShieldCheck },
      { id: 'MEU_RESULTADO', label: 'Meu Fechamento Anual', icon: Coins },
    ];
  };

  const navItems = renderNavTabs();

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans text-slate-900 selection:bg-emerald-500 selection:text-white pb-16 md:pb-0">
      {/* Top Navbar */}
      <Navbar
        state={state}
        onOpenManual={() => setIsManualOpen(true)}
        onOpenAudit={() => setIsAuditOpen(true)}
        onOpenMobileInstall={() => setIsMobileInstallOpen(true)}
        onOpenMobilePreview={() => setIsMobilePreviewOpen(true)}
        onNavigateCloud={() => setActiveTab('NUVEM')}
        onOpenGitHub={() => setIsGitHubSyncOpen(true)}
        onLogout={handleLogout}
      />

      {/* Secondary Subnav Bar */}
      <nav className="bg-white border-b border-slate-200 sticky top-16 z-30 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center gap-1 overflow-x-auto py-2">
          {navItems.map(item => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.id === 'AUDITORIA') {
                    setIsAuditOpen(true);
                  } else {
                    setActiveTab(item.id);
                  }
                }}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Master Views */}
        {activeTab === 'DASHBOARD' && state.currentRole === 'MASTER' && (
          <DashboardView
            state={state}
            onNavigateTab={tab => setActiveTab(tab)}
            onOpenPixModal={openPixModal}
          />
        )}
        {activeTab === 'LICENCAS' && (
          <MasterLicensingView state={state} onOpenPixModal={openPixModal} />
        )}
        {activeTab === 'SUPORTE' && <SupportSessionView state={state} />}
        {(activeTab === 'BOLOES' || activeTab === 'MEUS_BOLOES') && (
          <BolaoModuleView state={state} onOpenPixModal={openPixModal} />
        )}

        {/* Admin Views */}
        {activeTab === 'DASHBOARD' && state.currentRole === 'TENANT_ADMIN' && (
          <DashboardView
            state={state}
            onNavigateTab={tab => setActiveTab(tab)}
            onOpenPixModal={openPixModal}
          />
        )}
        {activeTab === 'MEMBROS' && <MembersView state={state} />}
        {activeTab === 'CONTRIBUICOES' && (
          <ContributionsView state={state} onOpenPixModal={openPixModal} />
        )}
        {activeTab === 'EMPRESTIMOS' && (
          <LoansView state={state} onOpenPixModal={openPixModal} />
        )}
        {activeTab === 'CONSENTIMENTO' && <ConsentView state={state} />}
        {activeTab === 'LEDGER' && <LedgerView state={state} />}
        {activeTab === 'FECHAMENTO' && (
          <CycleClosingView state={state} onOpenPixModal={openPixModal} />
        )}
        {activeTab === 'LICENCA' && (
          <MasterLicensingView state={state} onOpenPixModal={openPixModal} />
        )}
        {(activeTab === 'RIFAS' || activeTab === 'MINHAS_RIFAS') && (
          <RaffleModuleView state={state} onOpenPixModal={openPixModal} />
        )}

        {/* Multi-Cloud View (GCP + OCI) - Accessible across all roles */}
        {activeTab === 'NUVEM' && <MultiCloudView />}

        {/* Member Views */}
        {activeTab === 'MEU_PAINEL' && (
          <DashboardView
            state={state}
            onNavigateTab={tab => setActiveTab(tab)}
            onOpenPixModal={openPixModal}
          />
        )}
        {activeTab === 'MINHAS_CONTRIBUICOES' && (
          <ContributionsView state={state} onOpenPixModal={openPixModal} />
        )}
        {activeTab === 'MEU_EMPRESTIMO' && (
          <LoansView state={state} onOpenPixModal={openPixModal} />
        )}
        {activeTab === 'AUTORIZACAO_ADMIN' && <ConsentView state={state} />}
        {activeTab === 'MEU_RESULTADO' && (
          <CycleClosingView state={state} onOpenPixModal={openPixModal} />
        )}
      </main>

      {/* Footer com Aviso Legal Homologado */}
      <footer className="bg-white border-t border-slate-200 mt-auto py-6 mb-14 md:mb-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-xs text-slate-500 flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="font-bold text-slate-700">FRcaixinha 2.2</span> • Solução Mobile & Multi-Cloud para automação de caixinhas privadas.
            <div className="text-[11px] text-slate-400 mt-0.5">
              Não atua como instituição bancária nem detém custódia de depósitos de terceiros (Cláusula 1.1 e 1.7).
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsManualOpen(true)}
              className="text-emerald-700 hover:underline cursor-pointer"
            >
              Manual em 16 Passos (Cláusula 11.4)
            </button>
            <span>•</span>
            <button
              onClick={() => setIsAuditOpen(true)}
              className="text-indigo-700 hover:underline cursor-pointer"
            >
              Matriz AT-01 a AT-50
            </button>
            <span>•</span>
            <button
              onClick={() => setActiveTab('NUVEM')}
              className="text-cyan-700 hover:underline cursor-pointer font-medium"
            >
              OCI + GCP Soberano
            </button>
          </div>
        </div>
      </footer>

      {/* Mobile Sticky Bottom Navigation Dock (md:hidden) */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-slate-900/95 backdrop-blur-md border-t border-slate-800 flex items-center justify-around py-1.5 px-2 text-[10px] text-slate-400 select-none shadow-2xl">
        <button
          onClick={() => setActiveTab(state.currentRole === 'TENANT_MEMBER' ? 'MEU_PAINEL' : 'DASHBOARD')}
          className={`flex flex-col items-center gap-0.5 p-1 rounded-xl transition-colors cursor-pointer ${
            ['DASHBOARD', 'MEU_PAINEL'].includes(activeTab) ? 'text-emerald-400 font-bold' : 'hover:text-white'
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          <span>Início</span>
        </button>

        <button
          onClick={() => setActiveTab(state.currentRole === 'TENANT_MEMBER' ? 'MINHAS_CONTRIBUICOES' : 'CONTRIBUICOES')}
          className={`flex flex-col items-center gap-0.5 p-1 rounded-xl transition-colors cursor-pointer ${
            ['CONTRIBUICOES', 'MINHAS_CONTRIBUICOES'].includes(activeTab) ? 'text-emerald-400 font-bold' : 'hover:text-white'
          }`}
        >
          <Wallet className="w-4 h-4" />
          <span>Cotas</span>
        </button>

        <button
          onClick={() => setActiveTab(state.currentRole === 'TENANT_MEMBER' ? 'MEU_EMPRESTIMO' : 'EMPRESTIMOS')}
          className={`flex flex-col items-center gap-0.5 p-1 rounded-xl transition-colors cursor-pointer ${
            ['EMPRESTIMOS', 'MEU_EMPRESTIMO'].includes(activeTab) ? 'text-emerald-400 font-bold' : 'hover:text-white'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>Price</span>
        </button>

        <button
          onClick={() => setActiveTab(state.currentRole === 'TENANT_MEMBER' ? 'MEUS_BOLOES' : 'BOLOES')}
          className={`flex flex-col items-center gap-0.5 p-1 rounded-xl transition-colors cursor-pointer ${
            ['BOLOES', 'MEUS_BOLOES', 'RIFAS', 'MINHAS_RIFAS'].includes(activeTab) ? 'text-emerald-400 font-bold' : 'hover:text-white'
          }`}
        >
          <Ticket className="w-4 h-4" />
          <span>Bolões</span>
        </button>

        <button
          onClick={() => setActiveTab('NUVEM')}
          className={`flex flex-col items-center gap-0.5 p-1 rounded-xl transition-colors cursor-pointer ${
            activeTab === 'NUVEM' ? 'text-cyan-400 font-bold' : 'hover:text-white'
          }`}
        >
          <Cloud className="w-4 h-4" />
          <span>Nuvem</span>
        </button>

        <button
          onClick={() => setIsMobileInstallOpen(true)}
          className="flex flex-col items-center gap-0.5 p-1 rounded-xl text-emerald-400 hover:text-emerald-300 font-bold cursor-pointer"
        >
          <Smartphone className="w-4 h-4" />
          <span>App</span>
        </button>
      </div>

      {/* Modais Globais */}
      <PixModal
        isOpen={pixModalData.isOpen}
        onClose={() => setPixModalData(prev => ({ ...prev, isOpen: false }))}
        title={pixModalData.title}
        amount={pixModalData.amount}
        description={pixModalData.description}
        recipientName={pixModalData.recipientName}
        referenceId={pixModalData.referenceId}
        onConfirmPayment={pixModalData.onConfirm}
      />

      <AdminManualModal
        isOpen={isManualOpen}
        onClose={() => setIsManualOpen(false)}
      />

      <AuditSuiteModal
        isOpen={isAuditOpen}
        onClose={() => setIsAuditOpen(false)}
      />

      <MobileInstallModal
        isOpen={isMobileInstallOpen}
        onClose={() => setIsMobileInstallOpen(false)}
        onOpenGitHub={() => setIsGitHubSyncOpen(true)}
      />

      <GitHubSyncModal
        isOpen={isGitHubSyncOpen}
        onClose={() => setIsGitHubSyncOpen(false)}
      />

      <MobileDevicePreviewModal
        isOpen={isMobilePreviewOpen}
        onClose={() => setIsMobilePreviewOpen(false)}
      >
        <div className="bg-slate-100 min-h-full p-3 space-y-4">
          <div className="bg-slate-900 text-white p-3 rounded-2xl flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-white">FRcaixinha</span>
              <span className="text-[10px] font-bold bg-emerald-500 text-slate-950 px-1 py-0.2 rounded font-mono">2.2</span>
            </div>
            <span className="text-[10px] text-emerald-400 font-mono">OCI + GCP Ativos</span>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs space-y-2">
            <div className="text-xs font-bold text-slate-800">Visualização de App Mobile</div>
            <p className="text-[11px] text-slate-500">
              O layout é 100% responsivo para telas sensíveis ao toque de smartphones Android e Apple iPhone, com navegação rápida de polegar e suporte a PWA.
            </p>
            <button
              onClick={() => {
                setIsMobilePreviewOpen(false);
                setIsMobileInstallOpen(true);
              }}
              className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-all"
            >
              Ver Instruções de Instalação no Aparelho
            </button>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs space-y-2">
            <div className="text-xs font-bold text-slate-800">Módulos em Execução Mobile</div>
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <div className="p-2 bg-slate-50 rounded-xl border border-slate-100 font-medium">💰 Empréstimo Price</div>
              <div className="p-2 bg-slate-50 rounded-xl border border-slate-100 font-medium">🎟️ Rifas da Caixinha</div>
              <div className="p-2 bg-slate-50 rounded-xl border border-slate-100 font-medium">🍀 Bolões Oficiais</div>
              <div className="p-2 bg-slate-50 rounded-xl border border-slate-100 font-medium">☁️ OCI + GCP Nuvem</div>
            </div>
          </div>
        </div>
      </MobileDevicePreviewModal>
    </div>
  );
}
