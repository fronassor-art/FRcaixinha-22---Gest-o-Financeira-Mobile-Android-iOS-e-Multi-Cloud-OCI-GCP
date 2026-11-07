-- M25900 AI Studio — INVITE OUTBOX. Disposable STAGING CI exclusively.
-- Never apply to Termux 5433 / OCI / production, and never send real email.
-- No plaintext token, password, CPF, email, provider credential or payload stored.
BEGIN;
DO $check$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.invite_queue_staging_ci',true) IS DISTINCT FROM '1'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS (
      SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_invite_queue_ci'
       AND NOT rolsuper AND NOT rolbypassrls
       AND NOT rolcreatedb AND NOT rolcreaterole
    )
 THEN RAISE EXCEPTION 'M25900_DENIED: isolated disposable staging database required';
 END IF;
END $check$;

CREATE TABLE public.invite_delivery_outbox_staging (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 invitation_id uuid NOT NULL UNIQUE REFERENCES public.invitations(id) ON DELETE RESTRICT,
 event_id uuid NOT NULL UNIQUE,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 target_role varchar(30) NOT NULL CHECK(target_role IN('TENANT_ADMIN','TENANT_MEMBER')),
 recipient_digest char(64) NOT NULL CHECK(recipient_digest ~ '^[0-9a-f]{64}$'),
 document_id uuid NOT NULL REFERENCES public.contract_documents(id) ON DELETE RESTRICT,
 sealed_payload_ref varchar(180) NOT NULL
    CHECK(sealed_payload_ref ~ '^ci://[A-Za-z0-9._/-]{10,150}$'),
 status varchar(30) NOT NULL DEFAULT 'HELD_CI_NOT_SENT'
    CHECK(status='HELD_CI_NOT_SENT'),
 provider_delivery_confirmed boolean NOT NULL DEFAULT false
    CHECK(provider_delivery_confirmed=false),
 recipient_verified boolean NOT NULL DEFAULT false
    CHECK(recipient_verified=false),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(event_id<>'00000000-0000-0000-0000-000000000000'::uuid)
);

CREATE TABLE public.invite_delivery_audit_staging (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 outbox_id uuid NOT NULL UNIQUE REFERENCES public.invite_delivery_outbox_staging(id) ON DELETE RESTRICT,
 invitation_id uuid NOT NULL REFERENCES public.invitations(id) ON DELETE RESTRICT,
 event_id uuid NOT NULL UNIQUE,
 action varchar(42) NOT NULL CHECK(action='CI_INVITE_HELD_NO_DELIVERY'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.invite_delivery_outbox_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_delivery_outbox_staging FORCE ROW LEVEL SECURITY;
ALTER TABLE public.invite_delivery_audit_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_delivery_audit_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.invite_delivery_outbox_staging,public.invite_delivery_audit_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_invite_queue_ci;

-- No table policy: roles cannot read or mutate rows. Narrow entrypoint below
-- executes under function owner, only for the dedicated CI staging identity.
CREATE FUNCTION public.invite_enqueue_held_staging_ci(
 p_invitation uuid,p_event uuid,p_digest varchar,p_sealed_ref varchar
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 inv record;
 existing record;
 staged uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_invite_queue_ci'
   OR current_setting('frcaixinha.invite_queue_staging_ci',true) IS DISTINCT FROM '1'
   OR p_invitation IS NULL OR p_event IS NULL
   OR p_event='00000000-0000-0000-0000-000000000000'::uuid
   OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
   OR p_sealed_ref IS NULL
   OR p_sealed_ref !~ '^ci://[A-Za-z0-9._/-]{10,150}$'
 THEN RAISE EXCEPTION 'M25900_DENIED: caller or payload invalid'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('M25900|'||p_invitation::text,0));
 SELECT i.id,i.tenant_id,i.inviter_user_id,i.target_role,
        i.required_document_id,i.target_email
 INTO inv
 FROM public.invitations i
 JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ATIVO'
 JOIN public.users u ON u.id=i.inviter_user_id AND u.status='ACTIVE'
 JOIN public.contract_documents d ON d.id=i.required_document_id
     AND d.document_kind='TENANT_MEMBERSHIP'
     AND d.published_at IS NOT NULL
 WHERE i.id=p_invitation AND i.expires_at>now()
   AND i.revoked_at IS NULL AND i.accepted_at IS NULL
   AND i.delivery_status='PENDING_DELIVERY'
   AND (
     (i.target_role='TENANT_ADMIN' AND u.is_master)
     OR
     (i.target_role='TENANT_MEMBER' AND EXISTS(
        SELECT 1 FROM public.memberships m
        WHERE m.tenant_id=i.tenant_id AND m.user_id=i.inviter_user_id
          AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
     ))
   )
 FOR UPDATE OF i;
 IF NOT FOUND THEN RAISE EXCEPTION 'M25900_DENIED: invitation not eligible'; END IF;

 IF p_digest IS DISTINCT FROM encode(
   public.digest(lower(trim(inv.target_email)),'sha256'),'hex'
 ) THEN RAISE EXCEPTION 'M25900_DENIED: recipient binding invalid'; END IF;

 -- UNIQUE invitation_id and event_id plus row lock protect concurrency.
 SELECT id,invitation_id,event_id,recipient_digest,sealed_payload_ref
 INTO existing FROM public.invite_delivery_outbox_staging
 WHERE invitation_id=p_invitation OR event_id=p_event FOR UPDATE;
 IF FOUND THEN
   IF existing.invitation_id<>p_invitation
      OR existing.event_id<>p_event OR existing.recipient_digest<>p_digest
      OR existing.sealed_payload_ref<>p_sealed_ref
   THEN RAISE EXCEPTION 'M25900_DENIED: conflicting replay'; END IF;
   RETURN 'REPLAY:'||existing.id::text;
 END IF;

 INSERT INTO public.invite_delivery_outbox_staging
   (invitation_id,event_id,tenant_id,target_role,recipient_digest,
    document_id,sealed_payload_ref)
 VALUES
   (inv.id,p_event,inv.tenant_id,inv.target_role,p_digest,
    inv.required_document_id,p_sealed_ref)
 RETURNING id INTO staged;

 INSERT INTO public.invite_delivery_audit_staging
   (outbox_id,invitation_id,event_id,action)
 VALUES(staged,inv.id,p_event,'CI_INVITE_HELD_NO_DELIVERY');

 RETURN 'NEW:'||staged::text;
END $fn$;

REVOKE ALL ON FUNCTION public.invite_enqueue_held_staging_ci(
 uuid,uuid,varchar,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_verifier_role,frcaixinha_invite_queue_ci;
GRANT EXECUTE ON FUNCTION public.invite_enqueue_held_staging_ci(
 uuid,uuid,varchar,varchar) TO frcaixinha_invite_queue_ci;
COMMIT;
