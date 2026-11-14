/** M20500: stable idempotency only for an identical attempt in the same identity scope. */
export type CyclePriceAttemptInput=Readonly<{
  scope:string;cycleId:string;amountCents:number;reason:string;
}>;
export type CyclePriceAttempt=CyclePriceAttemptInput&Readonly<{idempotencyKey:string}>;

/** Keep the key after a network failure. Reset it on success or identity change. */
export function reuseOrCreateCyclePriceAttempt(
  current:CyclePriceAttempt|null, next:CyclePriceAttemptInput,
  newUuid:()=>string,
):CyclePriceAttempt{
  if(current && current.scope===next.scope &&
     current.cycleId===next.cycleId &&
     current.amountCents===next.amountCents &&
     current.reason===next.reason)return current;
  return {...next,idempotencyKey:newUuid()};
}
