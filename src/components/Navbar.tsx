import React, { useState } from 'react';
import { BookOpen, Cloud, Github, LogOut, ShieldCheck, SlidersHorizontal, Smartphone, X } from 'lucide-react';
import { AppState } from '../services/store';

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
  state, onOpenManual, onOpenAudit, onOpenMobileInstall,
  onOpenMobilePreview, onNavigateCloud, onOpenGitHub, onLogout,
}) => {
  const [toolsOpen, setToolsOpen] = useState(false);
  const currentUser = state.users.find(user => user.id === state.currentUserId);
  const displayName = (currentUser?.name || 'Sua conta').trim().split(' ')[0];
  const build = String(import.meta.env?.VITE_APP_BUILD_REF || 'local').slice(0, 7);
  const master = state.currentRole === 'MASTER';

  const tools = [
    {label:'Infraestrutura',icon:Cloud,action:onNavigateCloud},
    {label:'Auditoria',icon:ShieldCheck,action:onOpenAudit},
    {label:'Manual',icon:BookOpen,action:onOpenManual},
    {label:'GitHub',icon:Github,action:onOpenGitHub},
    {label:'Instalar app',icon:Smartphone,action:onOpenMobileInstall},
    {label:'Visualizar celular',icon:Smartphone,action:onOpenMobilePreview},
  ];
  return (
    <header className="fr-app-header relative z-40 shrink-0 border-b border-[#9f7a38]/35 bg-[#032d21] text-[#fff2cd] shadow-lg">
      <div className="mx-auto flex h-[66px] max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <img src="/icon.svg" alt="FR Finance" width="44" height="44"
            className="h-11 w-11 shrink-0 rounded-xl border border-[#b99444]/60" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <strong className="truncate text-lg tracking-tight text-[#f6d689]">FR Finance</strong>
              <span className="text-[10px] text-[#d2be89]" title="Versão instalada">{build}</span>
            </div>
            <p className="truncate text-[11px] text-emerald-100/70">
              {master ? 'Plataforma' : state.currentRole === 'TENANT_ADMIN' ? 'Administração' : 'Área do membro'}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden sm:block max-w-32 truncate text-sm text-[#e6dfc3]">Olá, {displayName}</span>
          {master && (
            <div className="relative">
              <button type="button" onClick={() => setToolsOpen(value => !value)}
                aria-label="Ferramentas do Master" aria-expanded={toolsOpen}
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#6c8a68] text-[#f6dc9f]">
                {toolsOpen ? <X className="h-5 w-5" /> : <SlidersHorizontal className="h-5 w-5" />}
              </button>
              {toolsOpen && (
                <div className="absolute right-0 top-12 z-50 w-52 rounded-xl border border-[#8b7041] bg-[#07402f] p-2 shadow-xl">
                  {tools.map(item => {
                    const Icon = item.icon;
                    return (
                      <button key={item.label} type="button" onClick={() => { setToolsOpen(false); item.action(); }}
                        className="flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-white hover:bg-[#176e4d]">
                        <Icon className="h-4 w-4 text-[#e8c775]" />{item.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
          <button type="button" onClick={onLogout} title="Sair da conta" aria-label="Sair da conta"
            className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#856d40] text-[#f7e6bc]">
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
};
