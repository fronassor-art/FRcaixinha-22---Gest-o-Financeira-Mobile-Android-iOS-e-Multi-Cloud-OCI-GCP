-- FR Finance M31400–M31800: synthetic SaaS capacity under tenant row lock.
-- DISPOSABLE CI ONLY; NEVER Termux port 5433, OCI or production.
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'postgres'
 OR current_setting('is_superuser')<>'on'
 OR current_setting('frcaixinha.saas_capacity_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_capacity_ci'
   AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M31400_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.saas_capacity_budgets_staging (
 tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id) ON DELETE RESTRICT,
 plan_tier varchar(20) NOT NULL REFERENCES public.platform_license_plans(tier),
 ci_only boolean NOT NULL DEFAULT true CHECK(ci_only),
 production_enabled boolean NOT NULL DEFAULT false CHECK(NOT production_enabled),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE public.saas_capacity_events_staging (
 event_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
 request_id uuid NOT NULL UNIQUE,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 admin_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 action varchar(10) NOT NULL CHECK(action IN ('HOLD','RELEASE')),
 category varchar(10) NOT NULL CHECK(category IN ('MEMBER','QUOTA')),
 quantity integer NOT NULL CHECK(quantity BETWEEN 1 AND 100),
 related_hold_event_id uuid REFERENCES public.saas_capacity_events_staging(event_id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 real_membership_created boolean NOT NULL DEFAULT false CHECK(NOT real_membership_created),
 real_quota_created boolean NOT NULL DEFAULT false CHECK(NOT real_quota_created),
 real_charge_created boolean NOT NULL DEFAULT false CHECK(NOT real_charge_created),
 CHECK(
   (action='HOLD' AND related_hold_event_id IS NULL)
   OR (action='RELEASE' AND related_hold_event_id IS NOT NULL)
 )
);
CREATE UNIQUE INDEX saas_capacity_one_release_ci
 ON public.saas_capacity_events_staging(related_hold_event_id)
 WHERE action='RELEASE';
CREATE INDEX saas_capacity_tenant_events_ci
 ON public.saas_capacity_events_staging(tenant_id,category,action,created_at);
ALTER TABLE public.saas_capacity_budgets_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_capacity_budgets_staging FORCE ROW LEVEL SECURITY;
ALTER TABLE public.saas_capacity_events_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_capacity_events_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_capacity_budgets_staging,public.saas_capacity_events_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_capacity_ci;

CREATE FUNCTION public.saas_capacity_actor_ci(p_tenant uuid,p_admin uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 RETURN EXISTS(
  SELECT 1 FROM public.tenants t JOIN public.users u ON u.id=p_admin
  JOIN public.memberships m ON m.tenant_id=t.id
   AND m.user_id=p_admin AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
  WHERE t.id=p_tenant AND t.admin_user_id=p_admin AND t.status='ATIVO'
   AND u.status='ACTIVE'
 );
END $fn$;

CREATE FUNCTION public.saas_capacity_hold_ci(
 p_request uuid,p_tenant uuid,p_admin uuid,p_category varchar,p_quantity integer
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 locked uuid; previous record; config record;
 actual_count bigint; pending_count bigint; maximum bigint; new_event uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_capacity_ci'
 OR current_setting('frcaixinha.saas_capacity_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M31400_CI_WORKER_DENIED'; END IF;
 IF p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_tenant IS NULL OR p_admin IS NULL
 OR p_category IS NULL OR p_category NOT IN ('MEMBER','QUOTA')
 OR p_quantity IS NULL OR p_quantity NOT BETWEEN 1 AND 100
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;

 -- Serializes same-tenant competing reservations, even different request IDs.
 SELECT t.id INTO locked FROM public.tenants t
 WHERE t.id=p_tenant FOR UPDATE;
 IF NOT FOUND OR NOT public.saas_capacity_actor_ci(p_tenant,p_admin)
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;

 SELECT * INTO previous FROM public.saas_capacity_events_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
  IF previous.tenant_id=p_tenant AND previous.admin_user_id=p_admin
   AND previous.action='HOLD' AND previous.category=p_category
   AND previous.quantity=p_quantity
  THEN RETURN jsonb_build_object('state','REPLAY_CI','event_id',previous.event_id,
     'real_authorized',false); END IF;
  RETURN jsonb_build_object('state','DENIED','real_authorized',false);
 END IF;

 SELECT p.tier,p.members_limit,p.quotas_limit,p.status
 INTO config FROM public.saas_capacity_budgets_staging b
 JOIN public.platform_license_plans p ON p.tier=b.plan_tier
 WHERE b.tenant_id=p_tenant AND b.ci_only AND NOT b.production_enabled;
 IF NOT FOUND OR config.status<>'ACTIVE'
 OR config.members_limit IS NULL OR config.quotas_limit IS NULL
 THEN RETURN jsonb_build_object('state','PLAN_UNVERIFIED','real_authorized',false); END IF;

 IF p_category='MEMBER' THEN
  SELECT count(*) INTO actual_count FROM public.memberships m
  WHERE m.tenant_id=p_tenant AND m.role='TENANT_MEMBER'
   AND m.status='ATIVA';
  maximum:=config.members_limit;
 ELSE
  SELECT count(*) INTO actual_count FROM public.quotas q
  WHERE q.tenant_id=p_tenant AND q.status='ATIVA';
  maximum:=config.quotas_limit;
 END IF;
 SELECT coalesce(sum(h.quantity),0) INTO pending_count
 FROM public.saas_capacity_events_staging h
 WHERE h.tenant_id=p_tenant AND h.category=p_category AND h.action='HOLD'
 AND NOT EXISTS(
  SELECT 1 FROM public.saas_capacity_events_staging r
  WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id
 );
 IF actual_count + pending_count + p_quantity > maximum
 THEN RETURN jsonb_build_object('state','CAPACITY_EXCEEDED',
   'limit',maximum,'actual',actual_count,'held',pending_count,
   'real_authorized',false); END IF;

 INSERT INTO public.saas_capacity_events_staging
 (request_id,tenant_id,admin_user_id,action,category,quantity)
 VALUES(p_request,p_tenant,p_admin,'HOLD',p_category,p_quantity)
 RETURNING event_id INTO new_event;
 RETURN jsonb_build_object('state','HELD_CI_NO_REAL_ALLOCATION',
  'event_id',new_event,'remaining',maximum-actual_count-pending_count-p_quantity,
  'real_authorized',false,'real_membership_created',false,
  'real_quota_created',false,'real_charge_created',false);
END $fn$;

CREATE FUNCTION public.saas_capacity_release_ci(
 p_request uuid,p_tenant uuid,p_admin uuid,p_hold uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE locked uuid; previous record; held record; release_event uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_capacity_ci'
 OR current_setting('frcaixinha.saas_capacity_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M31400_CI_WORKER_DENIED'; END IF;
 IF p_request IS NULL OR p_tenant IS NULL OR p_admin IS NULL OR p_hold IS NULL
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;
 SELECT t.id INTO locked FROM public.tenants t WHERE t.id=p_tenant FOR UPDATE;
 IF NOT FOUND OR NOT public.saas_capacity_actor_ci(p_tenant,p_admin)
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;
 SELECT * INTO previous FROM public.saas_capacity_events_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
  IF previous.tenant_id=p_tenant AND previous.admin_user_id=p_admin
   AND previous.action='RELEASE' AND previous.related_hold_event_id=p_hold
  THEN RETURN jsonb_build_object('state','REPLAY_RELEASE_CI',
   'real_authorized',false); END IF;
  RETURN jsonb_build_object('state','DENIED','real_authorized',false);
 END IF;
 SELECT * INTO held FROM public.saas_capacity_events_staging
 WHERE event_id=p_hold AND tenant_id=p_tenant AND admin_user_id=p_admin
   AND action='HOLD' FOR UPDATE;
 IF NOT FOUND OR EXISTS(
  SELECT 1 FROM public.saas_capacity_events_staging
  WHERE action='RELEASE' AND related_hold_event_id=p_hold
 ) THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;
 INSERT INTO public.saas_capacity_events_staging
 (request_id,tenant_id,admin_user_id,action,category,quantity,related_hold_event_id)
 VALUES(p_request,p_tenant,p_admin,'RELEASE',held.category,held.quantity,p_hold)
 RETURNING event_id INTO release_event;
 RETURN jsonb_build_object('state','RELEASED_CI',
 'event_id',release_event,'real_authorized',false);
END $fn$;

CREATE FUNCTION public.saas_capacity_events_immutable_ci()
RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN RAISE EXCEPTION 'M31400_IMMUTABLE_EVENTS_CI'; END $fn$;
CREATE TRIGGER saas_capacity_no_mutation_ci
 BEFORE UPDATE OR DELETE ON public.saas_capacity_events_staging
 FOR EACH ROW EXECUTE FUNCTION public.saas_capacity_events_immutable_ci();
REVOKE ALL ON FUNCTION public.saas_capacity_actor_ci(uuid,uuid),
 public.saas_capacity_hold_ci(uuid,uuid,uuid,varchar,integer),
 public.saas_capacity_release_ci(uuid,uuid,uuid,uuid),
 public.saas_capacity_events_immutable_ci()
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_capacity_ci;
GRANT EXECUTE ON FUNCTION
 public.saas_capacity_hold_ci(uuid,uuid,uuid,varchar,integer),
 public.saas_capacity_release_ci(uuid,uuid,uuid,uuid)
 TO frcaixinha_saas_capacity_ci;
COMMIT;
