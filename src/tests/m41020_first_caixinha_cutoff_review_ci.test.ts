import assert from "node:assert/strict";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {readFileSync} from "node:fs";
import {buildFirstCaixinhaCalendarDraftV1} from "../services/firstCaixinhaCalendarDraftV1";
import {FirstCaixinhaCalendarDraftPanel} from "../components/FirstCaixinhaCalendarDraftPanel";
import {previewFirstCaixinhaCutoffV22} from "../services/firstCaixinhaCutoffReviewV22";

const draft=buildFirstCaixinhaCalendarDraftV1();
const pending=previewFirstCaixinhaCutoffV22(draft,null);
assert.equal(pending.status,"NO_OPTION_SELECTED");
assert.equal(pending.capitalDaysEndExclusive,null);
assert.equal(pending.capitalDaysCalendarDays,null);
assert.equal(pending.acceptanceRecorded,false);
assert.equal(pending.persisted,false);
assert.equal(pending.financialCalculationEnabled,false);
assert.equal(pending.cycleOpeningEnabled,false);

const excludesPayment=previewFirstCaixinhaCutoffV22(draft,"EXCLUDE_FINAL_PAYMENT_DATE");
assert.equal(excludesPayment.capitalDaysStartInclusive,"2026-12-10");
assert.equal(excludesPayment.capitalDaysEndExclusive,"2027-12-20");
assert.equal(excludesPayment.capitalDaysCalendarDays,375);
assert.equal(excludesPayment.finalPaymentDateIncluded,false);
assert.equal(excludesPayment.acceptanceRecorded,false);
assert.equal(excludesPayment.persisted,false);
assert.equal(excludesPayment.financialCalculationEnabled,false);

const includesPayment=previewFirstCaixinhaCutoffV22(draft,"INCLUDE_FINAL_PAYMENT_DATE");
assert.equal(includesPayment.capitalDaysEndExclusive,"2027-12-21");
assert.equal(includesPayment.capitalDaysCalendarDays,376);
assert.equal(includesPayment.finalPaymentDateIncluded,true);
assert.equal(includesPayment.acceptanceRecorded,false);
assert.equal(includesPayment.persisted,false);
assert.equal(includesPayment.financialCalculationEnabled,false);

assert.throws(
  ()=>previewFirstCaixinhaCutoffV22(draft,"UNRECOGNIZED" as never),
  /INVALID_FIRST_CAIXINHA_CUTOFF_CHOICE/,
);
assert.throws(
  ()=>previewFirstCaixinhaCutoffV22({...draft,capitalDaysCutoffResolved:true},null),
  /INVALID_FIRST_CAIXINHA_DRAFT/,
);
assert.throws(
  ()=>previewFirstCaixinhaCutoffV22({...draft,closeAndFinalPaymentDate:"2027-02-29"},null),
  /INVALID_FIRST_CAIXINHA_DRAFT/,
);

const html=renderToStaticMarkup(React.createElement(FirstCaixinhaCalendarDraftPanel));
assert.match(html,/Excluir 20\/12\/2027 do corte do Capital-Dias/);
assert.match(html,/Incluir 20\/12\/2027 no corte do Capital-Dias/);
assert.match(html,/Selecione uma opção para comparar a duração/);
assert.doesNotMatch(html,/Janela \[/);
assert.doesNotMatch(html,/checked=/);
const source=readFileSync("src/components/FirstCaixinhaCalendarDraftPanel.tsx","utf8");
assert.match(source,/onChange=\{\(\)=>setChoice\("EXCLUDE_FINAL_PAYMENT_DATE"\)\}/);
assert.match(source,/onChange=\{\(\)=>setChoice\("INCLUDE_FINAL_PAYMENT_DATE"\)\}/);
assert.doesNotMatch(source,/financialApi|localStorage|fetch\(/);
assert.match(source,/não registra aceite, não salva política e não habilita cálculo financeiro/);
console.log("M41020_FIRST_CAIXINHA_CUTOFF_REVIEW=PASS_SOURCE_ONLY");
