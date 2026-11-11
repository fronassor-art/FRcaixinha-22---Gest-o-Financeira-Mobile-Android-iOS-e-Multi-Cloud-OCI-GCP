import React, { useEffect, useRef, useState } from 'react';
import { Bell, BellOff, Mail, MessageCircle, RefreshCw, Smartphone, ShieldCheck } from 'lucide-react';
import type { UserRole } from '../types';
import { authService, type AuthSessionSnapshot } from '../services/authService';
import { createNotificationReplyFence } from '../services/notificationReplyFence';
import {
  InboxNotification, InboxPage, inboxCapabilities, fetchInbox,
  createSelfTest, acknowledgeInbox,
} from '../services/notificationInbox';

/** M19000: real local in-app inbox only after authorized migration 031.
 * External channels remain "Não ativado". No fake messages or unread count.
 */
export const NotificationsView: React.FC<{role: UserRole}> = ({ role }) => {
  const [ready,setReady]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string | null>(null);
  const [page,setPage]=useState<InboxPage | null>(null);
  const [rows,setRows]=useState<InboxNotification[]>([]);
  const [saving,setSaving]=useState<string | null>(null);
  const [loadedContext,setLoadedContext]=useState<string | null>(null);
  const replies=useRef(createNotificationReplyFence());
  const roleRef=useRef(role);
  roleRef.current=role;
  const contextKey=()=>{
    const user=authService.getUser();
    return user ? [user.role,user.id,user.tenantId||''].join(':') : null;
  };
  const isCurrent=(ticket:number,session:AuthSessionSnapshot,expectedContext:string)=>
    replies.current.isCurrent(ticket) && roleRef.current===role &&
    authService.isSessionSnapshotCurrent(session) &&
    authService.getUser()?.role===role && contextKey()===expectedContext;
  const context=role==='MASTER'?'Plataforma':
    role==='TENANT_ADMIN'?'Administração da caixinha':'Minhas notificações';

  const refresh=async(cursor: string | null=null,append=false)=>{
    const ticket=replies.current.issue();
    const session=authService.captureSession();
    const scope=contextKey();
    if(!session.token || !scope || authService.getUser()?.role!==role) {
      setRows([]);setPage(null);setReady(false);setLoadedContext(null);
      setBusy(false);setError('Sessão ou perfil inválido. Faça login novamente.');
      return;
    }
    setBusy(true);setError(null);
    try {
      if(!cursor) {
        const available=await inboxCapabilities();
        if(!isCurrent(ticket,session,scope))return;
        setReady(available);
        if(!available) {
          setRows([]);setPage(null);setLoadedContext(null);
          setError('Caixa de entrada local ainda não habilitada. Confira o banco e a FastAPI.');
          return;
        }
      }
      const incoming=await fetchInbox(cursor);
      if(!isCurrent(ticket,session,scope))return;
      setPage(incoming);
      setLoadedContext(scope);
      setRows(previous=>append
        ? [...previous,...incoming.items.filter(item=>!previous.some(old=>old.id===item.id))]
        : incoming.items);
    } catch(exc) {
      if(!isCurrent(ticket,session,scope))return;
      setError(exc instanceof Error?exc.message:'Não foi possível consultar notificações.');
      if(!append) {setRows([]);setPage(null);setLoadedContext(null);}
    } finally {
      if(isCurrent(ticket,session,scope))setBusy(false);
    }
  };

  useEffect(()=>{
    const unsubscribe=authService.subscribe(()=>{
      replies.current.invalidate();
      setRows([]);setPage(null);setReady(false);setLoadedContext(null);
      setBusy(false);setSaving(null);setError(null);
    });
    replies.current.invalidate();
    setRows([]);setPage(null);setReady(false);setLoadedContext(null);
    setBusy(false);setSaving(null);setError(null);
    void refresh();
    return ()=>{
      replies.current.invalidate();
      unsubscribe();
    };
  },[role]);

  const selfTest=async()=>{
    const session=authService.captureSession();
    const scope=contextKey();
    const same=()=>authService.isSessionSnapshotCurrent(session) &&
      roleRef.current===role && contextKey()===scope;
    setSaving('test');setError(null);
    try {
      await createSelfTest();
      if(same())await refresh();
    } catch(exc) {
      if(same())setError(exc instanceof Error?exc.message:'Teste interno indisponível.');
    } finally {
      if(same())setSaving(null);
    }
  };

  const markRead=async(id:string)=>{
    const session=authService.captureSession();
    const scope=contextKey();
    const same=()=>authService.isSessionSnapshotCurrent(session) &&
      roleRef.current===role && contextKey()===scope;
    setSaving(id);setError(null);
    try {
      await acknowledgeInbox(id);
      if(same())await refresh();
    } catch(exc) {
      if(same())setError(exc instanceof Error?exc.message:'Leitura não confirmada.');
    } finally {
      if(same())setSaving(null);
    }
  };

  // Hide the previous account's result on the very first render after a
  // role, user or tenant transition, before the effect clears old state.
  const visible=loadedContext!==null && loadedContext===contextKey() &&
    authService.getUser()?.role===role;
  const visibleReady=visible && ready;
  const visiblePage=visible ? page : null;
  const visibleRows=visible ? rows : [];

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
        <p className="mt-3 text-sm text-[#3d5748]">
          {visibleReady?'Avisos internos salvos na sua conta e nesta caixinha.':
            'Estamos preparando a central de avisos do FR Finance no banco local.'}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button type="button" disabled={busy || saving!==null} onClick={()=>void refresh()}
            className="rounded-lg bg-[#195c3c] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            <RefreshCw className="mr-1 inline h-4 w-4"/> Atualizar
          </button>
          {visibleReady&&<button type="button" disabled={busy || saving!==null} onClick={()=>void selfTest()}
            className="rounded-lg border border-[#195c3c] px-4 py-2 text-sm font-semibold text-[#195c3c] disabled:opacity-50">
            Enviar aviso interno de teste
          </button>}
        </div>
      </header>

      {error&&<div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">{error}</div>}
      {!visibleReady&&<div role="status" className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
        <div className="flex items-center gap-2"><BellOff className="h-5 w-5"/>
          <strong>Recebimento de notificações ainda não ativado</strong>
        </div>
        <p className="mt-2 text-sm">A caixa interna exige migração 031, login válido e FastAPI local. Nenhuma mensagem simulada será apresentada como recebida.</p>
      </div>}
      {visibleReady&&<section aria-label="Caixa de entrada" className="space-y-3">
        <h2 className="font-bold text-[#073d2b]">Caixa de entrada
          {visiblePage&&<span className="ml-2 rounded-full bg-[#e5f2e8] px-2 py-1 text-xs text-[#195c3c]">
            {visiblePage.unread_count} não lidas
          </span>}
        </h2>
        {busy&&<p role="status" className="text-sm">Consultando mensagens...</p>}
        {!busy&&visibleRows.length===0&&!error&&<p role="status" className="rounded-xl bg-white p-5 text-sm">
          Nenhum aviso encontrado nesta conta.
        </p>}
        {visibleRows.map(item=><article key={item.id}
          className="rounded-xl border border-[#d1dfd1] bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 className="font-semibold text-[#123f2c]">{item.title}</h3>
              <p className="mt-1 text-sm text-[#526d5a]">{item.message}</p>
              <p className="mt-2 text-xs text-[#64806e]">
                {new Date(item.created_at).toLocaleString('pt-BR')}
              </p>
            </div>
            {!item.read_at?<button type="button"
              disabled={saving!==null||busy} onClick={()=>void markRead(item.id)}
              className="rounded-lg border border-[#195c3c] px-3 py-2 text-xs font-semibold text-[#195c3c] disabled:opacity-50">
              {saving===item.id?'Confirmando...':'Marcar como lida'}
            </button>:<span className="text-xs text-[#64806e]">Lida</span>}
          </div>
        </article>)}
        {visiblePage?.has_more&&visiblePage.next_cursor&&<button type="button"
          disabled={busy||saving!==null} onClick={()=>void refresh(visiblePage.next_cursor,true)}
          className="w-full rounded-lg border border-[#cadacb] bg-white px-4 py-3 text-sm font-semibold disabled:opacity-50">
          Carregar mais
        </button>}
      </section>}
      <h2 className="text-base font-bold text-[#073d2b]">Outros canais</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          {label:'E-mail',Icon:Mail,detail:'Requer e-mail verificado e serviço de envio'},
          {label:'Push',Icon:Smartphone,detail:'Requer dispositivo e serviço push'},
          {label:'WhatsApp',Icon:MessageCircle,detail:'Requer consentimento e integração aprovada'},
        ].map(({label,Icon,detail})=><article key={label}
          className="rounded-xl border border-[#d1dfd1] bg-white p-4">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-[#195c3c]"/>
            <h3 className="text-sm font-semibold">{label}</h3>
          </div>
          <p className="mt-2 text-xs">{detail}</p>
          <p className="mt-2 text-xs font-semibold text-amber-800">Não ativado</p>
        </article>)}
      </div>
      <p className="flex items-start gap-2 text-xs text-[#506a59]">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0"/>
        Avisos internos não autorizam pagamentos, Pix, empréstimos, conciliação
        ou acesso a outra caixinha.
      </p>
    </section>
  );
};
