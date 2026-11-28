-- M5800: execute as LOGIN frcaixinha_mp_financial_worker in isolated CI PG16.
-- Neither session_user nor database name is taken from client context.
DO $probe$
DECLARE
 t uuid := 'ffffffff-0000-4000-8000-000000000011';
 other_t uuid := 'ffffffff-0000-4000-8000-000000000012';
 cycle uuid := 'ffffffff-0000-4000-8000-000000000031';
 member uuid := 'ffffffff-0000-4000-8000-000000000021';
 obligation uuid := 'ffffffff-0000-4000-8000-000000000041';
 second_obligation uuid := 'ffffffff-0000-4000-8000-000000000042';
 op varchar := 'P_'||repeat('a',32);
 ext varchar := 'FRC_'||repeat('a',40);
 idem varchar := 'pix_'||repeat('a',40);
 op_b varchar := 'P_'||repeat('b',32);
 ext_b varchar := 'FRC_'||repeat('b',40);
 idem_b varchar := 'pix_'||repeat('b',40);
 ord varchar := 'ORD01HRYFWNYRE1MR1E60MW3X0T2P';
 pay varchar := 'PAY01HRYFXQ53Q3JPEC48MYWMR0TE';
 r text;
 checkout record;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_financial_worker'
    OR current_user<>'frcaixinha_mp_financial_worker'
    OR (SELECT rolsuper OR rolbypassrls FROM pg_roles
        WHERE rolname=current_user)
    OR has_table_privilege(current_user,
       'public.mp_pix_collection_operations_staging','INSERT')
    OR has_table_privilege(current_user,
       'public.mp_pix_receipts_staging','UPDATE')
    OR has_table_privilege(current_user,
       'public.ledger_entries','INSERT')
    OR NOT has_function_privilege(current_user,
       'public.mp_orders_staging_reserve(uuid,uuid,uuid,uuid,varchar,uuid,bigint,smallint,varchar,varchar,varchar,varchar,varchar,varchar)','EXECUTE') THEN
    RAISE EXCEPTION 'CI worker privileges violated';
 END IF;

 SELECT public.mp_orders_staging_reserve(
    t,cycle,member,obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15000::bigint,1::smallint,op,ext,idem,
    '2002'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar
 ) INTO r;
 IF r<>'NEW' THEN RAISE EXCEPTION 'expected NEW, got %',r; END IF;
 SELECT public.mp_orders_staging_reserve(
    t,cycle,member,obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15000::bigint,1::smallint,op,ext,idem,
    '2002'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar
 ) INTO r;
 IF r<>'EXISTS' THEN RAISE EXCEPTION 'idempotency replay failed'; END IF;

 BEGIN
   PERFORM public.mp_orders_staging_reserve(
    t,cycle,member,obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15000::bigint,2::smallint,op_b,ext_b,idem_b,
    '2002'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar);
   RAISE EXCEPTION 'duplicate active Pix incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M038 DENIED: active or uncertain Pix attempt' THEN
     RAISE;
   END IF;
 END;

 BEGIN
   PERFORM public.mp_orders_staging_reserve(
    t,cycle,member,obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15000::bigint,2::smallint,op_b,ext_b,idem_b,
    '3003'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar);
   RAISE EXCEPTION 'cross-tenant merchant incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M038 DENIED: collection account or tenant scope' THEN RAISE; END IF;
 END;
 BEGIN
   PERFORM public.mp_orders_staging_reserve(
    other_t,cycle,member,obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15000::bigint,1::smallint,op_b,ext_b,idem_b,
    '3003'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar);
   RAISE EXCEPTION 'cross-tenant member incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M038 DENIED: collection account or tenant scope' THEN RAISE; END IF;
 END;
 BEGIN
   PERFORM public.mp_orders_staging_reserve(
    t,cycle,member,obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15001::bigint,2::smallint,op_b,ext_b,idem_b,
    '2002'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar);
   RAISE EXCEPTION 'overpayment incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M038 DENIED: contribution outstanding mismatch' THEN RAISE; END IF;
 END;

 SELECT public.mp_orders_staging_save_checkout(
  t,op,ord,pay,'00020126SYNTHETIC-CI'::text,NULL::text,NULL::text
 ) INTO r;
 IF r<>'INSERTED' THEN RAISE EXCEPTION 'checkout not inserted'; END IF;
 SELECT public.mp_orders_staging_save_checkout(
  t,op,ord,pay,'00020126SYNTHETIC-CI'::text,NULL::text,NULL::text
 ) INTO r;
 IF r<>'REPLAY' THEN RAISE EXCEPTION 'checkout replay not idempotent'; END IF;

 SELECT * INTO checkout FROM public.mp_orders_staging_get_checkout(t,op);
 IF checkout.order_id<>ord OR checkout.payment_id<>pay
    OR checkout.amount_cents<>15000
    OR checkout.status<>'AGUARDANDO_PROVEDOR' THEN
    RAISE EXCEPTION 'checkout read incorrect';
 END IF;

 BEGIN
   PERFORM public.mp_orders_staging_save_checkout(
    t,op,ord,'PAY01OTHERPAYMENT0123456789012'::varchar,
    '00020126SYNTHETIC-CI'::text,NULL::text,NULL::text);
   RAISE EXCEPTION 'conflicting provider payment incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M038 DENIED: conflicting provider checkout' THEN RAISE; END IF;
 END;

 SELECT public.mp_orders_staging_reserve(
    t,cycle,member,second_obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15000::bigint,1::smallint,op_b,ext_b,idem_b,
    '2002'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar
 ) INTO r;
 IF r<>'NEW' THEN RAISE EXCEPTION 'second obligation should reserve'; END IF;
 SELECT public.mp_orders_staging_mark_uncertain(t,op_b) INTO r;
 IF r<>'UNCERTAIN' THEN RAISE EXCEPTION 'timeout should mark uncertain'; END IF;
 SELECT * INTO checkout FROM public.mp_orders_staging_get_checkout(t,op_b);
 IF FOUND THEN RAISE EXCEPTION 'unknown order must not yield QR code'; END IF;
 SELECT public.mp_orders_staging_reserve(
    t,cycle,member,second_obligation,'CONTRIBUTION'::varchar,NULL::uuid,
    15000::bigint,1::smallint,op_b,ext_b,idem_b,
    '2002'::varchar,'policy-2027-ci'::varchar,'HOMOLOGACAO'::varchar
 ) INTO r;
 IF r<>'EXISTS' THEN RAISE EXCEPTION 'ambiguous replay must be EXISTS'; END IF;
 RAISE NOTICE 'M5800_WORKER_DATABASE_INTEGRATION=PASS';
END $probe$;
