-- CI ONLY. Runs in frcaixinha_ci, then rolls back all synthetic records.
BEGIN;
DO $test$
DECLARE
 v_user uuid:=gen_random_uuid();v_tenant uuid:=gen_random_uuid();
 v_cycle uuid:=gen_random_uuid();v_member uuid:=gen_random_uuid();
 v_key uuid:=gen_random_uuid();v_raw text:=repeat('x',48);
 v_start date:=(current_date+45);
 v_price bigint;v_allowed bool;v_status text;v_req uuid;
BEGIN
 INSERT INTO public.users(id,email,full_name,cpf,phone,status)
 VALUES(v_user,'m20400.'||v_user||'@example.invalid','CI cycle policy',
        left(replace(v_user::text,'-',''),14),'+550000000000','ACTIVE');
 INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status)
 VALUES(v_tenant,'CI tenant M20400','CI_CYCLE_PRICE',v_user,'ATIVO');
 INSERT INTO public.memberships(id,tenant_id,user_id,role,status)
 VALUES(v_member,v_tenant,v_user,'TENANT_ADMIN','ATIVA');
 INSERT INTO public.cycles(id,tenant_id,year,start_date,end_date,settlement_date,status)
 VALUES(v_cycle,v_tenant,extract(year FROM v_start)::integer,
        v_start,v_start+364,v_start+380,'ABERTO');
 INSERT INTO public.policies(tenant_id,cycle_id,contribution_per_quota,status)
 VALUES(v_tenant,v_cycle,100.00,'ACTIVE');
 INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at)
 VALUES(encode(public.digest(v_raw,'sha256'),'hex'),v_user,'TENANT_ADMIN',
        v_tenant,now()+interval '10 minutes');
 SELECT amount_cents,can_edit INTO v_price,v_allowed
 FROM public.cycle_price_status(v_raw,v_tenant);
 IF v_price<>10000 OR NOT v_allowed THEN
  RAISE EXCEPTION 'M20400 initial policy not editable'; END IF;
 SELECT change_status,amount_cents,request_id INTO v_status,v_price,v_req
 FROM public.cycle_price_change(v_raw,v_tenant,v_cycle,15000,
 'Definição auditada de valor por caixinha e ciclo',v_key);
 IF v_status<>'APPLIED' OR v_price<>15000 THEN
  RAISE EXCEPTION 'M20400 editable policy update not applied'; END IF;
 SELECT change_status,amount_cents INTO v_status,v_price
 FROM public.cycle_price_change(v_raw,v_tenant,v_cycle,15000,
 'Definição auditada de valor por caixinha e ciclo',v_key);
 IF v_status<>'APPLIED' OR v_price<>15000 THEN
  RAISE EXCEPTION 'M20400 idempotent replay failed'; END IF;
 IF (SELECT contribution_per_quota FROM public.policies
     WHERE tenant_id=v_tenant AND cycle_id=v_cycle)<>'150.00'::numeric
 THEN RAISE EXCEPTION 'M20400 policy not 150'; END IF;
 INSERT INTO public.contributions(
  tenant_id,cycle_id,membership_id,competence,due_date,amount_due)
 VALUES(v_tenant,v_cycle,v_member,to_char(v_start,'YYYY-MM'),
        v_start+10,150.00);
 SELECT change_status,amount_cents INTO v_status,v_price
 FROM public.cycle_price_change(v_raw,v_tenant,v_cycle,20000,
 'Pedido de revisão sem alterar contribuições já emitidas',gen_random_uuid());
 IF v_status<>'PENDING_REVIEW' OR v_price<>15000 THEN
  RAISE EXCEPTION 'M20400 existing obligation was mutated'; END IF;
 IF (SELECT contribution_per_quota FROM public.policies WHERE tenant_id=v_tenant
     AND cycle_id=v_cycle)<>'150.00'::numeric
 THEN RAISE EXCEPTION 'M20400 financial obligation mutated'; END IF;
 IF (SELECT count(*) FROM public.cycle_contribution_price_audit
   WHERE tenant_id=v_tenant)<>2
 THEN RAISE EXCEPTION 'M20400 audit count incorrect'; END IF;
 BEGIN
  PERFORM public.cycle_price_status(repeat('y',48),v_tenant);
  RAISE EXCEPTION 'M20400 invalid token was accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  UPDATE public.cycle_contribution_price_audit SET reason='alteração proibida'
  WHERE tenant_id=v_tenant;
  RAISE EXCEPTION 'M20400 immutable audit update accepted';
 EXCEPTION WHEN raise_exception THEN
  IF SQLERRM='M20400 immutable audit update accepted'
  THEN RAISE; END IF;
 END;
 RAISE NOTICE 'M20400_SYNTHETIC_ADMIN_150_REVIEW_IDEMPOTENCE=PASS';
END $test$;
ROLLBACK;
