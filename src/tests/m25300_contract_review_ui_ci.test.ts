/** M25300: revisão contratual não é aceite nem criação de contas. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {ContractReviewPanel} from '../components/ContractReviewPanel';
import {
  parseContractCatalog, parseContractDigestPreview,
  targetForPreparer, validateReviewInput,
} from '../services/invitationContractReview';

const tenant='00000000-0000-4000-8000-000000000001';
const document='00000000-0000-4000-8000-000000000002';
const hash='a'.repeat(64);

assert.equal(targetForPreparer('MASTER'),'TENANT_ADMIN');
assert.equal(targetForPreparer('TENANT_ADMIN'),'TENANT_MEMBER');
validateReviewInput('TENANT_ADMIN',tenant,document,'Texto de homologação');
assert.throws(()=>validateReviewInput('TENANT_MEMBER' as any,tenant));
assert.throws(()=>validateReviewInput('MASTER','invalid'));
assert.throws(()=>validateReviewInput('MASTER',tenant,'invalid'));
assert.throws(()=>validateReviewInput('MASTER',tenant,document,'á'.repeat(40000)));
assert.throws(()=>validateReviewInput('MASTER',tenant,document,''));

const catalog={
  source:'POSTGRESQL_RLS',
  scope:'AI_STUDIO_PUBLISHED_MEMBERSHIP_CONTRACT_CATALOG',
  target_role:'TENANT_MEMBER',
  status:'BLOCKED',
  tenant_active_verified:true,
  document_kind:'TENANT_MEMBERSHIP',
  contract_body_available:false,
  acceptance_recorded:false,
  invitation_created:false,
  delivery_verified:false,
  activation_authorized:false,
  writes_performed:false,
  documents:[{
    document_id:document,version:'2026.11',sha256:hash,
    published_at:'2026-11-07T12:00:00+00:00',
  }],
};
assert.equal(parseContractCatalog(catalog,'TENANT_MEMBER').documents[0].sha256,hash);
assert.throws(()=>parseContractCatalog({...catalog,status:'ACTIVE'},'TENANT_MEMBER'));
assert.throws(()=>parseContractCatalog({...catalog,target_role:'TENANT_ADMIN'},'TENANT_MEMBER'));
assert.throws(()=>parseContractCatalog({...catalog,acceptance_recorded:true},'TENANT_MEMBER'));
assert.throws(()=>parseContractCatalog({...catalog,contract_body_available:true},'TENANT_MEMBER'));
assert.throws(()=>parseContractCatalog({...catalog,documents:[{...catalog.documents[0],sha256:'invalid'}]},'TENANT_MEMBER'));
assert.throws(()=>parseContractCatalog({...catalog,tenant_active_verified:false},'TENANT_MEMBER'));
assert.deepEqual(parseContractCatalog({...catalog,tenant_active_verified:false,documents:[]},'TENANT_MEMBER').documents,[]);

const preview={
  source:'POSTGRESQL_RLS',
  scope:'AI_STUDIO_CONTRACT_BODY_DIGEST_PREFLIGHT',
  target_role:'TENANT_MEMBER',
  status:'BLOCKED',
  tenant_active_verified:true,
  document_published_verified:true,
  exact_utf8_document_digest_matched:true,
  canonical_document_hosted:false,
  body_rendered_for_invitee:false,
  consent_verified:false,
  acceptance_recorded:false,
  invitation_created:false,
  email_sent:false,
  user_created:false,
  membership_changed:false,
  writes_performed:false,
  activation_authorized:false,
};
assert.equal(parseContractDigestPreview(preview,'TENANT_MEMBER').exact_utf8_document_digest_matched,true);
assert.throws(()=>parseContractDigestPreview({...preview,acceptance_recorded:true},'TENANT_MEMBER'));
assert.throws(()=>parseContractDigestPreview({...preview,body_rendered_for_invitee:true},'TENANT_MEMBER'));
assert.throws(()=>parseContractDigestPreview({...preview,document_published_verified:false},'TENANT_MEMBER'));
assert.throws(()=>parseContractDigestPreview({...preview,activation_authorized:true},'TENANT_MEMBER'));
assert.throws(()=>parseContractDigestPreview(preview,'TENANT_ADMIN'));

const adminHtml=renderToStaticMarkup(
  React.createElement(ContractReviewPanel,{role:'TENANT_ADMIN',tenantId:tenant})
);
assert.match(adminHtml,/Preparação do termo para membros/);
assert.match(adminHtml,/Consultar versões publicadas/);
assert.match(adminHtml,/não registra aceite/);
assert.match(adminHtml,/assinatura, consentimento e envio de e-mail indisponíveis/);
assert.doesNotMatch(adminHtml,/type="submit"/);
const masterHtml=renderToStaticMarkup(
  React.createElement(ContractReviewPanel,{role:'MASTER',tenantId:tenant})
);
assert.match(masterHtml,/Preparação do termo para administradores/);

const members=readFileSync('src/components/MembersView.tsx','utf8');
assert.match(members,/state.currentRole === 'TENANT_ADMIN'/);
assert.match(members,/ContractReviewPanel key=\{key\} role="TENANT_ADMIN"/);
const onboarding=readFileSync('src/components/MasterOnboardingView.tsx','utf8');
assert.match(onboarding,/ContractReviewPanel key=\{scope/);
assert.match(onboarding,/role="MASTER"/);
const service=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(service,/invitations\/preflight\/contract-catalog/);
assert.match(service,/invitations\/preflight\/contract-text/);
assert.match(service,/validateReviewInput\(role, tenantId, documentId, contractText\)/);
const panel=readFileSync('src/components/ContractReviewPanel.tsx','utf8');
assert.doesNotMatch(panel,/localStorage|sessionStorage|navigator\.clipboard/);
assert.doesNotMatch(panel,/createInvitation|recordAcceptance|register\(/);
assert.match(panel,/sequence\.current !== request/);
console.log('M25300_CONTRACT_REVIEW_UI=PASS');
