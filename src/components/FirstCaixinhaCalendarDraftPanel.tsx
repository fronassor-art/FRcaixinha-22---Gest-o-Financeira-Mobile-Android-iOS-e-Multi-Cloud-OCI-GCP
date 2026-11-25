import React,{useState} from "react";
import {buildFirstCaixinhaCalendarDraftV1} from "../services/firstCaixinhaCalendarDraftV1";
import {
  previewFirstCaixinhaCutoffV22,
  type FirstCaixinhaCutoffChoiceV22,
} from "../services/firstCaixinhaCutoffReviewV22";

const DATE_LABEL=(value:string)=>value.split("-").reverse().join("/");

/** Master-only planning card. It is not attached to a tenant or invitation. */
export const FirstCaixinhaCalendarDraftPanel:React.FC=()=>{
  const plan=buildFirstCaixinhaCalendarDraftV1();
  const [choice,setChoice]=useState<FirstCaixinhaCutoffChoiceV22|null>(null);
  const cutoffPreview=previewFirstCaixinhaCutoffV22(plan,choice);
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
        <li>O corte do Capital-Dias e a data de pagamento final são decisões separadas. Compare as opções abaixo; nenhuma vem pré-selecionada.</li>
        <li>Definir o valor da cota e a quantidade de cotas por membro; nenhuma cobrança é calculada nesta prévia.</li>
        <li>Os Contratos A (licença SaaS) e B (adesão da caixinha) continuam minutas V2.2, sem aceite habilitado.</li>
      </ul>
    </div>
    <fieldset className="grid gap-2 rounded-lg border border-[#c8d7cd] bg-white p-3">
      <legend className="px-1 text-sm font-semibold">Comparar o corte do Capital-Dias</legend>
      <label className="flex items-start gap-2 text-sm">
        <input aria-label="Excluir 20/12/2027 do corte do Capital-Dias" className="mt-1"
          type="radio" name="first-caixinha-cutoff" value="EXCLUDE_FINAL_PAYMENT_DATE"
          checked={choice==="EXCLUDE_FINAL_PAYMENT_DATE"}
          onChange={()=>setChoice("EXCLUDE_FINAL_PAYMENT_DATE")}/>
        <span>Excluir 20/12/2027: fim exclusivo em 20/12/2027.</span>
      </label>
      <label className="flex items-start gap-2 text-sm">
        <input aria-label="Incluir 20/12/2027 no corte do Capital-Dias" className="mt-1"
          type="radio" name="first-caixinha-cutoff" value="INCLUDE_FINAL_PAYMENT_DATE"
          checked={choice==="INCLUDE_FINAL_PAYMENT_DATE"}
          onChange={()=>setChoice("INCLUDE_FINAL_PAYMENT_DATE")}/>
        <span>Incluir 20/12/2027: fim exclusivo em 21/12/2027.</span>
      </label>
    </fieldset>
    {cutoffPreview.choice===null?<p role="status" className="text-xs text-[#6e4a18]">
      Selecione uma opção para comparar a duração. Sem seleção, o corte permanece em aberto.
    </p>:<div role="status" aria-live="polite" className="rounded-lg bg-[#f2f7f3] p-3 text-sm text-[#123d2b]">
      <p className="font-semibold">Prévia temporária · {cutoffPreview.capitalDaysCalendarDays} dias civis</p>
      <p>Janela [ {DATE_LABEL(cutoffPreview.capitalDaysStartInclusive)}, {DATE_LABEL(cutoffPreview.capitalDaysEndExclusive!)} ).
        O dia 20/12/2027 {cutoffPreview.finalPaymentDateIncluded?"entra":"não entra"} nesta comparação.</p>
      <p className="mt-1 text-xs">Esta escolha existe só nesta tela: não registra aceite, não salva política e não habilita cálculo financeiro.</p>
    </div>}
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
