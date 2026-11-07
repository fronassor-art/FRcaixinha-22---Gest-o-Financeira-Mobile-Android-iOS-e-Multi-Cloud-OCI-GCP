-- M27100 restricted CI queue role: issue only synthetic challenge.
DO $probe$
DECLARE
 ev uuid:='eeeeeeee-0000-4000-8000-000000000015';
 good varchar:=encode(public.digest(repeat('T',48),'sha256'),'hex');
 result text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_invite_queue_ci'
 OR current_setting('frcaixinha.email_proof_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M27100_DENIED: producer CI only'; END IF;

 result:=public.invite_issue_ci_email_challenge(ev,good,300);
 IF result<>'ISSUED_CI_NOT_DELIVERED' THEN RAISE EXCEPTION 'M27100 expected sealed synthetic issue'; END IF;
 IF public.invite_issue_ci_email_challenge(ev,good,300)<>'REPLAY_CI_NOT_DELIVERED'
 THEN RAISE EXCEPTION 'M27100 issue replay invalid'; END IF;
 IF public.invite_issue_ci_email_challenge(
   'eeeeeeee-0000-4000-8000-000000000099',good,300)<>'DENIED'
 THEN RAISE EXCEPTION 'M27100 phantom outbox accepted'; END IF;
END $probe$;
