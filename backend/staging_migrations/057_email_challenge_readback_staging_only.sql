-- M27500: verified challenge readback for a segregated CI-only attestor.
-- Never use on Termux port 5433, OCI staging or production.
-- No token, recipient or secret is persisted or returned by this function.
BEGIN;
DO $guard$
BEGIN
 IF current_database() <> 'frcaixinha_staging'
   OR session_user <> 'postgres'
   OR current_setting('is_superuser') <> 'on'
   OR current_setting('frcaixinha.email_attestation_staging_ci',true) IS DISTINCT FROM '1'
   OR NOT EXISTS(
     SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_email_attestor_ci'
       AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb
   )
 THEN RAISE EXCEPTION 'M27500_DENIED: disposable CI database/role only'; END IF;
END $guard$;

CREATE FUNCTION public.invite_challenge_readback_staging_ci(
 p_event uuid,p_lease uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 result jsonb;
BEGIN
 IF current_database() <> 'frcaixinha_staging'
   OR session_user <> 'frcaixinha_email_attestor_ci'
   OR current_setting('frcaixinha.email_attestation_staging_ci',true) IS DISTINCT FROM '1'
   OR p_event IS NULL OR p_lease IS NULL
   OR p_event='00000000-0000-0000-0000-000000000000'::uuid
   OR p_lease='00000000-0000-0000-0000-000000000000'::uuid
 THEN RAISE EXCEPTION 'M27500_DENIED: CI attestor or event/lease invalid'; END IF;

 SELECT jsonb_build_object(
   'tenant_id',o.tenant_id,
   'event_id',o.event_id,
   'document_id',o.document_id,
   'outbox_id',o.id,
   'challenge_digest',c.challenge_digest,
   'issued_at',floor(extract(epoch FROM c.issued_at))::bigint,
   'expires_at',floor(extract(epoch FROM c.expires_at))::bigint,
   'failed_attempts',c.failed_attempts,
   'consumed',false,
   'challenge_status',c.state,
   'outbox_status',o.status,
   'terminal_quarantine',false
 ) INTO result
 FROM public.invite_email_challenges_staging c
 JOIN public.invite_delivery_outbox_staging o ON o.id=c.outbox_id
 JOIN public.invite_encrypted_envelopes_staging e
    ON e.outbox_id=o.id AND e.event_id=o.event_id
   AND e.tenant_id=o.tenant_id AND e.document_id=o.document_id
   AND e.target_role=o.target_role AND e.purpose='INVITATION'
   AND e.status='SEALED_CI_NOT_SENT'
 JOIN public.invite_dispatch_leases_staging l
    ON l.outbox_id=o.id AND l.lease_id=p_lease
 JOIN public.invitations i ON i.id=o.invitation_id
 JOIN public.tenants t ON t.id=i.tenant_id AND t.status='ATIVO'
 JOIN public.contract_documents d ON d.id=i.required_document_id
   AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL
 WHERE o.event_id=p_event
   AND o.tenant_id=i.tenant_id
   AND o.document_id=i.required_document_id
   AND o.status='HELD_CI_NOT_SENT'
   AND o.provider_delivery_confirmed=false AND o.recipient_verified=false
   AND i.revoked_at IS NULL AND i.accepted_at IS NULL
   AND i.delivery_status='PENDING_DELIVERY'
   AND i.expires_at>clock_timestamp()
   AND e.expires_at>extract(epoch from clock_timestamp())::bigint
   AND l.lease_expires_at>clock_timestamp()
   AND c.consumed_at IS NULL
   AND c.failed_attempts=0
   AND c.state='CI_CHALLENGE_NOT_DELIVERED'
   AND c.issued_at<=clock_timestamp()
   AND c.expires_at>clock_timestamp()
   AND c.expires_at<=i.expires_at
   AND c.expires_at<=to_timestamp(e.expires_at)
   AND NOT EXISTS(
     SELECT 1 FROM public.invite_delivery_terminal_gate_staging g
     WHERE g.outbox_id=o.id
   );
 RETURN result;
END $fn$;

REVOKE ALL ON FUNCTION public.invite_challenge_readback_staging_ci(uuid,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
    frcaixinha_verifier_role,frcaixinha_invite_queue_ci,
    frcaixinha_email_proof_ci,frcaixinha_invite_dispatch_ci,
    frcaixinha_envelope_producer_ci,frcaixinha_email_attestor_ci;
GRANT EXECUTE ON FUNCTION public.invite_challenge_readback_staging_ci(uuid,uuid)
 TO frcaixinha_email_attestor_ci;
COMMIT;
