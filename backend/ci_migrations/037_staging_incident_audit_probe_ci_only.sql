-- M14000 synthetic role-authenticated append-only probe. Disposable CI only.
DO $ci$
DECLARE
 t uuid := 'ffffffff-0000-4000-8000-000000000011';
 foreign_t uuid := 'ffffffff-0000-4000-8000-000000000012';
 op varchar := 'P_'||repeat('a',32);
 genesis varchar := repeat('0',64);
 d1 text;
 d2 text;
 got text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_mp_financial_worker'
   OR has_table_privilege(session_user,
      'public.mp_orders_incident_audit_staging','SELECT')
   OR has_table_privilege(session_user,
      'public.mp_orders_incident_audit_staging','INSERT')
   OR has_table_privilege(session_user,
      'public.mp_orders_incident_audit_staging','UPDATE')
   OR has_table_privilege(session_user,
      'public.mp_orders_incident_audit_staging','DELETE')
   OR has_table_privilege(session_user,
      'public.ledger_transactions','INSERT')
   OR NOT has_function_privilege(session_user,
      'public.mp_orders_staging_append_incident_audit(uuid,varchar,varchar,varchar,varchar,varchar)',
      'EXECUTE')
   OR has_function_privilege('frcaixinha_app_role',
      'public.mp_orders_staging_append_incident_audit(uuid,varchar,varchar,varchar,varchar,varchar)',
      'EXECUTE')
 THEN
   RAISE EXCEPTION 'M14000 DENIED: worker grants or table exposure';
 END IF;

 got:=public.mp_orders_staging_append_incident_audit(
   t,op,'BANK_MISSING','OPENED',repeat('a',64),genesis);
 IF got !~ '^NEW:[a-f0-9]{64}$' THEN
   RAISE EXCEPTION 'M14000 unexpected first append: %',got;
 END IF;
 d1:=substr(got,5);

 got:=public.mp_orders_staging_append_incident_audit(
   t,op,'BANK_MISSING','OPENED',repeat('a',64),genesis);
 IF got<>'REPLAY:'||d1 THEN
   RAISE EXCEPTION 'M14000 idempotent replay failed';
 END IF;

 BEGIN
   PERFORM public.mp_orders_staging_append_incident_audit(
     t,op,'BANK_MISSING','SECURITY_ESCALATED',repeat('b',64),genesis);
   RAISE EXCEPTION 'M14000 stale predecessor accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M040 DENIED: stale or forged predecessor' THEN RAISE; END IF;
 END;

 got:=public.mp_orders_staging_append_incident_audit(
   t,op,'BANK_MISSING','EVIDENCE_REVIEW_REQUESTED',repeat('b',64),d1);
 IF got !~ '^NEW:[a-f0-9]{64}$' THEN
   RAISE EXCEPTION 'M14000 next append failed';
 END IF;
 d2:=substr(got,5);
 IF d2=d1 THEN RAISE EXCEPTION 'M14000 duplicate digest'; END IF;

 BEGIN
   PERFORM public.mp_orders_staging_append_incident_audit(
     foreign_t,op,'BANK_MISSING','OPENED',repeat('a',64),genesis);
   RAISE EXCEPTION 'M14000 tenant crossing accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M040 DENIED: unauthenticated or unscoped incident append'
     THEN RAISE; END IF;
 END;

 BEGIN
   PERFORM public.mp_orders_staging_append_incident_audit(
     t,op,'BANK_MISSING','RELEASE_HOLD',repeat('c',64),d2);
   RAISE EXCEPTION 'M14000 forbidden financial action accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M040 DENIED: unauthenticated or unscoped incident append'
     THEN RAISE; END IF;
 END;

 RAISE NOTICE 'M14000_APPEND_ONLY_RLS_ROLE_REPLAY=PASS';
END $ci$;
