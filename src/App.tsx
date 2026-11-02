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
import { ServerLoansView } from './components/ServerLoansView';
import { ConsentView } from './components/ConsentView';
import { LedgerView } from './components/LedgerView';
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
import { SessionSecurityPanel } from './components/SessionSecurityPanel';
import { authService, AuthenticatedUser, AuthContext, contextLabel } from './services/authService';

export default function App() {
  const [state, setState] = useState<AppState>(() => appStore.getState());
  const [activeTab, setActiveTab] = useState<string>('DASHBOARD');
  const [authenticatedUser, setAuthenticatedUser] = useState<AuthenticatedUser | null>(() => authService.getUser());
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState<boolean>(false);
  const [contexts, setContexts] = useState<AuthContext[]>([]);
  const [changingContext, setChangingContext] = useState(false);
  const [contextError, setContextError] = useState<string | null>(null);
  const [securityOpen, setSecurityOpen] = useState(false);

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
        authService.listContexts().then(setContexts).catch(() => setContexts([]));
      } else {
        setAuthenticatedUser(null);
        appStore.clearAuthenticatedContext();
      }
    });

    const unsubscribeAuth = authService.subscribe(() => {
      const user = authService.getUser();
      setAuthenticatedUser(user);
      if (!user) {
        setContexts([]);
        setSecurityOpen(false);
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
    authService.listContexts().then(setContexts).catch(() => setContexts([]));
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
    setContexts([]);
    setActiveTab('DASHBOARD');
    setSecurityOpen(false);
  };

  const handleContextSwitch = async (context: AuthContext) => {
    setChangingContext(true);
    setContextError(null);
    try {
      const user = await authService.switchContext(context);
      appStore.clearAuthenticatedContext();
      appStore.setAuthenticatedContext(user);
      setActiveTab(user.role === 'TENANT_MEMBER' ? 'MEU_PAINEL' : 'DASHBOARD');
    } catch (error) {
      setContextError(error instanceof Error ? error.message : 'Falha na troca de vínculo.');
    } finally {
      setChangingContext(false);
    }
  };

  // Quando o papel muda, descartar qualquer aba herdada de outro perfil.
  useEffect(() => {
    const allowed = state.currentRole === 'MASTER'
      ? ['DASHBOARD', 'LICENCAS', 'SUPORTE', 'NUVEM', 'AUDITORIA']
      : state.currentRole === 'TENANT_ADMIN'
        ? ['DASHBOARD', 'MEMBROS', 'CONTRIBUICOES', 'EMPRESTIMOS', 'FECHAMENTO']
        : ['MEU_PAINEL', 'MINHAS_CONTRIBUICOES', 'MEU_EMPRESTIMO', 'MEU_RESULTADO'];
    if (!allowed.includes(activeTab)) {
      setActiveTab(state.currentRole === 'TENANT_MEMBER' ? 'MEU_PAINEL' : 'DASHBOARD');
    }
  }, [state.currentRole, activeTab]);

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

  if (changingContext) {
    return <div role="status" className="min-h-screen grid place-items-center bg-slate-950 text-white">Validando vínculo no servidor...</div>;
  }

  // Itens de navegação conforme papel autenticado (Cláusula 11.1)
  const renderNavTabs = () => {
    if (state.currentRole === 'MASTER') {
      return [
        { id: 'DASHBOARD', label: 'Plataforma', icon: LayoutDashboard },
        { id: 'LICENCAS', label: 'Licenças e Preços', icon: DollarSign },
        { id: 'SUPORTE', label: 'Suporte', icon: LifeBuoy },
        { id: 'NUVEM', label: 'Infraestrutura', icon: Cloud },
        { id: 'AUDITORIA', label: 'Suíte AT-01 a AT-50', icon: ShieldCheck },
      ];
    }

    if (state.currentRole === 'TENANT_ADMIN') {
      return [
        { id: 'DASHBOARD', label: 'Visão Geral', icon: LayoutDashboard },
        { id: 'MEMBROS', label: 'Membros e Cotas', icon: Users },
        { id: 'CONTRIBUICOES', label: 'Contribuições', icon: Wallet },
        { id: 'EMPRESTIMOS', label: 'Empréstimos', icon: TrendingUp },
        { id: 'FECHAMENTO', label: 'Fechamento', icon: Coins },
      ];
    }

    // TENANT_MEMBER
    return [
      { id: 'MEU_PAINEL', label: 'Meu Painel', icon: LayoutDashboard },
      { id: 'MINHAS_CONTRIBUICOES', label: 'Minhas Contribuições', icon: Wallet },
      { id: 'MEU_EMPRESTIMO', label: 'Meu Empréstimo', icon: TrendingUp },
      { id: 'MEU_RESULTADO', label: 'Meu Resultado', icon: Coins },
    ];
  };

  const navItems = renderNavTabs();
  const visibleTab = navItems.some(item => item.id === activeTab) ? activeTab : null;

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans text-slate-900 selection:bg-emerald-500 selection:text-white pb-16 md:pb-0">
      {/* Top Navbar */}
      <Navbar
        state={state}
        onOpenManual={() => setIsManualOpen(true)}
        onOpenAudit={() => setIsAuditOpen(true)}
        onOpenMobileInstall={() => setIsMobileInstallOpen(true)}
        onOpenMobilePreview={() => setIsMobilePreviewOpen(true)}
        onNavigateCloud={() => { if (state.currentRole === 'MASTER') setActiveTab('NUVEM'); }}
        onOpenGitHub={() => setIsGitHubSyncOpen(true)}
        onLogout={handleLogout}
      />

      {contexts.length > 1 && (
        <div className="bg-white border-b border-slate-200 px-4 py-3 flex flex-wrap items-center gap-3 text-sm">
          <label htmlFor="active-context" className="font-semibold">Meu acesso único — vínculo ativo</label>
          <select id="active-context" aria-label="Selecionar perfil e caixinha autorizados"
            disabled={changingContext}
            className="min-h-11 min-w-0 max-w-full rounded-lg border border-slate-300 px-3 disabled:opacity-60"
            value={authenticatedUser.role + ':' + (authenticatedUser.tenantId || '')}
            onChange={event => {
              const context = contexts.find(item => item.role + ':' + (item.tenant_id || '') === event.target.value);
              if (context) void handleContextSwitch(context);
            }}>
            {contexts.map(item => <option key={item.role + ':' + (item.tenant_id || '')} value={item.role + ':' + (item.tenant_id || '')}>
              {contextLabel(item)}
            </option>)}
          </select>
          {changingContext && <span role="status" className="text-slate-600">Validando novo vínculo no servidor...</span>}
        </div>
      )}
      {contextError && <div role="alert" className="bg-rose-50 p-3 text-sm text-rose-900">{contextError}</div>}
      <div className="bg-slate-50 px-4 py-1 border-b border-slate-200 text-right">
        <button type="button" onClick={() => setSecurityOpen(open => !open)}
          aria-expanded={securityOpen}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold">
          {securityOpen ? 'Ocultar segurança da conta' : 'Segurança e sessões'}
        </button>
      </div>
      {securityOpen && <SessionSecurityPanel onClose={() => setSecurityOpen(false)} />}

      <div role="note" className="bg-amber-50 border-b border-amber-200 px-4 py-1 text-[11px] font-medium text-amber-900">
        Ambiente de homologação. Nenhuma movimentação financeira real está habilitada.
      </div>
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
        {visibleTab === 'DASHBOARD' && state.currentRole === 'MASTER' && (
          <DashboardView
            state={state}
            onNavigateTab={tab => setActiveTab(tab)}
            onOpenPixModal={openPixModal}
          />
        )}
        {visibleTab === 'LICENCAS' && (
          <MasterLicensingView state={state} onOpenPixModal={openPixModal} />
        )}
        {visibleTab === 'SUPORTE' && <SupportSessionView state={state} />}
        {(visibleTab === 'BOLOES' || visibleTab === 'MEUS_BOLOES') && (
          <BolaoModuleView state={state} onOpenPixModal={openPixModal} />
        )}

        {/* Admin Views */}
        {visibleTab === 'DASHBOARD' && state.currentRole === 'TENANT_ADMIN' && (
          <DashboardView
            state={state}
            onNavigateTab={tab => setActiveTab(tab)}
            onOpenPixModal={openPixModal}
          />
        )}
        {visibleTab === 'MEMBROS' && <MembersView state={state} />}
        {visibleTab === 'CONTRIBUICOES' && (
          <ContributionsView state={state} onOpenPixModal={openPixModal} />
        )}
        {visibleTab === 'EMPRESTIMOS' && (
          <ServerLoansView state={state} />
        )}
        {visibleTab === 'CONSENTIMENTO' && <ConsentView state={state} />}
        {visibleTab === 'LEDGER' && <LedgerView state={state} />}
        {visibleTab === 'FECHAMENTO' && state.currentRole === 'TENANT_ADMIN' && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-2">
            <h2 className="text-lg font-bold">Fechamento</h2>
            <p className="text-sm text-slate-700">
              Apuração consolidada ainda não disponível nesta interface.
              Os dados serão exibidos somente após confirmação pelo servidor.
              Nenhuma liquidação financeira foi autorizada por esta tela.
            </p>
          </section>
        )}
        {visibleTab === 'LICENCA' && (
          <MasterLicensingView state={state} onOpenPixModal={openPixModal} />
        )}
        {(visibleTab === 'RIFAS' || visibleTab === 'MINHAS_RIFAS') && (
          <RaffleModuleView state={state} onOpenPixModal={openPixModal} />
        )}

        {/* Multi-Cloud View (GCP + OCI) - Accessible across all roles */}
        {visibleTab === 'NUVEM' && <MultiCloudView />}

        {/* Member Views */}
        {visibleTab === 'MEU_PAINEL' && (
          <DashboardView
            state={state}
            onNavigateTab={tab => setActiveTab(tab)}
            onOpenPixModal={openPixModal}
          />
        )}
        {visibleTab === 'MINHAS_CONTRIBUICOES' && (
          <ContributionsView state={state} onOpenPixModal={openPixModal} />
        )}
        {visibleTab === 'MEU_EMPRESTIMO' && (
          <ServerLoansView state={state} />
        )}
        {visibleTab === 'AUTORIZACAO_ADMIN' && <ConsentView state={state} />}
        {visibleTab === 'MEU_RESULTADO' && state.currentRole === 'TENANT_MEMBER' && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-2">
            <h2 className="text-lg font-bold">Meu resultado anual</h2>
            <p className="text-sm text-slate-700">
              Seu demonstrativo individual ainda não está disponível no servidor.
              Informações de outros membros e resultados administrativos
              não são exibidos neste perfil.
            </p>
          </section>
        )}
      </main>

      {/* Footer com Aviso Legal Homologado */}
      <footer className="hidden md:block bg-white border-t border-slate-200 mt-auto py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-xs text-slate-500 flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="font-bold text-slate-700">FRcaixinha AI Studio</span> • Ambiente de homologação.
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

      {/* Menu inferior compacto, derivado das abas autorizadas do perfil. */}
      <nav aria-label="Navegação do aplicativo" className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-slate-900 border-t border-slate-800 flex justify-around gap-1 px-2 py-2">
        {navItems.slice(0,4).map(item => {
          const Icon = item.icon;
          const shortLabel = item.id === 'MEU_RESULTADO' ? 'Resultado'
            : item.id === 'MINHAS_CONTRIBUICOES' ? 'Contrib.'
            : item.id === 'MEU_EMPRESTIMO' ? 'Crédito'
            : item.id === 'DASHBOARD' || item.id === 'MEU_PAINEL' ? 'Início'
            : item.id === 'CONTRIBUICOES' ? 'Contrib.'
            : item.id === 'EMPRESTIMOS' ? 'Crédito' : item.label;
          return (
            <button key={item.id} type="button" onClick={() => setActiveTab(item.id)}
              aria-current={activeTab === item.id ? 'page' : undefined}
              className={'min-w-0 flex-1 rounded-lg px-1 py-1 text-[11px] flex flex-col items-center gap-1 ' + (activeTab === item.id ? 'text-emerald-300 font-bold' : 'text-slate-300')}>
              <Icon className="h-5 w-5" />
              <span className="truncate max-w-full">{shortLabel}</span>
            </button>
          );
        })}
      </nav>

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
