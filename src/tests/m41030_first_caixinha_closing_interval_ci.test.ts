import assert from "node:assert/strict";
import React from "react";
import {readFileSync} from "node:fs";
import {renderToStaticMarkup} from "react-dom/server";
import {FirstCaixinhaCalendarDraftPanel} from "../components/FirstCaixinhaCalendarDraftPanel";
import {buildFirstCaixinhaCalendarDraftV1} from "../services/firstCaixinhaCalendarDraftV1";
import {previewFirstCaixinhaCloseIntervalV22} from "../services/firstCaixinhaCloseIntervalV22";

const draft = buildFirstCaixinhaCalendarDraftV1();
const preview = previewFirstCaixinhaCloseIntervalV22(draft);
assert.equal(preview.scope, "OWNER_FIRST_CAIXINHA_ONLY");
assert.equal(preview.status, "READ_ONLY_CALENDAR_INTERVAL");
assert.equal(preview.lastContributionDate, "2027-11-10");
assert.equal(preview.closeAndFinalPaymentDate, "2027-12-20");
assert.equal(preview.elapsedCalendarDaysBetweenDates, 40);
assert.equal(preview.capitalDaysCutoffResolved, false);
assert.equal(preview.acceptanceRecorded, false);
assert.equal(preview.persisted, false);
assert.equal(preview.cycleOpeningEnabled, false);
assert.equal(preview.financialCalculationEnabled, false);

assert.throws(
  () => previewFirstCaixinhaCloseIntervalV22(null),
  /INVALID_FIRST_CAIXINHA_DRAFT/,
);
assert.throws(
  () => previewFirstCaixinhaCloseIntervalV22({
    ...draft,
    closeAndFinalPaymentDate: "2027-02-29",
  }),
  /INVALID_FIRST_CAIXINHA_DRAFT/,
);
assert.throws(
  () => previewFirstCaixinhaCloseIntervalV22({
    ...draft,
    financialExecutionEnabled: true,
  }),
  /INVALID_FIRST_CAIXINHA_DRAFT/,
);
assert.throws(
  () => previewFirstCaixinhaCloseIntervalV22({
    ...draft,
    capitalDaysCutoffResolved: true,
  }),
  /INVALID_FIRST_CAIXINHA_DRAFT/,
);

const html = renderToStaticMarkup(React.createElement(FirstCaixinhaCalendarDraftPanel));
assert.match(html, /Intervalo após a última contribuição/);
assert.match(html, /40 dias civis/);
assert.match(html, /10\/11\/2027/);
assert.match(html, /20\/12\/2027/);
assert.match(html, /não cria vencimento adicional/);
assert.match(html, /não define o corte do Capital-Dias/);

const source = readFileSync("src/components/FirstCaixinhaCalendarDraftPanel.tsx", "utf8");
assert.doesNotMatch(source, /financialApi|localStorage|fetch\(/);
console.log("M41030_FIRST_CAIXINHA_CLOSE_INTERVAL=PASS_SOURCE_ONLY");
