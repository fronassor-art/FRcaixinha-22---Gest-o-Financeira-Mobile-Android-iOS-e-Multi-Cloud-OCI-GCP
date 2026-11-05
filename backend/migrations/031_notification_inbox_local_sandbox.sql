-- FR Caixinha AI Studio: LOCAL notification inbox (sandbox ONLY).
-- New standalone migration 031; NOT staging schema 041, not financial events.
-- Apply ONLY with a verified backup and 001-027 present, in single transaction.
BEGIN;
DO $guard$
DECLARE ok boolean;
BEGIN
 ok:=((
   current_database()='frcaixinha_aistudio_dev'
   AND inet_server_port()=5433
   AND current_user='frc_ai_owner'
   AND current_setting('data_directory')=
      '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
   AND current_setting('server_version_num')::integer>=180000
   AND current_setting('server_version_num')::integer<190000
 ) OR (
   current_database()='frcaixinha_staging'
   AND session_user='postgres'
   AND current_setting('frcaixinha.notifications_local_ci',true)='1'
 ));
 IF NOT ok
  OR to_regclass('public.users') IS NULL
  OR to_regclass('public.memberships') IS NULL
  OR to_regclass('public.sessions') IS NULL
  OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_app_role'
          AND NOT rolsuper AND NOT rolbypassrls)
  OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_auth_role'
          AND NOT rolsuper AND NOT rolbypassrls)
  OR to_regclass('public.notification_inbox') IS NOT NULL
 THEN RAISE EXCEPTION 'M031 DENIED: only approved AI Studio local or disposable CI with clean schema'; END IF;
END $guard$;

CREATE TABLE public.notification_inbox (
 id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
 tenant_id uuid REFERENCES public.tenants(id) ON DELETE RESTRICT,
 recipient_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 recipient_role varchar(20) NOT NULL CHECK(
  recipient_role IN ('MASTER','TENANT_ADMIN','TENANT_MEMBER')),
 event_id uuid NOT NULL CHECK(
  event_id<>'00000000-0000-0000-0000-000000000000'::uuid),
 kind varchar(30) NOT NULL DEFAULT 'SELF_TEST' CHECK(kind='SELF_TEST'),
 title varchar(100) NOT NULL CHECK(
  title='Aviso de teste interno'),
 message varchar(280) NOT NULL CHECK(
  message='Teste do recebimento interno realizado nesta conta. Nenhum pagamento ou envio externo foi executado.'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 read_at timestamptz,
 CHECK((recipient_role='MASTER' AND tenant_id IS NULL) OR
       (recipient_role IN ('TENANT_ADMIN','TENANT_MEMBER') AND tenant_id IS NOT NULL)),
 CONSTRAINT notification_local_unique_event UNIQUE NULLS NOT DISTINCT(
    tenant_id,recipient_user_id,recipient_role,event_id),
 CHECK(read_at IS NULL OR read_at>=created_at)
);
CREATE INDEX notification_local_keyset ON public.notification_inbox
  (recipient_user_id,recipient_role,tenant_id,created_at DESC,id DESC);

ALTER TABLE public.notification_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_inbox FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.notification_inbox FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT SELECT ON TABLE public.notification_inbox TO frcaixinha_app_role;

CREATE OR REPLACE FUNCTION public.notification_local_active_context(
 p_user uuid,p_tenant uuid,p_role varchar
) RETURNS boolean LANGUAGE plpgsql STABLE SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF session_user NOT IN ('frc_ai_app','frcaixinha_ci','frcaixinha_pg18_app')
    OR p_user IS NULL OR p_user IS DISTINCT FROM
       NULLIF(current_setting('app.current_user_id',true),'')::uuid
    OR p_role IS DISTINCT FROM current_setting('app.current_role',true)
    OR p_tenant IS DISTINCT FROM
       NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 THEN RETURN false; END IF;
 RETURN EXISTS(
   SELECT 1 FROM public.users u WHERE u.id=p_user AND u.status='ACTIVE'
   AND (
     (p_role='MASTER' AND p_tenant IS NULL AND u.is_master=true)
     OR (
       p_role IN ('TENANT_ADMIN','TENANT_MEMBER')
       AND p_tenant IS NOT NULL AND u.is_master=false
       AND EXISTS(SELECT 1 FROM public.memberships m
         JOIN public.tenants t ON t.id=m.tenant_id
         WHERE m.user_id=p_user AND m.tenant_id=p_tenant
           AND m.role=p_role AND m.status='ATIVA'
           AND t.status='ATIVO')
     )
   )
 );
END $fn$;
REVOKE ALL ON FUNCTION public.notification_local_active_context(uuid,uuid,varchar)
 FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.notification_local_active_context(uuid,uuid,varchar)
 TO frcaixinha_app_role;

CREATE POLICY notification_local_read_own ON public.notification_inbox
 FOR SELECT TO frcaixinha_app_role USING (
 recipient_user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
 AND recipient_role=current_setting('app.current_role',true)
 AND tenant_id IS NOT DISTINCT FROM
     NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 AND public.notification_local_active_context(
   recipient_user_id,tenant_id,recipient_role)
);

-- No user-supplied recipient, tenant, title, event, money or HTML.
-- Transaction-local SQL context is set by the authenticated backend.
CREATE OR REPLACE FUNCTION public.notification_local_create_selftest()
 RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 u uuid; t uuid; r varchar; created uuid; total integer;
BEGIN
 u:=NULLIF(current_setting('app.current_user_id',true),'')::uuid;
 t:=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid;
 r:=current_setting('app.current_role',true);
 IF NOT public.notification_local_active_context(u,t,r) THEN
   RAISE EXCEPTION 'M031 DENIED: session context inactive'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(
   'M031-SELFTEST|'||u||'|'||coalesce(t::text,'MASTER')||'|'||r,0));
 SELECT count(*) INTO total FROM public.notification_inbox n
  WHERE n.recipient_user_id=u AND n.recipient_role=r
    AND n.tenant_id IS NOT DISTINCT FROM t AND n.kind='SELF_TEST'
    AND n.created_at>=clock_timestamp()-interval '24 hours';
 IF total>=10 THEN RAISE EXCEPTION 'M031 DENIED: daily synthetic notice rate limit'; END IF;
 INSERT INTO public.notification_inbox (
  tenant_id,recipient_user_id,recipient_role,event_id,kind,title,message
 ) VALUES(
  t,u,r,uuid_generate_v4(),'SELF_TEST','Aviso de teste interno',
  'Teste do recebimento interno realizado nesta conta. Nenhum pagamento ou envio externo foi executado.'
 ) RETURNING id INTO created;
 RETURN created;
END $fn$;

CREATE OR REPLACE FUNCTION public.notification_local_mark_read(p_id uuid)
 RETURNS text LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 u uuid; t uuid; r varchar; current_read timestamptz;
BEGIN
 u:=NULLIF(current_setting('app.current_user_id',true),'')::uuid;
 t:=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid;
 r:=current_setting('app.current_role',true);
 IF p_id IS NULL OR NOT public.notification_local_active_context(u,t,r)
 THEN RETURN 'NOT_FOUND'; END IF;
 SELECT n.read_at INTO current_read FROM public.notification_inbox n
 WHERE n.id=p_id AND n.recipient_user_id=u
   AND n.recipient_role=r AND n.tenant_id IS NOT DISTINCT FROM t
 FOR UPDATE;
 IF NOT FOUND THEN RETURN 'NOT_FOUND'; END IF;
 IF current_read IS NOT NULL THEN RETURN 'ALREADY_READ'; END IF;
 UPDATE public.notification_inbox SET read_at=clock_timestamp() WHERE id=p_id;
 RETURN 'READ';
END $fn$;

REVOKE ALL ON FUNCTION public.notification_local_create_selftest() FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
REVOKE ALL ON FUNCTION public.notification_local_mark_read(uuid) FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.notification_local_create_selftest() TO frcaixinha_app_role;
GRANT EXECUTE ON FUNCTION public.notification_local_mark_read(uuid) TO frcaixinha_app_role;

-- No direct INSERT/UPDATE/DELETE to the app role. No real domain event
-- producer, no external provider and no financial effect from this migration.
COMMIT;
