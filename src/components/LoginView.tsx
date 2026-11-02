import React, { useState } from 'react';
import {
  ArrowLeft, ArrowRight, Eye, EyeOff, KeyRound, Lock, Mail,
  ShieldCheck, Users, BriefcaseBusiness, AlertCircle, HelpCircle,
} from 'lucide-react';
import { authService, AuthenticatedUser } from '../services/authService';

interface LoginViewProps {
  onLoginSuccess: (user: AuthenticatedUser) => void;
  sessionExpiredNotice?: boolean;
}

type AccessMode = 'login' | 'new';
type NewAccess = 'member' | 'admin' | null;

/** O login é único. O papel nunca é escolhido nem concedido pelo cliente. */
export const LoginView: React.FC<LoginViewProps> = ({
  onLoginSuccess,
  sessionExpiredNotice = false,
}) => {
  const [mode, setMode] = useState<AccessMode>('login');
  const [newAccess, setNewAccess] = useState<NewAccess>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [resetHelp, setResetHelp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const build = String(import.meta.env?.VITE_APP_BUILD_REF || 'local').slice(0, 7);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError('Informe o e-mail e a senha.');
      return;
    }
    setLoading(true);
    try {
      const user = await authService.login(email.trim(), password);
      setPassword('');
      onLoginSuccess(user);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível entrar.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen min-w-0 overflow-x-hidden bg-slate-950 px-4 py-7 sm:py-12 flex flex-col items-center justify-center">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-600">
            <Lock className="h-6 w-6 text-white" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-white">FRcaixinha</h1>
            <p className="text-xs text-slate-400">Acesso único e seguro</p>
          </div>
        </div>

        <section className="rounded-3xl bg-white p-5 shadow-xl sm:p-7" aria-label="Acesso à FRcaixinha">
          <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1" role="group" aria-label="Opções de acesso">
            <button type="button" onClick={() => { setMode('login'); setNewAccess(null); setError(null); }}
              aria-pressed={mode === 'login'}
              className={'min-h-11 rounded-lg px-3 text-sm font-semibold ' +
                (mode === 'login' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600')}>
              Entrar
            </button>
            <button type="button" onClick={() => { setMode('new'); setError(null); setResetHelp(false); }}
              aria-pressed={mode === 'new'}
              className={'min-h-11 rounded-lg px-3 text-sm font-semibold ' +
                (mode === 'new' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600')}>
              Primeiro acesso
            </button>
          </div>

          {mode === 'login' ? (
            <div className="mt-6">
              <h2 className="text-xl font-bold text-slate-900">Entrar na sua conta</h2>
              <p className="mt-1 text-sm text-slate-600">
                Um login para Master, Administrador ou Membro.
              </p>
              {sessionExpiredNotice && (
                <p role="status" className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                  Sua sessão expirou. Entre novamente.
                </p>
              )}
              {error && (
                <div role="alert" className="mt-4 flex items-start gap-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-900">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{error}
                </div>
              )}

              <form className="mt-5 space-y-4" onSubmit={submit}>
                <div>
                  <label htmlFor="login-username" className="mb-1.5 block text-sm font-semibold text-slate-800">
                    E-mail ou usuário
                  </label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                    <input id="login-username" type="text" autoComplete="username" value={email}
                      onChange={e => setEmail(e.target.value)} placeholder="Seu e-mail"
                      className="min-h-12 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-3 text-base text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-600" />
                  </div>
                </div>
                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <label htmlFor="login-password" className="text-sm font-semibold text-slate-800">Senha</label>
                    <button type="button" onClick={() => setResetHelp(v => !v)}
                      aria-expanded={resetHelp} className="text-xs font-semibold text-emerald-800 underline underline-offset-2">
                      Esqueci a senha
                    </button>
                  </div>
                  <div className="relative">
                    <KeyRound className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                    <input id="login-password" type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)}
                      placeholder="Sua senha" className="min-h-12 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-12 text-base text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-600" />
                    <button type="button" onClick={() => setShowPassword(v => !v)}
                      aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                      className="absolute right-3 top-3 min-h-6 min-w-6 text-slate-500">
                      {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </div>
                  {resetHelp && (
                    <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950">
                      A recuperação automática ainda não está disponível nesta homologação.
                      Procure o responsável pelo seu acesso. Nenhum e-mail foi enviado.
                    </p>
                  )}
                </div>
                <button type="submit" disabled={loading}
                  className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-base font-bold text-white disabled:opacity-60">
                  {loading ? 'Verificando acesso...' : 'Entrar'}
                  {!loading && <ArrowRight className="h-5 w-5" aria-hidden="true" />}
                </button>
              </form>
              <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-slate-500">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                Perfil e permissões validados pelo servidor
              </p>
            </div>
          ) : (
            <div className="mt-6">
              <h2 className="text-xl font-bold text-slate-900">Primeiro acesso</h2>
              <p className="mt-1 text-sm text-slate-600">Como você deseja participar?</p>
              <div className="mt-4 grid gap-3">
                <button type="button" onClick={() => setNewAccess('member')}
                  aria-pressed={newAccess === 'member'}
                  className={'flex min-h-16 w-full items-center gap-3 rounded-xl border p-4 text-left ' +
                    (newAccess === 'member' ? 'border-emerald-600 bg-emerald-50' : 'border-slate-200 bg-white')}>
                  <Users className="h-6 w-6 shrink-0 text-emerald-700" aria-hidden="true" />
                  <span><strong className="block text-sm text-slate-900">Sou novo membro</strong>
                    <span className="text-xs text-slate-600">Participar de uma caixinha</span></span>
                </button>
                <button type="button" onClick={() => setNewAccess('admin')}
                  aria-pressed={newAccess === 'admin'}
                  className={'flex min-h-16 w-full items-center gap-3 rounded-xl border p-4 text-left ' +
                    (newAccess === 'admin' ? 'border-emerald-600 bg-emerald-50' : 'border-slate-200 bg-white')}>
                  <BriefcaseBusiness className="h-6 w-6 shrink-0 text-emerald-700" aria-hidden="true" />
                  <span><strong className="block text-sm text-slate-900">Quero administrar uma caixinha</strong>
                    <span className="text-xs text-slate-600">Solicitar acesso de administrador</span></span>
                </button>
              </div>

              {newAccess && (
                <div role="status" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-sm font-semibold text-amber-950">
                    {newAccess === 'member' ? 'Acesso de membro' : 'Acesso de administrador'}
                  </p>
                  <p className="mt-1 text-sm text-amber-950">
                    {newAccess === 'member'
                      ? 'Peça um convite ao administrador da caixinha que deseja participar.'
                      : 'O Administrador Master precisa autorizar seu ingresso e vínculo com uma caixinha.'}
                  </p>
                  <p className="mt-2 text-xs text-amber-900">
                    Os convites eletrônicos e a ativação por e-mail ainda não foram
                    habilitados. Não é possível criar a conta diretamente neste aplicativo.
                  </p>
                </div>
              )}

              <button type="button" onClick={() => { setMode('login'); setNewAccess(null); }}
                className="mt-5 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-slate-300 text-sm font-semibold text-slate-800">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Já tenho conta
              </button>
            </div>
          )}
        </section>

        <p className="mt-5 text-center text-xs text-slate-400">
          Homologação • build {build} • operações financeiras desabilitadas
        </p>
      </div>
    </main>
  );
};
