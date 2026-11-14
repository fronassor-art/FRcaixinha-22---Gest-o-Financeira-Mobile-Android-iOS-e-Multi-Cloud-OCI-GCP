-- M37438: synthetic dev fixture inside CI PG18 transaction only.
-- Must run in an already existing disposable frcaixinha_ci service.
DO $m37438_seed$
DECLARE
 u uuid:=gen_random_uuid();t uuid:=gen_random_uuid();
 cyc uuid:=gen_random_uuid();p uuid:=gen_random_uuid();
 ma uuid:=gen_random_uuid();mm uuid:=gen_random_uuid();
BEGIN
 IF current_database()<>'frcaixinha_ci' OR session_user<>'postgres'
  OR inet_server_port()<>5432
  OR current_setting('frfinance.m37437_ci_disposable',true)<>'1'
  OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
 THEN RAISE EXCEPTION 'M37438 disposable CI only'; END IF;
 IF (SELECT count(*) FROM public.users)<>0
  OR (SELECT count(*) FROM public.tenants)<>0
  OR (SELECT count(*) FROM public.memberships)<>0
  OR (SELECT count(*) FROM public.cycles)<>0
  OR (SELECT count(*) FROM public.policies)<>0
  OR (SELECT count(*) FROM public.quotas)<>0
  OR (SELECT count(*) FROM public.contributions)<>0
  OR (SELECT count(*) FROM public.audit_events)<>0
 THEN RAISE EXCEPTION 'M37438 disposable CI baseline not empty'; END IF;
 -- Test-only reproduction of pre-043 legacy rows, then restore NOT VALID checks.
 ALTER TABLE public.policies DROP CONSTRAINT policy_minimum_150_new;
 ALTER TABLE public.quotas DROP CONSTRAINT quota_minimum_150_new;
 INSERT INTO public.users(id,email,full_name,cpf,phone,status)
 VALUES(u,'m37438.'||u||'@example.invalid','Synthetic dev reset candidate',
        left(replace(u::text,'-',''),14),'+550000000000','ACTIVE');
 INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status)
 VALUES(t,'M37438 synthetic only','CI_M37438',u,'ATIVO');
 INSERT INTO public.memberships(id,tenant_id,user_id,role,status)
 VALUES(ma,t,u,'TENANT_ADMIN','ATIVA'),
       (mm,t,u,'TENANT_MEMBER','ATIVA');
 INSERT INTO public.cycles(id,tenant_id,year,start_date,end_date,settlement_date,status)
 VALUES(cyc,t,2027,DATE '2027-01-01',DATE '2027-12-31',DATE '2028-01-15','ABERTO');
 INSERT INTO public.policies(id,tenant_id,cycle_id,contribution_per_quota,status)
 VALUES(p,t,cyc,100.00,'ACTIVE');
 INSERT INTO public.quotas(tenant_id,membership_id,quota_number,value_brl,status)
 VALUES(t,mm,1,100.00,'ATIVA');
 INSERT INTO public.contributions(tenant_id,cycle_id,membership_id,competence,due_date,amount_due)
 SELECT t,cyc,mm,to_char(make_date(2027,n,1),'YYYY-MM'),
        make_date(2027,n,10),100.00
 FROM generate_series(1,12) AS n;
 INSERT INTO public.cycle_contribution_price_audit
  (tenant_id,cycle_id,policy_id,actor_user_id,idempotency_key,
   old_price_cents,requested_price_cents,change_status,reason)
 VALUES(t,cyc,p,u,gen_random_uuid(),10000,15000,'PENDING_REVIEW',
        'CI synthetic obsolete price review only');
 INSERT INTO public.audit_events
  (actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref)
 SELECT u,'TENANT_ADMIN',t,'CI_SYNTHETIC_BASELINE','CI_FIXTURE','CI_MARKER',
 'Disposable transaction test for safe cleanup','CI_BENCHMARK'
 FROM generate_series(1,3);
 INSERT INTO public.audit_events
  (actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref)
 SELECT u,'SYSTEM',NULL,'CI_UNRELATED_GLOBAL_EVENT','CI_BACKGROUND','CI_OTHER_SCOPE',
  'Unrelated disposable CI evidence, outside affected tenant','CI_UNRELATED'
 FROM generate_series(1,2);
 ALTER TABLE public.policies ADD CONSTRAINT policy_minimum_150_new
   CHECK (contribution_per_quota>=150.00) NOT VALID;
 ALTER TABLE public.quotas ADD CONSTRAINT quota_minimum_150_new
   CHECK (value_brl>=150.00) NOT VALID;
END $m37438_seed$;
