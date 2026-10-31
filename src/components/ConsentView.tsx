import React from 'react';
import { ShieldCheck, AlertTriangle, CheckCircle, FileText, Lock, UserCheck, XCircle } from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { formatDateBR } from '../services/financialEngine';

interface ConsentViewProps {
  state: AppState;
}

export const ConsentView: React.FC<ConsentViewProps> = ({ state }) => {
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const consent = state.adminSelfConsents.find(c => c.tenant_id === state.currentTenantId);
  const currentMember = state.memberships.find(
    m => m.tenant_id === state.currentTenantId && m.user_id === state.currentUserId
  );

  const adminMember = state.memberships.find(
    m => m.tenant_id === state.currentTenantId && m.user_id === currentTenant?.admin_user_id
  );

  // Demais membros ativos (excluindo o próprio administrador)
  const otherActiveMembers = state.memberships.filter(
    m => m.tenant_id === state.currentTenantId && m.status === 'ATIVA' && m.id !== adminMember?.id
  );

  const activeSignaturesCount = consent?.signatures.filter(s => !s.revoked_at).length || 0;
  const isUnanimous = otherActiveMembers.length > 0 && otherActiveMembers.every(om =>
    consent?.signatures.some(s => s.signer_membership_id === om.id && !s.revoked_at)
  );

  const handleToggleMySignature = (memberId: string) => {
    appStore.toggleAdminConsentSignature(memberId);
  };

  return (
    <div className="space-y-6">
      {/* Header com Regra Contratual */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Autorização Coletiva Anual para Crédito Próprio do Administrador</h2>
            <span
              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                isUnanimous
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-rose-100 text-rose-800'
              }`}
            >
              {isUnanimous ? 'STATUS: ATIVO (100% Unânime)' : 'STATUS: SUSPENSO / REVOGADO'}
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Cláusulas 2.5 e 8.8: Todos os demais membros ativos assinam cláusula específica com validade apenas no ciclo de 2027.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-600">
            Assinaturas válidas: <strong>{activeSignaturesCount} de {otherActiveMembers.length} membros</strong>
          </span>
        </div>
      </div>

      {/* Alerta de Validação em Tempo Real */}
      {!isUnanimous ? (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <strong className="block font-bold">Autoempréstimo do Administrador Bloqueado pelo Backend (Cláusula 2.5):</strong>
            <p>
              Diante de revogação eficaz ou membro não anuente, o sistema susta a executividade imediatamente e impede qualquer liberação Pix. Empréstimos de outros membros continuam operando normalmente.
            </p>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
          <div>
            <strong className="block font-bold">Unanimidade Registrada e Válida para o Ciclo de 2027:</strong>
            <span>
              O administrador {adminMember?.user_name} está legitimado a solicitar e autoaprovar crédito próprio sob as mesmas taxas e limites da caixinha.
            </span>
          </div>
        </div>
      )}

      {/* Texto Contratual Formal */}
      <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-xs space-y-3">
        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400">
          <FileText className="w-4 h-4" />
          <span>INSTRUMENTO ELETRÔNICO: {consent?.document_version}</span>
        </div>
        <div className="text-xs text-slate-300 leading-relaxed font-sans bg-slate-800/60 p-4 rounded-xl border border-slate-700/60">
          "Pelo presente instrumento, nós, membros ativos identificados da caixinha fechada {currentTenant?.display_name},
          autorizamos expressamente e em caráter unânime para o ciclo financeiro de 2027 que o administrador-membro{' '}
          <strong>{adminMember?.user_name} (CPF {adminMember?.user_cpf})</strong> possa contrair empréstimos internos
          com autoaprovação, submetendo-se rigorosamente às mesmas taxas, prazos, limites de caixa livre e sanções por
          inadimplência aplicáveis aos demais membros. A presente autorização é revogável a qualquer tempo e não se
          estende ao ciclo financeiro subsequente (Artigos 117 e 119 do Código Civil)."
        </div>
      </div>

      {/* Roster de Membros e Assinaturas */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
        <h3 className="font-bold text-slate-900 text-sm">Quadro de Assinaturas dos Membros Ativos</h3>
        <div className="divide-y divide-slate-100">
          {otherActiveMembers.map(member => {
            const sig = consent?.signatures.find(s => s.signer_membership_id === member.id);
            const isSigned = sig && !sig.revoked_at;

            return (
              <div key={member.id} className="py-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                      isSigned ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                    }`}
                  >
                    {isSigned ? <UserCheck className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  </div>
                  <div>
                    <strong className="text-sm text-slate-900">{member.user_name}</strong>
                    <div className="text-xs text-slate-500 font-mono">
                      CPF: {member.user_cpf} • {isSigned ? `Assinado em ${formatDateBR(sig.signed_at)}` : 'Não assinado / Revogado'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                      isSigned
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {isSigned ? 'ANUÊNCIA EFICAZ' : 'REVOGADO / PENDENTE'}
                  </span>

                  {/* Botão de Teste Interativo para Assinar / Revogar */}
                  <button
                    onClick={() => handleToggleMySignature(member.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                      isSigned
                        ? 'bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200'
                        : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-2xs'
                    }`}
                  >
                    {isSigned ? 'Revogar Assinatura' : 'Assinar Termo'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
