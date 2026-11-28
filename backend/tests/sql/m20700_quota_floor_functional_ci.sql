-- M20700: functional test in disposable CI database only.
BEGIN;
DO $test$
DECLARE v_user uuid:=gen_random_uuid();v_tenant uuid:=gen_random_uuid();
 v_cycle uuid:=gen_random_uuid();v_member uuid:=gen_random_uuid();
 v_token text:=repeat('m',48);v_status text;v_amount bigint;
BEGIN
 IF EXISTS(SELECT 1 FROM information_schema.columns
   WHERE table_schema='public' AND
   ((table_name='policies' AND column_name='contribution_per_quota') OR
    (table_name='quotas' AND column_name='value_brl'))
   AND column_default IS NOT NULL) THEN RAISE EXCEPTION 'default 100 still enabled'; END IF;
 INSERT INTO public.users(id,email,full_name,cpf,phone,status)
 VALUES(v_user,'m20700.'||v_user||'@example.invalid','CI minimum 150',
   left(replace(v_user::text,'-',''),14),'+550000000000','ACTIVE');
 INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status)
 VALUES(v_tenant,'CI M20700','CI_QUOTA_FLOOR',v_user,'ATIVO');
 INSERT INTO public.memberships(id,tenant_id,user_id,role,status)
 VALUES(v_member,v_tenant,v_user,'TENANT_ADMIN','ATIVA');
 INSERT INTO public.cycles(id,tenant_id,year,start_date,end_date,settlement_date,status)
 VALUES(v_cycle,v_tenant,2027,current_date+45,current_date+409,current_date+425,'ABERTO');
 BEGIN
   INSERT INTO public.policies(tenant_id,cycle_id,contribution_per_quota,status)
   VALUES(v_tenant,v_cycle,100.00,'ACTIVE');
   RAISE EXCEPTION 'bad policy accepted';
 EXCEPTION WHEN check_violation THEN NULL; END;
 INSERT INTO public.policies(tenant_id,cycle_id,contribution_per_quota,status)
 VALUES(v_tenant,v_cycle,150.00,'ACTIVE');
 BEGIN
   INSERT INTO public.quotas(tenant_id,membership_id,quota_number,value_brl,status)
   VALUES(v_tenant,v_member,1,100.00,'ATIVA');
   RAISE EXCEPTION 'bad quota accepted';
 EXCEPTION WHEN check_violation THEN NULL; END;
 INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at)
 VALUES(encode(public.digest(v_token,'sha256'),'hex'),v_user,
   'TENANT_ADMIN',v_tenant,now()+interval '10 minutes');
 BEGIN
   PERFORM public.cycle_price_change(v_token,v_tenant,v_cycle,10000,
     'Valor menor que o mínimo contratual',gen_random_uuid());
   RAISE EXCEPTION 'bad change accepted';
 EXCEPTION WHEN invalid_parameter_value THEN NULL; END;
 SELECT change_status,amount_cents INTO v_status,v_amount
 FROM public.cycle_price_change(v_token,v_tenant,v_cycle,20000,
   'Valor escolhido pelo administrador da caixinha',gen_random_uuid());
 IF v_status<>'APPLIED' OR v_amount<>20000 THEN
  RAISE EXCEPTION 'valid R$200 amount rejected'; END IF;
 IF (SELECT count(*) FROM public.contributions WHERE tenant_id=v_tenant)<>0
 THEN RAISE EXCEPTION 'unexpected legacy debt rewrite'; END IF;
 RAISE NOTICE 'M20700_EXPLICIT_R$200_MINIMUM_R$150_NO_DEBT_WRITE=PASS';
END $test$;
ROLLBACK;
