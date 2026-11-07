-- M24300: worker read-only recovery evidence after CI generated revisions.
DO $probe$
DECLARE
 a uuid:='ffffffff-0000-4000-8000-000000000091';
 b uuid:='ffffffff-0000-4000-8000-000000000092';
 ua uuid:='ffffffff-0000-4000-8000-000000000081';
 ub uuid:='ffffffff-0000-4000-8000-000000000082';
 state varchar;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_oauth_worker' THEN
   RAISE EXCEPTION 'M24300 WORKER PROBE DENIED';
 END IF;
 IF has_table_privilege(current_user,
   'public.mp_oauth_token_revisions_staging','SELECT') THEN
   RAISE EXCEPTION 'M24300 DIRECT TABLE READ FORBIDDEN';
 END IF;
 SELECT public.mp_staging_oauth_revision_state(
    a,ua,'2002','m23600-ci-revision-a01','kms://ci/staging/opaque-v1'
 ) INTO state;
 IF state IS DISTINCT FROM 'ACTIVE' THEN
   RAISE EXCEPTION 'M24300 expected ACTIVE synthetic revision';
 END IF;
 SELECT public.mp_staging_oauth_revision_state(
    a,ua,'2002','m23600-ci-revision-a02','kms://ci/staging/opaque-v2'
 ) INTO state;
 IF state IS DISTINCT FROM 'FAILED' THEN
   RAISE EXCEPTION 'M24300 expected FAILED synthetic revision';
 END IF;
 SELECT public.mp_staging_oauth_revision_state(
    a,ua,'2002','m23600-ci-revision-a03','kms://ci/staging/opaque-v3'
 ) INTO state;
 IF state IS DISTINCT FROM 'PENDING' THEN
   RAISE EXCEPTION 'M24300 expected PENDING synthetic revision';
 END IF;
 SELECT public.mp_staging_oauth_revision_state(
    a,ua,'2002','m23600-ci-revision-a01','kms://ci/staging/WRONG-ref'
 ) INTO state;
 IF state IS NOT NULL THEN
   RAISE EXCEPTION 'M24300 mismatched protected ref exposed status';
 END IF;
 SELECT public.mp_staging_oauth_revision_state(
    a,ub,'2002','m23600-ci-revision-a01','kms://ci/staging/opaque-v1'
 ) INTO state;
 IF state IS NOT NULL THEN
   RAISE EXCEPTION 'M24300 cross-actor exposed status';
 END IF;
 SELECT public.mp_staging_oauth_revision_state(
    b,ub,'2002','m23600-ci-revision-a01','kms://ci/staging/opaque-v1'
 ) INTO state;
 IF state IS NOT NULL THEN
   RAISE EXCEPTION 'M24300 cross-tenant exposed status';
 END IF;
 SELECT public.mp_staging_oauth_revision_state(
    a,ua,'2002','m23600-ci-revision-does-not-exist','kms://ci/staging/opaque-v1'
 ) INTO state;
 IF state IS NOT NULL THEN
   RAISE EXCEPTION 'M24300 missing revision got a state';
 END IF;
 RAISE NOTICE 'M24300_OAUTH_REVISION_RECOVERY_SCOPE=PASS';
END $probe$;
