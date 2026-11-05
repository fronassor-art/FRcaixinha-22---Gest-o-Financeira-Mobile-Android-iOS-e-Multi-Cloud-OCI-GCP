-- AI Studio M16000. Disposable GitHub Actions database only.
-- NOT for Termux/OCI/production. All notifications are synthetic and UNDELIVERED.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.notifications_staging_ci',true) IS DISTINCT FROM '1'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on'
    OR to_regclass('public.users') IS NULL
    OR to_regclass('public.memberships') IS NULL
    OR to_regclass('public.cycles') IS NULL
    OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_notify_producer_ci'
       AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'M041 DENIED: ephemeral CI-only notification schema'; END IF;
END $guard$;

CREATE TABLE public.notification_outbox_staging (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid REFERENCES public.tenants(id) ON DELETE RESTRICT,
 cycle_year integer,
 event_id uuid NOT NULL CHECK(event_id<>'00000000-0000-0000-0000-000000000000'::uuid),
 recipient_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 recipient_role varchar(20) NOT NULL CHECK(recipient_role IN('MASTER','TENANT_ADMIN','TENANT_MEMBER')),
 kind varchar(48) NOT NULL CHECK(kind IN(
 'LICENSE_REGULARIZATION','LICENSE_REVERSED_REVIEW','SUPPORT_ACCESS_ALERT',
 'INVITATION_ACCEPTANCE_PENDING','CONTRIBUTION_DUE_INFO','CONTRIBUTION_OVERDUE_INFO',
 'LOAN_REVIEW_PENDING','FINANCIAL_STATUS_UNVERIFIED',
 'CLOSING_REVIEW_PENDING','SECURITY_SESSION_ALERT')),
 channel varchar(12) NOT NULL DEFAULT 'IN_APP' CHECK(channel='IN_APP'),
 source_sha char(64) NOT NULL CHECK(source_sha ~ '^[a-f0-9]{64}$'),
 digest char(64) NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 delivery_status varchar(28) NOT NULL DEFAULT 'HELD_CI_NO_DELIVERY'
    CHECK(delivery_status='HELD_CI_NO_DELIVERY'),
 event_authenticated boolean NOT NULL DEFAULT false CHECK(event_authenticated=false),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK(bank_reconciled=false),
 financial_effect_applied boolean NOT NULL DEFAULT false CHECK(financial_effect_applied=false),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK((tenant_id IS NULL AND cycle_year IS NULL AND recipient_role='MASTER'
    AND kind='SECURITY_SESSION_ALERT')
   OR (tenant_id IS NOT NULL AND cycle_year BETWEEN 2020 AND 2100
    AND recipient_role<>'MASTER')),
 CONSTRAINT notification_outbox_no_duplicate UNIQUE NULLS NOT DISTINCT
   (tenant_id,event_id,recipient_user_id,recipient_role,channel)
);

CREATE TABLE public.notification_inbox_staging (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 outbox_id uuid NOT NULL UNIQUE REFERENCES public.notification_outbox_staging(id) ON DELETE RESTRICT,
 tenant_id uuid REFERENCES public.tenants(id) ON DELETE RESTRICT,
 recipient_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 recipient_role varchar(20) NOT NULL CHECK(recipient_role IN('MASTER','TENANT_ADMIN','TENANT_MEMBER')),
 kind varchar(48) NOT NULL,
 title varchar(100) NOT NULL,
 message varchar(280) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 read_at timestamptz,
 CHECK((tenant_id IS NULL AND recipient_role='MASTER')
    OR (tenant_id IS NOT NULL AND recipient_role<>'MASTER'))
);
CREATE INDEX notification_inbox_keyset_staging
 ON public.notification_inbox_staging(recipient_user_id,recipient_role,tenant_id,created_at DESC,id DESC);

ALTER TABLE public.notification_outbox_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_outbox_staging FORCE ROW LEVEL SECURITY;
ALTER TABLE public.notification_inbox_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_inbox_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.notification_outbox_staging,public.notification_inbox_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_financial_worker,
 frcaixinha_mp_webhook_ingest,frcaixinha_notify_producer_ci;
GRANT SELECT ON public.notification_inbox_staging TO frcaixinha_app_role;
CREATE POLICY notification_recipient_context_ci ON public.notification_inbox_staging
 FOR SELECT TO frcaixinha_app_role USING (
 recipient_user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
 AND recipient_role=current_setting('app.current_role',true)
 AND tenant_id IS NOT DISTINCT FROM
     NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 AND (
   (recipient_role='MASTER' AND tenant_id IS NULL)
   OR (recipient_role IN ('TENANT_ADMIN','TENANT_MEMBER') AND tenant_id IS NOT NULL)
 ));

-- No arbitrary free-form text, contact data, or payout in the entrypoint.
CREATE OR REPLACE FUNCTION public.notification_enqueue_staging_ci(
 p_tenant uuid,p_cycle integer,p_event uuid,p_recipient uuid,
 p_role varchar,p_kind varchar,p_sha varchar
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE prior public.notification_outbox_staging%ROWTYPE;
 claim text;
 out_id uuid;
 subject text;
 body text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_notify_producer_ci'
 OR current_setting('frcaixinha.notifications_staging_ci',true) IS DISTINCT FROM '1'
 OR p_event IS NULL OR p_event='00000000-0000-0000-0000-000000000000'::uuid
 OR p_recipient IS NULL OR p_recipient='00000000-0000-0000-0000-000000000000'::uuid
 OR p_sha IS NULL OR p_sha !~ '^[a-f0-9]{64}$'
 OR NOT (
   (p_role='MASTER' AND p_tenant IS NULL AND p_cycle IS NULL
      AND p_kind='SECURITY_SESSION_ALERT'
      AND EXISTS(SELECT 1 FROM public.users u WHERE u.id=p_recipient
        AND u.is_master AND u.status='ACTIVE'))
   OR
   (p_role IN ('TENANT_ADMIN','TENANT_MEMBER')
      AND p_tenant IS NOT NULL AND p_cycle BETWEEN 2020 AND 2100
      AND EXISTS(SELECT 1 FROM public.users u WHERE u.id=p_recipient
        AND u.status='ACTIVE')
      AND EXISTS(SELECT 1 FROM public.memberships m
        WHERE m.tenant_id=p_tenant AND m.user_id=p_recipient
          AND m.role=p_role AND m.status='ATIVA')
      AND EXISTS(SELECT 1 FROM public.cycles c
        WHERE c.tenant_id=p_tenant AND c.year=p_cycle)
      AND (
        (p_kind IN('LICENSE_REGULARIZATION','LICENSE_REVERSED_REVIEW',
          'SUPPORT_ACCESS_ALERT','CLOSING_REVIEW_PENDING') AND p_role='TENANT_ADMIN')
        OR (p_kind IN('INVITATION_ACCEPTANCE_PENDING','CONTRIBUTION_DUE_INFO',
          'CONTRIBUTION_OVERDUE_INFO') AND p_role='TENANT_MEMBER')
        OR p_kind IN ('LOAN_REVIEW_PENDING','FINANCIAL_STATUS_UNVERIFIED',
          'SECURITY_SESSION_ALERT')
      ))
 )
 THEN RAISE EXCEPTION 'M041 DENIED: untrusted event, recipient, cycle or role'; END IF;
 CASE p_kind
 WHEN 'LICENSE_REGULARIZATION' THEN subject:='Regularização da licença';body:='Confira a licença no painel.';
 WHEN 'LICENSE_REVERSED_REVIEW' THEN subject:='Licença em revisão';body:='Evento sujeito a conferência; nenhum pagamento confirmado.';
 WHEN 'SUPPORT_ACCESS_ALERT' THEN subject:='Acesso técnico';body:='Consulte o evento de suporte.';
 WHEN 'INVITATION_ACCEPTANCE_PENDING' THEN subject:='Convite pendente';body:='Consulte o convite e o aceite.';
 WHEN 'CONTRIBUTION_DUE_INFO' THEN subject:='Contribuição a conferir';body:='Confira o vencimento e o status registrados.';
 WHEN 'CONTRIBUTION_OVERDUE_INFO' THEN subject:='Pendência de contribuição';body:='Confira a obrigação registrada no aplicativo.';
 WHEN 'LOAN_REVIEW_PENDING' THEN subject:='Empréstimo em revisão';body:='Sem autorização de desembolso.';
 WHEN 'FINANCIAL_STATUS_UNVERIFIED' THEN subject:='Pagamento em verificação';body:='Sem confirmação bancária de pagamento.';
 WHEN 'CLOSING_REVIEW_PENDING' THEN subject:='Fechamento em revisão';body:='Sem autorização de fechamento ou Pix.';
 WHEN 'SECURITY_SESSION_ALERT' THEN subject:='Segurança de acesso';body:='Confira suas sessões.';
 ELSE RAISE EXCEPTION 'M041 DENIED: unsupported template'; END CASE;
 claim:=encode(sha256(convert_to(concat_ws('|',
    'AI_STUDIO_M16000_CI_ONLY',coalesce(p_tenant::text,'PLATFORM'),
    coalesce(p_cycle::text,'PLATFORM'),p_event,p_recipient,
    p_role,p_kind,p_sha,'IN_APP'),'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(
   'M041|'||coalesce(p_tenant::text,'PLATFORM')||'|'||p_event||
   '|'||p_recipient||'|'||p_role,0));
 SELECT * INTO prior FROM public.notification_outbox_staging o
 WHERE o.tenant_id IS NOT DISTINCT FROM p_tenant
   AND o.event_id=p_event AND o.recipient_user_id=p_recipient
   AND o.recipient_role=p_role AND o.channel='IN_APP' FOR UPDATE;
 IF FOUND THEN
   IF prior.digest<>claim OR prior.source_sha<>p_sha
    OR prior.kind<>p_kind OR prior.cycle_year IS DISTINCT FROM p_cycle
   THEN RAISE EXCEPTION 'M041 DENIED: conflicting event replay'; END IF;
   RETURN 'REPLAY:'||prior.id;
 END IF;
 INSERT INTO public.notification_outbox_staging
   (tenant_id,cycle_year,event_id,recipient_user_id,recipient_role,kind,source_sha,digest)
 VALUES(p_tenant,p_cycle,p_event,p_recipient,p_role,p_kind,p_sha,claim)
 RETURNING id INTO out_id;
 INSERT INTO public.notification_inbox_staging
   (outbox_id,tenant_id,recipient_user_id,recipient_role,kind,title,message)
 VALUES(out_id,p_tenant,p_recipient,p_role,p_kind,subject,body);
 RETURN 'NEW:'||out_id;
END $fn$;

-- CI-only read acknowledgement. Session GUC alone is NOT an auth proof!
CREATE OR REPLACE FUNCTION public.notification_mark_read_staging_ci(p_id uuid)
 RETURNS text LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $mark$
DECLARE found_row public.notification_inbox_staging%ROWTYPE;
 who uuid;
 scope uuid;
 active_role text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user NOT IN ('frcaixinha_ci','frcaixinha_pg18_app')
   OR current_setting('frcaixinha.notifications_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M041 DENIED: CI reader only'; END IF;
 who:=NULLIF(current_setting('app.current_user_id',true),'')::uuid;
 scope:=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid;
 active_role:=current_setting('app.current_role',true);
 SELECT * INTO found_row FROM public.notification_inbox_staging
 WHERE id=p_id AND recipient_user_id=who
   AND tenant_id IS NOT DISTINCT FROM scope
   AND recipient_role=active_role FOR UPDATE;
 IF NOT FOUND THEN RETURN 'NOT_FOUND'; END IF;
 IF NOT (
  (active_role='MASTER' AND scope IS NULL AND EXISTS(
     SELECT 1 FROM public.users WHERE id=who AND is_master AND status='ACTIVE'))
  OR
  (active_role IN('TENANT_ADMIN','TENANT_MEMBER') AND scope IS NOT NULL AND EXISTS(
     SELECT 1 FROM public.memberships m WHERE m.user_id=who
       AND m.tenant_id=scope AND m.role=active_role AND m.status='ATIVA'))
 ) THEN RETURN 'NOT_FOUND'; END IF;
 IF found_row.read_at IS NOT NULL THEN RETURN 'ALREADY_READ'; END IF;
 UPDATE public.notification_inbox_staging SET read_at=clock_timestamp()
 WHERE id=p_id AND read_at IS NULL;
 RETURN 'READ';
END $mark$;

REVOKE ALL ON FUNCTION public.notification_enqueue_staging_ci(
 uuid,integer,uuid,uuid,varchar,varchar,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_financial_worker,
 frcaixinha_mp_webhook_ingest;
GRANT EXECUTE ON FUNCTION public.notification_enqueue_staging_ci(
 uuid,integer,uuid,uuid,varchar,varchar,varchar) TO frcaixinha_notify_producer_ci;

REVOKE ALL ON FUNCTION public.notification_mark_read_staging_ci(uuid)
 FROM PUBLIC,frcaixinha_notify_producer_ci,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_financial_worker,
 frcaixinha_mp_webhook_ingest;
GRANT EXECUTE ON FUNCTION public.notification_mark_read_staging_ci(uuid)
 TO frcaixinha_app_role;
-- No external send, no FCM/APNs, no WhatsApp, no bank reconciliation/ledger.
COMMIT;
