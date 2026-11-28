-- M26000: single-use recovery, invalid / expired / pending delivery, CI role only.
DO $probe$
DECLARE
 event uuid:='eeeeeeee-0000-4000-8000-000000000026'::uuid;
 new_hash varchar:='$argon2id$v=19$m=65536,t=3,p=4$'||repeat('Z',72);
 outcome varchar;
 rejected_bad boolean:=false;
BEGIN
 IF session_user<>'frcaixinha_account_recovery_ci'
    OR current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.recovery_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M26000 restricted CI reset worker required'; END IF;

 IF public.password_reset_rotate_staging_ci(repeat('e',64),new_hash,event)<>'DENIED'
  OR public.password_reset_rotate_staging_ci(repeat('f',64),new_hash,event)<>'DENIED'
  OR public.password_reset_rotate_staging_ci(repeat('a',64),new_hash,event)<>'DENIED'
 THEN RAISE EXCEPTION 'M26000 unverified, expired or absent reset token allowed'; END IF;

 outcome:=public.password_reset_rotate_staging_ci(repeat('c',64),new_hash,event);
 IF outcome<>'ROTATED' THEN
  RAISE EXCEPTION 'M26000 rotation failed';
 END IF;
 IF public.password_reset_rotate_staging_ci(repeat('c',64),new_hash,event)<>'DENIED'
    OR public.password_reset_rotate_staging_ci(repeat('d',64),new_hash,event)<>'DENIED'
 THEN RAISE EXCEPTION 'M26000 replay or second token accepted'; END IF;

 BEGIN
  PERFORM public.password_reset_rotate_staging_ci(
   repeat('c',64),'weak',event);
  rejected_bad:=true;
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M26000_DENIED:%' THEN RAISE; END IF;
 END;
 IF rejected_bad THEN RAISE EXCEPTION 'M26000 accepted malformed password hash'; END IF;
END $probe$;
