-- M26300 FR Finance AI Studio - provider-neutral receipt audit, CI ONLY.
-- Fake signed provider events may be recorded, but no real mail, acceptance,
-- delivery, recipient verification, consent, invitation or user activation.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres' OR current_setting('is_superuser')<>'on'
    OR current_setting('frcaixinha.mail_receipt_staging_ci',true) IS DISTINCT FROM '1'
    OR NOT EXISTS (
      SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_mail_receipt_ci'
       AND NOT rolsuper AND NOT rolbypassrls
       AND NOT rolcreatedb AND NOT rolcreaterole
    )
 THEN RAISE EXCEPTION 'M26300_DENIED: disposable staging only'; END IF;
END $guard$;

CREATE TABLE public.invite_provider_receipts_staging (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 receipt_event_id uuid NOT NULL UNIQUE,
 outbox_id uuid NOT NULL REFERENCES public.invite_delivery_outbox_staging(id)
   ON DELETE RESTRICT,
 lease_id uuid NOT NULL REFERENCES public.invite_dispatch_attempt_audit_staging(lease_id)
   ON DELETE RESTRICT,
 kind varchar(36) NOT NULL CHECK(kind IN('CI_SMTP_ACCEPTED','CI_BOUNCE')),
 body_sha256 char(64) NOT NULL CHECK(body_sha256 ~ '^[0-9a-f]{64}$'),
 state varchar(40) NOT NULL DEFAULT 'CI_RECEIPT_ONLY_NO_DELIVERY'
   CHECK(state='CI_RECEIPT_ONLY_NO_DELIVERY'),
 provider_delivery_confirmed boolean NOT NULL DEFAULT false
   CHECK(provider_delivery_confirmed=false),
 recipient_verified boolean NOT NULL DEFAULT false
   CHECK(recipient_verified=false),
 acceptance_recorded boolean NOT NULL DEFAULT false
   CHECK(acceptance_recorded=false),
 account_activated boolean NOT NULL DEFAULT false
   CHECK(account_activated=false),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(lease_id,kind)
);
ALTER TABLE public.invite_provider_receipts_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_provider_receipts_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.invite_provider_receipts_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_mail_receipt_ci;

CREATE FUNCTION public.invite_record_mock_receipt_staging_ci(
 p_outbox_event uuid,p_lease uuid,p_receipt_event uuid,
 p_kind varchar,p_body_digest varchar
) RETURNS varchar LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 source_row record;
 existing record;
 receipt_id uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_mail_receipt_ci'
   OR current_setting('frcaixinha.mail_receipt_staging_ci',true) IS DISTINCT FROM '1'
   OR p_outbox_event IS NULL OR p_lease IS NULL OR p_receipt_event IS NULL
   OR p_receipt_event='00000000-0000-0000-0000-000000000000'::uuid
   OR p_kind IS NULL OR p_kind NOT IN ('CI_SMTP_ACCEPTED','CI_BOUNCE')
   OR p_body_digest IS NULL OR p_body_digest !~ '^[0-9a-f]{64}$'
 THEN RAISE EXCEPTION 'M26300_DENIED: CI receipt worker or fields invalid'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('M26300|'||p_receipt_event::text,0));
 SELECT o.id INTO source_row
 FROM public.invite_delivery_outbox_staging o
 JOIN public.invite_dispatch_attempt_audit_staging a
   ON a.outbox_id=o.id AND a.lease_id=p_lease
 WHERE o.event_id=p_outbox_event
   AND o.status='HELD_CI_NOT_SENT'
   AND o.provider_delivery_confirmed=false
   AND o.recipient_verified=false;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;

 SELECT id,outbox_id,lease_id,kind,body_sha256
 INTO existing FROM public.invite_provider_receipts_staging
 WHERE receipt_event_id=p_receipt_event FOR UPDATE;
 IF FOUND THEN
   IF existing.outbox_id<>source_row.id OR existing.lease_id<>p_lease
      OR existing.kind<>p_kind OR existing.body_sha256<>p_body_digest
   THEN RAISE EXCEPTION 'M26300_DENIED: conflicting signed event replay'; END IF;
   RETURN 'REPLAY:'||existing.id::text;
 END IF;

 INSERT INTO public.invite_provider_receipts_staging
 (receipt_event_id,outbox_id,lease_id,kind,body_sha256)
 VALUES(p_receipt_event,source_row.id,p_lease,p_kind,p_body_digest)
 RETURNING id INTO receipt_id;
 RETURN 'RECORDED:'||receipt_id::text;
END $fn$;

REVOKE ALL ON FUNCTION public.invite_record_mock_receipt_staging_ci(
 uuid,uuid,uuid,varchar,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_mail_receipt_ci;
GRANT EXECUTE ON FUNCTION public.invite_record_mock_receipt_staging_ci(
 uuid,uuid,uuid,varchar,varchar) TO frcaixinha_mail_receipt_ci;
COMMIT;
