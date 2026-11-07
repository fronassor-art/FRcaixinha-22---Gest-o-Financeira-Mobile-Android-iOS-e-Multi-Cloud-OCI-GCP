-- M23600: worker-only CAS, cross-tenant and version conflict tests.
DO $probe$
DECLARE
 a uuid:='ffffffff-0000-4000-8000-000000000091';
 b uuid:='ffffffff-0000-4000-8000-000000000092';
 ua uuid:='ffffffff-0000-4000-8000-000000000081';
 ub uuid:='ffffffff-0000-4000-8000-000000000082';
 ok boolean;
 ref varchar;
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_mp_oauth_worker' THEN
    RAISE EXCEPTION 'M23600 WORKER CI DENIED';
 END IF;
 IF has_table_privilege(current_user,
    'public.mp_oauth_seller_consents_staging','SELECT')
   OR has_table_privilege(current_user,
    'public.mp_oauth_token_revisions_staging','UPDATE')
   OR has_table_privilege(current_user,
    'public.mp_oauth_token_revisions_staging','INSERT') THEN
   RAISE EXCEPTION 'M23600 DIRECT TABLE PERMISSION';
 END IF;
 SELECT public.mp_staging_oauth_eligible(a,ua,'2002') INTO ok;
 IF ok IS NOT TRUE THEN
   RAISE EXCEPTION 'M23600 valid consent not found';
 END IF;
 SELECT public.mp_staging_oauth_eligible(a,ub,'2002') INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 foreign actor eligible';
 END IF;
 SELECT public.mp_staging_oauth_stage(
   a,ua,'2002','m23600-ci-revision-a01','kms://ci/staging/opaque-v1',0
 ) INTO ok;
 IF ok IS NOT TRUE THEN
   RAISE EXCEPTION 'M23600 first revision stage';
 END IF;
 SELECT public.mp_staging_oauth_activate(
   a,ua,'2002','m23600-ci-revision-a01',repeat('a',64),repeat('b',64)
 ) INTO ok;
 IF ok IS NOT TRUE THEN
   RAISE EXCEPTION 'M23600 first revision activation';
 END IF;
 SELECT public.mp_staging_oauth_active_ref(a,ua,'2002') INTO ref;
 IF ref IS DISTINCT FROM 'kms://ci/staging/opaque-v1' THEN
   RAISE EXCEPTION 'M23600 active credential reference';
 END IF;
 SELECT public.mp_staging_oauth_activate(
   a,ua,'2002','m23600-ci-revision-a01',repeat('a',64),repeat('b',64)
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 activation replay';
 END IF;
 SELECT public.mp_staging_oauth_stage(
   a,ua,'2002','m23600-ci-revision-a02','kms://ci/staging/opaque-v2',0
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 stale generation staged';
 END IF;
 SELECT public.mp_staging_oauth_stage(
   b,ub,'2002','m23600-ci-revision-cross','kms://ci/staging/foreign',0
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 cross-tenant seller reused';
 END IF;
 SELECT public.mp_staging_oauth_stage(
   a,ub,'2002','m23600-ci-revision-badactor','kms://ci/staging/foreign',1
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 cross-actor staged';
 END IF;
 SELECT public.mp_staging_oauth_stage(
   a,ua,'2002','m23600-ci-revision-a02','kms://ci/staging/opaque-v2',1
 ) INTO ok;
 IF ok IS NOT TRUE THEN
   RAISE EXCEPTION 'M23600 second revision stage';
 END IF;
 SELECT public.mp_staging_oauth_activate(
   a,ua,'2002','m23600-ci-revision-a02','invalid',repeat('b',64)
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 malformed fingerprint accepted';
 END IF;
 SELECT public.mp_staging_oauth_fail_pending(
   a,ua,'2002','m23600-ci-revision-a02'
 ) INTO ok;
 IF ok IS NOT TRUE THEN
   RAISE EXCEPTION 'M23600 pending fail';
 END IF;
 SELECT public.mp_staging_oauth_activate(
   a,ua,'2002','m23600-ci-revision-a02',repeat('c',64),repeat('d',64)
 ) INTO ok;
 IF ok IS NOT FALSE THEN
   RAISE EXCEPTION 'M23600 failed stage activated';
 END IF;
 SELECT public.mp_staging_oauth_active_ref(a,ua,'2002') INTO ref;
 IF ref IS DISTINCT FROM 'kms://ci/staging/opaque-v1' THEN
   RAISE EXCEPTION 'M23600 active revision lost after failure';
 END IF;
 SELECT public.mp_staging_oauth_stage(
   a,ua,'2002','m23600-ci-revision-a03','kms://ci/staging/opaque-v3',1
 ) INTO ok;
 IF ok IS NOT TRUE THEN
   RAISE EXCEPTION 'M23600 pending for revocation test';
 END IF;
 RAISE NOTICE 'M23600_OAUTH_CONSENT_CAS_STAGING=PASS';
END $probe$;
