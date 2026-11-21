-- M31400: synthetic plan capacity budgets for two isolated CI tenants only.
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('frcaixinha.saas_capacity_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M31400_FIXTURE_NOT_DISPOSABLE'; END IF;
END $guard$;
INSERT INTO public.saas_capacity_budgets_staging(tenant_id,plan_tier)
VALUES
 ('daba0000-0000-4000-8000-000000000010','ESSENCIAL'),
 ('daba0000-0000-4000-8000-000000000020','ESSENCIAL');
