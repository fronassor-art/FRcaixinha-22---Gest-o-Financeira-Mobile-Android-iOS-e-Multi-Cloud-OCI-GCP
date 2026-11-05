-- M5900: CI-only webhook login, legacy inbox and Order inbox.
-- HMAC verification happens in FastAPI BEFORE calling append functions;
-- database worker only handles authenticated, scoped durable ingestion.
DO $probe$
DECLARE
 t uuid := 'ffffffff-0000-4000-8000-000000000011';
 other_t uuid := 'ffffffff-0000-4000-8000-000000000012';
 seller varchar := '2002';
 ord varchar := 'ORD01HRYFWNYRE1MR1E60MW3X0T2P';
 notification varchar := 'N_STAGING_CI_0001';
 request_id varchar := 'req-5700-stage-1';
 digest varchar := repeat('a',64);
 existing record;
 result text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_webhook_ingest'
    OR current_user<>'frcaixinha_mp_webhook_ingest'
    OR has_table_privilege(current_user,'public.mp_signed_order_inbox_staging','INSERT')
    OR has_table_privilege(current_user,'public.mp_signed_webhook_inbox_staging','SELECT')
    OR has_table_privilege(current_user,'public.ledger_entries','INSERT')
    OR NOT has_function_privilege(current_user,
         'public.mp_staging_append_signed_order(uuid,varchar,varchar,varchar,varchar,varchar,varchar,varchar,boolean)','EXECUTE')
    OR has_function_privilege('frcaixinha_app_role',
         'public.mp_staging_append_signed_order(uuid,varchar,varchar,varchar,varchar,varchar,varchar,varchar,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'CI webhook role privileges violated';
 END IF;
 SELECT * INTO existing FROM public.mp_staging_resolve_seller(seller);
 IF existing.tenant_id<>t OR existing.seller_id<>seller
    OR existing.webhook_secret_ocid NOT LIKE 'ocid1.secret.%' THEN
    RAISE EXCEPTION 'seller resolution not scoped';
 END IF;
 SELECT public.mp_staging_append_signed_order(
  t,seller,notification,request_id,ord,
  'order.processed'::varchar,'processed'::varchar,digest,false
 ) INTO result;
 IF result<>'INSERTED' THEN RAISE EXCEPTION 'Order notification not inserted'; END IF;
 SELECT public.mp_staging_append_signed_order(
  t,seller,notification,request_id,ord,
  'order.processed'::varchar,'processed'::varchar,digest,false
 ) INTO result;
 IF result<>'REPLAY' THEN RAISE EXCEPTION 'duplicate Orders not idempotent'; END IF;
 BEGIN
   PERFORM public.mp_staging_append_signed_order(
    t,seller,notification,request_id,ord,
    'order.processed'::varchar,'canceled'::varchar,digest,false);
   RAISE EXCEPTION 'conflicting signed Order incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M4500 DENIED: duplicate event conflict' THEN RAISE; END IF;
 END;
 BEGIN
   PERFORM public.mp_staging_append_signed_order(
    other_t,seller,'N_WRONG_TENANT'::varchar,'req-cross-tenant'::varchar,
    ord,'order.processed'::varchar,'processed'::varchar,digest,false);
   RAISE EXCEPTION 'cross-tenant signed Order incorrectly accepted';
 EXCEPTION WHEN OTHERS THEN
   IF SQLERRM NOT LIKE 'M4500 DENIED: order notification scope' THEN RAISE; END IF;
 END;
 RAISE NOTICE 'M5900_ORDERS_INBOX_ROLE=PASS';
END $probe$;
