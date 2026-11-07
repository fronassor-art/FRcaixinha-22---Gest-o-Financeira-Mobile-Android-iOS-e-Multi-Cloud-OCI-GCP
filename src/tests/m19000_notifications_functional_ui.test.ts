import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseInboxPage} from '../services/notificationInbox';

const client=readFileSync('src/services/notificationInbox.ts','utf8');
const view=readFileSync('src/components/NotificationsView.tsx','utf8');

const item={
  id:'eeeeeeee-0000-4000-8000-000000000001',kind:'SELF_TEST',
  title:'Aviso de teste interno',message:'Teste do recebimento interno realizado nesta conta.',
  created_at:'2026-11-05T12:00:00.000000Z',read_at:null,
};
const page={
 contract:'AI_STUDIO_M19000_IN_APP_LOCAL_INBOX_V1',
 items:[item],unread_count:1,has_more:false,next_cursor:null,
};
assert.equal(parseInboxPage(page).items[0].id,item.id);
for(const modified of [
  {...page,unread_count:-1},
  {...page,unread_count:null},
  {...page,has_more:true,next_cursor:null},
  {...page,items:[item,item]},
  {...page,items:[{...item,id:'BAD'}]},
  {...page,items:[{...item,kind:'FINANCE_PAID'}]},
  {...page,items:[{...item,read_at:'not a date'}]},
  {...page,items:Array.from({length:51},()=>item)},
]) assert.throws(()=>parseInboxPage(modified));
assert.ok(client.includes('authService.captureSession()'));
assert.ok(client.includes('isSessionSnapshotCurrent'));
assert.ok(client.includes("response.status === 401"));
assert.ok(view.includes('Enviar aviso interno de teste'));
assert.ok(view.includes('Marcar como lida'));
assert.ok(view.includes('Não ativado'));
assert.ok(!view.includes('localStorage.setItem'));
assert.ok(!view.includes('requestPermission('));
console.log('M19000 UI de inbox autenticada, contagem real e teste local PASS');
