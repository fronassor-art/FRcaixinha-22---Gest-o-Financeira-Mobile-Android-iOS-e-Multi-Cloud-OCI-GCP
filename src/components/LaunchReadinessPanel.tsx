import React, {useEffect, useState} from 'react';
import {financialApi} from '../services/financialApiService';
import {LaunchReadiness} from '../services/launchReadiness';
import {AppState} from '../services/store';

/** Master-only status of launch blockers: labels are NOT capability toggles. */
export const LaunchReadinessPanel: React.FC<{state:AppState}> = ({state}) => {
  const scope=[state.currentUserId,state.currentRole,state.currentTenantId].join(':');
  const [snapshot,setSnapshot]=useState<{
    scope:string;loading:boolean;report:LaunchReadiness|null;error:boolean;
  }>({scope:'',loading:false,report:null,error:false});
  const [reload,setReload]=useState(0);
  useEffect(() => {
    if(state.currentRole!=='MASTER')return;
    const key=scope+'|'+reload;
    let active=true;
    setSnapshot({scope:key,loading:true,report:null,error:false});
    financialApi.fetchMasterLaunchReadiness()
      .then(report=>{if(active)setSnapshot({scope:key,loading:false,report,error:false});})
      .catch(()=>{if(active)setSnapshot({scope:key,loading:false,report:null,error:true});});
    return()=>{active=false;};
  },[scope,reload,state.currentRole]);
  if(state.currentRole!=='MASTER')return null;
  const key=scope+'|'+reload;
  const current=snapshot.scope===key?snapshot:
    {scope:key,loading:true,report:null,error:false};
  return <section className="fr-light-card rounded-2xl p-4 space-y-3"
    aria-label="Mapa de conclusão da plataforma">
    <h3 className="font-bold text-[#143d29]">Mapa de conclusão e integrações</h3>
    <p className="text-sm text-[#53695b]">
      A implementação de um módulo não equivale à homologação operacional.
      Cada item permanece pendente até existir evidência real de implantação.
    </p>
    {current.loading&&<p role="status" className="text-sm">Verificando requisitos...</p>}
    {current.error&&<p role="alert" className="text-sm text-[#933b2b]">
      O relatório de requisitos não pôde ser confirmado.
    </p>}
    {current.report&&<>
      <p className="text-sm font-semibold text-[#8c4820]">
        {current.report.unverified_gates} requisitos aguardam evidências de produção.
        Nenhuma integração real foi ativada pelo relatório.
      </p>
      <div className="max-h-[28rem] overflow-y-auto rounded-xl border border-[#c4d5c9] p-3">
        <ul className="space-y-3">
          {current.report.requirements.map(item=>
            <li key={item.id} className="border-b border-[#dce9dd] pb-3 last:border-0">
              <p className="break-words text-xs font-bold text-[#174d34]">
                {item.id.replaceAll('_',' ')} · {item.category}
              </p>
              <p className="text-xs text-[#53695b]">
                {item.engineering_source_present
                  ? 'Há código de preparação; falta validar a operação real.'
                  : 'Etapa técnica ainda requer implementação e integração.'}
              </p>
              <p className="mt-1 text-xs text-[#8c4820]">{item.required_evidence}</p>
            </li>)}
        </ul>
      </div>
      <p className="text-xs text-[#53695b]">
        Configurações válidas sintaticamente não comprovam domínio, TLS, banco,
        e-mail entregue, aceite contratual ou transações bancárias.
      </p>
    </>}
    <button type="button" onClick={()=>setReload(n=>n+1)}
      className="min-h-11 rounded-lg border border-[#8eae99] bg-white px-3 py-2 text-sm font-semibold text-[#12462e]">
      Atualizar requisitos
    </button>
  </section>;
};
