import React from "react";
import {buildFirstCaixinhaCalendarDraftV1} from "../services/firstCaixinhaCalendarDraftV1";

const DATE_LABEL=(value:string)=>value.split("-").reverse().join("/");

/** Master-only planning card. It is not attached to a tenant or invitation. */
export const FirstCaixinhaCalendarDraftPanel:React.FC=()=>{
  const plan=buildFirstCaixinhaCalendarDraftV1();
  return <section aria-label="Calendário planejado da primeira caixinha"
    className="fr-light-card space-y-3 rounded-2xl border border-[#d8c38d] p-4">
    <header>
      <h3 className="font-bold text-[#123d2b]">Primeira caixinha · calendário informado</h3>
      <p className="mt-1 text-xs text-[#52695b]">
        Rascunho somente do Master, ainda sem vínculo a tenant ou convite. Não define o calendário das demais caixinhas.
      </p>
    </header>
    <dl className="grid gap-2 text-sm sm:grid-cols-2">
      <div><dt className="font-semibold">Início e primeira contribuição</dt><dd>{DATE_LABEL(plan.cycleStart)}</dd></div>
      <div><dt className="font-semibold">Última contribuição prevista</dt><dd>{DATE_LABEL(plan.lastContributionDate)}</dd></div>
      <div><dt className="font-semibold">Dia de vencimento mensal</dt><dd>Dia {plan.contributionDueDay} · {plan.contributionCount} datas</dd></div>
      <div><dt className="font-semibold">Encerramento e pagamento final informado</dt><dd>{DATE_LABEL(plan.closeAndFinalPaymentDate)}</dd></div>
    </dl>
    <details className="rounded-lg border border-[#c8d7cd] bg-white p-3">
      <summary className="cursor-pointer text-sm font-semibold">Conferir as 12 datas mensais</summary>
      <ol className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2"
        aria-label="Datas mensais informadas para a primeira caixinha">
        {plan.contributionDates.map((date,index)=><li key={date}>Contribuição {index+1}: {DATE_LABEL(date)}</li>)}
      </ol>
    </details>
    <div className="rounded-lg bg-[#fff8e7] p-3 text-xs text-[#6e4a18]">
      <p className="font-semibold">Antes de vincular esta proposta ao administrador</p>
      <ul className="mt-1 list-disc space-y-1 pl-4">
        <li>Definir se o corte do Capital-Dias inclui 20/12/2027; o cálculo permanece bloqueado enquanto isso não for expresso.</li>
        <li>Definir o valor da cota e a quantidade de cotas por membro; nenhuma cobrança é calculada nesta prévia.</li>
        <li>Os Contratos A (licença SaaS) e B (adesão da caixinha) continuam minutas V2.2, sem aceite habilitado.</li>
      </ul>
    </div>
    <details className="rounded-lg border border-[#c8d7cd] bg-white p-3">
      <summary className="cursor-pointer text-sm font-semibold">Conferir a sequência prevista</summary>
      <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
        <li><strong>Master:</strong> preparar e enviar o convite do administrador — emissão real ainda bloqueada.</li>
        <li><strong>Administrador convidado:</strong> cadastrar-se, revisar o Contrato A e pagar a licença SaaS somente após publicação da oferta e liberação do provedor.</li>
        <li><strong>Administrador da caixinha:</strong> revisar e aceitar o Contrato B com o calendário e os valores próprios desta caixinha.</li>
        <li><strong>Membros:</strong> receber convite, cadastrar-se, aceitar o Contrato B e pagar as contribuições à conta legítima indicada pela administração da caixinha.</li>
      </ol>
      <p className="mt-2 text-xs text-[#52695b]">A assinatura do FR Finance e as contribuições da caixinha são contratos e pagamentos distintos.</p>
    </details>
    <p role="note" className="text-xs font-semibold text-[#8a3828]">
      Prévia sem efeitos: não abre ciclo, não aceita contrato, não cria convite, não cobra licença ou cotas e não executa pagamento.
    </p>
  </section>;
};
