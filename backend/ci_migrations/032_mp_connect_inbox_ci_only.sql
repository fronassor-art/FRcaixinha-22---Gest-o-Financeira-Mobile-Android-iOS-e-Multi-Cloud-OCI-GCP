-- AI Studio M2500: laboratório CI de persistência de OAuth/inbox.
-- NÃO é uma migração Termux/prod, NÃO valida dinheiro nem faz OAuth real.
-- Em frcaixinha_aistudio_dev a guarda DEVE lançar exceção antes de DDL.
DO $guard$
BEGIN
 IF current_database() <> 'frcaixinha_ci'
 OR current_setting('frcaixinha.ci_sandbox', true) IS DISTINCT FROM '1' THEN
   RAISE EXCEPTION 'BLOQUEADO M032: somente PostgreSQL CI descartável';
 END IF;
END $guard$;

CREATE TABLE public.mp_ci_oauth_attempts (
 attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 state_sha256 varchar(64) NOT NULL UNIQUE CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
 redirect_sha256 varchar(64) NOT NULL CHECK (redirect_sha256 ~ '^[0-9a-f]{64}$'),
 pkce_challenge varchar(128) NOT NULL CHECK (pkce_challenge ~ '^[A-Za-z0-9_-]{43,128}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 source varchar(32) NOT NULL DEFAULT 'SYNTHETIC_OAUTH_DRAFT_ONLY'
   CHECK (source='SYNTHETIC_OAUTH_DRAFT_ONLY'),
 CHECK (consumed_at IS NULL OR consumed_at >= created_at)
);
CREATE INDEX mp_ci_oauth_tenant_recent ON public.mp_ci_oauth_attempts(tenant_id,created_at DESC);

CREATE TABLE public.mp_ci_seller_bindings (
 tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id) ON DELETE RESTRICT,
 seller_id varchar(40) NOT NULL UNIQUE CHECK (seller_id ~ '^[0-9]{1,40}$'),
 actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 revoked_at timestamptz,
 source varchar(30) NOT NULL DEFAULT 'SYNTHETIC_BINDING_ONLY'
   CHECK (source='SYNTHETIC_BINDING_ONLY'),
 UNIQUE (tenant_id,seller_id),
 CHECK (revoked_at IS NULL OR revoked_at >= created_at)
);

CREATE TABLE public.mp_ci_webhook_inbox (
 notification_id varchar(100) PRIMARY KEY CHECK (notification_id ~ '^[A-Za-z0-9_-]{1,100}$'),
 event_id uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 seller_id varchar(40) NOT NULL,
 resource_id varchar(100) NOT NULL CHECK (resource_id ~ '^[A-Za-z0-9_-]{1,100}$'),
 request_id varchar(120) NOT NULL UNIQUE CHECK (request_id ~ '^[A-Za-z0-9._:-]{1,120}$'),
 event_action varchar(48) NOT NULL
   CHECK (event_action IN ('payment.created','payment.updated','application.authorized','application.deauthorized')),
 payload_sha256 varchar(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
 received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source varchar(40) NOT NULL DEFAULT 'SYNTHETIC_SIGNED_ENVELOPE_FIXTURE'
   CHECK (source='SYNTHETIC_SIGNED_ENVELOPE_FIXTURE'),
 provider_get_authenticated boolean NOT NULL DEFAULT false CHECK (provider_get_authenticated=false),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK (bank_reconciled=false),
 ledger_written boolean NOT NULL DEFAULT false CHECK (ledger_written=false),
 paid boolean NOT NULL DEFAULT false CHECK (paid=false),
 closing_authorized boolean NOT NULL DEFAULT false CHECK (closing_authorized=false),
 FOREIGN KEY (tenant_id,seller_id)
  REFERENCES public.mp_ci_seller_bindings(tenant_id,seller_id) ON DELETE RESTRICT
);
CREATE INDEX mp_ci_webhook_tenant_recent ON public.mp_ci_webhook_inbox(tenant_id,received_at DESC);

ALTER TABLE public.mp_ci_oauth_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_ci_oauth_attempts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mp_ci_seller_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_ci_seller_bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mp_ci_webhook_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_ci_webhook_inbox FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.mp_ci_oauth_attempts, public.mp_ci_seller_bindings,
 public.mp_ci_webhook_inbox FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;

CREATE FUNCTION public.mp_ci_guard_admin(p_tenant uuid)
 RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_actor uuid;
BEGIN
 IF current_database()<>'frcaixinha_ci'
 OR current_setting('frcaixinha.ci_sandbox',true) IS DISTINCT FROM '1'
 OR p_tenant IS NULL
 OR current_setting('app.current_role',true) IS DISTINCT FROM 'TENANT_ADMIN'
 OR NULLIF(current_setting('app.current_tenant_id',true),'')::uuid IS DISTINCT FROM p_tenant THEN
   RAISE EXCEPTION 'BLOQUEADO: operação somente tenant admin em CI descartável';
 END IF;
 v_actor := NULLIF(current_setting('app.current_user_id',true),'')::uuid;
 IF v_actor IS NULL OR NOT public.rls_is_tenant_admin(v_actor,p_tenant) THEN
   RAISE EXCEPTION 'BLOQUEADO: sem autorização tenant';
 END IF;
 RETURN v_actor;
END $$;

CREATE FUNCTION public.mp_ci_open_oauth(
 p_tenant uuid, p_state_sha text, p_redirect_sha text, p_pkce text, p_ttl_seconds integer
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_actor uuid; v_id uuid;
BEGIN
 v_actor := public.mp_ci_guard_admin(p_tenant);
 IF p_state_sha IS NULL OR p_state_sha !~ '^[0-9a-f]{64}$'
 OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[0-9a-f]{64}$'
 OR p_pkce IS NULL OR p_pkce !~ '^[A-Za-z0-9_-]{43,128}$'
 OR p_ttl_seconds IS NULL OR p_ttl_seconds NOT BETWEEN 1 AND 600 THEN
   RAISE EXCEPTION 'BLOQUEADO: tentativa OAuth sintética inválida';
 END IF;
 INSERT INTO public.mp_ci_oauth_attempts(
  tenant_id,actor_user_id,state_sha256,redirect_sha256,pkce_challenge,expires_at
 ) VALUES (p_tenant,v_actor,p_state_sha,p_redirect_sha,p_pkce,
           clock_timestamp()+make_interval(secs=>p_ttl_seconds))
 RETURNING attempt_id INTO v_id;
 RETURN v_id;
END $$;

CREATE FUNCTION public.mp_ci_consume_oauth(
 p_tenant uuid, p_state_sha text, p_redirect_sha text
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_actor uuid; v_id uuid;
BEGIN
 v_actor := public.mp_ci_guard_admin(p_tenant);
 IF p_state_sha IS NULL OR p_state_sha !~ '^[0-9a-f]{64}$'
 OR p_redirect_sha IS NULL OR p_redirect_sha !~ '^[0-9a-f]{64}$' THEN
   RETURN false;
 END IF;
 UPDATE public.mp_ci_oauth_attempts SET consumed_at=clock_timestamp()
 WHERE tenant_id=p_tenant AND actor_user_id=v_actor
 AND state_sha256=p_state_sha AND redirect_sha256=p_redirect_sha
 AND consumed_at IS NULL AND expires_at>clock_timestamp()
 RETURNING attempt_id INTO v_id;
 RETURN v_id IS NOT NULL;
END $$;

CREATE FUNCTION public.mp_ci_bind_seller(p_tenant uuid, p_seller varchar)
 RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_actor uuid; v_id uuid;
BEGIN
 v_actor := public.mp_ci_guard_admin(p_tenant);
 IF p_seller IS NULL OR p_seller !~ '^[0-9]{1,40}$' THEN
   RAISE EXCEPTION 'BLOQUEADO: seller sintético inválido';
 END IF;
 INSERT INTO public.mp_ci_seller_bindings(tenant_id,seller_id,actor_user_id)
 VALUES(p_tenant,p_seller,v_actor)
 ON CONFLICT (tenant_id) DO NOTHING;
 SELECT tenant_id INTO v_id FROM public.mp_ci_seller_bindings
 WHERE tenant_id=p_tenant AND seller_id=p_seller AND revoked_at IS NULL;
 IF v_id IS NULL THEN
   RAISE EXCEPTION 'BLOQUEADO: seller alterado ou revogado';
 END IF;
 RETURN v_id;
END $$;

CREATE FUNCTION public.mp_ci_revoke_seller(p_tenant uuid, p_seller varchar)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_actor uuid; v_id uuid;
BEGIN
 v_actor := public.mp_ci_guard_admin(p_tenant);
 UPDATE public.mp_ci_seller_bindings SET revoked_at=clock_timestamp()
 WHERE tenant_id=p_tenant AND seller_id=p_seller AND revoked_at IS NULL
 RETURNING tenant_id INTO v_id;
 RETURN v_id IS NOT NULL;
END $$;

CREATE FUNCTION public.mp_ci_append_webhook(
 p_tenant uuid, p_seller varchar, p_notification varchar, p_resource varchar,
 p_request varchar, p_action varchar, p_sha text
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE v_actor uuid; v_existing public.mp_ci_webhook_inbox%ROWTYPE; v_new uuid;
BEGIN
 v_actor := public.mp_ci_guard_admin(p_tenant);
 IF p_seller IS NULL OR p_seller !~ '^[0-9]{1,40}$'
 OR p_notification IS NULL OR p_notification !~ '^[A-Za-z0-9_-]{1,100}$'
 OR p_resource IS NULL OR p_resource !~ '^[A-Za-z0-9_-]{1,100}$'
 OR p_request IS NULL OR p_request !~ '^[A-Za-z0-9._:-]{1,120}$'
 OR p_action IS NULL OR p_action NOT IN
  ('payment.created','payment.updated','application.authorized','application.deauthorized')
 OR p_sha IS NULL OR p_sha !~ '^[0-9a-f]{64}$' THEN
   RAISE EXCEPTION 'BLOQUEADO: evento sintético inválido';
 END IF;
 IF NOT EXISTS(
  SELECT 1 FROM public.mp_ci_seller_bindings
  WHERE tenant_id=p_tenant AND seller_id=p_seller AND revoked_at IS NULL
 ) THEN RAISE EXCEPTION 'BLOQUEADO: seller não vinculado ou revogado'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(
  'FRC-MP-CI-INBOX|'||p_notification,0));
 SELECT * INTO v_existing FROM public.mp_ci_webhook_inbox
 WHERE notification_id=p_notification;
 IF FOUND THEN
  IF v_existing.tenant_id<>p_tenant OR v_existing.seller_id<>p_seller
   OR v_existing.resource_id<>p_resource OR v_existing.request_id<>p_request
   OR v_existing.event_action<>p_action OR v_existing.payload_sha256<>p_sha THEN
    RAISE EXCEPTION 'BLOQUEADO: replay conflitante ou troca de tenant';
  END IF;
  RETURN v_existing.event_id;
 END IF;
 INSERT INTO public.mp_ci_webhook_inbox(
  tenant_id,seller_id,notification_id,resource_id,request_id,event_action,payload_sha256
 ) VALUES (p_tenant,p_seller,p_notification,p_resource,p_request,p_action,p_sha)
 RETURNING event_id INTO v_new;
 RETURN v_new;
END $$;

REVOKE ALL ON FUNCTION
 public.mp_ci_guard_admin(uuid),
 public.mp_ci_open_oauth(uuid,text,text,text,integer),
 public.mp_ci_consume_oauth(uuid,text,text),
 public.mp_ci_bind_seller(uuid,varchar),
 public.mp_ci_revoke_seller(uuid,varchar),
 public.mp_ci_append_webhook(uuid,varchar,varchar,varchar,varchar,varchar,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- Helper não deve ser invocável diretamente pelo app. As demais são guardadas.
GRANT EXECUTE ON FUNCTION
 public.mp_ci_open_oauth(uuid,text,text,text,integer),
 public.mp_ci_consume_oauth(uuid,text,text),
 public.mp_ci_bind_seller(uuid,varchar),
 public.mp_ci_revoke_seller(uuid,varchar),
 public.mp_ci_append_webhook(uuid,varchar,varchar,varchar,varchar,varchar,text)
 TO frcaixinha_app_role;
