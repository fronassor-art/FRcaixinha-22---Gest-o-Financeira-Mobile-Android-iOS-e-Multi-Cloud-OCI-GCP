-- M26100: previously expired CI lease can be claimed once with new nonce.
DO $probe$
DECLARE
 event_id uuid:='eeeeeeee-0000-4000-8000-000000000015';
 first uuid:='eeeeeeee-0000-4000-8000-000000000031';
 second uuid:='eeeeeeee-0000-4000-8000-000000000032';
 third uuid:='eeeeeeee-0000-4000-8000-000000000033';
 result text;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_invite_dispatch_ci'
    OR current_setting('frcaixinha.invite_dispatch_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M26100_DENIED: disposable CI worker only'; END IF;
 result:=public.invite_dispatch_lease_staging_ci(event_id,first);
 IF result<>'DENIED' THEN RAISE EXCEPTION 'M26100 stale nonce accepted'; END IF;
 result:=public.invite_dispatch_lease_staging_ci(event_id,second);
 IF result<>'HELD:2' THEN RAISE EXCEPTION 'M26100 first reclaim failed'; END IF;
 result:=public.invite_dispatch_lease_staging_ci(event_id,second);
 IF result<>'REPLAY:2' THEN RAISE EXCEPTION 'M26100 second lease replay failed'; END IF;
 result:=public.invite_dispatch_lease_staging_ci(event_id,third);
 IF result<>'DENIED' THEN RAISE EXCEPTION 'M26100 third worker bypassed lease'; END IF;
END $probe$;
