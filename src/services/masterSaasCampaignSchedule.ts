/** M40952 — local display only, never authorization or server eligibility. */
export const MASTER_CAMPAIGN_WRITES_RELEASED: boolean = false;

export function campaignScheduleLabel(
  item: {state: string; starts_at: string; ends_at: string},
  now: number,
): string {
  if (item.state === 'CANCELED') return 'Cancelada';
  if (item.state === 'DRAFT') return 'Rascunho';
  if (item.state !== 'PUBLISHED' || !Number.isFinite(now)) return 'Não confirmada';
  // A timestamp without explicit timezone cannot be classified reliably.
  const zoned = /(?:Z|[+-]\d{2}:\d{2})$/;
  if (!zoned.test(item.starts_at) || !zoned.test(item.ends_at)) return 'Não confirmada';
  const start = Date.parse(item.starts_at), end = Date.parse(item.ends_at);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start)
    return 'Não confirmada';
  if (now < start) return 'Agendada';
  if (now >= end) return 'Encerrada';
  return 'Dentro da vigência';
}
