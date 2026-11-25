import React from 'react';
import {contractModelsV22, type ContractModelKind} from '../services/contractModelsV22';

/** Read-only consultation of generic V2.2 templates, independent of auth/PSP. */
export const ContractModelPreviewV22: React.FC<{kind: ContractModelKind}> = ({kind}) => {
  const text=contractModelsV22[kind];
  const license=kind==='SAAS_LICENSE';
  return (
    <details className="rounded-xl border border-[#8eae99] bg-[#f5faf6] p-3 text-[#143d29]">
      <summary className="cursor-pointer font-semibold text-sm min-h-10">
        {license ? 'Conhecer o modelo de contrato do FR Finance (A)' : 'Consultar modelo de adesão da caixinha (B)'}
      </summary>
      <p className="my-2 text-xs font-semibold text-[#914c13]" role="note">
        Minuta V2.2 para consulta. Não é contrato publicado, proposta de cobrança ou aceite.
        Campos de identificação e condições ainda dependem de preenchimento e revisão jurídica.
      </p>
      <p className="text-xs mb-2">{license
        ? 'Relação entre licenciante FR Finance e administrador contratante. Não exige login nem integração bancária para leitura.'
        : 'Modelo geral entre administrador e membro. Não contém dados de uma caixinha nem substitui o termo individual do ciclo.'}</p>
      <pre tabIndex={0} aria-label="Texto integral da minuta" className="max-h-[45vh] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-[#c3d5c8] p-3 text-sm font-sans select-text">{text}</pre>
      <a className="mt-3 inline-block min-h-10 text-sm font-semibold underline"
        href={'data:text/plain;charset=utf-8,'+encodeURIComponent(text)}
        download={license?'FR-Finance-Contrato-A-minuta-V2.2.txt':'FR-Finance-Contrato-B-minuta-V2.2.txt'}>
        Baixar minuta em texto
      </a>
      <p className="text-xs">Se o dispositivo não permitir baixar, selecione o texto para copiar. Nenhum aceite ou cadastro é registrado nesta consulta.</p>
    </details>
  );
};
