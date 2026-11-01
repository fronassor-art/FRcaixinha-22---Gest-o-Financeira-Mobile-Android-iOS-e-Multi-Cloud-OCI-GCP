import { Contribution } from '../types';

export interface DisplayContribution extends Contribution {
  member_name?: string | null;
}

/** Valida os dados recebidos antes de mostrá-los no contexto autenticado. */
export function normalizeContributions(value: unknown, tenantId: string): DisplayContribution[] {
  if (!Array.isArray(value)) throw new Error('Resposta de contribuições inválida.');
  return value.map((row: any) => {
    if (!row || row.tenant_id !== tenantId || typeof row.id !== 'string' ||
        typeof row.membership_id !== 'string' || typeof row.cycle_id !== 'string' ||
        typeof row.competence !== 'string' || typeof row.due_date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(row.due_date) ||
        !['PENDENTE', 'PARCIAL', 'QUITADA'].includes(row.payment_status) ||
        !['NO_PRAZO', 'VENCIDA', 'REGULARIZADA'].includes(row.due_status)) {
      throw new Error('Dados de contribuição inconsistentes.');
    }
    const isMoney = (v: unknown) => typeof v === 'number' || (typeof v === 'string' && /^\d+(\.\d{1,2})?$/.test(v));
    const due = Number(row.amount_due);
    const paid = Number(row.amount_paid);
    if (!isMoney(row.amount_due) || !isMoney(row.amount_paid) || !Number.isFinite(due) || !Number.isFinite(paid) || due <= 0 || paid < 0) {
      throw new Error('Valores de contribuição inválidos.');
    }
    return { id: row.id, tenant_id: row.tenant_id, cycle_id: row.cycle_id,
      membership_id: row.membership_id, competence: row.competence, due_date: row.due_date,
      amount_due: due, amount_paid: paid, payment_status: row.payment_status,
      due_status: row.due_status === 'NO_PRAZO' ? 'A_VENCER' : row.due_status, paid_at: row.paid_at ?? null,
      member_name: typeof row.member_name === 'string' ? row.member_name : null };
  });
}
