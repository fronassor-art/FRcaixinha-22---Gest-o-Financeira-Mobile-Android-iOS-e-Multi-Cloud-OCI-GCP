import React, { useState } from 'react';
import {
  Wallet,
  Users,
  ShieldAlert,
  ChevronDown,
  BookOpen,
  Calendar,
  RotateCcw,
  UserCheck,
  Check,
  Building2,
  Lock,
  Compass,
  Cloud,
  Smartphone,
  Apple,
  Github
} from 'lucide-react';
import { appStore, AppState } from '../services/store';
import { UserRole } from '../types';

interface NavbarProps {
  state: AppState;
  onOpenManual: () => void;
  onOpenAudit: () => void;
  onOpenMobileInstall: () => void;
  onOpenMobilePreview: () => void;
  onNavigateCloud: () => void;
  onOpenGitHub: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  state,
  onOpenManual,
  onOpenAudit,
  onOpenMobileInstall,
  onOpenMobilePreview,
  onNavigateCloud,
  onOpenGitHub,
}) => {
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);

  const currentUser = state.users.find(u => u.id === state.currentUserId);
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const currentSub = state.subscriptions.find(s => s.tenant_id === state.currentTenantId);

  const handleSelectContext = (userId: string, role: UserRole, tenantId?: string) => {
    appStore.switchContext(userId, role, tenantId);
    setIsRoleDropdownOpen(false);
  };

  const handleReset = () => {
    if (window.confirm('Deseja redefinir todos os dados para o estado inicial homologado do contrato?')) {
      appStore.resetAllToSeed();
    }
  };

  return (
    <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-40 shadow-md">
      {/* Top Banner: Central Immutable Calendar Info */}
      <div className="bg-emerald-950/80 border-b border-emerald-900/60 px-4 py-1.5 text-[11px] text-emerald-200 flex flex-wrap items-center justify-between gap-2">
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
              <span className="text-xs font-bold bg-emerald-500 text-slate-950 px-1.5 py-0.5 rounded font-mono">2.2</span>
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
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-gradient-to-r from-slate-800 to-slate-850 hover:from-slate-750 hover:to-slate-800 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700/80 transition-all cursor-pointer shadow-xs"
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
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-emerald-950/80 hover:bg-emerald-900 text-emerald-200 text-xs font-semibold rounded-lg border border-emerald-700/60 transition-colors cursor-pointer"
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
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 transition-colors cursor-pointer shadow-xs"
            title="Sincronizar com Repositório GitHub (Git commit eebe257)"
          >
            <Github className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden sm:inline">GitHub</span>
          </button>

          {/* Quick Manual Button */}
          <button
            onClick={onOpenManual}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition-colors cursor-pointer"
            title="Abrir Manual Oficial em 16 Passos (Cláusula 11.4)"
          >
            <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden xl:inline">Manual</span>
          </button>

          {/* Quick Audit Button */}
          <button
            onClick={onOpenAudit}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-indigo-950/70 hover:bg-indigo-900/80 text-indigo-200 text-xs font-semibold rounded-lg border border-indigo-700/60 transition-colors cursor-pointer shadow-xs"
            title="Verificar Cenários de Prova AT-01 a AT-50"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-indigo-400" />
            <span className="hidden xl:inline">Auditoria</span>
          </button>

          {/* Reset Seed Button */}
          <button
            onClick={handleReset}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
            title="Restaurar dados iniciais para homologação"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Role & Tenant Selector Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
              className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-slate-800/90 hover:bg-slate-750 border border-slate-700 transition-all cursor-pointer text-left"
            >
              <div className="w-7 h-7 rounded-lg bg-emerald-600/30 text-emerald-300 flex items-center justify-center text-xs font-bold shrink-0">
                {state.currentRole === 'MASTER' ? '👑' : state.currentRole === 'TENANT_ADMIN' ? '💼' : '👤'}
              </div>
              <div className="hidden sm:block">
                <div className="text-xs font-bold text-white flex items-center gap-1">
                  <span>{currentUser?.name.split(' ')[0]}</span>
                  <span className="text-[10px] text-emerald-400 font-mono">({state.currentRole})</span>
                </div>
                <div className="text-[10px] text-slate-400 truncate max-w-[130px]">
                  {state.currentRole === 'MASTER' ? 'Plataforma Global' : currentTenant?.display_name}
                </div>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>

            {/* Dropdown Menu */}
            {isRoleDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setIsRoleDropdownOpen(false)}
                />
                <div className="absolute right-0 mt-2 w-80 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-2 z-40 animate-in fade-in zoom-in-95">
                  <div className="px-3 py-2 border-b border-slate-800">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Alternar Perfil e Contexto
                    </span>
                    <p className="text-[11px] text-slate-300">
                      Identidade única com segregação de permissões (Cláusula 2.3)
                    </p>
                  </div>

                  <div className="py-1.5 space-y-1">
                    {/* Master */}
                    <button
                      onClick={() => handleSelectContext('usr-master', 'MASTER')}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors ${
                        state.currentRole === 'MASTER'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">👑</span>
                        <div>
                          <div className="font-bold">Master da Plataforma</div>
                          <div className="text-[10px] opacity-75">Licenciamento, Preços & Suporte</div>
                        </div>
                      </div>
                      {state.currentRole === 'MASTER' && <Check className="w-4 h-4" />}
                    </button>

                    {/* Admin Inaugural (João Silva) */}
                    <button
                      onClick={() => handleSelectContext('usr-admin-joao', 'TENANT_ADMIN', 'tenant-inaugural')}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors ${
                        state.currentRole === 'TENANT_ADMIN' && state.currentTenantId === 'tenant-inaugural'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">💼</span>
                        <div>
                          <div className="font-bold">Admin: Caixinha Inaugural</div>
                          <div className="text-[10px] opacity-75">João Silva • 20% a.m. • 85/15</div>
                        </div>
                      </div>
                      {state.currentRole === 'TENANT_ADMIN' && state.currentTenantId === 'tenant-inaugural' && (
                        <Check className="w-4 h-4" />
                      )}
                    </button>

                    {/* Admin como Membro (João Silva - Participação Própria) */}
                    <button
                      onClick={() => handleSelectContext('usr-admin-joao', 'TENANT_MEMBER', 'tenant-inaugural')}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors ${
                        state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-admin-joao'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">👤</span>
                        <div>
                          <div className="font-bold">João Silva (Como Membro)</div>
                          <div className="text-[10px] opacity-75">1 cota própria • Autoempréstimo Cláusula 2.5</div>
                        </div>
                      </div>
                      {state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-admin-joao' && (
                        <Check className="w-4 h-4" />
                      )}
                    </button>

                    {/* Membro Maria Oliveira */}
                    <button
                      onClick={() => handleSelectContext('usr-maria', 'TENANT_MEMBER', 'tenant-inaugural')}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors ${
                        state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-maria'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">👤</span>
                        <div>
                          <div className="font-bold">Membro: Maria Oliveira</div>
                          <div className="text-[10px] opacity-75">2 cotas • Adimplente</div>
                        </div>
                      </div>
                      {state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-maria' && (
                        <Check className="w-4 h-4" />
                      )}
                    </button>

                    {/* Membro Pedro Santos (Empréstimo ativo) */}
                    <button
                      onClick={() => handleSelectContext('usr-pedro', 'TENANT_MEMBER', 'tenant-inaugural')}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors ${
                        state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-pedro'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">👤</span>
                        <div>
                          <div className="font-bold">Membro: Pedro Santos</div>
                          <div className="text-[10px] opacity-75">1 cota • Empréstimo Price em andamento</div>
                        </div>
                      </div>
                      {state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-pedro' && (
                        <Check className="w-4 h-4" />
                      )}
                    </button>

                    {/* Membro Ana Costa (3 meses de atraso - Cláusula 6.5) */}
                    <button
                      onClick={() => handleSelectContext('usr-ana', 'TENANT_MEMBER', 'tenant-inaugural')}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors ${
                        state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-ana'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">⚠️</span>
                        <div>
                          <div className="font-bold">Membro: Ana Costa</div>
                          <div className="text-[10px] text-amber-400">3 meses vencidos • Sem lucro (Cláusula 6.5)</div>
                        </div>
                      </div>
                      {state.currentRole === 'TENANT_MEMBER' && state.currentUserId === 'usr-ana' && (
                        <Check className="w-4 h-4" />
                      )}
                    </button>

                    <div className="border-t border-slate-800 my-1"></div>

                    {/* Outro Tenant: Renata Martins (Tech) */}
                    <button
                      onClick={() => handleSelectContext('usr-admin-renata', 'TENANT_ADMIN', 'tenant-tech')}
                      className={`w-full text-left p-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-colors ${
                        state.currentRole === 'TENANT_ADMIN' && state.currentTenantId === 'tenant-tech'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-cyan-400" />
                        <div>
                          <div className="font-bold">Admin: Caixinha Tech</div>
                          <div className="text-[10px] opacity-75">Renata Martins • 10% a.m. • 80/20</div>
                        </div>
                      </div>
                      {state.currentRole === 'TENANT_ADMIN' && state.currentTenantId === 'tenant-tech' && (
                        <Check className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
