-- M26100 / FR Finance AI Studio: CI-only simulated dispatch claim, NO EMAIL.
-- Disposable GitHub Actions frcaixinha_staging, NEVER OCI or Termux 5433.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on'
    OR current_setting('frcaixinha.invite_dispatch_staging_ci',true) IS DISTINCT FROM '1'
    OR NOT EXISTS (SELECT 1 FROM pg_roles
                   WHERE rolname='frcaixinha_invite_dispatch_ci'
                     AND NOT rolsuper AND NOT rolbypassrls
                     AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M26100_DENIED: disposable CI staging operator required';
 END IF;
END $guard$;

CREATE TABLE public.invite_dispatch_leases_staging (
 outbox_id uuid PRIMARY KEY REFERENCES public.invite_delivery_outbox_staging(id)
  ON DELETE RESTRICT,
 lease_id uuid NOT NULL UNIQUE,
 lease_expires_at timestamptz NOT NULL,
 attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 3),
 status varchar(30) NOT NULL DEFAULT 'HELD_CI_NO_NETWORK'
   CHECK (status='HELD_CI_NO_NETWORK'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE public.invite_dispatch_attempt_audit_staging (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 outbox_id uuid NOT NULL REFERENCES public.invite_delivery_outbox_staging(id)
  ON DELETE RESTRICT,
 attempt_number integer NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
 lease_id uuid NOT NULL UNIQUE,
 action varchar(40) NOT NULL DEFAULT 'CI_DISPATCH_HELD_WITHOUT_NETWORK'
   CHECK(action='CI_DISPATCH_HELD_WITHOUT_NETWORK'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(outbox_id,attempt_number)
);
ALTER TABLE public.invite_dispatch_leases_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_dispatch_leases_staging FORCE ROW LEVEL SECURITY;
ALTER TABLE public.invite_dispatch_attempt_audit_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_dispatch_attempt_audit_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.invite_dispatch_leases_staging,
              public.invite_dispatch_attempt_audit_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_invite_dispatch_ci;

CREATE FUNCTION public.invite_dispatch_lease_staging_ci(
 p_event uuid,p_lease uuid
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 queue_row record;
 existing record;
 next_attempt integer;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_invite_dispatch_ci'
   OR current_setting('frcaixinha.invite_dispatch_staging_ci',true) IS DISTINCT FROM '1'
   OR p_event IS NULL OR p_event='00000000-0000-0000-0000-000000000000'::uuid
   OR p_lease IS NULL OR p_lease='00000000-0000-0000-0000-000000000000'::uuid
 THEN RAISE EXCEPTION 'M26100_DENIED: CI worker or input invalid'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('M26100|'||p_event::text,0));
 SELECT o.id,o.invitation_id INTO queue_row
 FROM public.invite_delivery_outbox_staging o
 JOIN public.invitations i ON i.id=o.invitation_id
 JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ATIVO'
 JOIN public.contract_documents d ON d.id=i.required_document_id
   AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL
 JOIN public.users u ON u.id=i.inviter_user_id AND u.status='ACTIVE'
 WHERE o.event_id=p_event AND o.status='HELD_CI_NOT_SENT'
   AND o.provider_delivery_confirmed=false
   AND o.recipient_verified=false
   AND o.tenant_id=i.tenant_id AND o.target_role=i.target_role
   AND o.document_id=i.required_document_id
   AND i.accepted_at IS NULL AND i.revoked_at IS NULL
   AND i.expires_at>clock_timestamp()
   AND i.delivery_status='PENDING_DELIVERY'
   AND (
      (i.target_role='TENANT_ADMIN' AND u.is_master)
      OR (i.target_role='TENANT_MEMBER' AND EXISTS(
       SELECT 1 FROM public.memberships m
        WHERE m.tenant_id=i.tenant_id AND m.user_id=i.inviter_user_id
         AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
      ))
   )
 FOR UPDATE OF o;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;

 SELECT outbox_id,lease_id,lease_expires_at,attempts
  INTO existing FROM public.invite_dispatch_leases_staging
  WHERE outbox_id=queue_row.id FOR UPDATE;

 IF FOUND THEN
   IF existing.lease_expires_at>clock_timestamp() THEN
     IF existing.lease_id=p_lease THEN
       RETURN 'REPLAY:'||existing.attempts::text;
     END IF;
     RETURN 'DENIED';
   END IF;
   IF existing.attempts>=3 THEN RETURN 'EXHAUSTED'; END IF;
   IF existing.lease_id=p_lease THEN RETURN 'DENIED'; END IF;
   next_attempt:=existing.attempts+1;
   UPDATE public.invite_dispatch_leases_staging
    SET lease_id=p_lease,lease_expires_at=clock_timestamp()+interval '45 seconds',
        attempts=next_attempt
    WHERE outbox_id=queue_row.id;
 ELSE
   next_attempt:=1;
   INSERT INTO public.invite_dispatch_leases_staging
     (outbox_id,lease_id,lease_expires_at,attempts)
   VALUES(queue_row.id,p_lease,clock_timestamp()+interval '45 seconds',1);
 END IF;

 INSERT INTO public.invite_dispatch_attempt_audit_staging
  (outbox_id,attempt_number,lease_id)
 VALUES(queue_row.id,next_attempt,p_lease);
 RETURN 'HELD:'||next_attempt::text;
END $fn$;

REVOKE ALL ON FUNCTION public.invite_dispatch_lease_staging_ci(uuid,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_invite_dispatch_ci;
GRANT EXECUTE ON FUNCTION public.invite_dispatch_lease_staging_ci(uuid,uuid)
 TO frcaixinha_invite_dispatch_ci;
COMMIT;
