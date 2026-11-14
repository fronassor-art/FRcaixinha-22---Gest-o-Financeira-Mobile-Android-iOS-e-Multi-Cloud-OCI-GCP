import React, { useEffect, useState } from 'react';
import { AppState } from '../services/store';
import { financialApi } from '../services/financialApiService';
import { ContractReviewPanel } from './ContractReviewPanel';

interface MembersViewProps { state: AppState }
type Member = Awaited<ReturnType<typeof financialApi.fetchTenantMembers>>['members'][number];
type LoadState = { key: string; status: 'loading' | 'ready' | 'error'; members: Member[] };

export const MembersView: React.FC<MembersViewProps> = ({ state }) => {
  const key = [state.currentUserId, state.currentRole, state.currentTenantId].join(':');
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<LoadState>({ key: '', status: 'loading', members: [] });
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteDocument, setInviteDocument] = useState('');
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setResult({ key, status: 'loading', members: [] });
    if (state.currentRole !== 'TENANT_ADMIN' || !state.currentTenantId || !state.currentUserId) {
      setResult({ key, status: 'error', members: [] });
      return () => { active = false; };
    }
    financialApi.fetchTenantMembers(state.currentTenantId).then(data => {
      if (data.source !== 'POSTGRESQL_RLS' || data.tenant_id !== state.currentTenantId) {
        throw new Error('Contexto de membro inválido');
      }
      if (active) setResult({ key, status: 'ready', members: data.members });
    }).catch(() => {
      if (active) setResult({ key, status: 'error', members: [] });
    });
    return () => { active = false; };
  }, [key, revision]);

  const submitMemberInvite = async (event: React.FormEvent) => {
    event.preventDefault();
    setInviteMessage(null);
    if (inviteBusy || state.currentRole !== 'TENANT_ADMIN' || !state.currentTenantId) return;
    setInviteBusy(true);
    try {
      const result = await financialApi.issueMemberInvitation(
        state.currentTenantId, inviteEmail, inviteDocument,
      );
      if (!result.delivered) {
        setInviteMessage('Solicitação registrada na fila segura. O e-mail e a ativação do membro ainda não foram confirmados.');
        setInviteEmail('');
      }
    } catch {
      setInviteMessage('Convite não emitido. Verifique o contrato publicado e a disponibilidade da API de convites.');
    } finally {
      setInviteBusy(false);
    }
  };

  const current = result.key === key ? result : { key, status: 'loading' as const, members: [] };
  return (
    <section className="space-y-4" aria-labelledby="members-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white p-5">
        <div>
          <h2 id="members-heading" className="text-lg font-bold text-slate-900">Membros da Caixinha</h2>
          <p className="text-sm text-slate-600">
            Lista cadastral autorizada pelo PostgreSQL, sem CPF, telefone ou saldos de terceiros.
          </p>
        </div>
        <button type="button" onClick={() => setRevision(v => v + 1)}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-medium text-slate-900">
          Atualizar lista
        </button>
      </div>
      <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
        Convites só serão aceitos quando a API confirmar o registro em fila segura.
        E-mail recebido, identidade validada e admissão são etapas distintas.
        Nenhum membro fictício é exibido como real.
      </p>
      {state.currentRole === 'TENANT_ADMIN' && state.currentTenantId && state.currentUserId && (
        <form onSubmit={(event) => { void submitMemberInvite(event); }}
          className="space-y-3 rounded-xl border border-slate-200 bg-white p-4"
          aria-label="Solicitar convite de membro">
          <h3 className="text-base font-semibold text-[#143d29]">Convidar membro</h3>
          <p className="text-xs text-slate-600">Confirme a versão do contrato publicada abaixo. O servidor valida o vínculo e autoriza ou recusa o convite.</p>
          <label htmlFor="member-invite-email" className="block text-sm font-medium text-slate-900">
            E-mail do futuro membro
          </label>
          <input id="member-invite-email" type="email" required autoComplete="off"
            value={inviteEmail} onChange={event => setInviteEmail(event.target.value)}
            maxLength={254} className="w-full rounded-lg border border-slate-300 px-3 py-2"
            placeholder="membro@exemplo.com.br" />
          <label htmlFor="member-invite-document" className="block text-sm font-medium text-slate-900">
            UUID do contrato publicado
          </label>
          <input id="member-invite-document" type="text" required autoComplete="off"
            spellCheck={false} value={inviteDocument}
            onChange={event => setInviteDocument(event.target.value)}
            maxLength={36} className="w-full rounded-lg border border-slate-300 px-3 py-2"
            placeholder="Versão publicada no painel de contratos" />
          <button type="submit" disabled={inviteBusy}
            className="rounded-lg bg-[#143d29] px-4 py-2 font-semibold text-white disabled:opacity-50">
            {inviteBusy ? 'Verificando convite...' : 'Solicitar convite'}
          </button>
          {inviteMessage && <p role="status" aria-live="polite" className="text-sm text-slate-700">{inviteMessage}</p>}
        </form>
      )}
      {state.currentRole === 'TENANT_ADMIN' && state.currentTenantId && state.currentUserId && (
        <details className="rounded-xl border border-slate-200 bg-white p-4">
          <summary className="cursor-pointer text-sm font-semibold text-[#143d29]">
            Conferir versão do contrato antes de futuros convites
          </summary>
          <div className="mt-4">
            <ContractReviewPanel key={key} role="TENANT_ADMIN"
              tenantId={state.currentTenantId}/>
          </div>
        </details>
      )}
      {current.status === 'loading' && <p role="status">Carregando membros autorizados...</p>}
      {current.status === 'error' && <p role="alert" className="text-rose-900">
        Consulta de membros indisponível ou perfil não autorizado. Nenhuma lista fictícia será carregada.
      </p>}
      {current.status === 'ready' && current.members.length === 0 && (
        <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
          Ainda não há membros cadastrados nesta caixinha.
        </p>
      )}
      {current.status === 'ready' && current.members.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {current.members.map(member => (
            <article key={member.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="font-semibold text-slate-900">{member.name}</h3>
              <p className="text-sm text-slate-600">Papel: {member.role}</p>
              <p className="text-sm text-slate-600">Situação: {member.status}</p>
              <p className="text-sm text-slate-600">Ingresso: {member.joined_at}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};
