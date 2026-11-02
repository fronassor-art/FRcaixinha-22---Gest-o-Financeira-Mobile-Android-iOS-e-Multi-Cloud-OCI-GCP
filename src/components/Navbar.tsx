import React from 'react';
import {
  Wallet,
  Users,
  ShieldAlert,
  BookOpen,
  Calendar,
  RotateCcw,
  Building2,
  Lock,
  Cloud,
  Smartphone,
  Github,
  LogOut,
  ShieldCheck
} from 'lucide-react';
import { appStore, AppState } from '../services/store';

interface NavbarProps {
  state: AppState;
  onOpenManual: () => void;
  onOpenAudit: () => void;
  onOpenMobileInstall: () => void;
  onOpenMobilePreview: () => void;
  onNavigateCloud: () => void;
  onOpenGitHub: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  state,
  onOpenManual,
  onOpenAudit,
  onOpenMobileInstall,
  onOpenMobilePreview,
  onNavigateCloud,
  onOpenGitHub,
  onLogout,
}) => {
  const currentUser = state.users.find(u => u.id === state.currentUserId);
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const currentSub = state.subscriptions.find(s => s.tenant_id === state.currentTenantId);
  const build = String(import.meta.env?.VITE_APP_BUILD_REF || 'local').slice(0, 7);

  const handleReset = () => {
    if (window.confirm('Deseja redefinir todos os dados para o estado inicial homologado do contrato?')) {
      appStore.resetAllToSeed();
    }
  };

  return (
    <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-40 shadow-md">
      {/* Top Banner: Central Immutable Calendar Info */}
      <div className="hidden md:flex bg-emerald-950/80 border-b border-emerald-900/60 px-4 py-1.5 text-[11px] text-emerald-200 flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-medium">
            <Calendar className="w-3.5 h-3.5 text-emerald-400" />
            <span>Calendário Central Imutável: <strong>01/01/2027 a 31/12/2027</strong></span>
          </div>
          <span className="text-emerald-500">•</span>
          <span>Vencimento mensal central: <strong>Dia 10</strong></span>
          <span className="text-emerald-500">•</span>
          <span>Liquidação do ciclo: <strong>10/01/2028</strong></span>
        </div>
        <div className="flex items-center gap-3 text-emerald-300">
          <span className="bg-emerald-900/60 px-2 py-0.5 rounded text-[10px] font-mono">Fuso: America/Belem</span>
          <span className="text-[10px] bg-emerald-500/20 text-emerald-300 font-semibold px-2 py-0.5 rounded-full">
            Tolerância: ZERO DIAS (Cláusula 3.8)
          </span>
        </div>
      </div>

      {/* Main Navbar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center shadow-md shadow-emerald-500/20">
            <Wallet className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-white">FRcaixinha</span>
              <span className="text-xs font-bold bg-emerald-500 text-slate-950 px-1.5 py-0.5 rounded">AI</span>
              <span className="text-[10px] font-mono text-slate-400" title="Versão instalada">{build}</span>
            </div>
            <p className="text-[10px] text-slate-400 -mt-0.5 hidden sm:block">
              Automação e Contabilidade Privada • Sem Custódia Bancária
            </p>
          </div>
        </div>

        {/* Center / Right Controls */}
        <div className="flex items-center gap-1.5 sm:gap-2.5">
          {/* Multi-Cloud OCI + GCP Status Badge Button */}
          <button
            onClick={onNavigateCloud}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 bg-gradient-to-r from-slate-800 to-slate-850 hover:from-slate-750 hover:to-slate-800 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700/80 transition-all cursor-pointer shadow-xs"
            title="Ver Topologia Multi-Cloud: Google Cloud (SP) + Oracle Cloud (Vinhedo)"
          >
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <Cloud className="w-3.5 h-3.5 text-cyan-400" />
            </div>
            <span className="hidden xl:inline">Multi-Cloud: OCI + GCP</span>
            <span className="hidden sm:inline xl:hidden">OCI + GCP</span>
            <span className="text-[10px] bg-slate-700/80 text-emerald-300 font-mono px-1 rounded hidden sm:inline">
              4.1ms
            </span>
          </button>

          {/* Mobile Install App Button */}
          <button
            onClick={onOpenMobileInstall}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 bg-emerald-950/80 hover:bg-emerald-900 text-emerald-200 text-xs font-semibold rounded-lg border border-emerald-700/60 transition-colors cursor-pointer"
            title="Instalar App no Celular (Android ou iPhone)"
          >
            <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden lg:inline">Instalar App</span>
            <span className="text-[9px] bg-emerald-800/80 text-white font-bold px-1 rounded hidden sm:inline">
              iOS/Android
            </span>
          </button>

          {/* Mobile Device Frame Simulator Toggle */}
          <button
            onClick={onOpenMobilePreview}
            className="flex items-center gap-1 px-2 py-1.5 bg-slate-800/90 hover:bg-slate-700 text-slate-300 text-xs rounded-lg border border-slate-700 transition-colors cursor-pointer hidden md:flex"
            title="Simular visualização em Smartphone (iPhone 16 Pro / Galaxy S24)"
          >
            <Smartphone className="w-3.5 h-3.5 text-slate-400" />
            <span className="hidden xl:inline text-[11px]">Simulador Celular</span>
          </button>

          {/* GitHub Sync Button */}
          <button
            onClick={onOpenGitHub}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition-colors cursor-pointer shadow-xs"
            title="Sincronizar com Repositório GitHub (Git commit eebe257)"
          >
            <Github className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden sm:inline">GitHub</span>
          </button>

          {/* Quick Manual Button */}
          <button
            onClick={onOpenManual}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition-colors cursor-pointer"
            title="Abrir Manual Oficial em 16 Passos (Cláusula 11.4)"
          >
            <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden xl:inline">Manual</span>
          </button>

          {/* Quick Audit Button */}
          <button
            onClick={onOpenAudit}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 bg-indigo-950/70 hover:bg-indigo-900/80 text-indigo-200 text-xs font-semibold rounded-lg border border-indigo-700/60 transition-colors cursor-pointer shadow-xs"
            title="Verificar Cenários de Prova AT-01 a AT-50"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden xl:inline">Auditoria</span>
          </button>

          {/* Reset Seed Button */}
          <button
            onClick={handleReset}
            className="hidden md:inline-flex p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
            title="Restaurar dados iniciais para homologação"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Perfil Autenticado no Servidor (Sem seletor client-side de troca de papel) */}
          <div className="flex items-center gap-2 pl-1 border-l border-slate-800">
            <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-slate-800/90 border border-slate-700">
              <div className="w-7 h-7 rounded-lg bg-emerald-600/30 text-emerald-300 flex items-center justify-center text-xs font-bold shrink-0">
                {state.currentRole === 'MASTER' ? '👑' : state.currentRole === 'TENANT_ADMIN' ? '💼' : '👤'}
              </div>
              <div className="hidden sm:block">
                <div className="text-xs font-bold text-white flex items-center gap-1.5">
                  <span>{currentUser?.name || 'Usuário Autenticado'}</span>
                  <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded ${
                    state.currentRole === 'MASTER'
                      ? 'bg-indigo-900/80 text-indigo-300 border border-indigo-700/60'
                      : state.currentRole === 'TENANT_ADMIN'
                      ? 'bg-emerald-900/80 text-emerald-300 border border-emerald-700/60'
                      : 'bg-blue-900/80 text-blue-300 border border-blue-700/60'
                  }`}>
                    {state.currentRole}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 truncate max-w-[140px]">
                  {state.currentRole === 'MASTER' ? 'Plataforma Global' : currentTenant?.display_name || 'Caixinha'}
                </div>
              </div>
            </div>

            {/* Botão de Encerramento Seguro de Sessão (Logout) */}
            <button
              onClick={onLogout}
              className="flex items-center gap-1.5 px-2.5 py-1.5 bg-rose-950/60 hover:bg-rose-900/80 text-rose-200 text-xs font-semibold rounded-xl border border-rose-800/60 transition-colors cursor-pointer shadow-xs"
              title="Encerrar sessão de forma segura (Logout)"
            >
              <LogOut className="w-3.5 h-3.5 text-rose-400" />
              <span className="hidden md:inline">Sair</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
