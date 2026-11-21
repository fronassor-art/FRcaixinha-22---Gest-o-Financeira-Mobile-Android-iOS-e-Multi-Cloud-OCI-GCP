-- Synthetic data for annual consent CI only.
DO $g$ BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('frcaixinha.annual_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M30400_FIXTURE_DENIED'; END IF;
END $g$;
INSERT INTO public.users(id,email,full_name,cpf,phone) VALUES
('dada0000-0000-4000-8000-000000000001','admin30400@example.com','CI Admin','99000100001','000000000'),
('dada0000-0000-4000-8000-000000000002','member30401@example.com','CI Member One','99000100002','000000000'),
('dada0000-0000-4000-8000-000000000003','member30402@example.com','CI Member Two','99000100003','000000000');
INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id)
VALUES('dada0000-0000-4000-8000-000000000010','CI annual box','CI-M30400',
'dada0000-0000-4000-8000-000000000001');
INSERT INTO public.memberships(id,tenant_id,user_id,role) VALUES
('dada0000-0000-4000-8000-000000000011','dada0000-0000-4000-8000-000000000010','dada0000-0000-4000-8000-000000000001','TENANT_ADMIN'),
('dada0000-0000-4000-8000-000000000012','dada0000-0000-4000-8000-000000000010','dada0000-0000-4000-8000-000000000002','TENANT_MEMBER'),
('dada0000-0000-4000-8000-000000000013','dada0000-0000-4000-8000-000000000010','dada0000-0000-4000-8000-000000000003','TENANT_MEMBER');
