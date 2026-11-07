-- M27100 — EMAIL OWNERSHIP CI CHALLENGE ONLY, no real delivery or activation.
-- Runs solely on disposable GitHub Actions PostgreSQL frcaixinha_staging.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres' OR current_setting('is_superuser')<>'on'
    OR current_setting('frcaixinha.email_proof_staging_ci',true) IS DISTINCT FROM '1'
    OR NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_email_proof_ci'
          AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
          AND NOT rolcreaterole
    )
 THEN RAISE EXCEPTION 'M27100_DENIED: disposable CI role required'; END IF;
END $guard$;

CREATE TABLE public.invite_email_challenges_staging (
 outbox_id uuid PRIMARY KEY REFERENCES public.invite_delivery_outbox_staging(id)
   ON DELETE RESTRICT,
 challenge_digest char(64) NOT NULL CHECK (challenge_digest ~ '^[0-9a-f]{64}$'),
 issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 failed_attempts integer NOT NULL DEFAULT 0 CHECK(failed_attempts BETWEEN 0 AND 3),
 consumed_at timestamptz,
 state varchar(40) NOT NULL DEFAULT 'CI_CHALLENGE_NOT_DELIVERED'
   CHECK (state IN ('CI_CHALLENGE_NOT_DELIVERED','CI_TOKEN_CONSUMED_NOT_PROOF')),
 recipient_verified boolean NOT NULL DEFAULT false
   CHECK(recipient_verified=false),
 user_activated boolean NOT NULL DEFAULT false
   CHECK(user_activated=false),
 contract_accepted boolean NOT NULL DEFAULT false
   CHECK(contract_accepted=false)
);
ALTER TABLE public.invite_email_challenges_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_email_challenges_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.invite_email_challenges_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
   frcaixinha_verifier_role,frcaixinha_invite_queue_ci,
   frcaixinha_email_proof_ci;

CREATE FUNCTION public.invite_issue_ci_email_challenge(
 p_event uuid,p_digest varchar,p_expiry_seconds integer
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 outbox record; existing record; outbox_expiry timestamptz;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_invite_queue_ci'
    OR current_setting('frcaixinha.email_proof_staging_ci',true) IS DISTINCT FROM '1'
    OR p_event IS NULL OR p_digest IS NULL
    OR p_digest !~ '^[0-9a-f]{64}$'
    OR p_expiry_seconds IS NULL
    OR p_expiry_seconds NOT BETWEEN 60 AND 900
 THEN RAISE EXCEPTION 'M27100_DENIED: invalid CI issue request'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('M27100|'||p_event::text,0));
 SELECT o.id, i.expires_at AS invitation_expiry INTO outbox
 FROM public.invite_delivery_outbox_staging o
 JOIN public.invitations i ON i.id=o.invitation_id
 JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ATIVO'
 JOIN public.contract_documents d ON d.id=i.required_document_id
    AND d.published_at IS NOT NULL AND d.document_kind='TENANT_MEMBERSHIP'
 WHERE o.event_id=p_event
   AND o.tenant_id=i.tenant_id
   AND o.document_id=i.required_document_id
   AND o.status='HELD_CI_NOT_SENT'
   AND o.provider_delivery_confirmed=false
   AND o.recipient_verified=false
   AND i.revoked_at IS NULL AND i.accepted_at IS NULL
   AND i.delivery_status='PENDING_DELIVERY'
   AND i.expires_at>clock_timestamp()+make_interval(secs=>p_expiry_seconds)
   AND NOT EXISTS(SELECT 1 FROM public.invite_delivery_terminal_gate_staging g
                  WHERE g.outbox_id=o.id)
 FOR UPDATE OF o;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;

 SELECT * INTO existing FROM public.invite_email_challenges_staging
 WHERE outbox_id=outbox.id FOR UPDATE;
 IF FOUND THEN
   IF existing.challenge_digest=p_digest
      AND existing.consumed_at IS NULL
      AND existing.expires_at>clock_timestamp()
   THEN RETURN 'REPLAY_CI_NOT_DELIVERED'; END IF;
   RETURN 'DENIED';
 END IF;

 INSERT INTO public.invite_email_challenges_staging
  (outbox_id,challenge_digest,expires_at)
 VALUES (outbox.id,p_digest,clock_timestamp()+make_interval(secs=>p_expiry_seconds));
 RETURN 'ISSUED_CI_NOT_DELIVERED';
END $fn$;

CREATE FUNCTION public.invite_consume_ci_email_challenge(
 p_event uuid,p_raw_token varchar
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 row_data record;
 candidate_digest varchar;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_email_proof_ci'
   OR current_setting('frcaixinha.email_proof_staging_ci',true) IS DISTINCT FROM '1'
   OR p_event IS NULL OR p_raw_token IS NULL
   OR p_raw_token !~ '^[A-Za-z0-9_-]{32,256}$'
 THEN RAISE EXCEPTION 'M27100_DENIED: malformed CI challenge'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('M27100|'||p_event::text,0));
 SELECT c.outbox_id,c.challenge_digest,c.expires_at,c.consumed_at,
        c.failed_attempts INTO row_data
 FROM public.invite_email_challenges_staging c
 JOIN public.invite_delivery_outbox_staging o ON o.id=c.outbox_id
 JOIN public.invitations i ON i.id=o.invitation_id
 JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ATIVO'
 WHERE o.event_id=p_event
   AND o.status='HELD_CI_NOT_SENT'
   AND o.provider_delivery_confirmed=false
   AND o.recipient_verified=false
   AND i.revoked_at IS NULL AND i.accepted_at IS NULL
   AND i.expires_at>clock_timestamp()
   AND i.delivery_status='PENDING_DELIVERY'
   AND NOT EXISTS(SELECT 1 FROM public.invite_delivery_terminal_gate_staging g
                  WHERE g.outbox_id=o.id)
 FOR UPDATE OF c;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;

 IF row_data.consumed_at IS NOT NULL
    OR row_data.expires_at<=clock_timestamp()
    OR row_data.failed_attempts>=3 THEN RETURN 'DENIED'; END IF;
 candidate_digest=encode(public.digest(p_raw_token,'sha256'),'hex');
 IF candidate_digest<>row_data.challenge_digest THEN
   UPDATE public.invite_email_challenges_staging
    SET failed_attempts=failed_attempts+1 WHERE outbox_id=row_data.outbox_id;
   RETURN 'DENIED';
 END IF;
 UPDATE public.invite_email_challenges_staging
 SET consumed_at=clock_timestamp(),state='CI_TOKEN_CONSUMED_NOT_PROOF'
 WHERE outbox_id=row_data.outbox_id;
 RETURN 'CI_TOKEN_CONSUMED_NOT_PROOF';
END $fn$;

REVOKE ALL ON FUNCTION public.invite_issue_ci_email_challenge(uuid,varchar,integer)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
  frcaixinha_verifier_role,frcaixinha_invite_queue_ci,frcaixinha_email_proof_ci;
REVOKE ALL ON FUNCTION public.invite_consume_ci_email_challenge(uuid,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
  frcaixinha_verifier_role,frcaixinha_invite_queue_ci,frcaixinha_email_proof_ci;
GRANT EXECUTE ON FUNCTION public.invite_issue_ci_email_challenge(uuid,varchar,integer)
 TO frcaixinha_invite_queue_ci;
GRANT EXECUTE ON FUNCTION public.invite_consume_ci_email_challenge(uuid,varchar)
 TO frcaixinha_email_proof_ci;
COMMIT;
