-- M25900 synthetic-only invitation data for disposable frcaixinha_staging.
DO $only_ci$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.invite_queue_staging_ci',true) IS DISTINCT FROM '1'
    OR session_user<>'postgres' OR current_setting('is_superuser')<>'on'
 THEN RAISE EXCEPTION 'M25900 fixture requires disposable staging'; END IF;
END $only_ci$;

INSERT INTO public.users
 (id,email,full_name,cpf,phone,status,is_master)
VALUES
 ('eeeeeeee-0000-4000-8000-000000000011','master-m25900@example.com',
  'Master synthetic M25900','52998224725','11999999999','ACTIVE',true);

INSERT INTO public.tenants
 (id,display_name,contracting_party_id,admin_user_id,status)
VALUES
 ('eeeeeeee-0000-4000-8000-000000000012',
  'Tenant synthetic M25900','ci-m25900-invitation-tenant',
  'eeeeeeee-0000-4000-8000-000000000011','ATIVO');

INSERT INTO public.contract_documents
 (id,document_kind,version_label,sha256,source_reference,published_at)
VALUES
 ('eeeeeeee-0000-4000-8000-000000000013','TENANT_MEMBERSHIP',
  'ci-m25900-only-v1',repeat('a',64),'ci://m25900-approved-synthetic-term',now());

INSERT INTO public.invitations
 (id,tenant_id,inviter_user_id,target_email,target_role,token_hash,
  expires_at,required_document_id,delivery_status)
VALUES
 ('eeeeeeee-0000-4000-8000-000000000014',
  'eeeeeeee-0000-4000-8000-000000000012',
  'eeeeeeee-0000-4000-8000-000000000011',
  'future-admin-m25900@example.com','TENANT_ADMIN',
  repeat('b',64),now()+interval '12 hours',
  'eeeeeeee-0000-4000-8000-000000000013','PENDING_DELIVERY');
