-- M30900 synthetic SaaS owner and contract in disposable GitHub Actions only.
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('frcaixinha.saas_enroll_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M30900_SYNTHETIC_FIXTURE_DENIED'; END IF;
END $guard$;
INSERT INTO public.users(id,email,full_name,cpf,phone) VALUES
 ('daba0000-0000-4000-8000-000000000001','m30900-admin-a@example.invalid','CI SaaS Admin A','99993090001','00000000000'),
 ('daba0000-0000-4000-8000-000000000002','m30900-admin-b@example.invalid','CI SaaS Admin B','99993090002','00000000000');
INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status)
 VALUES
 ('daba0000-0000-4000-8000-000000000010','CI SaaS box A','CI-SAAS-M30900-A','daba0000-0000-4000-8000-000000000001','ATIVO'),
 ('daba0000-0000-4000-8000-000000000020','CI SaaS box B','CI-SAAS-M30900-B','daba0000-0000-4000-8000-000000000002','ATIVO');
INSERT INTO public.memberships(id,tenant_id,user_id,role,status) VALUES
 ('daba0000-0000-4000-8000-000000000011','daba0000-0000-4000-8000-000000000010',
  'daba0000-0000-4000-8000-000000000001','TENANT_ADMIN','ATIVA'),
 ('daba0000-0000-4000-8000-000000000021','daba0000-0000-4000-8000-000000000020',
  'daba0000-0000-4000-8000-000000000002','TENANT_ADMIN','ATIVA');
INSERT INTO public.contract_documents
 (id,document_kind,version_label,sha256,source_reference,published_at)
 VALUES ('daba0000-0000-4000-8000-000000000030','PLATFORM_LICENSE',
 'FR-M30900-CI-PUBLISHED',repeat('a',64),
 'SYNTHETIC_DISPOSABLE_TEST_DOCUMENT',clock_timestamp()-interval '2 days'),
 ('daba0000-0000-4000-8000-000000000031','PLATFORM_LICENSE',
 'FR-M30900-CI-DRAFT',repeat('c',64),
 'SYNTHETIC_DISPOSABLE_DRAFT_TEST',NULL);
INSERT INTO public.contract_acceptances
 (id,document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method)
 VALUES
 ('daba0000-0000-4000-8000-000000000040',
  'daba0000-0000-4000-8000-000000000030','PLATFORM_LICENSE',
  'daba0000-0000-4000-8000-000000000001',NULL,repeat('b',64),'CI_VERIFIED_IDENTITY'),
 ('daba0000-0000-4000-8000-000000000041',
  'daba0000-0000-4000-8000-000000000030','PLATFORM_LICENSE',
  'daba0000-0000-4000-8000-000000000002',NULL,repeat('d',64),'CI_VERIFIED_IDENTITY'),
 ('daba0000-0000-4000-8000-000000000042',
  'daba0000-0000-4000-8000-000000000031','PLATFORM_LICENSE',
  'daba0000-0000-4000-8000-000000000001',NULL,repeat('e',64),'CI_VERIFIED_IDENTITY');
