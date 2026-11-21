-- M32300: synthetic past approved payment and entitlement, disposable CI only.
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('frcaixinha.saas_renewal_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M32300_FIXTURE_DISPOSABLE_ONLY'; END IF;
END $guard$;
INSERT INTO public.saas_payment_intents
(id,preparation_id,tenant_id,admin_user_id,price_version_id,
expected_amount_cents,external_reference,idempotency_key,
platform_collector_id,provider_payment_id,live_mode,status)
SELECT 'daba0000-0000-4000-8000-000000000091',s.id,s.tenant_id,
s.admin_user_id,s.price_version_id,1000,'m32300-ci-fake-existing',
'm32300-ci-old-intent','123456','32300001',false,'APPROVED'
FROM public.saas_subscription_preparations s
WHERE s.tenant_id='daba0000-0000-4000-8000-000000000010'
AND s.admin_user_id='daba0000-0000-4000-8000-000000000001'
AND s.status='PENDING_PAYMENT';
INSERT INTO public.saas_license_entitlements
(id,preparation_id,payment_intent_id,tenant_id,plan_tier,valid_from,valid_until)
SELECT 'daba0000-0000-4000-8000-000000000090',i.preparation_id,i.id,
i.tenant_id,s.plan_tier,clock_timestamp()-interval '1 day',
clock_timestamp()+interval '15 days'
FROM public.saas_payment_intents i
JOIN public.saas_subscription_preparations s ON s.id=i.preparation_id
WHERE i.id='daba0000-0000-4000-8000-000000000091';
