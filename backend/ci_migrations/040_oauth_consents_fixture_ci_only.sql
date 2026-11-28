-- M23600: DBA-authored synthetic consents. GitHub CI disposable DB ONLY.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on' THEN
   RAISE EXCEPTION 'M23600 FIXTURE DENIED';
 END IF;
END $guard$;
INSERT INTO public.mp_oauth_seller_consents_staging(
 tenant_id,actor_user_id,seller_id,consent_version,approved_at
) VALUES
 ('ffffffff-0000-4000-8000-000000000091',
  'ffffffff-0000-4000-8000-000000000081',
  '2002','M23600-CI-CONSENT-V1',clock_timestamp()),
 ('ffffffff-0000-4000-8000-000000000092',
  'ffffffff-0000-4000-8000-000000000082',
  '3003','M23600-CI-CONSENT-V1',clock_timestamp());
COMMIT;
