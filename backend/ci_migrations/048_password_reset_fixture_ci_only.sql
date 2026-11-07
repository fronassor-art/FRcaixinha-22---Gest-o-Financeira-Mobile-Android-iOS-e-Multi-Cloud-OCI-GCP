-- M26000 disposable synthetic account, password reset and session fixture.
DO $ci$
BEGIN
 IF current_database()<>'frcaixinha_staging'
  OR session_user<>'postgres'
  OR current_setting('frcaixinha.recovery_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M26000 fixture must run only on disposable staging'; END IF;
END $ci$;

INSERT INTO public.users(id,email,full_name,cpf,phone,status,is_master)
VALUES('eeeeeeee-0000-4000-8000-000000000021',
       'member-m26000@example.com','Member synthetic M26000',
       '52998224726','11999999998','ACTIVE',false);

INSERT INTO public.memberships
(id,tenant_id,user_id,role,status)
VALUES('eeeeeeee-0000-4000-8000-000000000022',
       'eeeeeeee-0000-4000-8000-000000000012',
       'eeeeeeee-0000-4000-8000-000000000021',
       'TENANT_MEMBER','ATIVA');

INSERT INTO public.credentials(user_id,password_hash,algorithm)
VALUES('eeeeeeee-0000-4000-8000-000000000021',
       '$argon2id$v=19$m=65536,t=3,p=4$'||repeat('A',72),'argon2id');

INSERT INTO public.sessions(id,token_hash,user_id,active_role,active_tenant_id,expires_at)
VALUES('eeeeeeee-0000-4000-8000-000000000023',repeat('9',64),
       'eeeeeeee-0000-4000-8000-000000000021','TENANT_MEMBER',
       'eeeeeeee-0000-4000-8000-000000000012',now()+interval '15 minutes');

INSERT INTO public.password_reset_tokens
(id,user_id,token_hash,requested_at,expires_at,delivery_status)
VALUES
('eeeeeeee-0000-4000-8000-000000000024',
 'eeeeeeee-0000-4000-8000-000000000021',repeat('c',64),
 now(),now()+interval '15 minutes','DELIVERED'),
('eeeeeeee-0000-4000-8000-000000000025',
 'eeeeeeee-0000-4000-8000-000000000021',repeat('d',64),
 now(),now()+interval '15 minutes','DELIVERED'),
('eeeeeeee-0000-4000-8000-000000000027',
 'eeeeeeee-0000-4000-8000-000000000021',repeat('e',64),
 now()-interval '20 minutes',now()-interval '5 minutes','DELIVERED'),
('eeeeeeee-0000-4000-8000-000000000028',
 'eeeeeeee-0000-4000-8000-000000000021',repeat('f',64),
 now(),now()+interval '15 minutes','PENDING_DELIVERY');
