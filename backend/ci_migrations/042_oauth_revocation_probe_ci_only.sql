-- M23600 after DBA revokes synthetic consent: no active token ref or CAS.
DO $probe$
DECLARE
 a uuid:='ffffffff-0000-4000-8000-000000000091';
 ua uuid:='ffffffff-0000-4000-8000-000000000081';
 ok boolean;
 ref varchar;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
    RAISE EXCEPTION 'M23600 POST REVOCATION CI DENIED';
 END IF;
 SELECT public.mp_staging_oauth_eligible(a,ua,'2002') INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 revoked consent eligible';
 END IF;
 SELECT public.mp_staging_oauth_activate(
   a,ua,'2002','m23600-ci-revision-a03',repeat('e',64),repeat('f',64)
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 post-revocation CAS accepted';
 END IF;
 SELECT public.mp_staging_oauth_active_ref(a,ua,'2002') INTO ref;
 IF ref IS NOT NULL THEN
   RAISE EXCEPTION 'M23600 revoked credential still available';
 END IF;
 SELECT public.mp_staging_oauth_stage(
   a,ua,'2002','m23600-ci-revision-a04','kms://ci/staging/opaque-v4',1
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 post-revocation stage allowed';
 END IF;
 RAISE NOTICE 'M23600_POST_REVOCATION_DENIED=PASS';
END $probe$;
