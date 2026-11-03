import React, { useEffect, useState } from 'react';
import { authService, UserSessionInfo } from '../services/authService';

/** Segurança das sessões da própria identidade; não exibe IP, token ou hash. */
export function SessionSecurityPanel({ onClose }: { onClose: () => void }) {
  const [sessions, setSessions] = useState<UserSessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const userId = authService.getUser()?.id;

  useEffect(() => {
    let active = true;
    const snapshot = authService.captureSession();
    setLoading(true);
    setError('');
    setSessions([]);
    authService.listSessions().then(rows => {
      if (active && authService.isSessionSnapshotCurrent(snapshot) &&
          userId === authService.getUser()?.id) {
        setSessions(rows);
        setLoading(false);
      }
    }).catch(() => {
      if (active) {
        setError('Não foi possível consultar suas sessões no servidor.');
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [userId, revision]);

  const revoke = async (id: string) => {
    setBusyId(id);
    setError('');
    try {
      const revokedCurrent = await authService.revokeSession(id);
      if (revokedCurrent) {
        onClose();
        return;
      }
      setSessions(previous => previous.filter(item => item.id !== id));
    } catch {
      setError('A revogação não foi confirmada. Consulte o servidor novamente.');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section aria-label="Segurança da conta" className="border-b border-slate-200 bg-slate-50 px-4 py-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-bold text-slate-900">Sessões da minha conta</h2>
        <button type="button" onClick={onClose}
          className="rounded-lg border border-slate-300 px-3 py-2">Fechar</button>
      </div>
      <p className="my-2 text-xs text-slate-600">
        Consulte ou encerre acessos à sua conta. O servidor confirma cada alteração.
        Se a rede falhar, o bloqueio local não comprova revogação remota.
      </p>
      <button type="button" disabled={loading || busyId !== null}
        onClick={() => setRevision(value => value + 1)}
        className="mb-2 min-h-10 rounded-lg border border-slate-300 px-3 text-slate-800 disabled:opacity-50">
        Atualizar sessões
      </button>
      {loading && <p role="status">Consultando sessões no PostgreSQL...</p>}
      {error && <p role="alert" className="text-rose-800">{error}</p>}
      {!loading && sessions.length === 0 && !error &&
        <p>Nenhuma sessão ativa foi retornada.</p>}
      {!loading && sessions.length > 0 && (
        <ul className="grid gap-2">
          {sessions.map(item => (
            <li key={item.id} className="rounded-xl border border-slate-200 bg-white p-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold">{item.current ? 'Esta sessão' : 'Outro acesso'}</p>
                <p className="text-slate-600">
                  Válida até {new Date(item.expires_at).toLocaleString('pt-BR')}
                </p>
              </div>
              <button type="button" onClick={() => void revoke(item.id)}
                disabled={busyId !== null}
                className="rounded-lg border border-rose-300 bg-white px-3 py-2 text-rose-800 disabled:opacity-50">
                {busyId === item.id ? 'Revogando...' : 'Encerrar esta sessão'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
