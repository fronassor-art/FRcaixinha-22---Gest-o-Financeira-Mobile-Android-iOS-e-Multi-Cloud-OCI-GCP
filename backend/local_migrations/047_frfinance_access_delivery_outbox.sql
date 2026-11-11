-- FR Finance M38990: ONE ORIGINAL DATABASE, durable invite/reset outbox.
-- CANDIDATE: requires explicit migration approval and physical identity checks.
-- NEVER apply staging/CI SQL 050/051 or recreate DB/worktree/cluster.
-- Uses existing frc_ai_auth (not app, not owner) as narrow runtime role.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_aistudio_dev'
    OR session_user<>'frc_ai_owner' OR current_user<>'frc_ai_owner'
    OR inet_server_port()<>5433
    OR current_setting('data_directory') <>
       '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
    OR current_setting('server_version_num')::integer NOT BETWEEN 180000 AND 189999
    OR current_setting('frfinance.migration_047_approved',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M38990_WRONG_PROJECT_OR_MIGRATION_NOT_APPROVED'; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_auth'
                 AND NOT rolsuper AND NOT rolbypassrls
                 AND NOT rolcreatedb AND NOT rolcreaterole)
    OR to_regclass('public.invitations') IS NULL
    OR to_regclass('public.password_reset_tokens') IS NULL
    OR to_regclass('public.invite_email_verification') IS NULL
    OR to_regclass('public.contract_documents') IS NULL
    OR to_regclass('public.saas_license_entitlements') IS NULL
    OR to_regclass('public.sessions') IS NULL
 THEN RAISE EXCEPTION 'M38990_ORIGINAL_SCHEMA_OR_ROLE_MISSING'; END IF;
 IF to_regclass('public.frfinance_access_delivery_outbox') IS NOT NULL THEN
   RAISE EXCEPTION 'M38990_ALREADY_EXISTS_CHECK_MIGRATION_HISTORY'; END IF;
END $guard$;

CREATE TABLE public.frfinance_access_delivery_outbox (
 event_id uuid PRIMARY KEY,
 kind varchar(20) NOT NULL CHECK(kind IN ('INVITE_MEMBER','RESET','RESET_NOOP')),
 object_id uuid,
 tenant_id uuid,
 actor_id uuid,
 recipient_digest char(64) NOT NULL CHECK(recipient_digest ~ '^[0-9a-f]{64}$'),
 source_digest char(64) NOT NULL CHECK(source_digest ~ '^[0-9a-f]{64}$'),
 sealed_message bytea,
 state varchar(28) NOT NULL DEFAULT 'QUEUED'
   CHECK(state IN ('QUEUED','LEASED','SMTP_ACCEPTED','QUARANTINED','NO_ACCOUNT')),
 attempts smallint NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 2),
 lease_until timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 smtp_accepted_at timestamptz,
 CHECK(expires_at>created_at),
 CHECK(kind<>'RESET_NOOP' OR (sealed_message IS NULL AND state='NO_ACCOUNT')),
 CHECK(kind='RESET_NOOP' OR
       (octet_length(sealed_message) BETWEEN 44 AND 8192 AND object_id IS NOT NULL)),
 CHECK(state<>'SMTP_ACCEPTED' OR smtp_accepted_at IS NOT NULL)
);
CREATE INDEX frfinance_delivery_claim_idx
 ON public.frfinance_access_delivery_outbox(state,created_at)
 WHERE state='QUEUED';
CREATE INDEX frfinance_delivery_recipient_rate_idx
 ON public.frfinance_access_delivery_outbox(recipient_digest,created_at DESC);
CREATE INDEX frfinance_delivery_source_rate_idx
 ON public.frfinance_access_delivery_outbox(source_digest,created_at DESC);
ALTER TABLE public.frfinance_access_delivery_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.frfinance_access_delivery_outbox FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.frfinance_access_delivery_outbox
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frc_ai_app,frc_ai_auth;
-- No table policies: only narrowly-checked SECURITY DEFINER functions can
-- write/read this encrypted queue, and only for the existing auth login role.

CREATE FUNCTION public.frfinance_enqueue_member_invite(
 p_event uuid,p_session uuid,p_tenant uuid,p_document uuid,
 p_recipient varchar,p_token_digest char(64),p_recipient_digest char(64),
 p_source_digest char(64),p_cipher bytea
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp
AS $fn$
DECLARE actor uuid; invitation uuid; now_ timestamptz:=clock_timestamp();
BEGIN
 IF session_user<>'frc_ai_auth' OR current_database()<>'frcaixinha_aistudio_dev'
   OR p_event IS NULL OR p_event='00000000-0000-0000-0000-000000000000'::uuid
   OR p_session IS NULL OR p_tenant IS NULL OR p_document IS NULL
   OR p_recipient IS NULL OR length(p_recipient) NOT BETWEEN 5 AND 254
   OR p_recipient<>lower(trim(p_recipient))
   OR p_recipient !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
   OR p_token_digest !~ '^[0-9a-f]{64}$'
   OR p_recipient_digest !~ '^[0-9a-f]{64}$'
   OR p_source_digest !~ '^[0-9a-f]{64}$'
   OR octet_length(p_cipher) NOT BETWEEN 44 AND 8192
 THEN RAISE EXCEPTION 'M38990_INVITE_DENIED' USING ERRCODE='42501'; END IF;

 SELECT s.user_id INTO actor FROM public.sessions s
 JOIN public.users u ON u.id=s.user_id AND u.status='ACTIVE'
 JOIN public.memberships m ON m.user_id=s.user_id
   AND m.tenant_id=p_tenant AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 JOIN public.tenants t ON t.id=p_tenant AND t.status='ATIVO'
 JOIN public.contract_documents d ON d.id=p_document
   AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL
 WHERE s.id=p_session AND s.revoked_at IS NULL
   AND s.expires_at>now_ AND s.active_tenant_id=p_tenant
   AND s.active_role='TENANT_ADMIN'
   AND EXISTS(SELECT 1 FROM public.saas_license_entitlements e
              WHERE e.tenant_id=p_tenant AND e.status='ACTIVE'
                AND e.valid_from<=now_ AND e.valid_until>now_)
 LIMIT 1;
 IF actor IS NULL THEN
   RAISE EXCEPTION 'M38990_INVITE_NOT_AUTHORIZED' USING ERRCODE='42501';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('FR38990|'||actor::text,0));
 IF (SELECT count(*) FROM public.frfinance_access_delivery_outbox
       WHERE actor_id=actor AND created_at>now_-interval '1 hour')>=10
 THEN RAISE EXCEPTION 'M38990_INVITE_RATE_LIMIT' USING ERRCODE='42501'; END IF;

 INSERT INTO public.invitations (
    tenant_id,inviter_user_id,target_email,target_role,
    token_hash,expires_at,required_document_id)
 VALUES (p_tenant,actor,p_recipient,'TENANT_MEMBER',
         p_token_digest,now_+interval '48 hours',p_document)
 RETURNING id INTO invitation;
 INSERT INTO public.invite_email_verification (
    invitation_id,recipient_email,token_hash,expires_at)
 VALUES (invitation,p_recipient,p_token_digest,now_+interval '15 minutes');
 INSERT INTO public.frfinance_access_delivery_outbox(
    event_id,kind,object_id,tenant_id,actor_id,recipient_digest,source_digest,
    sealed_message,expires_at)
 VALUES(p_event,'INVITE_MEMBER',invitation,p_tenant,actor,
        p_recipient_digest,p_source_digest,p_cipher,now_+interval '15 minutes');
 RETURN true;
END $fn$;

CREATE FUNCTION public.frfinance_enqueue_password_reset(
 p_event uuid,p_recipient varchar,p_token_digest char(64),
 p_recipient_digest char(64),p_source_digest char(64),p_cipher bytea
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp
AS $fn$
DECLARE target uuid; reset_id uuid; now_ timestamptz:=clock_timestamp();
BEGIN
 IF session_user<>'frc_ai_auth' OR current_database()<>'frcaixinha_aistudio_dev'
   OR p_event IS NULL OR p_event='00000000-0000-0000-0000-000000000000'::uuid
   OR p_recipient IS NULL OR length(p_recipient) NOT BETWEEN 5 AND 254
   OR p_recipient<>lower(trim(p_recipient))
   OR p_recipient !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
   OR p_token_digest !~ '^[0-9a-f]{64}$'
   OR p_recipient_digest !~ '^[0-9a-f]{64}$'
   OR p_source_digest !~ '^[0-9a-f]{64}$'
   OR octet_length(p_cipher) NOT BETWEEN 44 AND 8192
 THEN RAISE EXCEPTION 'M38990_RESET_DENIED' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('FR38990R|'||p_recipient_digest,0));
 IF (SELECT count(*) FROM public.frfinance_access_delivery_outbox
     WHERE recipient_digest=p_recipient_digest
       AND kind IN ('RESET','RESET_NOOP')
       AND created_at>now_-interval '1 hour')>=3
    OR (SELECT count(*) FROM public.frfinance_access_delivery_outbox
     WHERE source_digest=p_source_digest
       AND kind IN ('RESET','RESET_NOOP')
       AND created_at>now_-interval '1 hour')>=15
 THEN RAISE EXCEPTION 'M38990_RESET_RATE_LIMIT' USING ERRCODE='42501'; END IF;

 SELECT id INTO target FROM public.users
  WHERE lower(email)=p_recipient AND status='ACTIVE' LIMIT 1;
 IF target IS NOT NULL THEN
   INSERT INTO public.password_reset_tokens(user_id,token_hash,expires_at)
   VALUES(target,p_token_digest,now_+interval '15 minutes')
   RETURNING id INTO reset_id;
 END IF;
 -- Always persist an indistinguishable record (including unknown users),
 -- but never retain their ciphertext when no account is active.
 INSERT INTO public.frfinance_access_delivery_outbox (
   event_id,kind,object_id,recipient_digest,source_digest,sealed_message,
   state,expires_at)
 VALUES (p_event,CASE WHEN target IS NULL THEN 'RESET_NOOP' ELSE 'RESET' END,
         reset_id,p_recipient_digest,p_source_digest,
         CASE WHEN target IS NULL THEN NULL ELSE p_cipher END,
         CASE WHEN target IS NULL THEN 'NO_ACCOUNT' ELSE 'QUEUED' END,
         now_+interval '15 minutes');
 RETURN true;
END $fn$;

-- Worker safely leases one encrypted message, never a plaintext password/token.
CREATE FUNCTION public.frfinance_claim_access_mail()
RETURNS TABLE (
 event_id uuid,kind varchar,sealed_message bytea,object_id uuid,
 expires_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp
AS $fn$
DECLARE chosen uuid;
BEGIN
 IF session_user<>'frc_ai_auth' OR current_database()<>'frcaixinha_aistudio_dev'
 THEN RAISE EXCEPTION 'M38990_WORKER_DENIED' USING ERRCODE='42501'; END IF;
 UPDATE public.frfinance_access_delivery_outbox q SET
  state='QUARANTINED'
 WHERE q.state='LEASED' AND q.lease_until<clock_timestamp();
 SELECT q.event_id INTO chosen
 FROM public.frfinance_access_delivery_outbox q
 WHERE q.state='QUEUED'
  AND q.expires_at>clock_timestamp()
  AND q.attempts=0
 ORDER BY q.created_at,q.event_id
 FOR UPDATE SKIP LOCKED LIMIT 1;
 IF chosen IS NULL THEN RETURN; END IF;
 UPDATE public.frfinance_access_delivery_outbox q
 SET state='LEASED',attempts=attempts+1,
     lease_until=clock_timestamp()+interval '90 seconds'
 WHERE q.event_id=chosen;
 RETURN QUERY SELECT q.event_id,q.kind,q.sealed_message,q.object_id,q.expires_at
 FROM public.frfinance_access_delivery_outbox q WHERE q.event_id=chosen;
END $fn$;

CREATE FUNCTION public.frfinance_ack_access_mail(
 p_event uuid,p_accepted boolean
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp
AS $fn$
BEGIN
 IF session_user<>'frc_ai_auth' OR current_database()<>'frcaixinha_aistudio_dev'
   OR p_event IS NULL OR p_accepted IS NULL
 THEN RAISE EXCEPTION 'M38990_WORKER_DENIED' USING ERRCODE='42501'; END IF;
 UPDATE public.frfinance_access_delivery_outbox SET
  state=CASE WHEN p_accepted IS TRUE THEN 'SMTP_ACCEPTED' ELSE 'QUARANTINED' END,
  smtp_accepted_at=CASE WHEN p_accepted IS TRUE THEN clock_timestamp() ELSE NULL END,
  lease_until=NULL
 WHERE event_id=p_event AND state='LEASED' AND lease_until>clock_timestamp();
 RETURN FOUND;
END $fn$;

REVOKE ALL ON FUNCTION public.frfinance_enqueue_member_invite(
 uuid,uuid,uuid,uuid,varchar,char,char,char,bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.frfinance_enqueue_password_reset(
 uuid,varchar,char,char,char,bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.frfinance_claim_access_mail() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.frfinance_ack_access_mail(uuid,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.frfinance_enqueue_member_invite(
 uuid,uuid,uuid,uuid,varchar,char,char,char,bytea) TO frc_ai_auth;
GRANT EXECUTE ON FUNCTION public.frfinance_enqueue_password_reset(
 uuid,varchar,char,char,char,bytea) TO frc_ai_auth;
GRANT EXECUTE ON FUNCTION public.frfinance_claim_access_mail() TO frc_ai_auth;
GRANT EXECUTE ON FUNCTION public.frfinance_ack_access_mail(uuid,boolean) TO frc_ai_auth;

DO $audit$
BEGIN
 IF has_table_privilege('frc_ai_auth','public.frfinance_access_delivery_outbox','SELECT')
   OR has_table_privilege('frc_ai_app','public.frfinance_access_delivery_outbox','INSERT')
   OR has_table_privilege('frcaixinha_app_role','public.frfinance_access_delivery_outbox','SELECT')
 THEN RAISE EXCEPTION 'M38990_UNSAFE_DIRECT_QUEUE_PRIVILEGE'; END IF;
END $audit$;
COMMIT;
