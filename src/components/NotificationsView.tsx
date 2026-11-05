import React from 'react';
import { Bell, BellOff, Mail, MessageCircle, ShieldCheck, Smartphone } from 'lucide-react';
import type { UserRole } from '../types';

/** M15000: a real inbox is NOT mounted until authenticated PostgreSQL/RLS.
 * No seed notifications, unread counters, browser permissions or push tokens.
 */
export const NotificationsView: React.FC<{role: UserRole}> = ({ role }) => {
  const context = role === 'MASTER' ? 'Plataforma'
    : role === 'TENANT_ADMIN' ? 'Administração da caixinha'
    : 'Minhas notificações';
  return (
    <section aria-labelledby="notification-title" className="mx-auto max-w-3xl space-y-5">
      <header className="rounded-2xl border border-[#cadacb] bg-white p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <Bell className="h-7 w-7 text-[#195c3c]" aria-hidden="true"/>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[#64806e]">{context}</p>
            <h1 id="notification-title" className="text-xl font-bold text-[#073d2b]">Notificações</h1>
          </div>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-[#3d5748]">
          Estamos preparando a central de avisos do FR Caixinha. Ainda não há
          caixa de entrada vinculada ao banco de dados para este perfil.
        </p>
      </header>
      <div role="status" aria-live="polite"
        className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
        <div className="flex items-center gap-3">
          <BellOff className="h-6 w-6 shrink-0" aria-hidden="true"/>
          <strong>Recebimento de notificações ainda não ativado</strong>
        </div>
        <p className="mt-2 text-sm">
          Nenhuma mensagem é exibida como entregue ou lida sem confirmação do
          servidor. Contagem de não lidas, confirmação de leitura e histórico
          dependem da implantação da caixa de entrada autenticada.
        </p>
      </div>
      <h2 className="text-base font-bold text-[#073d2b]">Canais previstos para homologação</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          {label:'Avisos dentro do aplicativo',Icon:Bell,detail:'Requer caixa de entrada com RLS'},
          {label:'E-mail',Icon:Mail,detail:'Requer endereço verificado e serviço de envio'},
          {label:'Notificações push',Icon:Smartphone,detail:'Requer dispositivo autorizado e provedor push'},
          {label:'WhatsApp',Icon:MessageCircle,detail:'Requer consentimento e integração aprovada'},
        ].map(({label,Icon,detail})=>(
          <article key={label} className="rounded-xl border border-[#d1dfd1] bg-white p-4">
            <div className="flex items-center gap-2">
              <Icon className="h-5 w-5 text-[#195c3c]" aria-hidden="true"/>
              <h3 className="text-sm font-semibold text-[#123f2c]">{label}</h3>
            </div>
            <p className="mt-2 text-xs text-[#526d5a]">{detail}</p>
            <p className="mt-2 text-xs font-semibold text-amber-800">Não ativado</p>
          </article>
        ))}
      </div>
      <p className="flex items-start gap-2 text-xs text-[#506a59]">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true"/>
        Alertas informativos não autorizam pagamentos, quitação, empréstimos, Pix
        nem acesso a dados de outras caixinhas. Os webhooks do provedor são
        separados das mensagens destinadas aos usuários.
      </p>
    </section>
  );
};
