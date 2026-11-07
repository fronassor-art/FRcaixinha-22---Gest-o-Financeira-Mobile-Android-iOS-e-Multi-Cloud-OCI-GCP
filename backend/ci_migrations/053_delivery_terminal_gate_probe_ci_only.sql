-- M26600 terminal dispatch state checks, CI-only transaction and rollback.
-- Synthetic signed SMTP-accepted receipt exists for lease 031 from M26300.
BEGIN;
DO $test$
DECLARE
 ev uuid:='eeeeeeee-0000-4000-8000-000000000015';
 accepted_lease uuid:='eeeeeeee-0000-4000-8000-000000000031';
 next_lease uuid:='eeeeeeee-0000-4000-8000-000000000034';
 result text;
BEGIN
 IF session_user<>'frcaixinha_invite_dispatch_ci'
 OR current_database()<>'frcaixinha_staging'
 OR current_setting('frcaixinha.delivery_gate_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M26600_DENIED: CI worker only'; END IF;
 IF has_function_privilege(
   current_user,'public.invite_dispatch_lease_staging_ci(uuid,uuid)','EXECUTE')
 THEN RAISE EXCEPTION 'M26600 legacy claim bypass still granted'; END IF;

 result:=public.invite_dispatch_mark_terminal_staging_ci(
 ev,accepted_lease,'CI_SMTP_ACCEPTED');
 IF result<>'QUARANTINED' THEN
  RAISE EXCEPTION 'M26600 signed SMTP accepted not suppressed';
 END IF;
 IF public.invite_dispatch_guarded_staging_ci(ev,next_lease)<>'QUARANTINED'
 THEN RAISE EXCEPTION 'M26600 allowed resend after SMTP accepted'; END IF;
 IF public.invite_dispatch_mark_terminal_staging_ci(
 ev,accepted_lease,'CI_SMTP_ACCEPTED')<>'REPLAY'
 THEN RAISE EXCEPTION 'M26600 exact replay was not idempotent'; END IF;

 -- A different lease, without a corresponding receipt proof, is denied.
 IF public.invite_dispatch_mark_terminal_staging_ci(
 ev,next_lease,'CI_SMTP_ACCEPTED')<>'DENIED'
 THEN RAISE EXCEPTION 'M26600 accepted unproved ACK'; END IF;
END $test$;
ROLLBACK;

-- Now persist a simulated ambiguous timeout: no automatic resend is possible.
DO $test$
DECLARE
 ev uuid:='eeeeeeee-0000-4000-8000-000000000015';
 past_lease uuid:='eeeeeeee-0000-4000-8000-000000000033';
 next_lease uuid:='eeeeeeee-0000-4000-8000-000000000034';
 result text;
 rejected_bad boolean:=false;
BEGIN
 result:=public.invite_dispatch_mark_terminal_staging_ci(
 ev,past_lease,'UNKNOWN_TIMEOUT');
 IF result<>'QUARANTINED' THEN RAISE EXCEPTION 'M26600 timeout not quarantined'; END IF;
 IF public.invite_dispatch_guarded_staging_ci(ev,next_lease)<>'QUARANTINED'
 THEN RAISE EXCEPTION 'M26600 replay allowed after ambiguous timeout'; END IF;
 IF public.invite_dispatch_mark_terminal_staging_ci(
 ev,past_lease,'UNKNOWN_TIMEOUT')<>'REPLAY'
 THEN RAISE EXCEPTION 'M26600 identical timeout not idempotent'; END IF;
 BEGIN
  PERFORM public.invite_dispatch_mark_terminal_staging_ci(
   ev,'eeeeeeee-0000-4000-8000-000000000031','CI_SMTP_ACCEPTED');
  rejected_bad:=true;
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M26600_DENIED:%' THEN RAISE; END IF;
 END;
 IF rejected_bad THEN RAISE EXCEPTION 'M26600 conflicting terminal update allowed'; END IF;
 IF public.invite_dispatch_guarded_staging_ci(
 'eeeeeeee-0000-4000-8000-000000000099',next_lease)<>'DENIED'
 THEN RAISE EXCEPTION 'M26600 phantom queue claim accepted'; END IF;
END $test$;
