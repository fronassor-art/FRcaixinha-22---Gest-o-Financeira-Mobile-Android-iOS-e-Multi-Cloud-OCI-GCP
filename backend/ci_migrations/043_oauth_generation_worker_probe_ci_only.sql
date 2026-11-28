-- M23900: no actor/tenant seller information outside authorized worker.
DO $probe$
DECLARE
 a uuid:='ffffffff-0000-4000-8000-000000000091';
 b uuid:='ffffffff-0000-4000-8000-000000000092';
 ua uuid:='ffffffff-0000-4000-8000-000000000081';
 ub uuid:='ffffffff-0000-4000-8000-000000000082';
 generation_number bigint;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
    RAISE EXCEPTION 'M23900 PROBE DENIED: identity';
 END IF;
 IF has_table_privilege(current_user,'public.mp_oauth_seller_consents_staging','SELECT') THEN
   RAISE EXCEPTION 'M23900 DIRECT TABLE READ PERMISSION';
 END IF;
 SELECT public.mp_staging_oauth_generation(a,ua,'2002')
  INTO generation_number;
 IF generation_number IS DISTINCT FROM 1 THEN
    RAISE EXCEPTION 'M23900 first tenant generation not updated';
 END IF;
 SELECT public.mp_staging_oauth_generation(b,ub,'3003')
  INTO generation_number;
 IF generation_number IS DISTINCT FROM 0 THEN
    RAISE EXCEPTION 'M23900 second tenant generation not zero';
 END IF;
 SELECT public.mp_staging_oauth_generation(a,ub,'2002')
  INTO generation_number;
 IF generation_number IS NOT NULL THEN
    RAISE EXCEPTION 'M23900 cross-tenant actor exposed';
 END IF;
 SELECT public.mp_staging_oauth_generation(b,ua,'3003')
  INTO generation_number;
 IF generation_number IS NOT NULL THEN
    RAISE EXCEPTION 'M23900 cross-tenant actor B exposed';
 END IF;
 SELECT public.mp_staging_oauth_generation(a,ua,'3003')
  INTO generation_number;
 IF generation_number IS NOT NULL THEN
    RAISE EXCEPTION 'M23900 cross-tenant seller exposed';
 END IF;
 RAISE NOTICE 'M23900_GENERATION_WORKER_SCOPE=PASS';
END $probe$;
