-- M26600 FR Finance AI Studio: terminal SMTP ambiguity/ACK suppression, CI ONLY.
-- Disposable frcaixinha_staging. No outgoing email, no real provider or user.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on'
    OR current_setting('frcaixinha.delivery_gate_staging_ci',true) IS DISTINCT FROM '1'
    OR NOT EXISTS (
      SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_invite_dispatch_ci'
       AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
    )
 THEN RAISE EXCEPTION 'M26600_DENIED: isolated disposable staging only'; END IF;
END $guard$;

CREATE TABLE public.invite_delivery_terminal_gate_staging (
 outbox_id uuid PRIMARY KEY REFERENCES public.invite_delivery_outbox_staging(id)
  ON DELETE RESTRICT,
 lease_id uuid NOT NULL REFERENCES public.invite_dispatch_attempt_audit_staging(lease_id)
  ON DELETE RESTRICT,
 state varchar(42) NOT NULL CHECK(state IN(
    'CI_UNKNOWN_TIMEOUT_QUARANTINE',
    'CI_SMTP_ACCEPTED_UNVERIFIED',
    'CI_BOUNCED_REQUIRES_REVIEW'
 )),
 provider_delivery_confirmed boolean NOT NULL DEFAULT false
   CHECK(provider_delivery_confirmed=false),
 recipient_verified boolean NOT NULL DEFAULT false
   CHECK(recipient_verified=false),
 consent_recorded boolean NOT NULL DEFAULT false
   CHECK(consent_recorded=false),
 user_activated boolean NOT NULL DEFAULT false
   CHECK(user_activated=false),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.invite_delivery_terminal_gate_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_delivery_terminal_gate_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.invite_delivery_terminal_gate_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_invite_dispatch_ci;

-- Old function must not bypass the new terminal quarantine.
REVOKE EXECUTE ON FUNCTION public.invite_dispatch_lease_staging_ci(uuid,uuid)
 FROM PUBLIC,frcaixinha_invite_dispatch_ci;

CREATE FUNCTION public.invite_dispatch_guarded_staging_ci(
 p_event uuid,p_lease uuid
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE q record;
BEGIN
 IF current_database()<>'frcaixinha_staging'
  OR session_user<>'frcaixinha_invite_dispatch_ci'
  OR current_setting('frcaixinha.delivery_gate_staging_ci',true) IS DISTINCT FROM '1'
  OR p_event IS NULL OR p_lease IS NULL
 THEN RAISE EXCEPTION 'M26600_DENIED: restricted CI worker only'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('M26100|'||p_event::text,0));
 SELECT o.id INTO q
 FROM public.invite_delivery_outbox_staging o
 WHERE o.event_id=p_event;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;
 IF EXISTS(SELECT 1 FROM public.invite_delivery_terminal_gate_staging g
           WHERE g.outbox_id=q.id)
 THEN RETURN 'QUARANTINED'; END IF;
 -- The guarded entrypoint supersedes the old staging flag; only it may
 -- re-open the inner CI-only dispatcher after the terminal check.
 PERFORM set_config('frcaixinha.invite_dispatch_staging_ci','1',true);
 RETURN public.invite_dispatch_lease_staging_ci(p_event,p_lease);
END $fn$;

CREATE FUNCTION public.invite_dispatch_mark_terminal_staging_ci(
 p_event uuid,p_lease uuid,p_result varchar
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE q record;
 prior record;
 outcome varchar;
BEGIN
 IF current_database()<>'frcaixinha_staging'
  OR session_user<>'frcaixinha_invite_dispatch_ci'
  OR current_setting('frcaixinha.delivery_gate_staging_ci',true) IS DISTINCT FROM '1'
  OR p_event IS NULL OR p_lease IS NULL
  OR p_result IS NULL OR p_result NOT IN(
    'UNKNOWN_TIMEOUT','CI_SMTP_ACCEPTED','CI_BOUNCE'
  )
 THEN RAISE EXCEPTION 'M26600_DENIED: worker or result invalid'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('M26100|'||p_event::text,0));
 SELECT o.id INTO q FROM public.invite_delivery_outbox_staging o
 JOIN public.invite_dispatch_attempt_audit_staging a
 ON a.outbox_id=o.id AND a.lease_id=p_lease
 WHERE o.event_id=p_event
 AND o.status='HELD_CI_NOT_SENT'
 AND o.provider_delivery_confirmed=false
 AND o.recipient_verified=false
 FOR UPDATE OF o;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;

 IF p_result IN('CI_SMTP_ACCEPTED','CI_BOUNCE') AND NOT EXISTS(
  SELECT 1 FROM public.invite_provider_receipts_staging r
  WHERE r.outbox_id=q.id AND r.lease_id=p_lease AND r.kind=p_result
 )
 THEN RETURN 'DENIED'; END IF;

 outcome:=CASE p_result
  WHEN 'UNKNOWN_TIMEOUT' THEN 'CI_UNKNOWN_TIMEOUT_QUARANTINE'
  WHEN 'CI_SMTP_ACCEPTED' THEN 'CI_SMTP_ACCEPTED_UNVERIFIED'
  ELSE 'CI_BOUNCED_REQUIRES_REVIEW' END;

 SELECT state,lease_id INTO prior FROM public.invite_delivery_terminal_gate_staging
 WHERE outbox_id=q.id FOR UPDATE;
 IF FOUND THEN
   IF prior.state=outcome AND prior.lease_id=p_lease THEN RETURN 'REPLAY'; END IF;
   RAISE EXCEPTION 'M26600_DENIED: conflicting terminal result';
 END IF;

 INSERT INTO public.invite_delivery_terminal_gate_staging(outbox_id,lease_id,state)
 VALUES(q.id,p_lease,outcome);
 RETURN 'QUARANTINED';
END $fn$;

REVOKE ALL ON FUNCTION public.invite_dispatch_guarded_staging_ci(uuid,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_invite_dispatch_ci;
REVOKE ALL ON FUNCTION public.invite_dispatch_mark_terminal_staging_ci(uuid,uuid,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_invite_dispatch_ci;
GRANT EXECUTE ON FUNCTION public.invite_dispatch_guarded_staging_ci(uuid,uuid)
 TO frcaixinha_invite_dispatch_ci;
GRANT EXECUTE ON FUNCTION public.invite_dispatch_mark_terminal_staging_ci(uuid,uuid,varchar)
 TO frcaixinha_invite_dispatch_ci;
COMMIT;
