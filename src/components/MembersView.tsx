import React, { useEffect, useState } from 'react';
import { AppState } from '../services/store';
import { financialApi } from '../services/financialApiService';

interface MembersViewProps { state: AppState }
type Member = Awaited<ReturnType<typeof financialApi.fetchTenantMembers>>['members'][number];
type LoadState = { key: string; status: 'loading' | 'ready' | 'error'; members: Member[] };

export const MembersView: React.FC<MembersViewProps> = ({ state }) => {
  const key = [state.currentUserId, state.currentRole, state.currentTenantId].join(':');
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<LoadState>({ key: '', status: 'loading', members: [] });

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
        Convites e aceite de novas contas ainda estão bloqueados até a integração de cadastro,
        verificação de identidade e autorização contratual. Nenhum membro fictício é exibido como real.
      </p>
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
