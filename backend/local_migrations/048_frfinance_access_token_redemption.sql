-- FR Finance M38993: consume EXISTING invite and reset tokens in same PG18.
-- ADDITIVE functions only. No new tables, clusters, users, directories or roles.
-- Not applied automatically; requires explicit operator approval in Termux.
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
   OR current_setting('frfinance.migration_048_approved',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M38993_WRONG_ORIGINAL_DATABASE_OR_NOT_APPROVED'; END IF;
 IF to_regclass('public.frfinance_access_delivery_outbox') IS NULL
   OR to_regclass('public.password_reset_tokens') IS NULL
   OR to_regclass('public.invite_email_verification') IS NULL
   OR to_regclass('public.credentials') IS NULL
   OR to_regclass('public.sessions') IS NULL
   OR to_regprocedure('public.frfinance_ack_access_mail(uuid,boolean)') IS NULL
   OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_auth'
      AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M38993_EXISTING_ACCESS_SCHEMA_INCOMPLETE'; END IF;
 IF to_regprocedure('public.frfinance_redeem_reset_token(character,character varying)') IS NOT NULL
   OR to_regprocedure('public.frfinance_verify_invite_email(character)') IS NOT NULL
 THEN RAISE EXCEPTION 'M38993_ALREADY_INSTALLED_NO_REPLAY'; END IF;
END $guard$;

-- A bearer token is proven only by its SHA256 digest; no raw token stored.
-- SMTP acceptance proves outgoing server submission; actual token redemption
-- proves receipt/ownership. No account or tenant created here.
CREATE FUNCTION public.frfinance_verify_invite_email(
 p_token_hash char(64)
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp
AS $fn$
DECLARE event_id uuid; evidence_id uuid; invite_id uuid; checked_at timestamptz;
BEGIN
 IF session_user<>'frc_ai_auth'
   OR current_database()<>'frcaixinha_aistudio_dev'
   OR p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
 THEN RAISE EXCEPTION 'M38993_INVITE_VERIFICATION_DENIED' USING ERRCODE='42501'; END IF;
 checked_at := clock_timestamp();
 SELECT o.event_id, v.id, i.id
   INTO event_id, evidence_id, invite_id
 FROM public.invite_email_verification v
 JOIN public.invitations i ON i.id=v.invitation_id
 JOIN public.frfinance_access_delivery_outbox o
   ON o.object_id=i.id AND o.kind='INVITE_MEMBER'
 WHERE v.token_hash=p_token_hash
   AND i.token_hash=p_token_hash
   AND v.recipient_email=i.target_email
   AND i.target_role='TENANT_MEMBER'
   AND i.tenant_id IS NOT NULL
   AND i.accepted_at IS NULL AND i.revoked_at IS NULL
   AND i.delivery_status='PENDING_DELIVERY'
   AND v.consumed_at IS NULL AND v.revoked_at IS NULL
   AND v.expires_at>checked_at AND i.expires_at>checked_at
   AND o.state='SMTP_ACCEPTED' AND o.smtp_accepted_at IS NOT NULL
   AND o.expires_at>checked_at
   AND EXISTS(SELECT 1 FROM public.tenants t
              WHERE t.id=i.tenant_id AND t.status='ATIVO')
   AND EXISTS(SELECT 1 FROM public.contract_documents d
              WHERE d.id=i.required_document_id
                AND d.document_kind='TENANT_MEMBERSHIP'
                AND d.published_at IS NOT NULL)
 FOR UPDATE OF v,i;
 IF evidence_id IS NULL THEN RETURN false; END IF;
 UPDATE public.invite_email_verification
 SET consumed_at=checked_at WHERE id=evidence_id
   AND consumed_at IS NULL AND revoked_at IS NULL;
 IF NOT FOUND THEN RETURN false; END IF;
 UPDATE public.invitations
 SET delivery_status='DELIVERED',delivered_at=checked_at
 WHERE id=invite_id AND accepted_at IS NULL
   AND revoked_at IS NULL AND delivery_status='PENDING_DELIVERY';
 IF NOT FOUND THEN
  RAISE EXCEPTION 'M38993_INVITE_ATOMIC_CONSUME_FAILED';
 END IF;
 RETURN true;
END $fn$;

-- A password reset only applies to an active existing user after the
-- one-use token was accepted for SMTP, expires, and is redeemed exactly once.
-- Per-user advisory lock serializes multiple simultaneous reset tokens.
CREATE FUNCTION public.frfinance_redeem_reset_token(
 p_token_hash char(64),p_password_hash varchar(255)
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp
AS $fn$
DECLARE account uuid; token_id uuid; checked_at timestamptz;
DECLARE touched integer;
BEGIN
 IF session_user<>'frc_ai_auth'
   OR current_database()<>'frcaixinha_aistudio_dev'
   OR p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
   OR p_password_hash IS NULL
   OR left(p_password_hash,10)<>'$argon2id$'
   OR length(p_password_hash) NOT BETWEEN 80 AND 255
 THEN RAISE EXCEPTION 'M38993_RESET_DENIED' USING ERRCODE='42501'; END IF;
 checked_at:=clock_timestamp();
 SELECT t.user_id INTO account
 FROM public.password_reset_tokens t
 JOIN public.users u ON u.id=t.user_id AND u.status='ACTIVE'
 WHERE t.token_hash=p_token_hash
   AND t.consumed_at IS NULL AND t.revoked_at IS NULL
   AND t.expires_at>checked_at
 LIMIT 1;
 IF account IS NULL THEN RETURN false; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('FR38993RESET|'||account::text,0));
 checked_at:=clock_timestamp();
 SELECT t.id INTO token_id
 FROM public.password_reset_tokens t
 JOIN public.frfinance_access_delivery_outbox o
  ON o.object_id=t.id AND o.kind='RESET'
 JOIN public.users u ON u.id=t.user_id AND u.status='ACTIVE'
 WHERE t.token_hash=p_token_hash
   AND t.user_id=account
   AND t.consumed_at IS NULL AND t.revoked_at IS NULL
   AND t.expires_at>checked_at
   AND o.state='SMTP_ACCEPTED' AND o.smtp_accepted_at IS NOT NULL
   AND o.expires_at>checked_at
 FOR UPDATE OF t;
 IF token_id IS NULL THEN RETURN false; END IF;

 UPDATE public.credentials
 SET password_hash=p_password_hash, algorithm='argon2id',
     failed_attempts=0,locked_until=NULL,password_changed_at=checked_at
 WHERE user_id=account;
 GET DIAGNOSTICS touched=ROW_COUNT;
 IF touched<>1 THEN RAISE EXCEPTION 'M38993_CREDENTIALS_NOT_UPDATED'; END IF;
 UPDATE public.password_reset_tokens
 SET delivery_status='DELIVERED',consumed_at=checked_at
 WHERE id=token_id AND consumed_at IS NULL AND revoked_at IS NULL;
 GET DIAGNOSTICS touched=ROW_COUNT;
 IF touched<>1 THEN RAISE EXCEPTION 'M38993_TOKEN_NOT_CONSUMED'; END IF;
 UPDATE public.password_reset_tokens
 SET revoked_at=checked_at
 WHERE user_id=account AND id<>token_id
   AND consumed_at IS NULL AND revoked_at IS NULL;
 UPDATE public.sessions
 SET revoked_at=checked_at
 WHERE user_id=account AND revoked_at IS NULL;
 RETURN true;
END $fn$;

REVOKE ALL ON FUNCTION public.frfinance_verify_invite_email(char) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.frfinance_redeem_reset_token(char,varchar) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.frfinance_verify_invite_email(char) TO frc_ai_auth;
GRANT EXECUTE ON FUNCTION public.frfinance_redeem_reset_token(char,varchar) TO frc_ai_auth;
DO $audit$
BEGIN
 IF has_function_privilege('frc_ai_app',
     'public.frfinance_redeem_reset_token(char,varchar)','EXECUTE')
   OR has_function_privilege('frc_ai_app',
     'public.frfinance_verify_invite_email(char)','EXECUTE')
   OR NOT has_function_privilege('frc_ai_auth',
     'public.frfinance_redeem_reset_token(char,varchar)','EXECUTE')
 THEN RAISE EXCEPTION 'M38993_UNSAFE_REDEMPTION_PRIVILEGES'; END IF;
END $audit$;
COMMIT;
