-- M26100: isolated worker may claim, replay, but NEVER send an email.
DO $probe$
DECLARE
 event_id uuid:='eeeeeeee-0000-4000-8000-000000000015';
 first_lease uuid:='eeeeeeee-0000-4000-8000-000000000031';
 alternate uuid:='eeeeeeee-0000-4000-8000-000000000032';
 result text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_invite_dispatch_ci'
    OR current_setting('frcaixinha.invite_dispatch_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M26100_DENIED: disposable claim worker only'; END IF;
 result:=public.invite_dispatch_lease_staging_ci(event_id,first_lease);
 IF result<>'HELD:1' THEN RAISE EXCEPTION 'M26100 initial claim not held: %',result; END IF;
 result:=public.invite_dispatch_lease_staging_ci(event_id,first_lease);
 IF result<>'REPLAY:1' THEN RAISE EXCEPTION 'M26100 exact replay rejected'; END IF;
 result:=public.invite_dispatch_lease_staging_ci(event_id,alternate);
 IF result<>'DENIED' THEN RAISE EXCEPTION 'M26100 competing worker accepted'; END IF;
 result:=public.invite_dispatch_lease_staging_ci(
  'eeeeeeee-0000-4000-8000-000000000099',alternate);
 IF result<>'DENIED' THEN RAISE EXCEPTION 'M26100 phantom event accepted'; END IF;
END $probe$;
