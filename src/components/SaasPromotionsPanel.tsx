import React, { useCallback, useEffect, useState } from 'react';
import { financialApi } from '../services/financialApiService';
import { formatBRL } from '../services/financialEngine';
import {CampaignDraftForm, EMPTY_MASTER_CAMPAIGN_DRAFT,
  discardMasterCampaignDraft, hasDraftContent, masterCampaignDraftStorage,
  readMasterCampaignDraft, saveMasterCampaignDraft,
} from '../services/masterCampaignDraftPersistence';

type Plan = {
  tier: 'ESSENCIAL' | 'INTERMEDIARIO' | 'AMPLIADO';
  status: string;
  version_id: string | null;
};
type Campaign = Awaited<ReturnType<typeof financialApi.fetchMasterSaasPromotions>>['promotions'][number];

export const MasterSaasPromotionsPanel: React.FC<{
  plans: Plan[];
  actorId: string | null;
}> = ({ plans, actorId }) => {
  const [items, setItems] = useState<Campaign[]>([]);
  const [status, setStatus] = useState<'loading'|'ready'|'error'>('loading');
  // M39075: somente formulario SaaS do Master, sem credenciais ou dados de membros.
  const [draftScope,setDraftScope] = useState(actorId);
  const [form,setForm] = useState<CampaignDraftForm>(() =>
    readMasterCampaignDraft(masterCampaignDraftStorage(),actorId) ||
    {...EMPTY_MASTER_CAMPAIGN_DRAFT}
  );
  const [restored,setRestored] = useState(() =>
    readMasterCampaignDraft(masterCampaignDraftStorage(),actorId) !== null
  );
  const [savedLocally,setSavedLocally] = useState<boolean|null>(null);
  const {tier, period, priceText, title, benefit, startsAt, endsAt, reason} = form;
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    // Um login Master diferente nao pode visualizar rascunhos de outro ator.
    const saved=readMasterCampaignDraft(masterCampaignDraftStorage(),actorId);
    setForm(saved || {...EMPTY_MASTER_CAMPAIGN_DRAFT});
    setRestored(saved !== null);
    setSavedLocally(null);
    setDraftScope(actorId);
  }, [actorId]);

  useEffect(() => {
    if (!restored || draftScope !== actorId) return;
    const frame=window.requestAnimationFrame(() => {
      document.getElementById('frfinance-master-saas-promotions')?.scrollIntoView({
        block: 'start', behavior: 'instant',
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [restored,draftScope,actorId]);

  const changeField = (field: keyof CampaignDraftForm, value: string) => {
    if (!actorId || draftScope !== actorId || busy) return;
    const updated={...form,[field]:value};
    setForm(updated);
    // Persistencia sincrona antes de Android suspender a WebView.
    setSavedLocally(saveMasterCampaignDraft(
      masterCampaignDraftStorage(),actorId,updated
    ));
  };

  const discardLocal = () => {
    if (!actorId || busy) return;
    discardMasterCampaignDraft(masterCampaignDraftStorage(),actorId);
    setForm({...EMPTY_MASTER_CAMPAIGN_DRAFT});
    setRestored(false);
    setSavedLocally(null);
    setMessage('Preenchimento local descartado. Nenhuma campanha publicada foi alterada.');
  };

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      const result = await financialApi.fetchMasterSaasPromotions();
      if (result.source !== 'POSTGRESQL_RLS' ||
          result.scope !== 'MASTER_SAAS_PROMOTIONS' ||
          result.billing !== 'OFF_NO_PROVIDER_NO_CHARGE') {
        throw new Error('Origem de campanhas não confirmada');
      }
      setItems(result.promotions);
      setStatus('ready');
    } catch {
      setItems([]);
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    let alive = true;
    setItems([]);
    setStatus('loading');
    financialApi.fetchMasterSaasPromotions().then(result => {
      if (result.source !== 'POSTGRESQL_RLS' ||
          result.scope !== 'MASTER_SAAS_PROMOTIONS' ||
          result.billing !== 'OFF_NO_PROVIDER_NO_CHARGE') {
        throw new Error('Resposta não autorizada');
      }
      if (alive) { setItems(result.promotions); setStatus('ready'); }
    }).catch(() => { if (alive) { setItems([]); setStatus('error'); } });
    return () => { alive = false; };
  }, [actorId]);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy || !actorId || draftScope !== actorId) return;
    const plan = plans.find(p => p.tier === tier && p.status === 'ACTIVE');
    const price = Number(priceText);
    const start = new Date(startsAt), end = new Date(endsAt);
    if (!plan?.version_id ||
        !Number.isFinite(price) || price <= 0 || price > 999999.99 ||
        Math.abs(price * 100 - Math.round(price * 100)) > 1e-6 ||
        Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) ||
        start >= end || end.getTime() <= Date.now() ||
        title.trim().length < 5 || benefit.trim().length < 10 ||
        reason.trim().length < 15) {
      setMessage('Confira o plano, os valores em centavos, a vigência e a justificativa.');
      return;
    }
    setBusy(true); setMessage('');
    try {
      const result = await financialApi.createMasterSaasPromotionDraft({
        plan_tier: tier, billing_period: period,
        base_price_version_id: plan.version_id, promotional_price: price,
        title: title.trim(), benefit_description: benefit.trim(),
        starts_at: start.toISOString(), ends_at: end.toISOString(),
        reason: reason.trim(),
      });
      if (result.status !== 'DRAFT_PERSISTED_NO_BILLING')
        throw new Error('Rascunho não persistido');
      discardMasterCampaignDraft(masterCampaignDraftStorage(),actorId);
      setForm({...EMPTY_MASTER_CAMPAIGN_DRAFT});
      setRestored(false);
      setSavedLocally(null);
      setMessage('Rascunho gravado. Publique separadamente para torná-lo visível aos novos administradores elegíveis.');
      await load();
    } catch { setMessage('Rascunho não confirmado. Atualize o catálogo e revise os dados.'); }
    finally { setBusy(false); }
  };

  const transition = async (item: Campaign, action: 'PUBLISH'|'CANCEL') => {
    if (busy) return;
    const promptReason = action === 'PUBLISH'
      ? 'Publicação de oferta comercial aprovada pelo Master'
      : 'Cancelamento comercial registrado pelo Master';
    setBusy(true); setMessage('');
    try {
      const result = await financialApi.transitionMasterSaasPromotion({
        campaign_id: item.campaign_id, expected_revision: item.revision,
        action, reason: promptReason,
      });
      if (result.status !== 'REVISION_PERSISTED_NO_BILLING')
        throw new Error('Mudança não persistida');
      setMessage(action === 'PUBLISH'
        ? 'Campanha publicada apenas dentro do aplicativo, sem envio externo ou cobrança.'
        : 'Campanha cancelada com nova versão auditável.');
      await load();
    } catch { setMessage('Mudança não confirmada. Atualize a lista; pode haver uma revisão mais recente.'); }
    finally { setBusy(false); }
  };

  if (draftScope !== actorId) {
    return <section role="status" className="rounded-xl border bg-white p-4">
      Confirmando identidade para recuperar o preenchimento da campanha...
    </section>;
  }

  return (
    <section id="frfinance-master-saas-promotions"
      className="rounded-2xl border border-emerald-200 bg-white p-4 sm:p-6 space-y-4">
      <header>
        <h2 className="font-extrabold text-lg text-emerald-900">Promoções SaaS — Administrador Master</h2>
        <p className="text-sm text-slate-700">
          Promoções mensais ou anuais para novos administradores, com preço, benefício e vigência próprios.
          Não envia mensagens, concede licença ou cobra Pix.
        </p>
        {restored && <p role="status" className="mt-2 rounded-lg bg-emerald-50 p-2 text-sm text-emerald-900">
          Preenchimento anterior recuperado neste aparelho. Revise valores e datas antes de criar.
        </p>}
        {hasDraftContent(form) && <p className="mt-2 text-xs text-slate-700">
          {savedLocally === false
            ? 'Atenção: armazenamento local indisponível; mantenha o aplicativo aberto.'
            : 'Preenchimento salvo automaticamente neste aparelho por até 72 horas, somente para esta conta Master.'}
        </p>}
      </header>
      <form onSubmit={create} className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <label className="block">Plano
          <select aria-label="Plano da promoção" value={tier} onChange={e=>changeField('tier',e.target.value)}
            className="block mt-1 w-full rounded-lg border p-2">
            <option value="ESSENCIAL">Essencial</option>
            <option value="INTERMEDIARIO">Intermediário</option>
          </select>
        </label>
        <label className="block">Período
          <select aria-label="Período promocional" value={period} onChange={e=>changeField('period',e.target.value)}
            className="block mt-1 w-full rounded-lg border p-2">
            <option value="MONTHLY">Mensal</option>
            <option value="ANNUAL">Anual</option>
          </select>
        </label>
        <label className="block">Preço promocional (R$)
          <input aria-label="Preço promocional" type="number" inputMode="decimal" min="0.01" max="999999.99"
            step="0.01" required value={priceText} onChange={e=>changeField('priceText',e.target.value)}
            className="block mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block">Público
          <input readOnly value="Novos administradores elegíveis"
            className="block mt-1 w-full rounded-lg border bg-slate-100 p-2" />
        </label>
        <label className="block">Início da vigência (horário do celular)
          <input type="datetime-local" aria-label="Início da promoção" required value={startsAt}
            onChange={e=>changeField('startsAt',e.target.value)}
            className="block mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block">Fim da vigência (horário do celular)
          <input type="datetime-local" aria-label="Fim da promoção" required value={endsAt}
            onChange={e=>changeField('endsAt',e.target.value)}
            className="block mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block sm:col-span-2">Título da campanha
          <input type="text" minLength={5} maxLength={120} required value={title}
            onChange={e=>changeField('title',e.target.value)} className="block mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block sm:col-span-2">Benefício e condições
          <textarea minLength={10} maxLength={500} required value={benefit}
            onChange={e=>changeField('benefit',e.target.value)} className="block mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block sm:col-span-2">Justificativa comercial auditável
          <textarea minLength={15} maxLength={500} required value={reason}
            onChange={e=>changeField('reason',e.target.value)} className="block mt-1 w-full rounded-lg border p-2" />
        </label>
        <button type="submit" disabled={busy || !plans.some(p=>p.tier===tier && p.status==='ACTIVE' && p.version_id)}
          className="rounded-lg bg-emerald-800 text-white font-semibold px-4 py-3 disabled:opacity-50">
          Criar rascunho (sem publicar)
        </button>
        <button type="button" onClick={()=>void load()} disabled={busy}
          className="rounded-lg border border-emerald-700 text-emerald-900 px-4 py-3">
          Atualizar campanhas
        </button>
        {hasDraftContent(form) &&
          <button type="button" onClick={discardLocal} disabled={busy}
            className="rounded-lg border border-slate-400 text-slate-800 px-4 py-3">
            Descartar preenchimento local
          </button>}
      </form>
      {message && <p role="status" className="text-sm text-emerald-950">{message}</p>}
      {status==='error' && <p role="alert" className="text-sm text-amber-900">
        Campanhas indisponíveis até migração SQL113 e reinício da API. Nenhuma promoção simulada.
      </p>}
      {status==='loading' && <p className="text-sm text-slate-600">Consultando campanhas no PostgreSQL...</p>}
      {status==='ready' && items.length===0 && <p className="text-sm text-slate-600">Nenhuma campanha cadastrada.</p>}
      {status==='ready' && items.map(item=>(
        <article key={item.campaign_id} className="border rounded-xl p-3 text-sm space-y-2">
          <div className="flex justify-between gap-2">
            <strong>{item.title}</strong><span>{item.state} • v{item.revision}</span>
          </div>
          <p>{item.plan_tier} • {item.billing_period==='MONTHLY'?'Mensal':'Anual'} •
            {' '}{formatBRL(Number(item.promotional_price))}</p>
          <p className="text-slate-700">{item.benefit_description}</p>
          <p className="text-xs text-slate-600">
            Vigência: {new Date(item.starts_at).toLocaleString('pt-BR')} até
            {' '}{new Date(item.ends_at).toLocaleString('pt-BR')}
          </p>
          {item.state==='DRAFT' &&
            <button type="button" disabled={busy} onClick={()=>void transition(item,'PUBLISH')}
              className="border border-emerald-700 rounded-lg px-3 py-2 disabled:opacity-50">
              Publicar campanha no aplicativo
            </button>}
          {item.state==='PUBLISHED' &&
            <button type="button" disabled={busy} onClick={()=>void transition(item,'CANCEL')}
              className="border border-amber-700 rounded-lg px-3 py-2 disabled:opacity-50">
              Cancelar publicação
            </button>}
        </article>
      ))}
    </section>
  );
};


export const NewAdminSaasOffersPanel: React.FC<{tenantId:string}> = ({tenantId}) => {
  type Offers = Awaited<ReturnType<typeof financialApi.fetchTenantSaasPromotions>>['offers'];
  const [offers,setOffers] = useState<Offers>([]);
  const [state,setState] = useState<'loading'|'ready'|'error'>('loading');
  useEffect(()=>{
    let active=true;
    setOffers([]);setState('loading');
    financialApi.fetchTenantSaasPromotions(tenantId).then(result=>{
      if (result.source!=='POSTGRESQL_RLS' ||
          result.scope!=='ELIGIBLE_NEW_TENANT_ADMIN_ONLY' ||
          result.tenant_id!==tenantId ||
          result.billing!=='OFF_NO_PROVIDER_NO_CHARGE')
        throw new Error('Promoções não autorizadas');
      if(active){setOffers(result.offers);setState('ready');}
    }).catch(()=>{if(active){setOffers([]);setState('error');}});
    return ()=>{active=false;};
  },[tenantId]);

  return <section className="mt-4 rounded-xl border border-emerald-200 bg-white p-4 text-sm">
    <h3 className="font-bold text-emerald-900">Ofertas de assinatura FR Finance</h3>
    {state==='loading' && <p>Verificando ofertas e elegibilidade no servidor...</p>}
    {state==='error' && <p>Ofertas indisponíveis. Nenhum preço promocional foi presumido.</p>}
    {state==='ready' && offers.length===0 && <p>Não há promoções elegíveis e vigentes.</p>}
    {state==='ready' && offers.map(offer=>(
      <article key={offer.campaign_id} className="mt-2 rounded-lg border p-3">
        <strong>{offer.title}</strong>
        <p>{offer.plan_tier} • {offer.billing_period==='MONTHLY'?'Mensal':'Anual'} •
          {' '}{formatBRL(Number(offer.promotional_price))}</p>
        <p className="text-slate-700">{offer.benefit_description}</p>
        <p className="text-xs text-slate-600">
          Válida até {new Date(offer.ends_at).toLocaleString('pt-BR')}
        </p>
      </article>
    ))}
    <p className="mt-2 text-xs text-amber-900">
      Divulgação informativa no aplicativo. Aceite, cobrança Pix, desconto em contrato
      e ativação de licença não estão disponíveis.
    </p>
  </section>;
};
