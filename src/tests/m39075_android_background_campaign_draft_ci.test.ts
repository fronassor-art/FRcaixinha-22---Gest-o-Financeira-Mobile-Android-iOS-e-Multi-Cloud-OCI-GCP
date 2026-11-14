/** M39075 — Android background/foreground e recuperação do rascunho Master. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  DRAFT_TTL_MS, EMPTY_MASTER_CAMPAIGN_DRAFT,
  DraftKeyValueStorage, discardMasterCampaignDraft,
  hasSavedMasterCampaignDraft, hasDraftContent,
  readMasterCampaignDraft, saveMasterCampaignDraft,
} from '../services/masterCampaignDraftPersistence';

class MockStorage implements DraftKeyValueStorage {
  items=new Map<string,string>();
  getItem(key:string){return this.items.get(key)??null;}
  setItem(key:string,value:string){this.items.set(key,value);}
  removeItem(key:string){this.items.delete(key);}
}

const master='11111111-1111-4111-8111-111111111111';
const other='22222222-2222-4222-8222-222222222222';
const now=Date.now();
const sample={
  ...EMPTY_MASTER_CAMPAIGN_DRAFT,
  tier:'INTERMEDIARIO' as const,
  period:'ANNUAL' as const,
  priceText:'137.49',
  title:'Campanha promocional para novos administradores',
  benefit:'Benefício condicionado à elegibilidade',
  startsAt:'2026-11-14T14:00',
  endsAt:'2026-11-30T19:00',
  reason:'Ação de marketing aprovada pelo Master',
};
const storage=new MockStorage();
assert.equal(hasDraftContent(EMPTY_MASTER_CAMPAIGN_DRAFT),false);
assert.equal(readMasterCampaignDraft(storage,master,now),null);
assert.equal(saveMasterCampaignDraft(storage,master,sample,now),true);
assert.deepEqual(readMasterCampaignDraft(storage,master,now+500),sample,
  'todos os campos continuam preenchidos depois da suspensão ou remontagem');
assert.equal(readMasterCampaignDraft(storage,other,now),null,
  'um segundo Master não lê o rascunho do primeiro');
assert.equal(hasSavedMasterCampaignDraft(storage,master),true);
assert.equal(saveMasterCampaignDraft(storage,other,sample,now),true);
discardMasterCampaignDraft(storage,master);
assert.equal(readMasterCampaignDraft(storage,master,now),null,
  'logout explícito descarta rascunho do ator atual');
assert.deepEqual(readMasterCampaignDraft(storage,other,now),sample,
  'outro login nunca perde o seu rascunho');
assert.equal(readMasterCampaignDraft(storage,other,now+DRAFT_TTL_MS+1),null,
  'rascunho expirado não pode reaparecer');

assert.equal(saveMasterCampaignDraft(storage,master,{...sample,title:''},now),true);
assert.deepEqual(readMasterCampaignDraft(storage,master,now),{...sample,title:''},
  'edição incompleta também deve continuar salva');
assert.equal(saveMasterCampaignDraft(storage,master,EMPTY_MASTER_CAMPAIGN_DRAFT,now),true);
assert.equal(readMasterCampaignDraft(storage,master,now),null,
  'formulário totalmente vazio não fica persistido');
assert.equal(saveMasterCampaignDraft(storage,master,sample,now),true);
const key=[...storage.items.keys()][0];
assert.equal(Boolean(key),true);
storage.items.set(key,'{not valid JSON');
assert.equal(readMasterCampaignDraft(storage,master,now),null,
  'registro corrompido nunca causa crash');
assert.equal(saveMasterCampaignDraft(storage,'not-uuid',sample,now),false,
  'escopo desconhecido não persiste');
assert.equal(saveMasterCampaignDraft(storage,null,sample,now),false,
  'sem Master autenticado não persiste');

const deniedStorage:DraftKeyValueStorage={
  getItem(){throw new Error('Storage blocked');},
  setItem(){throw new Error('Storage blocked');},
  removeItem(){throw new Error('Storage blocked');},
};
assert.equal(saveMasterCampaignDraft(deniedStorage,master,sample,now),false);
assert.equal(readMasterCampaignDraft(deniedStorage,master,now),null);
discardMasterCampaignDraft(deniedStorage,master);

const app=readFileSync('src/App.tsx','utf8');
const panel=readFileSync('src/components/SaasPromotionsPanel.tsx','utf8');
const auth=readFileSync('src/services/authService.ts','utf8');
assert.match(app,/resumeValidationPending && \(/);
assert.match(app,/inert=\{resumeValidationPending\}/);
assert.match(app,/aria-hidden=\{resumeValidationPending\}/);
assert.doesNotMatch(app,/if \(resumeValidationPending\)\s*\{\s*return\s*\(/,
  'não desmontar views ao voltar do segundo plano');
assert.match(app,/hasSavedMasterCampaignDraft\(masterCampaignDraftStorage\(\), user\.id\)/,
  'última tela só volta após um login Master válido');
assert.match(app,/discardMasterCampaignDraft\(masterCampaignDraftStorage\(\), outgoing\.id\)/);
assert.match(panel,/changeField\('priceText',e\.target\.value\)/);
for(const field of ['tier','period','startsAt','endsAt','title','benefit','reason']){
  assert(panel.includes("changeField('"+field+"',e.target.value)"),
    'todos os campos são persistidos: '+field);
}
assert.match(panel,/saveMasterCampaignDraft\(/);
assert.match(panel,/setSavedLocally\(saveMasterCampaignDraft\(/);
assert.match(panel,/readMasterCampaignDraft\(/);
assert.match(panel,/Descartar preenchimento local/);
assert.match(panel,/frfinance-master-saas-promotions/);
assert.match(panel,/Rascunho gravado/);
assert.doesNotMatch(auth,/localStorage\.setItem\([^)]*(token|password)/i,
  'tokens e senhas não podem entrar no rascunho local');
console.log('M39075_BACKGROUND_FOREGROUND_SAAS_DRAFT_RECOVERY=PASS');
