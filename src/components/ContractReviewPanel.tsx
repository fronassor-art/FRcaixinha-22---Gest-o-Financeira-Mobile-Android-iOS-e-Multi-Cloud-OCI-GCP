import React, {useEffect, useRef, useState} from 'react';
import {financialApi} from '../services/financialApiService';
import {
  ContractCatalog, ContractDigestPreview, InvitationPreparerRole,
  validateReviewInput,
} from '../services/invitationContractReview';

type Props = {
  role: InvitationPreparerRole;
  tenantId: string;
};

/** M25300: conferência de texto por responsável, não é tela de aceite do convidado.
 * Não persiste documentos, confirmações ou tokens no navegador.
 */
export const ContractReviewPanel: React.FC<Props> = ({role, tenantId}) => {
  const [catalog, setCatalog] = useState<ContractCatalog | null>(null);
  const [documentId, setDocumentId] = useState('');
  const [body, setBody] = useState('');
  const [result, setResult] = useState<ContractDigestPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const sequence = useRef(0);

  // Evita renderizar resultados de uma consulta antiga após desmontagem.
  useEffect(() => () => { sequence.current += 1; }, []);

  const resetResult = () => {
    sequence.current += 1;
    setResult(null);
    setError('');
  };

  const loadCatalog = async () => {
    if (loading) return;
    const request = ++sequence.current;
    setCatalog(null);
    setDocumentId('');
    setBody('');
    setResult(null);
    setError('');
    try {
      validateReviewInput(role, tenantId);
      setLoading(true);
      const next = await financialApi.fetchInvitationContractCatalog(role, tenantId);
      if (sequence.current !== request) return;
      setCatalog(next);
      setDocumentId(next.documents[0]?.document_id ?? '');
    } catch {
      if (sequence.current === request) {
        setError('Não foi possível consultar versões publicadas. Verifique o UUID da caixinha e sua sessão.');
      }
    } finally {
      if (sequence.current === request) setLoading(false);
    }
  };

  const verifyText = async () => {
    if (loading || !catalog || !catalog.tenant_active_verified || !documentId) return;
    const request = ++sequence.current;
    setResult(null);
    setError('');
    try {
      validateReviewInput(role, tenantId, documentId, body);
      setLoading(true);
      const answer = await financialApi.verifyInvitationContractText(role, tenantId, documentId, body);
      if (sequence.current === request) setResult(answer);
    } catch {
      if (sequence.current === request) {
        setError('Conferência indisponível. Confira o texto integral (até 64 KiB), a versão e a conexão.');
      }
    } finally {
      if (sequence.current === request) setLoading(false);
    }
  };

  const memberInvite = role === 'TENANT_ADMIN';
  return (
    <section className="fr-light-card space-y-3 rounded-2xl p-4"
      aria-label="Conferência técnica de contrato">
      <h3 className="font-bold text-[#143d29]">
        {memberInvite ? 'Preparação do termo para membros' : 'Preparação do termo para administradores'}
      </h3>
      <p className="text-sm text-[#53695b]">
        Confira a versão publicada e o texto integral antes de organizar futuros convites.
        <strong> Esta conferência não registra aceite, assinatura ou cadastro.</strong>
      </p>
      <p className="text-xs text-[#53695b]">
        O texto fornecido será enviado à API para comparação exata de SHA-256,
        mas não será salvo por esta tela.
      </p>
      <button type="button" onClick={() => void loadCatalog()} disabled={loading}
        className="min-h-11 rounded-lg border border-[#8eae99] bg-white px-3 py-2 text-sm font-semibold text-[#12462e] disabled:opacity-50">
        {loading ? 'Consultando...' : 'Consultar versões publicadas'}
      </button>
      {catalog && !catalog.tenant_active_verified && (
        <p role="status" className="text-sm text-[#914c13]">
          Esta caixinha não está confirmada como ativa. Nenhum contrato foi liberado para conferência.
        </p>
      )}
      {catalog && catalog.tenant_active_verified && catalog.documents.length === 0 && (
        <p role="status" className="text-sm text-[#914c13]">
          Nenhuma versão de adesão publicada está visível para esta sessão.
        </p>
      )}
      {catalog && catalog.tenant_active_verified && catalog.documents.length > 0 && (
        <>
          <label htmlFor="contract-review-document" className="block text-sm font-semibold text-[#143d29]">
            Versão publicada para conferência
          </label>
          <select id="contract-review-document" value={documentId}
            onChange={event => {
              resetResult();
              setDocumentId(event.target.value);
              setBody('');
            }}
            className="min-h-11 w-full rounded-lg border border-[#8eae99] bg-white px-3 py-2 text-sm">
            {catalog.documents.map(doc => (
              <option key={doc.document_id} value={doc.document_id}>{doc.version}</option>
            ))}
          </select>
          {catalog.documents.filter(item => item.document_id === documentId).map(doc => (
            <div key={doc.document_id} className="rounded-lg bg-[#edf4ee] p-3 text-xs text-[#385745]">
              <p>Documento: <code className="break-all">{doc.document_id}</code></p>
              <p className="mt-1">SHA-256 publicado: <code className="break-all">{doc.sha256}</code></p>
              <p className="mt-1">Publicado em: {doc.published_at}</p>
            </div>
          ))}
          <label htmlFor="contract-review-body" className="block text-sm font-semibold text-[#143d29]">
            Texto integral da versão escolhida (UTF-8)
          </label>
          <textarea id="contract-review-body" rows={7} maxLength={65536}
            value={body}
            onChange={event => { resetResult(); setBody(event.target.value); }}
            placeholder="Cole aqui o texto exato da versão contratual. Nenhum termo fictício será preenchido automaticamente."
            className="w-full rounded-lg border border-[#8eae99] bg-white p-3 text-sm text-[#143d29]"/>
          <button type="button" disabled={loading || !body || !documentId}
            onClick={() => void verifyText()}
            className="fr-gold-button min-h-11 w-full rounded-lg px-4 text-sm font-bold disabled:opacity-50">
            Comparar texto ao hash publicado
          </button>
        </>
      )}
      {error && <p role="alert" className="text-sm font-medium text-[#9a3127]">{error}</p>}
      {result && (
        <div role="status" className="rounded-lg border border-[#b5c9b8] bg-[#edf4ee] p-3 text-sm text-[#173f2c]">
          <strong>
            {result.exact_utf8_document_digest_matched
              ? 'Texto confere com o SHA-256 publicado.'
              : 'O texto não confere com a versão publicada.'}
          </strong>
          <p className="mt-2">
            O servidor não registrou aceite e não criou convite ou usuário.
            A ativação permanece bloqueada.
          </p>
        </div>
      )}
      <p className="text-xs font-semibold text-[#8c4820]">
        Modo de homologação: assinatura, consentimento e envio de e-mail indisponíveis.
      </p>
    </section>
  );
};
