import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, Eye, EyeOff, KeyRound, Mail, ShieldCheck, Users, BriefcaseBusiness, AlertCircle } from 'lucide-react';
import { authService, AuthenticatedUser } from '../services/authService';

interface LoginViewProps {
  onLoginSuccess: (user: AuthenticatedUser) => void;
  sessionExpiredNotice?: boolean;
}
type AccessMode = 'login' | 'new';
type NewAccess = 'member' | 'admin' | null;

/** Identidade única: somente o servidor concede o papel depois do login. */
export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess, sessionExpiredNotice = false }) => {
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
    <main className="fr-page fr-sheen min-h-dvh min-w-0 overflow-x-hidden px-4 py-8 sm:py-10 flex flex-col items-center justify-center">
      <div className="relative z-10 w-full max-w-sm">
        <div className="flex flex-col items-center pb-6">
          <img src="/icon.svg" alt="FRcaixinha — monograma dourado e folhas"
            width="120" height="120" className="h-24 w-24 rounded-[26px] shadow-2xl shadow-amber-600/20" />
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
            <span className="fr-gold-text">FR</span><span className="text-[#f7ecbf]">caixinha</span>
          </h1>
          <p className="mt-1 text-center text-sm text-emerald-100/80">
            Mais que um app, um futuro em construção.
          </p>
        </div>

        <section className="rounded-[26px] border border-[#b99950]/40 bg-[#043c2d]/90 p-5 shadow-2xl shadow-black/30 sm:p-7"
          aria-label="Acesso à FRcaixinha">
          <div className="grid grid-cols-2 gap-1 rounded-xl border border-[#376d4d] bg-[#032e24] p-1" role="group" aria-label="Opções de acesso">
            <button type="button" onClick={() => { setMode('login'); setNewAccess(null); setError(null); }}
              aria-pressed={mode === 'login'}
              className={'min-h-11 rounded-lg px-3 text-sm font-semibold ' + (mode === 'login' ? 'fr-gold-button' : 'text-[#e9d9a7]')}>
              Entrar
            </button>
            <button type="button" onClick={() => { setMode('new'); setError(null); setResetHelp(false); }}
              aria-pressed={mode === 'new'}
              className={'min-h-11 rounded-lg px-3 text-sm font-semibold ' + (mode === 'new' ? 'fr-gold-button' : 'text-[#e9d9a7]')}>
              Primeiro acesso
            </button>
          </div>

          {mode === 'login' ? (
            <div className="mt-5">
              <h2 className="text-xl font-bold text-[#fff5d7]">Entrar na sua conta</h2>
              <p className="mt-1 text-sm text-emerald-100/80">
                Um login para Master, Administrador ou Membro.
              </p>

              {sessionExpiredNotice && (
                <p role="status" className="mt-3 rounded-lg border border-amber-400/40 bg-amber-950/40 p-3 text-sm text-amber-100">
                  Sua sessão expirou. Entre novamente.
                </p>
              )}
              {error && (
                <div role="alert" className="mt-3 flex items-start gap-2 rounded-lg border border-rose-400/40 bg-rose-950/50 p-3 text-sm text-rose-100">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />{error}
                </div>
              )}

              <form className="mt-5 space-y-4" onSubmit={submit}>
                <div>
                  <label htmlFor="login-username" className="mb-1.5 block text-sm font-semibold text-[#f5e7c2]">E-mail ou usuário</label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-[#b6d1be]" aria-hidden="true" />
                    <input id="login-username" type="text" autoComplete="username" value={email}
                      onChange={event => setEmail(event.target.value)} placeholder="Seu e-mail"
                      className="fr-input min-h-12 w-full rounded-xl pl-11 pr-3 text-base" />
                  </div>
                </div>
                <div>
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <label htmlFor="login-password" className="text-sm font-semibold text-[#f5e7c2]">Senha</label>
                    <button type="button" onClick={() => setResetHelp(value => !value)}
                      aria-expanded={resetHelp}
                      className="text-xs font-semibold text-[#f3d483] underline underline-offset-2">Esqueci a senha</button>
                  </div>
                  <div className="relative">
                    <KeyRound className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-[#b6d1be]" aria-hidden="true" />
                    <input id="login-password" type={showPassword ? 'text' : 'password'} autoComplete="current-password"
                      value={password} onChange={event => setPassword(event.target.value)} placeholder="Sua senha"
                      className="fr-input min-h-12 w-full rounded-xl pl-11 pr-12 text-base" />
                    <button type="button" onClick={() => setShowPassword(value => !value)}
                      aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                      className="absolute right-3 top-3 min-h-7 min-w-7 text-[#f5de9d]">
                      {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </div>
                  {resetHelp && <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-900/20 p-3 text-xs text-amber-100">
                    Recuperação automática ainda indisponível. Consulte quem autorizou seu acesso.
                  </p>}
                </div>
                <button type="submit" disabled={loading}
                  className="fr-gold-button flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-4 text-base disabled:opacity-60">
                  {loading ? 'Verificando...' : 'Entrar'}
                  {!loading && <ArrowRight className="h-5 w-5" aria-hidden="true" />}
                </button>
              </form>
              <p className="mt-4 flex items-center justify-center gap-2 text-xs text-emerald-100/70">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" /> Acesso protegido pelo servidor
              </p>
            </div>
          ) : (
            <div className="mt-5">
              <h2 className="text-xl font-bold text-[#fff5d7]">Primeiro acesso</h2>
              <p className="mt-1 text-sm text-emerald-100/80">Como deseja participar?</p>
              <div className="mt-4 grid gap-3">
                <button type="button" onClick={() => setNewAccess('member')}
                  aria-pressed={newAccess === 'member'}
                  className={'fr-outline flex min-h-16 w-full items-center gap-3 rounded-xl p-4 text-left ' +
                    (newAccess === 'member' ? 'ring-2 ring-amber-300' : '')}>
                  <Users className="h-6 w-6 shrink-0 text-[#f4d689]" aria-hidden="true" />
                  <span><strong className="block text-sm text-white">Sou novo membro</strong>
                    <span className="text-xs text-emerald-100/70">Participar de uma caixinha</span></span>
                </button>
                <button type="button" onClick={() => setNewAccess('admin')}
                  aria-pressed={newAccess === 'admin'}
                  className={'fr-outline flex min-h-16 w-full items-center gap-3 rounded-xl p-4 text-left ' +
                    (newAccess === 'admin' ? 'ring-2 ring-amber-300' : '')}>
                  <BriefcaseBusiness className="h-6 w-6 shrink-0 text-[#f4d689]" aria-hidden="true" />
                  <span><strong className="block text-sm text-white">Quero administrar uma caixinha</strong>
                    <span className="text-xs text-emerald-100/70">Acesso sujeito à autorização</span></span>
                </button>
              </div>
              {newAccess && (
                <div role="status" className="mt-4 rounded-xl border border-amber-400/40 bg-[#123d2b] p-4">
                  <p className="text-sm font-semibold text-[#fff0be]">
                    {newAccess === 'member' ? 'Acesso de membro' : 'Acesso de administrador'}
                  </p>
                  <p className="mt-1 text-sm text-emerald-50">
                    {newAccess === 'member'
                      ? 'Peça um convite ao administrador da caixinha.'
                      : 'O Administrador Master precisa autorizar seu acesso.'}
                  </p>
                  <p className="mt-2 text-xs text-[#f7dc99]">
                    Os convites eletrônicos e a ativação por e-mail ainda não foram habilitados.
                    Não é possível criar a conta diretamente neste aplicativo.
                  </p>
                </div>
              )}
              <button type="button" onClick={() => { setMode('login'); setNewAccess(null); }}
                className="mt-5 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-[#8eab83] text-sm font-semibold text-[#f4e9cd]">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Já tenho conta
              </button>
            </div>
          )}
        </section>

        <p className="mt-4 text-center text-[11px] text-emerald-100/60">
          Homologação · build {build} · sem operações financeiras reais
        </p>
      </div>
    </main>
  );
};
