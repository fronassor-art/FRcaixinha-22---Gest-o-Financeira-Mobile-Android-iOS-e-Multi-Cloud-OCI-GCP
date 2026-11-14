import React, { useState } from 'react';
import { authService } from '../services/authService';

export type AccessLink = { mode: 'recuperacao' | 'convite'; token: string };

/** Existing Brevo links use /#recuperacao?token=... and /#convite?token=...
 * Never save opaque credentials in storage, logs, analytics or browser history.
 */
export function parseAccessLink(hash: string): AccessLink | null {
  if (typeof hash !== 'string') return null;
  const mode = hash.startsWith('#recuperacao?') ? 'recuperacao'
    : hash.startsWith('#convite?') ? 'convite' : null;
  if (!mode) return null;
  const query = hash.slice(hash.indexOf('?') + 1);
  if (query.length > 1024) return { mode, token: '' };
  const params = new URLSearchParams(query);
  const tokens = params.getAll('token');
  return {
    mode,
    token: tokens.length === 1 && Array.from(params.keys()).length === 1 &&
      /^[A-Za-z0-9_-]{32,256}$/.test(tokens[0]) ? tokens[0] : '',
  };
}

interface AccessLinkViewProps {
  link: AccessLink;
  onBack: () => void;
}

export const AccessLinkView: React.FC<AccessLinkViewProps> = ({link, onBack}) => {
  const [token, setToken] = useState(link.token);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy || !token || success) return;
    setNotice(null);
    if (link.mode === 'recuperacao' && (
      newPassword.length < 12 || newPassword.length > 128 ||
      newPassword !== confirmPassword
    )) {
      setNotice('Informe e confirme uma nova senha de 12 a 128 caracteres.');
      return;
    }
    setBusy(true);
    try {
      if (link.mode === 'recuperacao') {
        await authService.completePasswordReset(token, newPassword);
        setNotice('Senha alterada. Suas sessões antigas foram revogadas. Entre novamente.');
      } else {
        await authService.verifyInvitationEmail(token);
        setNotice('E-mail confirmado. A participação ainda depende de identidade e aceite contratual.');
      }
      // Discard the one-use token and plaintext password from component state.
      setToken('');
      setNewPassword('');
      setConfirmPassword('');
      setSuccess(true);
    } catch {
      // Never expose API errors with SQL details, tokens or account existence.
      setNotice('Não foi possível validar o link. Pode ter expirado ou o serviço está indisponível.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="fr-page fr-sheen min-h-dvh flex items-center justify-center px-4 py-8">
      <section aria-label="Validação de acesso FR Finance"
        className="w-full max-w-sm rounded-2xl border border-[#b99950]/50 bg-[#043c2d] p-6 text-white shadow-2xl">
        <h1 className="text-2xl font-bold text-[#f8df98]">
          {link.mode === 'recuperacao' ? 'Redefinir senha' : 'Confirmar e-mail de convite'}
        </h1>
        <p className="mt-2 text-sm text-emerald-100/80">
          {link.mode === 'recuperacao'
            ? 'Escolha uma nova senha. O link é de uso único.'
            : 'Confirme o acesso à caixa de e-mail. Isso não ativa sua conta automaticamente.'}
        </p>
        {!token && !success ? <p role="alert" className="mt-4 text-sm text-amber-100">
          Link inválido ou incompleto. Solicite outro pelo aplicativo.
        </p> : null}
        {!success && token ? (
          <form onSubmit={event => { void submit(event); }} className="mt-5 space-y-4">
            {link.mode === 'recuperacao' && (
              <>
                <label htmlFor="access-new-password" className="block text-sm">
                  Nova senha (mínimo 12 caracteres)
                </label>
                <input id="access-new-password" required minLength={12} maxLength={128}
                  autoComplete="new-password" type="password" value={newPassword}
                  onChange={event => setNewPassword(event.target.value)}
                  className="fr-input w-full rounded-lg px-3 py-2 text-base" />
                <label htmlFor="access-confirm-password" className="block text-sm">
                  Confirmar nova senha
                </label>
                <input id="access-confirm-password" required minLength={12} maxLength={128}
                  autoComplete="new-password" type="password" value={confirmPassword}
                  onChange={event => setConfirmPassword(event.target.value)}
                  className="fr-input w-full rounded-lg px-3 py-2 text-base" />
              </>
            )}
            <button type="submit" disabled={busy}
              className="fr-gold-button min-h-11 w-full rounded-lg px-4 disabled:opacity-60">
              {busy ? 'Verificando...' :
                link.mode === 'recuperacao' ? 'Salvar nova senha' : 'Confirmar titularidade'}
            </button>
          </form>
        ) : null}
        {notice && <p role="status" aria-live="polite"
          className="mt-4 rounded-lg border border-amber-300/50 p-3 text-sm">{notice}</p>}
        <button type="button" onClick={onBack}
          className="mt-5 w-full rounded-lg border border-[#b99950] px-4 py-3 text-sm">
          Voltar para o acesso
        </button>
      </section>
    </main>
  );
};
