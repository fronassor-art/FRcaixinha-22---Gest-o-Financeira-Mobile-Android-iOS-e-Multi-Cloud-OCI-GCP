/** M40420 — offline campaign/opportunity presentation and fail-closed UI. */
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {SpecialCreditView} from '../components/SpecialCreditView';
import type {AppState} from '../services/store';
import type {CreditOpportunity} from '../services/specialCreditApi';
import {
 parseCreditOpportunities,parseCreditCampaigns,parseCreditPreferences,
 creditReplyLabel,creditOpportunityCanReply,creditOpportunityCanSimulate,
} from '../services/specialCreditPresentation';
const UUID='11111111-1111-4111-8111-111111111111';
const TENANT='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const future=new Date(Date.now()+86400_000).toISOString();
const past=new Date(Date.now()-86400_000).toISOString();
const opportunity:CreditOpportunity={recipient_id:UUID,campaign_id:UUID,grant_id:UUID,
 title:'Oportunidade sintética',message:'Simulação sem dinheiro real',
 ceiling_brl:'3500.00',expires_at:future,response_status:'PENDING'};
const campaign={id:UUID,title:'Campanha sintética',status:'DRAFT',
 expires_at:future,recipients:1};
const prefs={preferences:{PUSH:false,EMAIL:false,WHATSAPP:false,SMS:false},
 external_dispatch:false};
let checks=0;
function check(fn:()=>void){fn();checks++;}
check(()=>assert.equal(parseCreditOpportunities([opportunity])[0].ceiling_brl,'3500.00'));
check(()=>assert.equal(parseCreditCampaigns([campaign])[0].status,'DRAFT'));
check(()=>assert.equal(parseCreditPreferences(prefs).external_dispatch,false));
check(()=>assert.equal(creditReplyLabel('PENDING'),'Aguardando sua resposta'));
check(()=>assert.equal(creditReplyLabel('INTERESTED'),'Tenho interesse'));
check(()=>assert.equal(creditReplyLabel('DECLINED'),'Não tenho interesse'));
check(()=>assert(creditOpportunityCanReply(opportunity)));
check(()=>assert(creditOpportunityCanSimulate(opportunity)));
check(()=>assert(!creditOpportunityCanReply({...opportunity,response_status:'INTERESTED'})));
check(()=>assert(!creditOpportunityCanReply({...opportunity,response_status:'DECLINED'})));
check(()=>assert(!creditOpportunityCanSimulate({...opportunity,response_status:'DECLINED'})));
check(()=>assert(!creditOpportunityCanReply({...opportunity,expires_at:past})));
check(()=>assert(!creditOpportunityCanSimulate({...opportunity,expires_at:past})));
for(const wrong of [
 null,{},[null],new Array(101).fill(opportunity),[opportunity,opportunity],
 [{...opportunity,ceiling_brl:'NaN'}],
 [{...opportunity,ceiling_brl:'50000.01'}],
 [{...opportunity,ceiling_brl:'0.00'}],
 [{...opportunity,ceiling_brl:'100.001'}],
 [{...opportunity,recipient_id:'invalid'}],
 [{...opportunity,response_status:'APPROVED'}],
 [{...opportunity,expires_at:'2026-11-17'}],
 [{...opportunity,title:' '}],
 [{...opportunity,message:' '}],
]){
 check(()=>assert.throws(()=>parseCreditOpportunities(wrong)));
}
for(const wrong of [
 null,{},[null],[campaign,campaign],new Array(101).fill(campaign),
 [{...campaign,status:'SENT'}],
 [{...campaign,recipients:-1}],
 [{...campaign,recipients:1.5}],
 [{...campaign,recipients:51}],
 [{...campaign,expires_at:'invalid-date'}],
 [{...campaign,id:'not-uuid'}],
]){
 check(()=>assert.throws(()=>parseCreditCampaigns(wrong)));
}
for(const wrong of [
 null,{}, {preferences:{}}, {...prefs,external_dispatch:true},
 {...prefs,preferences:{...prefs.preferences,PUSH:'yes'}},
 {...prefs,preferences:{...prefs.preferences,PIX:true}},
]){
 check(()=>assert.throws(()=>parseCreditPreferences(wrong)));
}
const state=(role:AppState['currentRole'])=>({
 currentRole:role,currentTenantId:TENANT,currentUserId:UUID,
} as AppState);
check(()=>assert.equal(renderToStaticMarkup(React.createElement(
 SpecialCreditView,{state:state('MASTER')})),''));
check(()=>assert.match(renderToStaticMarkup(React.createElement(
 SpecialCreditView,{state:state('TENANT_ADMIN')})),
 /Crédito Especial.*Campanhas/));
check(()=>assert.match(renderToStaticMarkup(React.createElement(
 SpecialCreditView,{state:state('TENANT_MEMBER')})),
 /Minhas Oportunidades de Crédito/));
const markup=renderToStaticMarkup(React.createElement(
 SpecialCreditView,{state:state('TENANT_MEMBER')}));
check(()=>assert.match(markup,/Push, e-mail, WhatsApp, SMS e Pix reais não são enviados/));
check(()=>assert.doesNotMatch(markup,/Registrar autorização especial/));
check(()=>assert.doesNotMatch(markup,/Tenho interesse<\/button>/));
assert.equal(checks,50,'M40420 test case count drift '+checks);
console.log('M40420_UI_PRESENTATION_AND_INVALID_PAYLOADS=PASS_50_OF_50');
console.log('M40420_MALFORMED_OFFERS_AND_REAL_DELIVERY=FAIL_CLOSED');
console.log('M40420_MEMBER_DECLINE_AND_EXPIRY=NO_ACTIONS');
console.log('M40420_MASTER_RENDER=BLOCKED');
console.log('M40420_NETWORK_AND_POSTGRES=NOT_ACCESSED');
