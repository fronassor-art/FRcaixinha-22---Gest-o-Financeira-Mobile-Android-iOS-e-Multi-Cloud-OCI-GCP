/** M40962: full V2.2 models, no authenticated data or acceptance. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {contractModelsV22} from '../services/contractModelsV22';
import {ContractModelPreviewV22} from '../components/ContractModelPreviewV22';

const master=readFileSync('docs/FR_Finance_Caderno_Mestre_V2_2_2026-11-24.md','utf8');
const a=master.indexOf('## CONTRATO A — ');
const b=master.indexOf('## CONTRATO B — ');
const end=master.indexOf('## Matriz de responsabilidades contratuais');
assert.ok(a>=0&&a<b&&b<end);
assert.equal(contractModelsV22.SAAS_LICENSE,master.slice(a,b));
assert.equal(contractModelsV22.MEMBER_ADHESION,master.slice(b,end));
assert.equal((contractModelsV22.SAAS_LICENSE.match(/^### A-\d\d —/gm)||[]).length,15);
assert.equal((contractModelsV22.MEMBER_ADHESION.match(/^### B-\d\d —/gm)||[]).length,14);
for(const kind of ['SAAS_LICENSE','MEMBER_ADHESION'] as const){
  const view=renderToStaticMarkup(React.createElement(ContractModelPreviewV22,{kind}));
  assert.match(view,/Minuta V2.2 para consulta/);
  assert.match(view,/Não é contrato publicado/);
  assert.match(view,/download=/);
  assert.match(view,/data:text\/plain;charset=utf-8,/);
  assert.doesNotMatch(view,/<form|type="submit"|<script/i);
  assert.ok(view.includes(kind==='SAAS_LICENSE'?'A-15':'B-14'));
}
const login=readFileSync('src/components/LoginView.tsx','utf8');
const panel=readFileSync('src/components/ContractReviewPanel.tsx','utf8');
const component=readFileSync('src/components/ContractModelPreviewV22.tsx','utf8');
assert.match(login,/<ContractModelPreviewV22 kind="SAAS_LICENSE"/);
assert.match(panel,/scope && <ContractModelPreviewV22 kind=\{memberInvite\?'MEMBER_ADHESION':'SAAS_LICENSE'\}/);
assert.match(panel,/catálogo legado de adesão geral/);
assert.doesNotMatch(component,/localStorage|sessionStorage|fetch\(|dangerouslySetInnerHTML|onSubmit|recordAcceptance/);
console.log('M40962_MODELS_V22_FULL_TEXT_AND_NO_ACCEPTANCE=PASS');
