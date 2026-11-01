import React, { useState, useEffect } from 'react';
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  ArrowRight,
  Server,
  KeyRound,
  CheckCircle2,
  X,
  FileCode2,
  Database
} from 'lucide-react';
import { authService, AuthenticatedUser, AuthStatusResponse } from '../services/authService';

interface LoginViewProps {
  onLoginSuccess: (user: AuthenticatedUser) => void;
  sessionExpiredNotice?: boolean;
}

export const LoginView: React.FC<LoginViewProps> = ({
  onLoginSuccess,
  sessionExpiredNotice = false,
}) => {
  const [usernameOrEmail, setUsernameOrEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusInfo, setStatusInfo] = useState<AuthStatusResponse | null>(null);

  // Modal Esqueci Minha Senha
  const [isForgotModalOpen, setIsForgotModalOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotFeedback, setForgotFeedback] = useState<string | null>(null);
  const [forgotError, setForgotError] = useState<string | null>(null);

  // Carregar status do servidor
  useEffect(() => {
    authService.checkAuthStatus().then(setStatusInfo);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!usernameOrEmail.trim()) {
      setErrorMessage('Informe seu e-mail ou nome de usuário.');
      return;
    }
    if (!password) {
      setErrorMessage('Digite sua senha de acesso.');
      return;
    }

    setIsLoading(true);
    try {
      const user = await authService.login(usernameOrEmail, password);
      onLoginSuccess(user);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Autenticação ainda não configurada. Nenhuma sessão foi iniciada.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotError(null);
    setForgotFeedback(null);

    if (!forgotEmail || !forgotEmail.includes('@')) {
      setForgotError('Informe um e-mail válido com @.');
      return;
    }

    setForgotLoading(true);
    try {
      const res = await authService.requestPasswordReset(forgotEmail);
      setForgotFeedback(res.message);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setForgotError(err.message);
      } else {
        setForgotError('Serviço de recuperação indisponível.');
      }
    } finally {
      setForgotLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 flex flex-col justify-center items-center px-4 py-8 sm:px-6">
      {/* Brand & Security Header */}
      <div className="w-full max-w-md text-center mb-6">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-400 shadow-xl shadow-emerald-500/20 mb-3">
          <Lock className="w-7 h-7 text-white" />
        </div>
        <div className="flex items-center justify-center gap-2">
          <h1 className="text-2xl font-black tracking-tight text-white">FRcaixinha</h1>
          <span className="text-xs font-bold bg-emerald-500 text-slate-950 px-2 py-0.5 rounded font-mono">2.2</span>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          Acesso Seguro & Governança • Segregação de Papéis Server-Side
        </p>
      </div>

      {/* Main Card */}
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl p-6 sm:p-8 border border-slate-100">
        {/* Session Expired Banner */}
        {sessionExpiredNotice && (
          <div
            role="alert"
            className="mb-5 p-3.5 bg-amber-50 border border-amber-200 rounded-2xl flex items-start gap-2.5 text-xs text-amber-900"
          >
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <strong className="block font-bold">Sessão Expirada por Inatividade</strong>
              Sua sessão anterior encerrou após tempo limite de inatividade. Faça login novamente para prosseguir.
            </div>
          </div>
        )}

        {/* Form Title */}
        <div className="mb-6">
          <h2 className="text-lg font-extrabold text-slate-900">Entrar na Caixinha</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            O servidor valida sua identidade e autoriza seu perfil (Master, Admin ou Membro).
          </p>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div
            role="alert"
            className="mb-5 p-3.5 bg-rose-50 border border-rose-200 rounded-2xl flex items-start gap-2.5 text-xs text-rose-800 animate-in fade-in"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <strong className="block font-bold">Acesso Bloqueado</strong>
              <div className="font-medium leading-relaxed mt-0.5">{errorMessage}</div>
            </div>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {/* E-mail / Usuário */}
          <div>
            <label
              htmlFor="login-username"
              className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5"
            >
              E-mail ou Usuário
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <Mail className="w-4 h-4" />
              </div>
              <input
                id="login-username"
                name="usernameOrEmail"
                type="text"
                autoComplete="username"
                required
                aria-required="true"
                aria-invalid={errorMessage ? 'true' : 'false'}
                value={usernameOrEmail}
                onChange={e => setUsernameOrEmail(e.target.value)}
                placeholder="seu.email@exemplo.com.br"
                className="w-full pl-10 pr-3.5 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all"
              />
            </div>
          </div>

          {/* Senha */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="login-password"
                className="block text-xs font-bold text-slate-700 uppercase tracking-wider"
              >
                Senha
              </label>
              <button
                type="button"
                onClick={() => {
                  setForgotFeedback(null);
                  setForgotError(null);
                  setIsForgotModalOpen(true);
                }}
                className="text-xs text-emerald-700 hover:text-emerald-800 font-semibold hover:underline cursor-pointer"
              >
                Esqueci a senha
              </button>
            </div>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <KeyRound className="w-4 h-4" />
              </div>
              <input
                id="login-password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                aria-required="true"
                aria-invalid={errorMessage ? 'true' : 'false'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-11 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all font-mono"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Ocultar senha' : 'Exibir senha'}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 py-3.5 px-4 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-bold rounded-xl text-sm shadow-md shadow-emerald-600/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                <span>Verificando Credenciais no Servidor...</span>
              </>
            ) : (
              <>
                <span>Acessar Painel Autorizado</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Divisor Informativo de Governança Técnica */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200"></div>
          </div>
          <div className="relative flex justify-center text-[10px] uppercase font-bold tracking-wider">
            <span className="bg-white px-3 text-slate-400">Governança Técnica & Conformidade</span>
          </div>
        </div>

        {/* Quadro de Transparência sobre Backend e IdP do Contrato Mestre */}
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-3">
          <div className="flex items-center gap-2 font-bold text-slate-900">
            <Database className="w-4 h-4 text-emerald-600" />
            <span>Contrato Técnico Mestre: FastAPI + PostgreSQL</span>
          </div>
          <p className="text-[11px] text-slate-600 leading-relaxed">
            O Contrato Técnico Mestre (Cláusulas 1.2, 14.1 e 16.2) exige backend <strong>FastAPI (Python)</strong> integrado a banco de dados relacional <strong>PostgreSQL</strong> com Row-Level Security (RLS) para proteção criptográfica e isolamento multi-inquilino.
          </p>
          <div className="p-2.5 bg-amber-50 border border-amber-200/80 rounded-xl text-[11px] text-amber-900 space-y-1">
            <div className="flex items-center gap-1.5 font-bold">
              <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
              <span>Autenticação Bloqueada por Segurança</span>
            </div>
            <p className="leading-snug">
              Sem a conexão ativa com o banco PostgreSQL/FastAPI de produção, <strong>nenhuma sessão é iniciada</strong> e não é permitido login com contas de teste ou papéis selecionados no cliente.
            </p>
          </div>
        </div>

        {/* Security Disclaimers */}
        <div className="mt-5 pt-4 border-t border-slate-100 text-[11px] text-slate-500 space-y-2">
          <div className="flex items-start gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span>
              <strong>Zero Senhas em Navegador:</strong> Senhas, tokens e dados financeiros nunca são gravados em localStorage.
            </span>
          </div>
          <div className="flex items-start gap-1.5">
            <Server className="w-4 h-4 text-slate-600 shrink-0 mt-0.5" />
            <span>
              <strong>Autoridade Estrita do Servidor:</strong> Permissões e papéis são definidos exclusivamente pelo backend autenticado.
            </span>
          </div>
        </div>
      </div>

      {/* Footer Disclaimer */}
      <div className="text-center mt-6 text-xs text-slate-400 max-w-md">
        <span>FRcaixinha 2.2 • Isolamento Multi-Inquilino & Governança Privada</span>
        <div className="text-[11px] text-slate-500 mt-0.5">
          Conformidade com LGPD e Segregação de Fundos (Cláusula 1.7 e 2.8).
        </div>
      </div>

      {/* Modal: Esqueci Minha Senha */}
      {isForgotModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                <HelpCircle className="w-5 h-5 text-emerald-600" />
                <span>Recuperação de Acesso</span>
              </h3>
              <button
                type="button"
                onClick={() => setIsForgotModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-600 mb-4 leading-relaxed">
              Informe seu e-mail cadastrado. Um link de redefinição com chave temporária será processado pelo servidor de autenticação.
            </p>

            {forgotFeedback ? (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-900 space-y-3">
                <div className="flex items-center gap-2 font-bold text-emerald-800">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  <span>Solicitação Processada</span>
                </div>
                <p className="leading-relaxed">{forgotFeedback}</p>
                <button
                  type="button"
                  onClick={() => setIsForgotModalOpen(false)}
                  className="w-full py-2 bg-emerald-600 text-white rounded-lg font-bold text-xs cursor-pointer"
                >
                  Fechar
                </button>
              </div>
            ) : (
              <form onSubmit={handleForgotPassword} className="space-y-4">
                {forgotError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800">
                    {forgotError}
                  </div>
                )}
                <div>
                  <label htmlFor="forgot-email-input" className="block text-xs font-semibold text-slate-700 mb-1">
                    E-mail Cadastrado
                  </label>
                  <input
                    id="forgot-email-input"
                    type="email"
                    required
                    value={forgotEmail}
                    onChange={e => setForgotEmail(e.target.value)}
                    placeholder="seu.email@exemplo.com.br"
                    className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsForgotModalOpen(false)}
                    className="px-4 py-2 border border-slate-300 rounded-xl text-xs text-slate-700 hover:bg-slate-100 font-medium cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={forgotLoading}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold cursor-pointer disabled:opacity-50"
                  >
                    {forgotLoading ? 'Enviando...' : 'Enviar Link de Redefinição'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
