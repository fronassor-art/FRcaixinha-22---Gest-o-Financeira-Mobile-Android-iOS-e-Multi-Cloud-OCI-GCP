-- M26300 negative and replay tests for CI-only signed receipt relay.
DO $probe$
DECLARE
 event_id uuid:='eeeeeeee-0000-4000-8000-000000000015';
 lease uuid:='eeeeeeee-0000-4000-8000-000000000031';
 receipt uuid:='eeeeeeee-0000-4000-8000-000000000041';
 alternative uuid:='eeeeeeee-0000-4000-8000-000000000042';
 outcome text;
 rejected_bad boolean;
BEGIN
 IF session_user<>'frcaixinha_mail_receipt_ci'
  OR current_database()<>'frcaixinha_staging'
  OR current_setting('frcaixinha.mail_receipt_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M26300_DENIED: CI worker required'; END IF;

 outcome:=public.invite_record_mock_receipt_staging_ci(
  event_id,lease,receipt,'CI_SMTP_ACCEPTED',repeat('a',64));
 IF outcome NOT LIKE 'RECORDED:%' THEN RAISE EXCEPTION 'M26300 first receipt not recorded'; END IF;
 IF public.invite_record_mock_receipt_staging_ci(
  event_id,lease,receipt,'CI_SMTP_ACCEPTED',repeat('a',64))
  <>replace(outcome,'RECORDED:','REPLAY:') THEN
  RAISE EXCEPTION 'M26300 exact replay not idempotent';
 END IF;

 rejected_bad:=false;
 BEGIN
  PERFORM public.invite_record_mock_receipt_staging_ci(
   event_id,lease,receipt,'CI_BOUNCE',repeat('a',64));
  rejected_bad:=true;
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M26300_DENIED:%' THEN RAISE; END IF;
 END;
 IF rejected_bad THEN RAISE EXCEPTION 'M26300 conflicting payload allowed'; END IF;

 rejected_bad:=false;
 BEGIN
  PERFORM public.invite_record_mock_receipt_staging_ci(
   event_id,lease,alternative,'CI_SMTP_ACCEPTED',repeat('b',64));
  rejected_bad:=true;
 EXCEPTION WHEN unique_violation THEN
  rejected_bad:=false;
 END;
 IF rejected_bad THEN RAISE EXCEPTION 'M26300 duplicate lease kind allowed'; END IF;

 IF public.invite_record_mock_receipt_staging_ci(
  event_id,'eeeeeeee-0000-4000-8000-000000000099',
  alternative,'CI_BOUNCE',repeat('b',64))<>'DENIED'
 THEN RAISE EXCEPTION 'M26300 missing lease accepted'; END IF;

 rejected_bad:=false;
 BEGIN
  PERFORM public.invite_record_mock_receipt_staging_ci(
   event_id,lease,alternative,'CI_DELIVERED',repeat('b',64));
  rejected_bad:=true;
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M26300_DENIED:%' THEN RAISE; END IF;
 END;
 IF rejected_bad THEN RAISE EXCEPTION 'M26300 false delivery claim allowed'; END IF;
END $probe$;
