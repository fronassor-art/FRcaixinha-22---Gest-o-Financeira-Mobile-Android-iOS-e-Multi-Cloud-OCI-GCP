-- M5700 GitHub Actions ephemeral frcaixinha_staging ONLY. 100% synthetic.
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on' THEN
   RAISE EXCEPTION 'NOT AN AUTHORIZED CI STAGING DATABASE';
 END IF;
END $guard$;
INSERT INTO public.users(id,email,full_name,cpf,phone)
VALUES
('ffffffff-0000-4000-8000-000000000001',
 'staging-ci-member-1@example.invalid','Synthetic Account A','99999999999901','00000000001'),
('ffffffff-0000-4000-8000-000000000002',
 'staging-ci-member-2@example.invalid','Synthetic Account B','99999999999902','00000000002');
INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id)
VALUES
('ffffffff-0000-4000-8000-000000000011','CI only tenant A',
 'ci-only-a','ffffffff-0000-4000-8000-000000000001'),
('ffffffff-0000-4000-8000-000000000012','CI only tenant B',
 'ci-only-b','ffffffff-0000-4000-8000-000000000002');
INSERT INTO public.memberships(id,tenant_id,user_id,role,status)
VALUES
('ffffffff-0000-4000-8000-000000000021',
 'ffffffff-0000-4000-8000-000000000011',
 'ffffffff-0000-4000-8000-000000000001','TENANT_MEMBER','ATIVA'),
('ffffffff-0000-4000-8000-000000000022',
 'ffffffff-0000-4000-8000-000000000012',
 'ffffffff-0000-4000-8000-000000000002','TENANT_MEMBER','ATIVA');
INSERT INTO public.cycles(id,tenant_id,year,start_date,end_date,settlement_date,status)
VALUES
('ffffffff-0000-4000-8000-000000000031',
 'ffffffff-0000-4000-8000-000000000011',
 2027,'2027-01-01','2027-12-31','2028-01-10','ABERTO'),
('ffffffff-0000-4000-8000-000000000032',
 'ffffffff-0000-4000-8000-000000000012',
 2027,'2027-01-01','2027-12-31','2028-01-10','ABERTO');
INSERT INTO public.contributions(
 id,tenant_id,cycle_id,membership_id,competence,due_date,amount_due
) VALUES
('ffffffff-0000-4000-8000-000000000041',
 'ffffffff-0000-4000-8000-000000000011',
 'ffffffff-0000-4000-8000-000000000031',
 'ffffffff-0000-4000-8000-000000000021',
 '2027-01','2027-01-10',150.00),
('ffffffff-0000-4000-8000-000000000042',
 'ffffffff-0000-4000-8000-000000000011',
 'ffffffff-0000-4000-8000-000000000031',
 'ffffffff-0000-4000-8000-000000000021',
 '2027-02','2027-02-10',150.00),
('ffffffff-0000-4000-8000-000000000043',
 'ffffffff-0000-4000-8000-000000000012',
 'ffffffff-0000-4000-8000-000000000032',
 'ffffffff-0000-4000-8000-000000000022',
 '2027-01','2027-01-10',150.00),
('ffffffff-0000-4000-8000-000000000044',
 'ffffffff-0000-4000-8000-000000000011',
 'ffffffff-0000-4000-8000-000000000031',
 'ffffffff-0000-4000-8000-000000000021',
 '2027-03','2027-03-10',150.00),
('ffffffff-0000-4000-8000-000000000045',
 'ffffffff-0000-4000-8000-000000000011',
 'ffffffff-0000-4000-8000-000000000031',
 'ffffffff-0000-4000-8000-000000000021',
 '2027-04','2027-04-10',150.00);
INSERT INTO public.mp_seller_connections_staging(
 tenant_id,seller_id,webhook_secret_ocid,verified_at
) VALUES
('ffffffff-0000-4000-8000-000000000011',
 '2002','ocid1.vaultsecret.oc1.ci-fake-only-aaaaaa',now()),
('ffffffff-0000-4000-8000-000000000012',
 '3003','ocid1.vaultsecret.oc1.ci-fake-only-bbbbbb',now());
COMMIT;
