DO $m37438_after$
BEGIN
 IF (SELECT count(*) FROM public.users)<>1
  OR (SELECT count(*) FROM public.tenants)<>1
  OR (SELECT count(*) FROM public.memberships)<>2
  OR (SELECT count(*) FROM public.cycles)<>0
  OR (SELECT count(*) FROM public.policies)<>0
  OR (SELECT count(*) FROM public.quotas)<>0
  OR (SELECT count(*) FROM public.contributions)<>0
  OR (SELECT count(*) FROM public.cycle_contribution_price_audit)<>0
  OR (SELECT count(*) FROM public.audit_events)<>6
  OR (SELECT count(*) FROM public.audit_events WHERE tenant_id IS NULL)<>2
  OR (SELECT count(*) FROM public.audit_events WHERE tenant_id IS NOT NULL)<>4
  OR (SELECT count(*) FROM pg_constraint
      WHERE conname IN('policy_minimum_150_new','quota_minimum_150_new')
      AND convalidated)<>2
  OR (SELECT count(*) FROM pg_trigger
      WHERE tgname IN('cycle_price_immutable_row','cycle_price_immutable_truncate')
      AND tgenabled='O')<>2
 THEN RAISE EXCEPTION 'M37438: transactional cleanup postcondition failed'; END IF;
 RAISE NOTICE 'M37438_REAL_POSTGRESQL18_SYNTHETIC_CLEANUP_BEFORE_ROLLBACK=PASS';
END $m37438_after$;
