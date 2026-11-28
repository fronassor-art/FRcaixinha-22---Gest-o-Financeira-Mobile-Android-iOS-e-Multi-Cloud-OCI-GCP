/** M37977: invalidate in-flight notification page/ack responses.
 * The counter is not an authorization token and must be combined with the
 * AuthService session and role checks before mutating the UI.
 */
export function createNotificationReplyFence() {
  let epoch=0;
  return {
    issue: ():number => ++epoch,
    invalidate: ():void => { epoch += 1; },
    isCurrent: (ticket:number):boolean =>
      Number.isSafeInteger(ticket) && ticket>0 && ticket===epoch,
  };
}
