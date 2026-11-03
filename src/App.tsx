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
  Menu, MoreHorizontal, ChevronDown, Crown, BriefcaseBusiness, UserRound, X, LogOut
} from 'lucide-react';
import { appStore, AppState } from './services/store';
import { Navbar } from './components/Navbar';
import { PixModal } from './components/PixModal';
import { AdminManualModal } from './components/AdminManualModal';
import { AuditSuiteModal } from './components/AuditSuiteModal';
import { DashboardView } from './components/DashboardView';
import { MasterTenantRegistryView } from './components/MasterTenantRegistryView';
import { MasterAdminRegistryView } from './components/MasterAdminRegistryView';
import { MasterOnboardingView } from './components/MasterOnboardingView';
import { MembersView } from './components/MembersView';
import { ContributionsView } from './components/ContributionsView';
import { MemberAnnualPreviewView } from './components/MemberAnnualPreviewView';
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
import { isRoleTabAllowed, initialRoleTab } from './services/roleScope';
import { authService, AuthenticatedUser } from './services/authService';
import { createForegroundSessionGuard } from './services/sessionResumeGuard';

export default function App() {
  const [state, setState] = useState<AppState>(() => appStore.getState());
  const [activeTab, setActiveTab] = useState<string>('DASHBOARD');
  const [authenticatedUser, setAuthenticatedUser] = useState<AuthenticatedUser | null>(() => authService.getUser());
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState<boolean>(false);
  const [resumeValidationPending, setResumeValidationPending] = useState(false);
  const [securityOpen, setSecurityOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

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
    // Resposta da inicialização nunca pode apagar um novo login que chegou
    // enquanto /me ainda estava pendente.
    let mounted = true;
    const bootstrap = authService.captureSession();
    void authService.checkCurrentUser().then(user => {
      if (!mounted) return;
      if (user && authService.isSessionSnapshotCurrent(bootstrap)) {
        setAuthenticatedUser(user);
        appStore.setAuthenticatedContext(user);
      } else if (!authService.getUser()) {
        setAuthenticatedUser(null);
        appStore.clearAuthenticatedContext();
      }
    });

    const unsubscribeAuth = authService.subscribe(() => {
      const user = authService.getUser();
      setAuthenticatedUser(user);
      if (!user) {
        setSecurityOpen(false);
        appStore.clearAuthenticatedContext();
      }
    });

    const handleExpired = () => {
      setSessionExpiredNotice(true);
    };
    window.addEventListener('frcaixinha:session-expired', handleExpired);

    // Android e navegador: depois de retornar do segundo plano, nenhuma
    // tela protegida aparece até que /auth/me confirme a sessão atual.
    const resumeGuard = createForegroundSessionGuard(authService, setResumeValidationPending);
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        void resumeGuard.revalidate();
      }
    };
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) void resumeGuard.revalidate();
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('pageshow', onPageShow);

    return () => {
      mounted = false;
      resumeGuard.dispose();
      unsubscribeAuth();
      window.removeEventListener('frcaixinha:session-expired', handleExpired);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('pageshow', onPageShow);
    };
  }, []);

  const handleLoginSuccess = (user: AuthenticatedUser) => {
    setAuthenticatedUser(user);
    setSessionExpiredNotice(false);
    appStore.setAuthenticatedContext(user);
    setSecurityOpen(false);
    setMoreOpen(false);
    setActiveTab(user.role === 'TENANT_MEMBER' ? 'MEU_PAINEL' : 'DASHBOARD');
  };

  const handleLogout = async () => {
    await authService.logout();
    setAuthenticatedUser(null);
    appStore.clearAuthenticatedContext();
    setActiveTab('DASHBOARD');
    setSecurityOpen(false);
    setMoreOpen(false);
  };

  // Papel ativo validado no servidor; bloqueia renderizacoes de outras funcoes.
  useEffect(() => {
    if (!isRoleTabAllowed(state.currentRole, activeTab)) {
      setActiveTab(initialRoleTab(state.currentRole));
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

  // Enquanto volta do segundo plano, nunca expor dados de um perfil cuja
  // autorização ainda não foi revalidada pelo servidor.
  if (resumeValidationPending) {
    return (
      <main role="status" aria-live="polite"
        className="min-h-screen flex items-center justify-center bg-[#edf5ed] p-6">
        <div className="max-w-md rounded-2xl border border-[#b7cbb8] bg-white p-6 text-center text-[#17452f]">
          <strong className="block text-lg">Verificando sua sessão</strong>
          <p className="mt-2 text-sm">Confirmando o acesso seguro com o servidor.</p>
        </div>
      </main>
    );
  }

  // Itens de navegação conforme papel autenticado (Cláusula 11.1)
  const renderNavTabs = () => {
    if (state.currentRole === 'MASTER') {
      return [
        { id: 'DASHBOARD', label: 'Plataforma', icon: LayoutDashboard },
        { id: 'CAIXINHAS', label: 'Caixinhas', icon: BriefcaseBusiness },
        { id: 'LICENCAS', label: 'Licenças e Preços', icon: DollarSign },
        { id: 'ADMINISTRADORES', label: 'Administradores', icon: Users },
        { id: 'ONBOARDING', label: 'Preparação de acesso', icon: ShieldCheck },
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
  const visibleTab = isRoleTabAllowed(state.currentRole, activeTab) &&
    navItems.some(item => item.id === activeTab) ? activeTab : null;

  return (
    <div className="fr-app-shell min-w-0 max-w-full bg-[#f3f7f1] flex flex-col font-sans text-slate-900 selection:bg-[#cbab59] selection:text-[#063d2e]">
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

      {/* Sessao de papel imutavel: para outra area, sair e autenticar de novo. */}
      <div className="fr-app-profile shrink-0 border-b border-[#a88a4c]/40 bg-[#073c2c] px-4 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
          <div aria-label="Perfil autenticado" className="flex min-h-11 min-w-0 flex-1 items-center gap-2 rounded-xl border border-[#c09b53]/50 bg-[#0b523a] px-3 py-2 text-xs sm:text-sm text-[#fff2cf]">
            {state.currentRole === 'MASTER' ? <Crown className="h-4 w-4 shrink-0 text-[#f0ce78]"/> :
              state.currentRole === 'TENANT_ADMIN' ? <BriefcaseBusiness className="h-4 w-4 shrink-0 text-[#f0ce78]"/> :
                <UserRound className="h-4 w-4 shrink-0 text-[#f0ce78]"/>}
            <span className="min-w-0 whitespace-normal break-words leading-4">
              {state.currentRole === 'MASTER' ? 'Administrador Master — Plataforma' :
                state.currentRole === 'TENANT_ADMIN' ? 'Administrador — Minha caixinha' : 'Membro — Minha caixinha'}
            </span>
          </div>
          <button type="button" onClick={() => setSecurityOpen(value => !value)}
            aria-expanded={securityOpen}
            className="min-h-10 shrink-0 px-2 text-xs text-[#f1d58d] underline underline-offset-4">
            Sessões
          </button>
        </div>
      </div>
      {securityOpen && <SessionSecurityPanel onClose={() => setSecurityOpen(false)} />}
      <div role="note" className="shrink-0 bg-[#eaf4e8] px-4 py-1 text-center text-[11px] text-[#42664b]">
        Ambiente de homologação · operações financeiras reais indisponíveis
      </div>
      {/* Secondary Subnav Bar */}
      <nav className="hidden shrink-0 md:block border-b border-[#b4cfb5] bg-[#e7f1e7]">
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
                    ? 'bg-[#085137] text-[#f7d986] shadow-xs'
                    : 'text-[#275c40] hover:text-[#073d2b] hover:bg-[#d3e6d4]'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-[#f5cf79]' : 'text-[#35654c]'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="fr-app-main flex-1 min-h-0 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5" tabIndex={0}>
        {/* Master Views */}
        {visibleTab === 'DASHBOARD' && state.currentRole === 'MASTER' && (
          <DashboardView
            state={state}
            onNavigateTab={tab => setActiveTab(tab)}
            onOpenPixModal={openPixModal}
          />
        )}
        {visibleTab === 'CAIXINHAS' && state.currentRole === 'MASTER' && (
          <MasterTenantRegistryView state={state} />
        )}
        {visibleTab === 'ADMINISTRADORES' && state.currentRole === 'MASTER' && (
          <MasterAdminRegistryView state={state}
            onOpenOnboarding={()=>setActiveTab('ONBOARDING')}
          />
        )}
        {visibleTab === 'ONBOARDING' && state.currentRole === 'MASTER' && (
          <MasterOnboardingView state={state} />
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
          <MemberAnnualPreviewView state={state}/>
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
          <MemberAnnualPreviewView state={state}/>
        )}
      </main>

      {/* Menu com quatro destinos; funcoes menos comuns ficam em Mais. */}
      <nav aria-label="Navegação principal" className="fr-mobile-nav relative z-40 flex shrink-0 justify-around gap-1 px-2 pt-2 md:hidden">
        {navItems.slice(0,3).map(item => {
          const Icon = item.icon;
          const shortLabel = item.id === 'DASHBOARD' || item.id === 'MEU_PAINEL' ? 'Início'
            : item.id === 'MINHAS_CONTRIBUICOES' || item.id === 'CONTRIBUICOES' ? 'Contrib.'
            : item.id === 'MEU_EMPRESTIMO' || item.id === 'EMPRESTIMOS' ? 'Crédito'
            : item.id === 'CAIXINHAS' ? 'Caixinhas'
            : item.id === 'LICENCAS' ? 'Licenças'
            : item.id === 'SUPORTE' ? 'Suporte' : item.label;
          return (
            <button key={item.id} type="button" onClick={() => { setActiveTab(item.id); setMoreOpen(false); }}
              aria-current={activeTab === item.id ? 'page' : undefined}
              className={'flex min-h-12 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[11px] ' +
                (activeTab === item.id ? 'bg-[#195c3c] font-bold text-[#f6d488]' : 'text-emerald-100/80')}>
              <Icon className="h-5 w-5"/>
              <span className="max-w-full truncate">{shortLabel}</span>
            </button>
          );
        })}
        <button type="button" onClick={() => setMoreOpen(value => !value)}
          aria-expanded={moreOpen} aria-label="Mais opções"
          className={'flex min-h-12 min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-xl px-1 text-[11px] ' +
            (moreOpen ? 'bg-[#195c3c] font-bold text-[#f6d488]' : 'text-emerald-100/80')}>
          <MoreHorizontal className="h-5 w-5"/><span>Mais</span>
        </button>
      </nav>

      {moreOpen && (
        <div role="dialog" aria-label="Mais opções" className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-3 pb-20 md:hidden">
          <section className="w-full max-w-md rounded-2xl border border-[#bfa260] bg-[#073b2b] p-4 text-[#fff1ce] shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-bold">Mais</h2>
              <button type="button" onClick={() => setMoreOpen(false)} aria-label="Fechar menu" className="p-2">
                <X className="h-5 w-5"/>
              </button>
            </div>
            {navItems.slice(3).map(item => {
              const Icon = item.icon;
              return <button key={item.id} type="button"
                onClick={() => { setMoreOpen(false); if(item.id === 'AUDITORIA') setIsAuditOpen(true); else setActiveTab(item.id); }}
                className="flex min-h-11 w-full items-center gap-3 border-b border-emerald-700/60 py-2 text-left text-sm">
                <Icon className="h-5 w-5 text-[#f0ca72]"/>{item.label}
              </button>;
            })}
            <button type="button" onClick={() => { setMoreOpen(false); setSecurityOpen(true); }}
              className="flex min-h-11 w-full items-center gap-3 border-b border-emerald-700/60 py-2 text-left text-sm">
              <ShieldCheck className="h-5 w-5 text-[#f0ca72]"/>Segurança e sessões
            </button>
            <button type="button" onClick={() => { setMoreOpen(false); void handleLogout(); }}
              className="flex min-h-11 w-full items-center gap-3 py-2 text-left text-sm">
              <LogOut className="h-5 w-5 text-[#f0ca72]"/>Sair da conta
            </button>
          </section>
        </div>
      )}

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
