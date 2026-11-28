import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  parseReviewCapabilities, parseReviewEvent, parseReviewTimeline
} from '../services/memberReviewBoundary';

const T='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const Q='00000000-0000-4000-8000-000000000003';
const M='00000000-0000-4000-8000-000000000004';
const U='00000000-0000-4000-8000-000000000005';
const E='00000000-0000-4000-8000-000000000006';
const cap={
 tenant_id:T,year:2027,role:'TENANT_MEMBER',schema_ready:true,
 sandbox_only:true,can_submit_contestation:true,can_review_independently:false,
 financial_effects_enabled:false,real_payout_enabled:false,
};
assert.equal(parseReviewCapabilities(cap,T,2027,'TENANT_MEMBER')
  .can_submit_contestation,true);
assert.equal(parseReviewCapabilities(
  {...cap,role:'TENANT_ADMIN',can_submit_contestation:false,
   can_review_independently:true},T,2027,'TENANT_ADMIN'
).can_review_independently,true);

const capInvalid=[
 {...cap,tenant_id:B},{...cap,year:2028},{...cap,role:'MASTER'},
 {...cap,financial_effects_enabled:true},
 {...cap,real_payout_enabled:true},
 {...cap,can_review_independently:true},
 {...cap,can_submit_contestation:'yes'},
 {...cap,can_submit_contestation:null},
 {...cap,sandbox_only:false},
 {...cap,schema_ready:false},
 {...cap,token:'secret'},
];
for(const x of capInvalid){
 assert.throws(()=>parseReviewCapabilities(x,T,2027,'TENANT_MEMBER'));
}
const event={
 event_id:E,event_seq:1,tenant_id:T,request_id:Q,
 membership_id:M,actor_user_id:U,
 event_kind:'MEMBER_CONTESTED',
 evidence_reference:'CI-EVIDENCE-REVIEW-2027',
 recorded_at:'2027-06-01T12:00:00+00:00',
 financial_effect_applied:false,bank_reconciled:false,
};
assert.equal(parseReviewEvent(event,T,Q).event_kind,'MEMBER_CONTESTED');
const eventInvalid=[
 {...event,tenant_id:B},{...event,request_id:B},
 {...event,event_id:'bad'}, {...event,membership_id:'bad'},
 {...event,actor_user_id:'bad'},
 {...event,event_seq:0},{...event,event_seq:1.5},
 {...event,event_kind:'CLOSE_REAL_CYCLE'},
 {...event,event_kind:'FREEZE_CAPITAL'},
 {...event,evidence_reference:'abc'},
 {...event,evidence_reference:'PII containing whitespace'},
 {...event,recorded_at:'not-a-timestamp'},
 {...event,financial_effect_applied:true},
 {...event,bank_reconciled:true},
 {...event,master_wallet_amount:8500},
];
for(const e of eventInvalid){
 assert.throws(()=>parseReviewEvent(e,T,Q));
}
const pending={
 tenant_id:T,request_id:Q,membership_id:M,request_kind:'DELINQUENCY_REVIEW',
 latest_event_kind:'MEMBER_CONTESTED',pending_technical_review:true,
 items:[event],has_more:false,financial_effect_applied:false,
 bank_reconciled:false,membership_status_changed:false,
 closing_authorized:false,payout_authorized:false,
};
const result=parseReviewTimeline(pending,T,Q);
assert.equal(result.items.length,1);
assert.equal(result.pending_technical_review,true);
assert.equal(result.financial_effect_applied,false);
assert.equal(result.closing_authorized,false);

const timelineInvalid=[
 {...pending,tenant_id:B},
 {...pending,request_id:B},
 {...pending,membership_id:B},
 {...pending,request_kind:'RELEASE_MONEY'},
 {...pending,latest_event_kind:'ADMIN_REVIEW_ACCEPTED_SANDBOX'},
 {...pending,pending_technical_review:false},
 {...pending,items:[event,event]},
 {...pending,items:[{...event,event_seq:2},{...event,event_seq:1}]},
 {...pending,items:[{...event,membership_id:B}]},
 {...pending,items:Array.from({length:101},()=>event)},
 {...pending,has_more:true},
 {...pending,financial_effect_applied:true},
 {...pending,bank_reconciled:true},
 {...pending,membership_status_changed:true},
 {...pending,closing_authorized:true},
 {...pending,payout_authorized:true},
 {...pending,app_master_token:'secret'},
];
for(const x of timelineInvalid){
 assert.throws(()=>parseReviewTimeline(x,T,Q));
}
for(let n=0;n<260;n++){
 const serial=(n+10).toString(16).padStart(12,'0');
 const isFinal=n%4===0;
 const item={...event,
   event_id:'00000000-0000-4000-8000-'+serial,
   event_seq:n+1,
   event_kind:isFinal?'ADMIN_REVIEW_ACCEPTED_SANDBOX':'MEMBER_CONTESTED',
 };
 const state={...pending,items:[item],
   latest_event_kind:item.event_kind,
   pending_technical_review:!isFinal,
 };
 const r=parseReviewTimeline(state,T,Q);
 assert.equal(r.pending_technical_review,!isFinal);
 assert.equal(r.items[0].event_seq,n+1);
 assert.equal(r.payout_authorized,false);
}
const api=readFileSync('src/services/financialApiService.ts','utf8');
const panel=readFileSync('src/components/MemberLifecyclePanel.tsx','utf8');
const detail=readFileSync('src/components/MemberReviewTimelinePanel.tsx','utf8');
assert.match(api,/fetchReviewCapabilities/);
assert.match(api,/fetchMemberReviewTimeline/);
assert.match(api,/submitMemberReviewEventSandbox/);
assert.match(api,/parseReviewTimeline/);
assert.match(api,/parseReviewCapabilities/);
assert.match(api,/parseReviewEvent/);
assert.match(api,/member-lifecycle\/review-capabilities/);
assert.match(api,/\/review-events/);
assert.match(panel,/<MemberReviewTimelinePanel/);
assert.match(detail,/Confirmo este evento sintético/);
assert.match(detail,/authService\.isSessionSnapshotCurrent/);
assert.match(detail,/globalThis\.crypto\?\.randomUUID/);
assert.match(detail,/Outro|Outra pessoa administradora/);
assert.match(detail,/MEMBER_CONTESTED/);
assert.match(detail,/can_review_independently/);
assert.match(detail,/can_submit_contestation/);
assert.match(detail,/Não é aprovação jurídica/);
assert.doesNotMatch(detail,/localStorage|closeCycle|createPix|releaseLoan/);
console.log('M1081_REVIEW_TIMELINE_UI=PASS; BAD_CAP='+capInvalid.length+
  '; BAD_EVENTS='+eventInvalid.length+
  '; BAD_TIMELINE='+timelineInvalid.length+'; CASES=260');
