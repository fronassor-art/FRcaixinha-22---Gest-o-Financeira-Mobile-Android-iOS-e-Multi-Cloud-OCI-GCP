-- M26700 / FR Finance AI Studio: store only AES-GCM ciphertext in CI.
-- Disposable frcaixinha_staging on GitHub Actions, NEVER Termux/OCI.
BEGIN;
DO $gate$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres' OR current_setting('is_superuser')<>'on'
    OR current_setting('frcaixinha.envelope_staging_ci',true) IS DISTINCT FROM '1'
    OR NOT EXISTS (
      SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_envelope_producer_ci'
        AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
    )
 THEN RAISE EXCEPTION 'M26700_DENIED: isolated disposable CI required'; END IF;
END $gate$;

CREATE TABLE public.invite_encrypted_envelopes_staging (
 outbox_id uuid PRIMARY KEY REFERENCES public.invite_delivery_outbox_staging(id)
  ON DELETE RESTRICT,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 event_id uuid NOT NULL UNIQUE,
 document_id uuid NOT NULL REFERENCES public.contract_documents(id) ON DELETE RESTRICT,
 target_role varchar(30) NOT NULL CHECK(target_role IN ('TENANT_ADMIN','TENANT_MEMBER')),
 purpose varchar(20) NOT NULL DEFAULT 'INVITATION'
  CHECK(purpose='INVITATION'),
 key_id varchar(80) NOT NULL CHECK(key_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{3,79}$'),
 nonce_b64 varchar(16) NOT NULL UNIQUE
  CHECK(nonce_b64 ~ '^[A-Za-z0-9_-]{16}$'),
 ciphertext_b64 varchar(3000) NOT NULL
  CHECK(length(ciphertext_b64) BETWEEN 24 AND 3000
    AND ciphertext_b64 ~ '^[A-Za-z0-9_-]+={0,2}$'),
 ciphertext_digest char(64) NOT NULL
  CHECK(ciphertext_digest ~ '^[0-9a-f]{64}$'),
 issued_at bigint NOT NULL,
 expires_at bigint NOT NULL CHECK(expires_at>issued_at
  AND expires_at-issued_at<=86400),
 status varchar(32) NOT NULL DEFAULT 'SEALED_CI_NOT_SENT'
  CHECK(status='SEALED_CI_NOT_SENT'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.invite_encrypted_envelopes_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_encrypted_envelopes_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.invite_encrypted_envelopes_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role,
      frcaixinha_invite_queue_ci,frcaixinha_envelope_producer_ci,
      frcaixinha_invite_dispatch_ci;

CREATE FUNCTION public.invite_store_encrypted_envelope_staging_ci(
 p_event uuid,p_tenant uuid,p_document uuid,p_role varchar,
 p_key_id varchar,p_nonce varchar,p_cipher varchar,
 p_issued bigint,p_expires bigint
) RETURNS varchar LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 parent_row record;
 existing record;
 stored uuid;
 digest_value varchar;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_envelope_producer_ci'
   OR current_setting('frcaixinha.envelope_staging_ci',true) IS DISTINCT FROM '1'
   OR p_event IS NULL OR p_tenant IS NULL OR p_document IS NULL
   OR p_role IS NULL OR p_role NOT IN('TENANT_ADMIN','TENANT_MEMBER')
   OR p_key_id IS NULL OR p_key_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{3,79}$'
   OR p_nonce IS NULL OR p_nonce !~ '^[A-Za-z0-9_-]{16}$'
   OR p_cipher IS NULL OR length(p_cipher) NOT BETWEEN 24 AND 3000
   OR p_cipher !~ '^[A-Za-z0-9_-]+={0,2}$'
   OR p_issued IS NULL OR p_expires IS NULL OR p_expires<=p_issued
   OR p_expires-p_issued>86400
   OR p_issued NOT BETWEEN extract(epoch from clock_timestamp())::bigint-30
                    AND extract(epoch from clock_timestamp())::bigint+30
 THEN RAISE EXCEPTION 'M26700_DENIED: producer or envelope fields invalid'; END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended('M26700|'||p_event::text,0));
 SELECT o.id,o.event_id,o.tenant_id,o.document_id,o.target_role,
        i.expires_at AS invitation_expires_at
 INTO parent_row FROM public.invite_delivery_outbox_staging o
 JOIN public.invitations i ON i.id=o.invitation_id
 JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ATIVO'
 JOIN public.contract_documents d ON d.id=i.required_document_id
     AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL
 WHERE o.event_id=p_event
   AND o.tenant_id=p_tenant AND o.document_id=p_document
   AND o.target_role=p_role AND o.status='HELD_CI_NOT_SENT'
   AND o.provider_delivery_confirmed=false AND o.recipient_verified=false
   AND i.revoked_at IS NULL AND i.accepted_at IS NULL
   AND i.expires_at>clock_timestamp()
   AND i.delivery_status='PENDING_DELIVERY'
 FOR UPDATE OF o;
 IF NOT FOUND THEN RETURN 'DENIED'; END IF;

 IF to_timestamp(p_expires)>parent_row.invitation_expires_at
    OR p_expires<=extract(epoch from clock_timestamp())::bigint
 THEN RETURN 'DENIED'; END IF;
 IF EXISTS(SELECT 1 FROM public.invite_delivery_terminal_gate_staging g
   WHERE g.outbox_id=parent_row.id)
 THEN RETURN 'QUARANTINED'; END IF;

 digest_value:=encode(public.digest(p_cipher,'sha256'),'hex');
 SELECT * INTO existing FROM public.invite_encrypted_envelopes_staging
 WHERE outbox_id=parent_row.id FOR UPDATE;
 IF FOUND THEN
   IF existing.event_id=p_event AND existing.tenant_id=p_tenant
      AND existing.document_id=p_document AND existing.target_role=p_role
      AND existing.key_id=p_key_id AND existing.nonce_b64=p_nonce
      AND existing.ciphertext_b64=p_cipher
      AND existing.ciphertext_digest=digest_value
      AND existing.issued_at=p_issued AND existing.expires_at=p_expires
   THEN RETURN 'REPLAY:'||existing.outbox_id::text; END IF;
   RAISE EXCEPTION 'M26700_DENIED: conflicting sealed envelope';
 END IF;
 INSERT INTO public.invite_encrypted_envelopes_staging
   (outbox_id,tenant_id,event_id,document_id,target_role,
    key_id,nonce_b64,ciphertext_b64,ciphertext_digest,issued_at,expires_at)
 VALUES(parent_row.id,p_tenant,p_event,p_document,p_role,p_key_id,
        p_nonce,p_cipher,digest_value,p_issued,p_expires)
 RETURNING outbox_id INTO stored;
 RETURN 'SEALED:'||stored::text;
END $fn$;

CREATE FUNCTION public.invite_read_encrypted_envelope_staging_ci(
 p_event uuid,p_lease uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 result jsonb;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_invite_dispatch_ci'
   OR current_setting('frcaixinha.envelope_staging_ci',true) IS DISTINCT FROM '1'
   OR p_event IS NULL OR p_lease IS NULL
 THEN RAISE EXCEPTION 'M26700_DENIED: delivery worker invalid'; END IF;
 SELECT jsonb_build_object(
  'tenant_id',e.tenant_id,'event_id',e.event_id,'document_id',e.document_id,
  'target_role',e.target_role,'purpose',e.purpose,
  'key_id',e.key_id,'nonce_b64',e.nonce_b64,
  'ciphertext_b64',e.ciphertext_b64,'issued_at',e.issued_at,
  'expires_at',e.expires_at
 ) INTO result
 FROM public.invite_encrypted_envelopes_staging e
 JOIN public.invite_delivery_outbox_staging o
  ON o.id=e.outbox_id AND o.event_id=p_event
 JOIN public.invite_dispatch_leases_staging l
  ON l.outbox_id=o.id AND l.lease_id=p_lease
 JOIN public.invitations i ON i.id=o.invitation_id
 JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ATIVO'
 JOIN public.contract_documents d ON d.id=i.required_document_id
  AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL
 WHERE l.lease_expires_at>clock_timestamp()
  AND e.expires_at>extract(epoch from clock_timestamp())::bigint
  AND e.status='SEALED_CI_NOT_SENT'
  AND o.status='HELD_CI_NOT_SENT'
  AND o.provider_delivery_confirmed=false AND o.recipient_verified=false
  AND i.expires_at>clock_timestamp()
  AND i.revoked_at IS NULL AND i.accepted_at IS NULL
  AND i.delivery_status='PENDING_DELIVERY'
  AND NOT EXISTS(
   SELECT 1 FROM public.invite_delivery_terminal_gate_staging g
   WHERE g.outbox_id=o.id
  );
 RETURN result;
END $fn$;

REVOKE ALL ON FUNCTION public.invite_store_encrypted_envelope_staging_ci(
 uuid,uuid,uuid,varchar,varchar,varchar,varchar,bigint,bigint)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role,
      frcaixinha_envelope_producer_ci,frcaixinha_invite_dispatch_ci;
REVOKE ALL ON FUNCTION public.invite_read_encrypted_envelope_staging_ci(uuid,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role,
      frcaixinha_envelope_producer_ci,frcaixinha_invite_dispatch_ci;
GRANT EXECUTE ON FUNCTION public.invite_store_encrypted_envelope_staging_ci(
 uuid,uuid,uuid,varchar,varchar,varchar,varchar,bigint,bigint)
 TO frcaixinha_envelope_producer_ci;
GRANT EXECUTE ON FUNCTION public.invite_read_encrypted_envelope_staging_ci(uuid,uuid)
 TO frcaixinha_invite_dispatch_ci;
COMMIT;
