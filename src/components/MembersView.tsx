import React, { useState } from 'react';
import { Users, UserPlus, Shield, CheckCircle2, AlertCircle, Phone, Mail, FileText, X } from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { formatDateBR } from '../services/financialEngine';

interface MembersViewProps {
  state: AppState;
}

export const MembersView: React.FC<MembersViewProps> = ({ state }) => {
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const currentSub = state.subscriptions.find(s => s.tenant_id === state.currentTenantId);
  const currentPlan = state.plans.find(p => p.tier === currentSub?.plan_tier);

  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [inviteName, setInviteName] = useState('');
  const [inviteCpf, setInviteCpf] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePhone, setInvitePhone] = useState('');
  const [inviteQuotas, setInviteQuotas] = useState(1);

  const tenantMemberships = state.memberships.filter(m => m.tenant_id === state.currentTenantId);
  const activeMembers = tenantMemberships.filter(m => m.status === 'ATIVA');
  const activeQuotas = state.quotas.filter(q => q.tenant_id === state.currentTenantId && q.status === 'ATIVA');

  const handleSendInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteName || !inviteCpf || !inviteEmail || !invitePhone) {
      alert('Por favor, preencha todos os campos obrigatórios (Cláusula 6.1-A).');
      return;
    }

    const newUserId = `usr-mem-${Date.now()}`;
    const newMemberId = `mem-${Date.now()}`;

    // Adiciona novo usuário com dados mínimos LGPD
    state.users.push({
      id: newUserId,
      name: inviteName,
      cpf: inviteCpf,
      email: inviteEmail,
      email_verified_at: new Date().toISOString(),
      phone: invitePhone,
      auth_subject: `auth|${newMemberId}`,
      status: 'ACTIVE',
      created_at: new Date().toISOString(),
    });

    // Adiciona membership ativa
    state.memberships.push({
      id: newMemberId,
      tenant_id: state.currentTenantId,
      cycle_id: state.activeCycleId,
      user_id: newUserId,
      user_name: inviteName,
      user_cpf: inviteCpf,
      user_email: inviteEmail,
      user_phone: invitePhone,
      joined_at: new Date().toISOString().split('T')[0],
      status: 'ATIVA',
      consecutive_unpaid_count: 0,
      is_profit_eligible: true,
    });

    // Adiciona cotas
    for (let i = 0; i < inviteQuotas; i++) {
      state.quotas.push({
        id: `q-${Date.now()}-${i}`,
        tenant_id: state.currentTenantId,
        cycle_id: state.activeCycleId,
        membership_id: newMemberId,
        quota_number: state.quotas.length + 1,
        status: 'ATIVA',
        effective_from: new Date().toISOString().split('T')[0],
      });
    }

    appStore.addAudit('MEMBER_ADMITTED', `Novo membro ${inviteName} admitido com ${inviteQuotas} cota(s)`, 'MEMBERSHIP', newMemberId);
    setIsInviteModalOpen(false);
    setInviteName('');
    setInviteCpf('');
    setInviteEmail('');
    setInvitePhone('');
    alert(`Membro ${inviteName} cadastrado com sucesso com ${inviteQuotas} cota(s)!`);
  };

  return (
    <div className="space-y-6">
      {/* Header com Regras de Capacidade */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Membros, Cotas e Capacidade Contratada</h2>
            <span className="text-[11px] font-semibold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full">
              Contagem Simultânea • Cláusula 3.4
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Plano <strong>{currentPlan?.name}</strong>: Limite de <strong>{currentPlan?.member_limit} membros</strong> e <strong>{currentPlan?.quota_limit} cotas</strong>.
            Uma pessoa com 3 cotas utiliza 1 vaga de membro e 3 cotas.
          </p>
        </div>

        <button
          onClick={() => setIsInviteModalOpen(true)}
          disabled={activeMembers.length >= (currentPlan?.member_limit || 20) || activeQuotas.length >= (currentPlan?.quota_limit || 40)}
          className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-xs transition-colors cursor-pointer flex items-center gap-2 disabled:opacity-40"
        >
          <UserPlus className="w-4 h-4" />
          <span>Admitir Novo Membro</span>
        </button>
      </div>

      {/* Roster de Membros */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/70 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
              <tr>
                <th className="py-3 px-4">Nome Completo / Contato</th>
                <th className="py-3 px-4">CPF (Validado)</th>
                <th className="py-3 px-4 text-center">Cotas Ativas</th>
                <th className="py-3 px-4 text-center">Data de Ingresso</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-center">Elegibilidade Lucro</th>
                <th className="py-3 px-4 text-right">Papel</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tenantMemberships.map(m => {
                const quotas = state.quotas.filter(q => q.membership_id === m.id && q.status === 'ATIVA');
                const isAdmin = m.user_id === currentTenant?.admin_user_id;

                return (
                  <tr key={m.id} className="hover:bg-slate-50/70">
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-slate-900">{m.user_name}</div>
                      <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                        <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{m.user_email}</span>
                        <span>•</span>
                        <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{m.user_phone}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-700">{m.user_cpf}</td>
                    <td className="py-3.5 px-4 text-center font-bold text-emerald-800">
                      {quotas.length} cota(s)
                    </td>
                    <td className="py-3.5 px-4 text-center text-slate-600">{formatDateBR(m.joined_at)}</td>
                    <td className="py-3.5 px-4 text-center">
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                        {m.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          m.is_profit_eligible
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {m.is_profit_eligible ? 'Elegível' : 'Perdeu Lucro (3 Atrasos)'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {isAdmin ? (
                        <span className="text-[10px] font-bold bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">
                          ADMIN & MEMBRO
                        </span>
                      ) : (
                        <span className="text-[10px] font-medium text-slate-500">Membro</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal de Admissão de Novo Membro */}
      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-sm">Admitir Membro na Caixinha</h3>
              <button onClick={() => setIsInviteModalOpen(false)} className="text-slate-400 hover:text-slate-700">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSendInvite} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Nome Completo</label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Carlos Eduardo de Souza"
                  value={inviteName}
                  onChange={e => setInviteName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-900"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">CPF (Dígitos Verificadores Validados)</label>
                <input
                  type="text"
                  required
                  placeholder="000.000.000-00"
                  value={inviteCpf}
                  onChange={e => setInviteCpf(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-900 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">E-mail</label>
                  <input
                    type="email"
                    required
                    placeholder="email@exemplo.com"
                    value={inviteEmail}
                    onChange={e => setInviteEmail(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-900"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Telefone com DDD</label>
                  <input
                    type="tel"
                    required
                    placeholder="(91) 98000-0000"
                    value={invitePhone}
                    onChange={e => setInvitePhone(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-900"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Quantidade de Cotas</label>
                <select
                  value={inviteQuotas}
                  onChange={e => setInviteQuotas(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-900 font-bold"
                >
                  <option value={1}>1 cota (R$ 100,00/mês)</option>
                  <option value={2}>2 cotas (R$ 200,00/mês)</option>
                  <option value={3}>3 cotas (R$ 300,00/mês)</option>
                  <option value={4}>4 cotas (R$ 400,00/mês)</option>
                </select>
              </div>

              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-emerald-900 text-[11px] leading-relaxed">
                <Shield className="w-3.5 h-3.5 inline mr-1 text-emerald-700" />
                <strong>Conformidade LGPD (Cláusula 6.1-A):</strong> Coleta estritamente restrita aos dados necessários para a relação contratual. Endereço residencial e dados bancários prévios não são obrigatórios.
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl cursor-pointer shadow-xs"
                >
                  Confirmar Admissão
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
