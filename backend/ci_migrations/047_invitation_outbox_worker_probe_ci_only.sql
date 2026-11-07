-- M25900 worker: assertions run as restricted frcaixinha_invite_queue_ci.
DO $probe$
DECLARE
 inv uuid:='eeeeeeee-0000-4000-8000-000000000014'::uuid;
 ev uuid:='eeeeeeee-0000-4000-8000-000000000015'::uuid;
 other uuid:='eeeeeeee-0000-4000-8000-000000000016'::uuid;
 digest varchar;
 response text;
 replay text;
 allowed_bad boolean:=false;
BEGIN
 IF session_user<>'frcaixinha_invite_queue_ci'
    OR current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.invite_queue_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M25900 restricted CI worker only'; END IF;

 digest:=encode(public.digest('future-admin-m25900@example.com','sha256'),'hex');
 response:=public.invite_enqueue_held_staging_ci(
   inv,ev,digest,'ci://encrypted-envelope-reference-1234');
 IF response NOT LIKE 'NEW:%' THEN
   RAISE EXCEPTION 'M25900 expected NEW but got %',response;
 END IF;
 replay:=public.invite_enqueue_held_staging_ci(
   inv,ev,digest,'ci://encrypted-envelope-reference-1234');
 IF replay<>replace(response,'NEW:','REPLAY:') THEN
   RAISE EXCEPTION 'M25900 idempotent exact event replay failed';
 END IF;

 BEGIN
  PERFORM public.invite_enqueue_held_staging_ci(
   inv,other,digest,'ci://encrypted-envelope-reference-1234');
  allowed_bad:=true;
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M25900_DENIED:%' THEN RAISE; END IF;
 END;
 IF allowed_bad THEN RAISE EXCEPTION 'M25900 allowed new event for existing invitation'; END IF;

 allowed_bad:=false;
 BEGIN
  PERFORM public.invite_enqueue_held_staging_ci(
   inv,ev,repeat('a',64),'ci://encrypted-envelope-reference-1234');
  allowed_bad:=true;
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M25900_DENIED:%' THEN RAISE; END IF;
 END;
 IF allowed_bad THEN RAISE EXCEPTION 'M25900 recipient digest mismatch allowed'; END IF;

 allowed_bad:=false;
 BEGIN
  PERFORM public.invite_enqueue_held_staging_ci(
   inv,ev,digest,'https://token-in-plaintext.example.com');
  allowed_bad:=true;
 EXCEPTION WHEN OTHERS THEN
  IF SQLERRM NOT LIKE 'M25900_DENIED:%' THEN RAISE; END IF;
 END;
 IF allowed_bad THEN RAISE EXCEPTION 'M25900 non-CI envelope ref allowed'; END IF;
END $probe$;
