-- M23200: run using ONLY unprivileged frcaixinha_mp_oauth_worker in disposable CI.
DO $probe$
DECLARE
 a uuid:='ffffffff-0000-4000-8000-000000000091';
 b uuid:='ffffffff-0000-4000-8000-000000000092';
 ua uuid:='ffffffff-0000-4000-8000-000000000081';
 ub uuid:='ffffffff-0000-4000-8000-000000000082';
 state text:=repeat('a',64);
 redirect text:=repeat('b',64);
 attempt uuid;
 got record;
BEGIN
 IF current_database()<>'frcaixinha_staging'
  OR session_user<>'frcaixinha_mp_oauth_worker' THEN
  RAISE EXCEPTION 'M23200 CI PROBE DENIED';
 END IF;
 IF has_table_privilege(current_user,
      'public.mp_oauth_attempts_staging','SELECT')
    OR has_table_privilege(current_user,
      'public.mp_oauth_attempts_staging','INSERT')
    OR has_table_privilege(current_user,
      'public.mp_oauth_attempts_staging','UPDATE') THEN
   RAISE EXCEPTION 'M23200 DENIED: direct access unexpectedly granted';
 END IF;
 SELECT public.mp_staging_oauth_begin(
   a,ua,state,redirect,repeat('X',43),
   'ocid1.secret.oc1.ci-oauth-pkce-ref-12345678',
   '123456','https://app.example.invalid/connect/callback',600
 ) INTO attempt;
 IF attempt IS NULL THEN
   RAISE EXCEPTION 'M23200 DENIED: state not reserved';
 END IF;

 -- Cannot consume across tenant, actor or redirect; these attempts
 -- must not mark the legitimate state as consumed.
 SELECT * INTO got
 FROM public.mp_staging_oauth_consume(b,ub,state,redirect);
 IF FOUND THEN RAISE EXCEPTION 'M23200 DENIED: cross-tenant consume'; END IF;
 SELECT * INTO got
 FROM public.mp_staging_oauth_consume(a,ub,state,redirect);
 IF FOUND THEN RAISE EXCEPTION 'M23200 DENIED: cross-actor consume'; END IF;
 SELECT * INTO got
 FROM public.mp_staging_oauth_consume(a,ua,state,repeat('c',64));
 IF FOUND THEN RAISE EXCEPTION 'M23200 DENIED: wrong redirect consumed'; END IF;

 SELECT * INTO got
 FROM public.mp_staging_oauth_consume(a,ua,state,redirect);
 IF NOT FOUND OR got.client_id<>'123456'
   OR got.pkce_challenge<>repeat('X',43)
   OR got.pkce_verifier_secret_ocid<>
      'ocid1.secret.oc1.ci-oauth-pkce-ref-12345678' THEN
   RAISE EXCEPTION 'M23200 DENIED: consumption mismatch';
 END IF;
 SELECT * INTO got
 FROM public.mp_staging_oauth_consume(a,ua,state,redirect);
 IF FOUND THEN RAISE EXCEPTION 'M23200 DENIED: replay accepted'; END IF;

 BEGIN
   PERFORM public.mp_staging_oauth_begin(
     a,ua,state,redirect,repeat('X',43),
     'ocid1.secret.oc1.ci-oauth-pkce-ref-12345678',
     '123456','https://app.example.invalid/connect/callback',600
   );
   RAISE EXCEPTION 'M23200 DENIED: duplicate state accepted';
 EXCEPTION WHEN unique_violation THEN NULL;
 END;

 BEGIN
   PERFORM public.mp_staging_oauth_begin(
     a,ub,repeat('d',64),redirect,repeat('X',43),
     'ocid1.secret.oc1.ci-oauth-pkce-ref-12345678',
     '123456','https://app.example.invalid/connect/callback',600
   );
   RAISE EXCEPTION 'M23200 DENIED: foreign admin accepted';
 EXCEPTION WHEN raise_exception THEN
   -- Distinguish our expected SQL guard from sentinel above.
   IF SQLERRM NOT LIKE 'M23200 DENIED: invalid OAuth admin%' THEN
     RAISE;
   END IF;
 END;
 RAISE NOTICE 'M23200_OAUTH_ATOMIC_STAGING=PASS';
END $probe$;
