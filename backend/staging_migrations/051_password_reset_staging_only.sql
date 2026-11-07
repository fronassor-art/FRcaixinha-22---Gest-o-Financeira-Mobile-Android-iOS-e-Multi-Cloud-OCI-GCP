-- M26000 AI Studio -- secure reset rotation rehearsal, disposable staging CI ONLY.
-- No public HTTP route, SMTP, production or Termux migration is enabled.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.recovery_staging_ci',true) IS DISTINCT FROM '1'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS (
      SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_account_recovery_ci'
        AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
    )
 THEN RAISE EXCEPTION 'M26000_DENIED: disposable staging DBA only'; END IF;
END $guard$;

CREATE TABLE public.password_recovery_audit_staging (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 reset_id uuid NOT NULL UNIQUE REFERENCES public.password_reset_tokens(id) ON DELETE RESTRICT,
 user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 event_id uuid NOT NULL UNIQUE,
 kind varchar(36) NOT NULL CHECK(kind='CI_PASSWORD_ROTATED_SESSIONS_REVOKED'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.password_recovery_audit_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_recovery_audit_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.password_recovery_audit_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_account_recovery_ci;

CREATE FUNCTION public.password_reset_rotate_staging_ci(
 p_token_digest varchar,p_new_hash varchar,p_event uuid
) RETURNS varchar LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 reset_row record;
 updated_count integer;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_account_recovery_ci'
    OR current_setting('frcaixinha.recovery_staging_ci',true) IS DISTINCT FROM '1'
    OR p_token_digest IS NULL OR p_token_digest !~ '^[0-9a-f]{64}$'
    OR p_new_hash IS NULL OR left(p_new_hash,10)<>'$argon2id$'
    OR length(p_new_hash) NOT BETWEEN 50 AND 255
    OR p_event IS NULL OR p_event='00000000-0000-0000-0000-000000000000'::uuid
 THEN RAISE EXCEPTION 'M26000_DENIED: worker identity or input invalid'; END IF;

 -- Single-use row lock is mandatory before any credential changes.
 SELECT r.id,r.user_id INTO reset_row
 FROM public.password_reset_tokens r
 JOIN public.users u ON u.id=r.user_id AND u.status='ACTIVE'
 WHERE r.token_hash=p_token_digest
   AND r.expires_at>now()
   AND r.consumed_at IS NULL AND r.revoked_at IS NULL
   AND r.delivery_status='DELIVERED'
 FOR UPDATE OF r;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;

 UPDATE public.credentials c
 SET password_hash=p_new_hash,algorithm='argon2id',password_changed_at=now()
 WHERE c.user_id=reset_row.user_id AND c.password_hash IS DISTINCT FROM p_new_hash;
 GET DIAGNOSTICS updated_count=ROW_COUNT;
 IF updated_count<>1 THEN
   RAISE EXCEPTION 'M26000_DENIED: credential change not completed';
 END IF;

 UPDATE public.password_reset_tokens SET consumed_at=now()
 WHERE id=reset_row.id AND consumed_at IS NULL;
 UPDATE public.password_reset_tokens SET revoked_at=now()
 WHERE user_id=reset_row.user_id AND id<>reset_row.id
   AND consumed_at IS NULL AND revoked_at IS NULL;
 -- Defence in depth: migration 026 also revokes on password_hash UPDATE.
 UPDATE public.sessions SET revoked_at=now()
 WHERE user_id=reset_row.user_id AND revoked_at IS NULL;

 INSERT INTO public.password_recovery_audit_staging
 (reset_id,user_id,event_id,kind)
 VALUES(reset_row.id,reset_row.user_id,p_event,
        'CI_PASSWORD_ROTATED_SESSIONS_REVOKED');

 RETURN 'ROTATED';
END $fn$;

REVOKE ALL ON FUNCTION public.password_reset_rotate_staging_ci(
 varchar,varchar,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_account_recovery_ci;
GRANT EXECUTE ON FUNCTION public.password_reset_rotate_staging_ci(
 varchar,varchar,uuid) TO frcaixinha_account_recovery_ci;
COMMIT;
