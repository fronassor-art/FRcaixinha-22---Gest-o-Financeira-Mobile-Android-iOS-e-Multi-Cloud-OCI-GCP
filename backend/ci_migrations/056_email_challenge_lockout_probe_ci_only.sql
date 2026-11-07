-- M27101: CI verifier proves 3 invalid guesses exhaust a challenge.
-- Test fixture is synthetic, reset by disposable DBA before this probe.
DO $probe$
DECLARE
 ev uuid:='eeeeeeee-0000-4000-8000-000000000015';
 result text;
 attempt integer;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_email_proof_ci'
 OR current_setting('frcaixinha.email_proof_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M27101_DENIED: CI verifier required'; END IF;
 FOR attempt IN 1..3 LOOP
   result:=public.invite_consume_ci_email_challenge(ev,repeat('U',48));
   IF result<>'DENIED' THEN RAISE EXCEPTION 'M27101 wrong token accepted'; END IF;
 END LOOP;
 result:=public.invite_consume_ci_email_challenge(ev,repeat('T',48));
 IF result<>'DENIED' THEN RAISE EXCEPTION 'M27101 valid token bypassed exhausted attempts'; END IF;
END $probe$;
