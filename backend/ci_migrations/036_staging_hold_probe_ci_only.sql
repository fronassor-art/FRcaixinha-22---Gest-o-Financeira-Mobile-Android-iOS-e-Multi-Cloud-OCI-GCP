-- M6600: Role-authenticated, persistent incident holds. Synthetic CI only.
DO $probe$
DECLARE
 t uuid := 'ffffffff-0000-4000-8000-000000000011';
 other_t uuid := 'ffffffff-0000-4000-8000-000000000012';
 op varchar := 'P_'||repeat('a',32);
 r text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_financial_worker'
    OR current_user<>'frcaixinha_mp_financial_worker'
    OR has_table_privilege(current_user,
        'public.mp_orders_reconciliation_holds_staging','INSERT')
    OR has_table_privilege(current_user,
        'public.mp_orders_reconciliation_holds_staging','SELECT')
    OR has_table_privilege(current_user,
        'public.ledger_transactions','INSERT')
    OR NOT has_function_privilege(current_user,
        'public.mp_orders_staging_record_hold(uuid,varchar,varchar,varchar)',
        'EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
        'public.mp_orders_staging_record_hold(uuid,varchar,varchar,varchar)',
        'EXECUTE')
 THEN
    RAISE EXCEPTION 'M6600 DENIED: worker or RLS privileges';
 END IF;

 SELECT public.mp_orders_staging_record_hold(
     t,op,'BANK_MISSING'::varchar,repeat('a',64)::varchar
 ) INTO r;
 IF r<>'NEW' THEN RAISE EXCEPTION 'M6600 incident insert failure'; END IF;
 SELECT public.mp_orders_staging_record_hold(
     t,op,'BANK_MISSING'::varchar,repeat('a',64)::varchar
 ) INTO r;
 IF r<>'REPLAY' THEN RAISE EXCEPTION 'M6600 replay failure'; END IF;

 BEGIN
  PERFORM public.mp_orders_staging_record_hold(
    t,op,'BANK_MISSING'::varchar,repeat('b',64)::varchar);
  RAISE EXCEPTION 'M6600 conflicting fingerprint accepted';
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M039 DENIED: conflicting reconciliation evidence' THEN
   RAISE;
  END IF;
 END;

 BEGIN
  PERFORM public.mp_orders_staging_record_hold(
    other_t,op,'BANK_MISSING'::varchar,repeat('a',64)::varchar);
  RAISE EXCEPTION 'M6600 wrong tenant accepted';
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M039 DENIED: unresolved Orders evidence or tenant scope' THEN
   RAISE;
  END IF;
 END;

 BEGIN
  PERFORM public.mp_orders_staging_record_hold(
    t,op,'READY_TO_PAY'::varchar,repeat('a',64)::varchar);
  RAISE EXCEPTION 'M6600 unauthorized auto-clear accepted';
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M039 DENIED: unresolved Orders evidence or tenant scope' THEN
   RAISE;
  END IF;
 END;

 BEGIN
  PERFORM public.mp_orders_staging_record_hold(
    t,'P_'||repeat('f',32),'BANK_MISSING'::varchar,
    repeat('a',64)::varchar);
  RAISE EXCEPTION 'M6600 unknown operation accepted';
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M039 DENIED: unresolved Orders evidence or tenant scope' THEN
   RAISE;
  END IF;
 END;
 RAISE NOTICE 'M6600_RECONCILIATION_HOLD=PASS';
END $probe$;
