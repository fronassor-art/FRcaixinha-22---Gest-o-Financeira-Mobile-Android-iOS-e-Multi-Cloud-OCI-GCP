-- M27100 CI-only verifier: token response is NOT identity attestation.
DO $probe$
DECLARE
 ev uuid:='eeeeeeee-0000-4000-8000-000000000015';
 result text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_email_proof_ci'
 OR current_setting('frcaixinha.email_proof_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M27100_DENIED: verifier CI only'; END IF;
 IF public.invite_consume_ci_email_challenge(
    'eeeeeeee-0000-4000-8000-000000000099',repeat('T',64))<>'DENIED'
 THEN RAISE EXCEPTION 'M27100 unknown event accepted'; END IF;
 IF public.invite_consume_ci_email_challenge(ev,repeat('U',64))<>'DENIED'
 THEN RAISE EXCEPTION 'M27100 forged token accepted'; END IF;
 result:=public.invite_consume_ci_email_challenge(ev,repeat('T',64));
 IF result<>'CI_TOKEN_CONSUMED_NOT_PROOF'
 THEN RAISE EXCEPTION 'M27100 synthetic token failed'; END IF;
 IF public.invite_consume_ci_email_challenge(ev,repeat('T',64))<>'DENIED'
 THEN RAISE EXCEPTION 'M27100 consumed token replay accepted'; END IF;
 IF public.invite_consume_ci_email_challenge(ev,repeat('U',64))<>'DENIED'
 THEN RAISE EXCEPTION 'M27100 wrong token after consume accepted'; END IF;
END $probe$;
