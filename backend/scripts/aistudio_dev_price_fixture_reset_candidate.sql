-- FR Finance M37437: CANDIDATE ONLY. NOT approved for local execution.
-- Exclusive original development database only. Special immutable-audit exception
-- MUST receive separate explicit approval and be run through a verified installer.
-- Does NOT create/rename/drop a database. Never apply to OCI or real accounts.
BEGIN;
SET LOCAL lock_timeout='5000ms';
SET LOCAL statement_timeout='30000ms';
SELECT pg_advisory_xact_lock(37437,2027);
DO $m37437$
DECLARE
 v_tenant uuid;v_cycle uuid;v_policy uuid;v_admin uuid;
 n bigint;v_before_users bigint;v_before_members bigint;
 v_before_sessions bigint;v_before_audit_events bigint;
 v_backup_sha constant text:='714bc50de8dfc42d25f1b9bbe54e9841df883f0d606f467015c0e153b4d9b88b';
BEGIN
 IF current_setting('frfinance.dev_cleanup_m37437',true)
    IS DISTINCT FROM 'EXPLICIT_DEV_ONLY_PURGE_APPROVED'
   OR current_setting('frfinance.m37437_verified_backup_sha',true)
    IS DISTINCT FROM v_backup_sha
 THEN RAISE EXCEPTION 'M37437: separate documented dev audit exception and backup verification required';
 END IF;
 IF NOT(
  current_database()='frcaixinha_aistudio_dev'
  AND session_user='frc_ai_owner' AND current_user='frc_ai_owner'
  AND inet_server_port()=5433
  AND current_setting('data_directory')='/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
  AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999
 ) AND NOT (
  current_database()='frcaixinha_ci'
  AND session_user='postgres' AND current_user='postgres'
  AND inet_server_port()=5432
  AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999
  AND current_setting('frfinance.m37437_ci_disposable',true)='1'
 ) THEN RAISE EXCEPTION 'M37437: wrong or unsafe PostgreSQL cluster'; END IF;
 LOCK TABLE public.cycles,public.policies,public.quotas,
  public.contributions,public.cycle_contribution_price_audit,
  public.audit_events IN ACCESS EXCLUSIVE MODE;
 IF (SELECT count(*) FROM public.policies WHERE contribution_per_quota<150)<>1
  OR (SELECT count(*) FROM public.quotas WHERE value_brl<150)<>1
  OR (SELECT count(*) FROM public.contributions WHERE amount_due<150)<>12
  OR (SELECT count(*) FROM public.cycle_contribution_price_audit
       WHERE old_price_cents<15000 OR requested_price_cents<15000)<>1
  OR (SELECT count(*) FROM public.pix_payment_intents)<>0
  OR (SELECT count(*) FROM public.ledger_transactions)<>0
  OR (SELECT count(*) FROM public.ledger_entries)<>0
  OR (SELECT count(*) FROM public.loans)<>0
  OR (SELECT count(*) FROM public.contributions
       WHERE amount_paid>0 OR paid_at IS NOT NULL OR payment_status='QUITADA')<>0
  OR (SELECT count(*) FROM public.tenants)<>1
  OR (SELECT count(*) FROM public.users)<>1
  OR (SELECT count(*) FROM public.memberships)<>2
 THEN RAISE EXCEPTION 'M37437: baseline drift or financial trace; no changes allowed'; END IF;
 SELECT p.tenant_id,p.cycle_id,p.id INTO v_tenant,v_cycle,v_policy
 FROM public.policies p WHERE p.contribution_per_quota<150;
 SELECT t.admin_user_id INTO v_admin FROM public.tenants t WHERE t.id=v_tenant;
 IF v_tenant IS NULL OR v_cycle IS NULL OR v_policy IS NULL OR v_admin IS NULL
  OR (SELECT count(*) FROM public.cycles c
      WHERE c.id=v_cycle AND c.tenant_id=v_tenant AND c.year=2027 AND c.status='ABERTO')<>1
  OR (SELECT count(*) FROM public.cycles)<>1
  OR (SELECT count(*) FROM public.policies)<>1
  OR (SELECT count(*) FROM public.quotas)<>1
  OR (SELECT count(*) FROM public.contributions)<>12
  OR (SELECT count(*) FROM public.cycle_contribution_price_audit)<>1
  OR (SELECT count(*) FROM public.cycle_opening_audit)<>0
  OR (SELECT count(*) FROM public.audit_events a WHERE a.tenant_id=v_tenant)<>3
  OR (SELECT count(*) FROM public.contributions c
       WHERE c.tenant_id=v_tenant AND c.cycle_id=v_cycle AND c.amount_due<150
        AND c.amount_paid=0 AND c.paid_at IS NULL
        AND c.payment_status='PENDENTE')<>12
  OR (SELECT count(*) FROM public.quotas q
       WHERE q.tenant_id=v_tenant AND q.value_brl<150)<>1
  OR (SELECT count(*) FROM public.cycle_contribution_price_audit a
       WHERE a.tenant_id=v_tenant AND a.cycle_id=v_cycle
         AND a.policy_id=v_policy AND a.change_status='PENDING_REVIEW')<>1
 THEN RAISE EXCEPTION 'M37437: synthetic-only cycle scope not proven'; END IF;
 IF EXISTS (
  SELECT 1 FROM public.audit_events a WHERE a.tenant_id=v_tenant
   AND (
    strpos(a.reason,'100')>0 OR strpos(a.evidence_ref,'100')>0
    OR a.object_id IN (v_cycle::text,v_policy::text)
    OR a.object_id IN (
     SELECT c.id::text FROM public.contributions c
     WHERE c.cycle_id=v_cycle AND c.tenant_id=v_tenant
    )
   )
 ) THEN RAISE EXCEPTION 'M37437: general audit events reference legacy price/cycle; review required'; END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_trigger
     WHERE tgrelid='public.cycle_contribution_price_audit'::regclass
       AND tgname IN('cycle_price_immutable_row','cycle_price_immutable_truncate')
       AND tgenabled='O')<>2
  OR (SELECT count(*) FROM pg_catalog.pg_constraint
      WHERE conname IN('policy_minimum_150_new','quota_minimum_150_new'))<>2
 THEN RAISE EXCEPTION 'M37437: immutable audit or contractual constraints not verified'; END IF;
 SELECT count(*) INTO v_before_users FROM public.users;
 SELECT count(*) INTO v_before_members FROM public.memberships;
 SELECT count(*) INTO v_before_sessions FROM public.sessions;
 SELECT count(*) INTO v_before_audit_events FROM public.audit_events;
 -- Synthetic-only cleanup. All steps are one transaction; any failure rolls back.
 DELETE FROM public.contributions
 WHERE tenant_id=v_tenant AND cycle_id=v_cycle AND amount_due<150;
 GET DIAGNOSTICS n=ROW_COUNT;
 IF n<>12 THEN RAISE EXCEPTION 'M37437: contribution delete count mismatch'; END IF;
 DELETE FROM public.quotas WHERE tenant_id=v_tenant AND value_brl<150;
 GET DIAGNOSTICS n=ROW_COUNT;
 IF n<>1 THEN RAISE EXCEPTION 'M37437: quota delete count mismatch'; END IF;
 -- Explicit, exceptional LOCAL DEV reset of the single append-only price audit.
 -- The pre-reset audit remains recoverable from the verified encrypted backup.
 -- ACCESS EXCLUSIVE lock prevents concurrent readers/writers during this exception.
 ALTER TABLE public.cycle_contribution_price_audit
  DISABLE TRIGGER cycle_price_immutable_row;
 DELETE FROM public.cycle_contribution_price_audit
 WHERE tenant_id=v_tenant AND cycle_id=v_cycle AND policy_id=v_policy
  AND change_status='PENDING_REVIEW';
 GET DIAGNOSTICS n=ROW_COUNT;
 IF n<>1 THEN RAISE EXCEPTION 'M37437: protected audit count mismatch'; END IF;
 ALTER TABLE public.cycle_contribution_price_audit
  ENABLE TRIGGER cycle_price_immutable_row;
 DELETE FROM public.policies WHERE tenant_id=v_tenant
  AND cycle_id=v_cycle AND id=v_policy AND contribution_per_quota<150;
 GET DIAGNOSTICS n=ROW_COUNT;
 IF n<>1 THEN RAISE EXCEPTION 'M37437: policy delete count mismatch'; END IF;
 DELETE FROM public.cycles WHERE tenant_id=v_tenant AND id=v_cycle AND year=2027;
 GET DIAGNOSTICS n=ROW_COUNT;
 IF n<>1 THEN RAISE EXCEPTION 'M37437: cycle delete count mismatch'; END IF;
 -- Revalidate the original minimum after the development-only fixture is gone.
 ALTER TABLE public.policies VALIDATE CONSTRAINT policy_minimum_150_new;
 ALTER TABLE public.quotas VALIDATE CONSTRAINT quota_minimum_150_new;
 -- Keep a non-monetary, append-only evidence event of the exceptional reset.
 INSERT INTO public.audit_events
  (actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref)
 VALUES
  (v_admin,'TENANT_ADMIN',v_tenant,'DEV_SYNTHETIC_RESET_M37437',
   'DEV_ONLY_CYCLE','M37437_SYNTHETIC_2027',
   'One-time consented removal of synthetic, unpaid cycle fixtures. Original evidence held in encrypted private backup.',
   'BACKUP_SHA256:'||v_backup_sha);
 IF (SELECT count(*) FROM public.users)<>v_before_users
  OR (SELECT count(*) FROM public.memberships)<>v_before_members
  OR (SELECT count(*) FROM public.sessions)<>v_before_sessions
  OR (SELECT count(*) FROM public.audit_events)<>v_before_audit_events+1
  OR (SELECT count(*) FROM public.cycles)<>0
  OR (SELECT count(*) FROM public.policies)<>0
  OR (SELECT count(*) FROM public.quotas)<>0
  OR (SELECT count(*) FROM public.contributions)<>0
  OR (SELECT count(*) FROM public.cycle_contribution_price_audit)<>0
  OR (SELECT count(*) FROM pg_catalog.pg_trigger
      WHERE tgrelid='public.cycle_contribution_price_audit'::regclass
       AND tgname IN('cycle_price_immutable_row','cycle_price_immutable_truncate')
       AND tgenabled='O')<>2
 THEN RAISE EXCEPTION 'M37437: postconditions failed; rollback required'; END IF;
END $m37437$;
COMMIT;
