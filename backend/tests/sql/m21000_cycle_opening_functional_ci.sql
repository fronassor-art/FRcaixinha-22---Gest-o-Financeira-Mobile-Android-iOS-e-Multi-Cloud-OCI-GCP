-- CI only, rolled back: no live user or financial funds.
BEGIN;
DO $test$
DECLARE
 u uuid:=gen_random_uuid();t uuid:=gen_random_uuid();
 raw_token text:=repeat('c',48);idem uuid:=gen_random_uuid();
 y integer; r record; r2 record;
BEGIN
 y:=greatest(2028,extract(year from current_date)::integer+2);
 INSERT INTO public.users(id,email,full_name,cpf,phone,status)
 VALUES(u,'m21000.'||u||'@example.invalid','CI admin',
 left(replace(u::text,'-',''),14),'+550000000000','ACTIVE');
 INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status)
 VALUES(t,'M21000 CI tenant','CI_OPEN_CYCLE',u,'ATIVO');
 INSERT INTO public.memberships(tenant_id,user_id,role,status)
 VALUES(t,u,'TENANT_ADMIN','ATIVA');
 INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at)
 VALUES(encode(public.digest(raw_token,'sha256'),'hex'),
  u,'TENANT_ADMIN',t,now()+interval '10 minutes');
 SELECT * INTO r FROM public.cycle_open_create(raw_token,t,y,20000,
 'Administrador declarou contribuicao de duzentos reais',idem);
 IF r.opening_status<>'CREATED' OR r.opened_amount_cents<>20000
 THEN RAISE EXCEPTION 'M21000 CREATE_FAILED'; END IF;
 SELECT * INTO r2 FROM public.cycle_open_create(raw_token,t,y,20000,
 'Administrador declarou contribuicao de duzentos reais',idem);
 IF r2.opening_status<>'REPLAY' OR r2.opened_cycle_id<>r.opened_cycle_id
 THEN RAISE EXCEPTION 'M21000 REPLAY_FAILED'; END IF;
 IF (SELECT contribution_per_quota FROM public.policies
  WHERE id=r.opened_policy_id)<>200.00
 THEN RAISE EXCEPTION 'M21000 PRICE_NOT_EXPLICIT'; END IF;
 IF (SELECT count(*) FROM public.cycle_opening_audit WHERE tenant_id=t)<>1
 THEN RAISE EXCEPTION 'M21000 AUDIT_NOT_UNIQUE'; END IF;
 BEGIN
  PERFORM public.cycle_open_create(raw_token,t,y,15000,
   'Administrador declarou contribuicao de duzentos reais',idem);
  RAISE EXCEPTION 'M21000 KEY_CONFLICT_ACCEPTED';
 EXCEPTION WHEN unique_violation THEN NULL; END;
 BEGIN
  PERFORM public.cycle_open_create(raw_token,t,y+1,10000,
   'Tentativa de cota abaixo do limite permitido',gen_random_uuid());
  RAISE EXCEPTION 'M21000 LOW_PRICE_ACCEPTED';
 EXCEPTION WHEN invalid_parameter_value THEN NULL; END;
 BEGIN
  PERFORM public.cycle_open_create(raw_token,t,y+1,25000,
   'Tentativa de abrir segundo ciclo simultaneo',gen_random_uuid());
  RAISE EXCEPTION 'M21000 DUPLICATE_OPEN_ACCEPTED';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 IF EXISTS(SELECT 1 FROM public.contributions WHERE tenant_id=t)
 OR EXISTS(SELECT 1 FROM public.ledger_transactions WHERE tenant_id=t)
 THEN RAISE EXCEPTION 'M21000 FINANCIAL_EFFECT'; END IF;
 RAISE NOTICE 'M21000_EXPLICIT_200_REPLAY_MINIMUM_150_NO_MONEY=PASS';
END $test$;
ROLLBACK;
