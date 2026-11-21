/** M38090-M38109: refuse stale Master preflight results across auth/form changes.
 * This fence is an in-memory UI guard, not a substitute for API authentication
 * or RLS, and never creates invitations, approvals, consent or sessions.
 */
export type MasterOnboardingTicket = Readonly<{
  sequence: number;
  scope: string;
  tenant: string;
  generation: number;
}>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function createMasterOnboardingFence() {
  let revision = 0;
  return {
    issue(scope: string, tenant: string, generation: number): MasterOnboardingTicket {
      if (typeof scope !== 'string' || !scope || typeof tenant !== 'string' ||
          !UUID.test(tenant) || !Number.isSafeInteger(generation) || generation < 0) {
        throw new Error('Contexto de pré-análise não confiável');
      }
      revision += 1;
      return Object.freeze({
        sequence: revision, scope, tenant: tenant.toLowerCase(), generation,
      });
    },
    cancel(): void { revision += 1; },
    isCurrent(ticket: MasterOnboardingTicket, scope: string, tenant: string,
              generation: number): boolean {
      return !!ticket && ticket.sequence === revision &&
        ticket.scope === scope && ticket.tenant === tenant.toLowerCase() &&
        ticket.generation === generation && Number.isSafeInteger(generation);
    },
  };
}
