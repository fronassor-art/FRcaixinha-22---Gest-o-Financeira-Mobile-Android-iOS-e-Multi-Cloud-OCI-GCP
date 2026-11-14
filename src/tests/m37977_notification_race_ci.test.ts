import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createNotificationReplyFence} from '../services/notificationReplyFence';

const fence=createNotificationReplyFence();
const old=fence.issue();
const newer=fence.issue();
assert.equal(fence.isCurrent(old),false,'older request cannot overwrite new page');
assert.equal(fence.isCurrent(newer),true);
fence.invalidate();
assert.equal(fence.isCurrent(newer),false,'logout/role switch revokes pending request');
const third=fence.issue();
assert.equal(fence.isCurrent(third),true);
assert.equal(fence.isCurrent(0),false);
assert.equal(fence.isCurrent(Number.NaN),false);
const view=readFileSync('src/components/NotificationsView.tsx','utf8');
for (const required of [
 'createNotificationReplyFence()', 'replies.current.issue()',
 'replies.current.invalidate()', 'authService.subscribe(',
 'isCurrent(ticket,session,scope)', 'setLoadedContext(scope)',
 'visibleRows.map(', 'visiblePage.next_cursor',
 'contextKey()===expectedContext', 'roleRef.current===role',
])assert(view.includes(required),required);
assert(!view.includes('localStorage.setItem'));
assert(!view.includes('requestPermission('));
console.log('M37977 request-fence and recipient scoped inbox render PASS');
