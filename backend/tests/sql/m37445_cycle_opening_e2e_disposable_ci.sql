-- FR Finance M37445 — authenticated synthetic opening in disposable PG18 CI.
-- Must remain in frcaixinha_ci on the ephemeral GitHub Actions service.
-- All inserts, sessions, cycles and audits are rolled back in the SAME transaction.
BEGIN;
SET LOCAL lock_timeout='5000ms';
SET LOCAL statement_timeout='30000ms';
DO $m37445$
DECLARE
  admin uuid:=gen_random_uuid();
  member uuid:=gen_random_uuid();
  tenants uuid[]:=ARRAY[gen_random_uuid(),gen_random_uuid(),gen_random_uuid()];
  cents bigint[]:=ARRAY[15000,20000,32500]::bigint[];
  yr integer:=greatest(2028,extract(year from current_date)::int+2);
  token text;
  member_token text:=repeat('m',48);
  reason_text text;
  idem uuid;
  v record;
  replay record;
  i int;
BEGIN
  IF current_database()<>'frcaixinha_ci'
    OR inet_server_port()<>5432
    OR session_user<>'postgres'
    OR current_user<>'postgres'
    OR current_setting('is_superuser')<>'on'
    OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
    OR current_setting('frfinance.m37445_disposable_ci',true)<>'1'
  THEN RAISE EXCEPTION 'M37445 CI_POSTGRES18_ONLY'; END IF;

  IF (SELECT count(*) FROM public.users)<>0
   OR (SELECT count(*) FROM public.tenants)<>0
   OR (SELECT count(*) FROM public.cycles)<>0
   OR (SELECT count(*) FROM public.contributions)<>0
   OR (SELECT count(*) FROM public.cycle_opening_audit)<>0
  THEN RAISE EXCEPTION 'M37445 CI_DATABASE_NOT_EMPTY'; END IF;

  IF NOT has_function_privilege('frcaixinha_app_role',
       'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)','EXECUTE')
    OR has_function_privilege('frcaixinha_auth_role',
       'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)','EXECUTE')
    OR has_table_privilege('frcaixinha_app_role',
       'public.cycle_opening_audit','INSERT')
  THEN RAISE EXCEPTION 'M37445 ROLE_BOUNDARY_INVALID'; END IF;

  INSERT INTO public.users(id,email,full_name,cpf,phone,status)
  VALUES
    (admin,'m37445.admin.'||admin||'@example.invalid',
      'Synthetic tenant administrator',left(replace(admin::text,'-',''),14),
      '+550000000000','ACTIVE'),
    (member,'m37445.member.'||member||'@example.invalid',
      'Synthetic tenant member',left(replace(member::text,'-',''),14),
      '+550000000000','ACTIVE');

  FOR i IN 1..3 LOOP
    token:=repeat(chr(64+i),48);
    reason_text:=format('Administrador escolheu expressamente %s centavos para o ciclo',cents[i]);
    idem:=gen_random_uuid();

    INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status)
    VALUES(tenants[i],format('M37445 CI tenant %s',i),format('M37445_CI_%s',i),
      admin,'ATIVO');
    INSERT INTO public.memberships(tenant_id,user_id,role,status)
    VALUES(tenants[i],admin,'TENANT_ADMIN','ATIVA');
    INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at)
    VALUES(encode(public.digest(token,'sha256'),'hex'),
      admin,'TENANT_ADMIN',tenants[i],now()+interval '20 minutes');

    SELECT * INTO v FROM public.cycle_open_create(
      token,tenants[i],yr,cents[i],reason_text,idem);
    IF v.opening_status<>'CREATED' OR v.opened_year<>yr
       OR v.opened_amount_cents<>cents[i]
    THEN RAISE EXCEPTION 'M37445 EXPLICIT_CYCLE_OPEN_FAILED'; END IF;
    IF (SELECT p.contribution_per_quota FROM public.policies p
        WHERE p.id=v.opened_policy_id)<>(cents[i]::numeric/100)
    THEN RAISE EXCEPTION 'M37445 INCORRECT_POLICY_AMOUNT'; END IF;

    SELECT * INTO replay FROM public.cycle_open_create(
      token,tenants[i],yr,cents[i],reason_text,idem);
    IF replay.opening_status<>'REPLAY'
      OR replay.opened_cycle_id IS DISTINCT FROM v.opened_cycle_id
      OR replay.opened_policy_id IS DISTINCT FROM v.opened_policy_id
    THEN RAISE EXCEPTION 'M37445 IDEMPOTENT_REPLAY_FAILED'; END IF;

    BEGIN
      PERFORM public.cycle_open_create(
        token,tenants[i],yr,cents[i]+100,reason_text,idem);
      RAISE EXCEPTION 'M37445 CONFLICT_ACCEPTED';
    EXCEPTION WHEN unique_violation THEN NULL; END;

    BEGIN
      PERFORM public.cycle_open_create(
        token,tenants[i],yr+1,cents[i],reason_text,gen_random_uuid());
      RAISE EXCEPTION 'M37445 PARALLEL_OPEN_ACCEPTED';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;

    BEGIN
      PERFORM public.cycle_open_create(
        token,tenants[i],yr+1,10000,reason_text,gen_random_uuid());
      RAISE EXCEPTION 'M37445 R100_ACCEPTED';
    EXCEPTION WHEN invalid_parameter_value THEN NULL; END;

    BEGIN
      PERFORM public.cycle_open_create(
        token,tenants[i],yr+1,14999,reason_text,gen_random_uuid());
      RAISE EXCEPTION 'M37445 R149_99_ACCEPTED';
    EXCEPTION WHEN invalid_parameter_value THEN NULL; END;
  END LOOP;

  -- A valid administrator for tenant 1 must not reuse its session on tenant 2.
  BEGIN
    PERFORM public.cycle_open_create(
      repeat('A',48),tenants[2],yr+1,20000,
      'Tentativa de acesso de outro tenant ao ciclo',
      gen_random_uuid());
    RAISE EXCEPTION 'M37445 CROSS_TENANT_ACCEPTED';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;

  INSERT INTO public.memberships(tenant_id,user_id,role,status)
  VALUES(tenants[1],member,'TENANT_MEMBER','ATIVA');
  INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at)
  VALUES(encode(public.digest(member_token,'sha256'),'hex'),
    member,'TENANT_MEMBER',tenants[1],now()+interval '20 minutes');
  BEGIN
    PERFORM public.cycle_open_create(
      member_token,tenants[1],yr+1,20000,
      'Membro sem privilégio tentou abrir o ciclo',
      gen_random_uuid());
    RAISE EXCEPTION 'M37445 MEMBER_OPEN_ACCEPTED';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;

  BEGIN
    PERFORM public.cycle_open_create(
      repeat('z',48),tenants[1],yr+1,20000,
      'Sessão inexistente tentou abrir o ciclo',
      gen_random_uuid());
    RAISE EXCEPTION 'M37445 INVALID_TOKEN_ACCEPTED';
  EXCEPTION WHEN insufficient_privilege THEN NULL; END;

  -- The immutable audit must reject direct updates and deletes.
  BEGIN
    UPDATE public.cycle_opening_audit
       SET reason='Alteração proibida por auditoria'
     WHERE tenant_id=tenants[1];
    RAISE EXCEPTION 'M37445 AUDIT_UPDATE_ACCEPTED';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM='M37445 AUDIT_UPDATE_ACCEPTED' THEN RAISE; END IF;
    IF SQLERRM<>'M21000 IMMUTABLE_AUDIT'
    THEN RAISE EXCEPTION 'M37445 AUDIT_UPDATE_UNEXPECTED_ERROR'; END IF;
  END;
  BEGIN
    DELETE FROM public.cycle_opening_audit WHERE tenant_id=tenants[1];
    RAISE EXCEPTION 'M37445 AUDIT_DELETE_ACCEPTED';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM='M37445 AUDIT_DELETE_ACCEPTED' THEN RAISE; END IF;
    IF SQLERRM<>'M21000 IMMUTABLE_AUDIT'
    THEN RAISE EXCEPTION 'M37445 AUDIT_DELETE_UNEXPECTED_ERROR'; END IF;
  END;

  IF (SELECT count(*) FROM public.cycles WHERE tenant_id=ANY(tenants))<>3
    OR (SELECT count(*) FROM public.policies WHERE tenant_id=ANY(tenants))<>3
    OR (SELECT count(*) FROM public.cycle_opening_audit
        WHERE tenant_id=ANY(tenants))<>3
    OR (SELECT count(DISTINCT amount_cents) FROM public.cycle_opening_audit
        WHERE tenant_id=ANY(tenants))<>3
    OR (SELECT count(*) FROM public.contributions WHERE tenant_id=ANY(tenants))<>0
    OR (SELECT count(*) FROM public.quotas WHERE tenant_id=ANY(tenants))<>0
    OR (SELECT count(*) FROM public.pix_payment_intents)<>0
    OR (SELECT count(*) FROM public.ledger_transactions)<>0
    OR (SELECT count(*) FROM public.ledger_entries)<>0
    OR (SELECT count(*) FROM public.loans)<>0
  THEN RAISE EXCEPTION 'M37445 FINANCIAL_OR_AUDIT_INTEGRITY_FAILED'; END IF;

  RAISE NOTICE 'M37445_PG18_CYCLE_OPEN_150_200_325_REPLAY_RLS_NO_FINANCE=PASS';
END $m37445$;
ROLLBACK;
