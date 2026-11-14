-- M23200: disposable GitHub CI only. Synthetic admins (not real tenants).
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on' THEN
  RAISE EXCEPTION 'M23200 CI FIXTURE DENIED';
 END IF;
END $guard$;
INSERT INTO public.users(id,email,full_name,cpf,phone) VALUES
 ('ffffffff-0000-4000-8000-000000000081','oauth-ci-a@example.invalid',
  'M23200 Admin A','99999999999981','00000000081'),
 ('ffffffff-0000-4000-8000-000000000082','oauth-ci-b@example.invalid',
  'M23200 Admin B','99999999999982','00000000082');
INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id) VALUES
 ('ffffffff-0000-4000-8000-000000000091','M23200 sandbox tenant A',
  'oauth-ci-a','ffffffff-0000-4000-8000-000000000081'),
 ('ffffffff-0000-4000-8000-000000000092','M23200 sandbox tenant B',
  'oauth-ci-b','ffffffff-0000-4000-8000-000000000082');
INSERT INTO public.memberships(id,tenant_id,user_id,role,status) VALUES
 ('ffffffff-0000-4000-8000-0000000000a1',
  'ffffffff-0000-4000-8000-000000000091',
  'ffffffff-0000-4000-8000-000000000081','TENANT_ADMIN','ATIVA'),
 ('ffffffff-0000-4000-8000-0000000000a2',
  'ffffffff-0000-4000-8000-000000000092',
  'ffffffff-0000-4000-8000-000000000082','TENANT_ADMIN','ATIVA');
COMMIT;
