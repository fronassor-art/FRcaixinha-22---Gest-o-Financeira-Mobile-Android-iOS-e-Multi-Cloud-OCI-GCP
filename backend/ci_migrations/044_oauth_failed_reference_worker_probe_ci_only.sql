-- M24200 CI: prove failed reference is limited to a FAILED row.
DO $probe$
DECLARE
 a uuid:='ffffffff-0000-4000-8000-000000000091';
 b uuid:='ffffffff-0000-4000-8000-000000000092';
 ua uuid:='ffffffff-0000-4000-8000-000000000081';
 ub uuid:='ffffffff-0000-4000-8000-000000000082';
 ref varchar;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_mp_oauth_worker' THEN
  RAISE EXCEPTION 'M24200 PROBE DENIED: worker identity';
 END IF;
 IF has_table_privilege(current_user,
     'public.mp_oauth_token_revisions_staging','SELECT') THEN
  RAISE EXCEPTION 'M24200 DIRECT READ FORBIDDEN';
 END IF;
 SELECT public.mp_staging_oauth_failed_ref(
  a,ua,'2002','m23600-ci-revision-a02') INTO ref;
 IF ref IS DISTINCT FROM 'kms://ci/staging/opaque-v2' THEN
  RAISE EXCEPTION 'M24200 failed opaque reference unavailable';
 END IF;
 SELECT public.mp_staging_oauth_failed_ref(
  a,ua,'2002','m23600-ci-revision-a01') INTO ref;
 IF ref IS NOT NULL THEN
  RAISE EXCEPTION 'M24200 ACTIVE reference exposed to deletion';
 END IF;
 SELECT public.mp_staging_oauth_failed_ref(
  a,ua,'2002','m23600-ci-revision-a03') INTO ref;
 IF ref IS NOT NULL THEN
  RAISE EXCEPTION 'M24200 PENDING reference exposed to deletion';
 END IF;
 SELECT public.mp_staging_oauth_failed_ref(
  b,ub,'3003','m23600-ci-revision-a02') INTO ref;
 IF ref IS NOT NULL THEN
  RAISE EXCEPTION 'M24200 cross tenant reference exposed';
 END IF;
 SELECT public.mp_staging_oauth_failed_ref(
  a,ub,'2002','m23600-ci-revision-a02') INTO ref;
 IF ref IS NOT NULL THEN
  RAISE EXCEPTION 'M24200 cross actor reference exposed';
 END IF;
 RAISE NOTICE 'M24200_FAILED_REFERENCE_WORKER_SCOPE=PASS';
END $probe$;
