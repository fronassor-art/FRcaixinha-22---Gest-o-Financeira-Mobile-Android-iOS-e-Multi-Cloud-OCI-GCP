-- M41320 candidate: existing canonical schema, disposable PG18 CI ONLY.
BEGIN;
DO $$ BEGIN
 IF current_database()<>'frcaixinha_ci' OR session_user<>'postgres' OR current_user<>'postgres'
 OR inet_server_port()<>5432 OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
 OR current_setting('frfinance.m41320_ci',true) IS DISTINCT FROM 'DISPOSABLE_ONLY'
 THEN RAISE EXCEPTION 'M41320_DISPOSABLE_ONLY'; END IF;
END $$;
ALTER TABLE public.cycles DROP CONSTRAINT uq_tenant_cycle_year;
ALTER TABLE public.contributions DROP CONSTRAINT uq_membership_competence;
ALTER TABLE public.contributions ADD UNIQUE(tenant_id,cycle_id,membership_id,competence);
ALTER TABLE public.cycles ADD UNIQUE(id,tenant_id);
ALTER TABLE public.contributions ADD UNIQUE(id,tenant_id,cycle_id);
-- M41330: canonical ledger, explicit cycle scope; legacy rows remain unscoped.
ALTER TABLE public.ledger_accounts ADD COLUMN cycle_id uuid, ADD COLUMN cycle_account_kind text;
ALTER TABLE public.ledger_accounts ADD FOREIGN KEY(cycle_id,tenant_id) REFERENCES public.cycles(id,tenant_id);
ALTER TABLE public.ledger_accounts ADD UNIQUE(tenant_id,cycle_id,cycle_account_kind);
ALTER TABLE public.ledger_accounts ADD CHECK(
 (cycle_id IS NULL AND cycle_account_kind IS NULL) OR
 (cycle_id IS NOT NULL AND cycle_account_kind IS NOT NULL AND
  ((cycle_account_kind='MANUAL_DOCUMENTED' AND account_type='ASSET') OR
   (cycle_account_kind='MEMBER_CAPITAL' AND account_type='EQUITY'))));
ALTER TABLE public.ledger_transactions ADD COLUMN cycle_id uuid;
ALTER TABLE public.ledger_transactions ADD FOREIGN KEY(cycle_id,tenant_id) REFERENCES public.cycles(id,tenant_id);
CREATE FUNCTION public.fr_v23_ledger_scope_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF (OLD.tenant_id,OLD.cycle_id) IS DISTINCT FROM (NEW.tenant_id,NEW.cycle_id)
 THEN RAISE EXCEPTION 'ledger scope immutable' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='ledger_accounts' THEN
  IF OLD.cycle_account_kind IS DISTINCT FROM NEW.cycle_account_kind THEN RAISE EXCEPTION 'ledger kind immutable' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER fr_v23_account_scope BEFORE UPDATE ON public.ledger_accounts FOR EACH ROW EXECUTE FUNCTION public.fr_v23_ledger_scope_immutable();
CREATE TRIGGER fr_v23_transaction_scope BEFORE UPDATE ON public.ledger_transactions FOR EACH ROW EXECUTE FUNCTION public.fr_v23_ledger_scope_immutable();
CREATE FUNCTION public.fr_v23_entry_scope() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE ta uuid;tc uuid;aa uuid;ac uuid;
BEGIN
 SELECT tenant_id,cycle_id INTO ta,tc FROM public.ledger_transactions WHERE id=NEW.transaction_id;
 SELECT tenant_id,cycle_id INTO aa,ac FROM public.ledger_accounts WHERE id=NEW.account_id;
 IF ta IS NULL OR aa IS NULL OR ta<>NEW.tenant_id OR aa<>NEW.tenant_id OR tc IS DISTINCT FROM ac
 THEN RAISE EXCEPTION 'cross-cycle ledger entry' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER fr_v23_entry_scope BEFORE INSERT OR UPDATE ON public.ledger_entries FOR EACH ROW EXECUTE FUNCTION public.fr_v23_entry_scope();
-- M41340: independent prospective prices in this guarded CI fixture only.
ALTER TABLE public.platform_license_price_versions ALTER COLUMN annual_price DROP EXPRESSION IF EXISTS;
ALTER TABLE public.platform_license_price_versions ALTER COLUMN annual_price SET NOT NULL;
ALTER TABLE public.platform_license_price_versions ADD CHECK(annual_price>0);
UPDATE public.platform_license_plans SET members_limit=200,quotas_limit=400
 WHERE tier='AMPLIADO' AND status='BLOCKED_PENDING_CEILING';
CREATE TABLE public.fr_v23_policy(
 cycle_id uuid PRIMARY KEY,tenant_id uuid NOT NULL,request_id uuid NOT NULL,
 actor uuid NOT NULL REFERENCES public.users(id),document_id uuid NOT NULL REFERENCES public.contract_documents(id),
 admin_acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id),
 policy_hash text NOT NULL CHECK(policy_hash ~ '^[0-9a-f]{64}$'),
 accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 first_due date NOT NULL,last_due date NOT NULL,quota_cents bigint NOT NULL CHECK(quota_cents BETWEEN 1 AND 100000000),
 admin_bps int NOT NULL CHECK(admin_bps BETWEEN 0 AND 10000),late_days int NOT NULL CHECK(late_days BETWEEN 1 AND 3650),
 late_competences int NOT NULL CHECK(late_competences BETWEEN 1 AND 120),
 mode text NOT NULL CHECK(mode IN ('MANUAL','MERCADO_PAGO','HYBRID')),
 UNIQUE(tenant_id,request_id),FOREIGN KEY(cycle_id,tenant_id) REFERENCES public.cycles(id,tenant_id)
);
-- Dates covered by the accepted hash cannot be edited in place.
CREATE FUNCTION public.fr_v23_cycle_dates_immutable() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF (OLD.tenant_id,OLD.year,OLD.start_date,OLD.end_date,OLD.settlement_date) IS DISTINCT FROM
 (NEW.tenant_id,NEW.year,NEW.start_date,NEW.end_date,NEW.settlement_date)
 AND EXISTS(SELECT 1 FROM public.fr_v23_policy p WHERE p.cycle_id=OLD.id)
 THEN RAISE EXCEPTION 'accepted dates immutable' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER fr_v23_cycle_dates BEFORE UPDATE ON public.cycles FOR EACH ROW EXECUTE FUNCTION public.fr_v23_cycle_dates_immutable();
CREATE TABLE public.fr_v23_member_consent(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),cycle_id uuid NOT NULL REFERENCES public.fr_v23_policy(cycle_id),
 membership_id uuid NOT NULL REFERENCES public.memberships(id),acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id),
 actor uuid NOT NULL REFERENCES public.users(id),policy_hash text NOT NULL CHECK(policy_hash ~ '^[0-9a-f]{64}$'),
 joined date NOT NULL,quotas int NOT NULL CHECK(quotas BETWEEN 1 AND 400),accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(cycle_id,membership_id),UNIQUE(id,cycle_id,membership_id)
);
CREATE TABLE public.fr_v23_admission(
 cycle_id uuid NOT NULL REFERENCES public.fr_v23_policy(cycle_id),membership_id uuid NOT NULL REFERENCES public.memberships(id),
 acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id),consent_id uuid NOT NULL,
 FOREIGN KEY(consent_id,cycle_id,membership_id) REFERENCES public.fr_v23_member_consent(id,cycle_id,membership_id),
 joined date NOT NULL,
 quotas int NOT NULL CHECK(quotas BETWEEN 1 AND 400),PRIMARY KEY(cycle_id,membership_id)
);
CREATE TABLE public.fr_v23_receipts(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,cycle_id uuid NOT NULL,contribution_id uuid NOT NULL,
 request_id uuid NOT NULL,actor uuid NOT NULL REFERENCES public.users(id),cents bigint NOT NULL CHECK(cents BETWEEN 1 AND 100000000),
 method text NOT NULL CHECK(method IN ('DINHEIRO','PIX_EXTERNO','TRANSFERENCIA','DEPOSITO')),
 occurred date NOT NULL,reference text NOT NULL CHECK(length(reference) BETWEEN 3 AND 100),
 evidence text NOT NULL CHECK(length(evidence) BETWEEN 3 AND 160),recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,request_id),UNIQUE(tenant_id,reference),UNIQUE(id,tenant_id),
 FOREIGN KEY(contribution_id,tenant_id,cycle_id) REFERENCES public.contributions(id,tenant_id,cycle_id)
);
CREATE TABLE public.fr_v23_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),receipt_id uuid NOT NULL,tenant_id uuid NOT NULL,request_id uuid NOT NULL,
 actor uuid NOT NULL REFERENCES public.users(id),action text NOT NULL CHECK(action IN ('CONFIRM','CONTEST','REVERSE')),
 occurred date NOT NULL,evidence text NOT NULL CHECK(length(evidence) BETWEEN 3 AND 160),
 ledger_id uuid REFERENCES public.ledger_transactions(id),recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,request_id),UNIQUE(receipt_id,action),
 FOREIGN KEY(receipt_id,tenant_id) REFERENCES public.fr_v23_receipts(id,tenant_id),
 CHECK((action='CONTEST')=(ledger_id IS NULL))
);
-- M41350: append-only managerial reservation; never a payout authorization.
CREATE TABLE public.fr_v23_reservation_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),tenant_id uuid NOT NULL,cycle_id uuid NOT NULL,
 request_id uuid NOT NULL,actor uuid NOT NULL REFERENCES public.users(id),
 action text NOT NULL CHECK(action IN ('HOLD','RELEASE')),cents bigint NOT NULL CHECK(cents>0),
 related_hold uuid,reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 8 AND 160 AND reason=btrim(reason)),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,request_id),UNIQUE(id,tenant_id,cycle_id),UNIQUE(related_hold),
 FOREIGN KEY(cycle_id,tenant_id) REFERENCES public.cycles(id,tenant_id),
 FOREIGN KEY(related_hold,tenant_id,cycle_id) REFERENCES public.fr_v23_reservation_events(id,tenant_id,cycle_id),
 CHECK((action='HOLD')=(related_hold IS NULL))
);
CREATE FUNCTION public.fr_v23_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN RAISE EXCEPTION 'immutable V23'; END $$;
DO $$ DECLARE t regclass; BEGIN
 FOR t IN SELECT unnest(ARRAY['public.fr_v23_policy'::regclass,'public.fr_v23_member_consent'::regclass,'public.fr_v23_admission'::regclass,'public.fr_v23_receipts'::regclass,'public.fr_v23_events'::regclass,'public.fr_v23_reservation_events'::regclass]) LOOP
 EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON %s FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role',t);
 EXECUTE format('CREATE TRIGGER immutable_row BEFORE UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION public.fr_v23_immutable()',t);
 EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION public.fr_v23_immutable()',t);
 END LOOP;
END $$;
CREATE FUNCTION public.fr_v23_actor(p_token text,p_tenant uuid,p_admin boolean)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;
BEGIN
 IF p_token IS NULL OR length(p_token) NOT BETWEEN 32 AND 512 THEN RAISE EXCEPTION 'denied' USING ERRCODE='42501'; END IF;
 SELECT s.user_id INTO a FROM public.sessions s JOIN public.users u ON u.id=s.user_id JOIN public.tenants t ON t.id=s.active_tenant_id
 JOIN public.memberships m ON m.tenant_id=t.id AND m.user_id=s.user_id AND m.role=s.active_role
 WHERE s.token_hash=encode(public.digest(p_token,'sha256'),'hex') AND s.active_tenant_id=p_tenant
 AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() AND u.status='ACTIVE' AND t.status='ATIVO' AND m.status='ATIVA'
 AND ((s.active_role='TENANT_ADMIN' AND t.admin_user_id=s.user_id) OR (NOT p_admin AND s.active_role='TENANT_MEMBER'))
 FOR SHARE OF s,u,t,m;
 IF a IS NULL THEN RAISE EXCEPTION 'denied' USING ERRCODE='42501'; END IF; RETURN a;
END $$;
-- Canonical license: a reconciled, in-term synthetic entitlement linked to its exact
-- preparation, price version, Contract A and payer. Never treats a pending payment as a license.
CREATE FUNCTION public.fr_v23_license(p_tenant uuid,p_admin uuid)
RETURNS TABLE(members_limit int,quotas_limit int) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE row_data record;n int:=0;
BEGIN
 FOR row_data IN SELECT pl.members_limit ml,pl.quotas_limit ql
 FROM public.saas_license_entitlements e
 JOIN public.saas_subscription_preparations sp ON sp.id=e.preparation_id
 JOIN public.saas_payment_intents pi ON pi.id=e.payment_intent_id AND pi.preparation_id=sp.id
 JOIN public.platform_license_plans pl ON pl.tier=e.plan_tier
 JOIN public.platform_license_price_versions pv ON pv.id=sp.price_version_id AND pv.plan_tier=pl.tier
 JOIN public.contract_acceptances ca ON ca.id=sp.contract_acceptance_id
 JOIN public.contract_documents d ON d.id=ca.document_id
 WHERE e.tenant_id=p_tenant AND sp.tenant_id=p_tenant AND pi.tenant_id=p_tenant
 AND sp.admin_user_id=p_admin AND pi.admin_user_id=p_admin AND ca.user_id=p_admin
 AND ca.document_kind='PLATFORM_LICENSE' AND ca.tenant_id IS NULL AND d.document_kind='PLATFORM_LICENSE'
 AND d.published_at IS NOT NULL AND ca.accepted_at>=d.published_at
 AND e.plan_tier=sp.plan_tier AND pi.price_version_id=pv.id
 AND e.status='ACTIVE' AND e.valid_from<=now() AND e.valid_until>now()
 AND sp.status NOT IN ('CANCELED','PAUSED_NO_PAYMENT') AND pi.status='APPROVED'
 AND pi.provider='MERCADO_PAGO' AND pi.currency='BRL' AND pi.live_mode=false
 AND pi.provider_payment_id IS NOT NULL AND pi.paid_at IS NOT NULL AND pi.reconciled_at>=pi.paid_at
 AND pi.reconciled_at<=now() AND ca.accepted_at<=pi.paid_at
 AND pi.expected_amount_cents=(CASE sp.billing_period WHEN 'MONTHLY' THEN pv.monthly_price ELSE pv.annual_price END)*100
 AND pl.status='ACTIVE' AND pl.tier<>'AMPLIADO' AND pl.members_limit IS NOT NULL AND pl.quotas_limit IS NOT NULL
 FOR SHARE OF e,sp,pi,pl,pv,ca,d
 LOOP
 n:=n+1;members_limit:=row_data.ml;quotas_limit:=row_data.ql;
 END LOOP;
 IF n<>1 THEN RAISE EXCEPTION 'license missing or ambiguous' USING ERRCODE='42501'; END IF;
 RETURN NEXT;
END $$;
CREATE FUNCTION public.fr_v23_preview(p_token text,p_tenant uuid,p_request uuid,p_start date,p_first date,p_last date,p_close date,p_quota bigint,p_bps int,p_late int,p_comp int,p_mode text,p_doc uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;doc_hash text;acc uuid;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,true);
 SELECT d.sha256,x.id INTO doc_hash,acc FROM public.contract_documents d JOIN public.contract_acceptances x ON x.document_id=d.id
 WHERE d.id=p_doc AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL
 AND x.user_id=a AND x.tenant_id=p_tenant AND x.accepted_at>=d.published_at;
 IF acc IS NULL THEN RAISE EXCEPTION 'contract missing' USING ERRCODE='42501'; END IF;
 RETURN encode(public.digest(jsonb_build_array('FR_V23_POLICY_V1',p_tenant,a,p_request,p_doc,doc_hash,acc,
 to_char(p_start,'YYYY-MM-DD'),to_char(p_first,'YYYY-MM-DD'),to_char(p_last,'YYYY-MM-DD'),to_char(p_close,'YYYY-MM-DD'),
 p_quota,p_bps,p_late,p_comp,p_mode)::text,'sha256'),'hex');
END $$;
CREATE FUNCTION public.fr_v23_cycle(p_token text,p_tenant uuid,p_request uuid,p_start date,p_first date,p_last date,p_close date,p_quota bigint,p_bps int,p_late int,p_comp int,p_mode text,p_doc uuid,p_hash text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;c uuid;prior record;n int;acc uuid;expected_hash text;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,true);
 PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,41320));
 IF p_request IS NULL OR p_start IS NULL OR p_first IS NULL OR p_last IS NULL OR p_close IS NULL
 OR NOT(p_start<=p_first AND p_first<=p_last AND p_last<=p_close)
 OR p_quota IS NULL OR p_quota NOT BETWEEN 1 AND 100000000 OR p_bps IS NULL OR p_bps NOT BETWEEN 0 AND 10000
 OR p_late IS NULL OR p_late NOT BETWEEN 1 AND 3650 OR p_comp IS NULL OR p_comp NOT BETWEEN 1 AND 120
 OR p_mode IS NULL OR p_mode NOT IN ('MANUAL','MERCADO_PAGO','HYBRID') THEN RAISE EXCEPTION 'invalid policy' USING ERRCODE='22023'; END IF;
 n:=(extract(year FROM p_last)::int-extract(year FROM p_first)::int)*12+extract(month FROM p_last)::int-extract(month FROM p_first)::int;
 IF n NOT BETWEEN 0 AND 119 OR (p_first+make_interval(months=>n))::date<>p_last THEN RAISE EXCEPTION 'anchor' USING ERRCODE='22023'; END IF;
 expected_hash:=public.fr_v23_preview(p_token,p_tenant,p_request,p_start,p_first,p_last,p_close,p_quota,p_bps,p_late,p_comp,p_mode,p_doc);
 IF p_hash IS DISTINCT FROM expected_hash THEN RAISE EXCEPTION 'policy hash mismatch' USING ERRCODE='23514'; END IF;
 SELECT p.*,cy.start_date,cy.settlement_date INTO prior FROM public.fr_v23_policy p JOIN public.cycles cy ON cy.id=p.cycle_id WHERE p.tenant_id=p_tenant AND p.request_id=p_request;
 IF FOUND THEN
 IF (prior.actor,prior.start_date,prior.first_due,prior.last_due,prior.settlement_date,prior.quota_cents,prior.admin_bps,prior.late_days,prior.late_competences,prior.mode,prior.document_id)
 IS DISTINCT FROM (a,p_start,p_first,p_last,p_close,p_quota,p_bps,p_late,p_comp,p_mode,p_doc)
 THEN RAISE EXCEPTION 'idempotency conflict' USING ERRCODE='23505'; END IF; RETURN prior.cycle_id; END IF;
 PERFORM * FROM public.fr_v23_license(p_tenant,a);
 SELECT x.id INTO acc FROM public.contract_acceptances x WHERE x.user_id=a AND x.tenant_id=p_tenant AND x.document_id=p_doc;
 IF acc IS NULL THEN RAISE EXCEPTION 'contract missing' USING ERRCODE='42501'; END IF;
 INSERT INTO public.cycles(tenant_id,year,start_date,end_date,settlement_date,status) VALUES(p_tenant,extract(year FROM p_start)::int,p_start,p_close,p_close,'ABERTO') RETURNING id INTO c;
 INSERT INTO public.fr_v23_policy(cycle_id,tenant_id,request_id,actor,document_id,admin_acceptance_id,policy_hash,
 first_due,last_due,quota_cents,admin_bps,late_days,late_competences,mode)
 VALUES(c,p_tenant,p_request,a,p_doc,acc,p_hash,p_first,p_last,p_quota,p_bps,p_late,p_comp,p_mode);
 RETURN c;
END $$;
CREATE FUNCTION public.fr_v23_read_policy(p_token text,p_tenant uuid,p_cycle uuid)
RETURNS TABLE(policy_hash text,document_id uuid,document_hash text,start_date date,first_due date,last_due date,closing date,
 quota_cents bigint,admin_bps int,late_days int,late_competences int,mode text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 PERFORM public.fr_v23_actor(p_token,p_tenant,false);
 RETURN QUERY SELECT p.policy_hash,p.document_id,d.sha256::text,c.start_date,p.first_due,p.last_due,c.settlement_date,
 p.quota_cents,p.admin_bps,p.late_days,p.late_competences,p.mode
 FROM public.fr_v23_policy p JOIN public.cycles c ON c.id=p.cycle_id JOIN public.contract_documents d ON d.id=p.document_id
 WHERE p.tenant_id=p_tenant AND p.cycle_id=p_cycle;
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
END $$;
CREATE FUNCTION public.fr_v23_accept_policy(p_token text,p_tenant uuid,p_cycle uuid,p_hash text,p_joined date,p_quotas int)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;m uuid;acc uuid;p record;prior record;cid uuid;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,false);
 PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,41320));
 SELECT pol.*,c.start_date INTO p FROM public.fr_v23_policy pol JOIN public.cycles c ON c.id=pol.cycle_id
 WHERE pol.tenant_id=p_tenant AND pol.cycle_id=p_cycle AND c.status='ABERTO';
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 IF p_hash IS DISTINCT FROM p.policy_hash THEN RAISE EXCEPTION 'policy hash mismatch' USING ERRCODE='23514'; END IF;
 IF p_joined IS NULL OR p_joined<p.start_date OR p_joined>p.last_due OR p_quotas IS NULL OR p_quotas NOT BETWEEN 1 AND 400
 OR p.quota_cents*p_quotas>100000000 THEN RAISE EXCEPTION 'invalid admission' USING ERRCODE='22023'; END IF;
 SELECT me.id,x.id INTO m,acc FROM public.memberships me JOIN public.contract_acceptances x ON x.user_id=me.user_id AND x.tenant_id=me.tenant_id
 JOIN public.contract_documents d ON d.id=x.document_id
 JOIN public.sessions se ON se.user_id=me.user_id AND se.active_tenant_id=me.tenant_id
 WHERE me.tenant_id=p_tenant AND me.user_id=a AND me.role='TENANT_MEMBER' AND me.status='ATIVA' AND me.joined_at<=p_joined
 AND se.token_hash=encode(public.digest(p_token,'sha256'),'hex') AND se.active_role='TENANT_MEMBER'
 AND x.document_id=p.document_id AND x.accepted_at>=d.published_at;
 IF m IS NULL OR acc IS NULL THEN RAISE EXCEPTION 'member acceptance missing' USING ERRCODE='42501'; END IF;
 SELECT * INTO prior FROM public.fr_v23_member_consent WHERE cycle_id=p_cycle AND membership_id=m;
 IF FOUND THEN
 IF (prior.actor,prior.acceptance_id,prior.policy_hash,prior.joined,prior.quotas) IS DISTINCT FROM (a,acc,p_hash,p_joined,p_quotas)
 THEN RAISE EXCEPTION 'consent conflict' USING ERRCODE='23505'; END IF; RETURN prior.id; END IF;
 INSERT INTO public.fr_v23_member_consent(cycle_id,membership_id,acceptance_id,actor,policy_hash,joined,quotas)
 VALUES(p_cycle,m,acc,a,p_hash,p_joined,p_quotas) RETURNING id INTO cid;RETURN cid;
END $$;
CREATE FUNCTION public.fr_v23_admit(p_token text,p_tenant uuid,p_cycle uuid,p_member uuid,p_joined date,p_quotas int)
RETURNS int LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;p record;acc uuid;consent uuid;prior record;n int;lim record;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,true);PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,41320));
 SELECT pol.*,c.start_date INTO p FROM public.fr_v23_policy pol JOIN public.cycles c ON c.id=pol.cycle_id WHERE pol.tenant_id=p_tenant AND pol.cycle_id=p_cycle AND c.status='ABERTO';
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 IF p_joined IS NULL OR p_joined<p.start_date OR p_joined>p.last_due OR p_quotas IS NULL OR p_quotas NOT BETWEEN 1 AND 400 OR p.quota_cents*p_quotas>100000000
 THEN RAISE EXCEPTION 'invalid admission' USING ERRCODE='22023'; END IF;
 SELECT x.id INTO acc FROM public.memberships m JOIN public.contract_acceptances x ON x.user_id=m.user_id AND x.tenant_id=m.tenant_id
 WHERE m.id=p_member AND m.tenant_id=p_tenant AND m.role='TENANT_MEMBER' AND m.status='ATIVA' AND x.document_id=p.document_id AND m.joined_at<=p_joined;
 IF acc IS NULL THEN RAISE EXCEPTION 'member acceptance missing' USING ERRCODE='42501'; END IF;
 SELECT c.id INTO consent FROM public.fr_v23_member_consent c JOIN public.memberships m ON m.id=c.membership_id
 WHERE c.cycle_id=p_cycle AND c.membership_id=p_member AND c.actor=m.user_id AND c.acceptance_id=acc
 AND c.policy_hash=p.policy_hash AND c.joined=p_joined AND c.quotas=p_quotas;
 SELECT * INTO prior FROM public.fr_v23_admission WHERE cycle_id=p_cycle AND membership_id=p_member;
 IF FOUND THEN IF (prior.joined,prior.quotas,prior.acceptance_id,prior.consent_id) IS DISTINCT FROM (p_joined,p_quotas,acc,consent) THEN RAISE EXCEPTION 'admission conflict' USING ERRCODE='23505'; END IF;
 RETURN (SELECT count(*)::int FROM public.contributions WHERE cycle_id=p_cycle AND membership_id=p_member); END IF;
 IF consent IS NULL THEN RAISE EXCEPTION 'specific cycle consent missing' USING ERRCODE='42501'; END IF;
 SELECT * INTO lim FROM public.fr_v23_license(p_tenant,a);
 -- Count legacy active seats/quotas conservatively as well as V2.3 admissions;
 -- do not infer released capacity from suspension or cancellation of a member with an open admission.
 IF (SELECT count(*) FROM (
  SELECT m.id FROM public.memberships m WHERE m.tenant_id=p_tenant AND m.role='TENANT_MEMBER' AND m.status='ATIVA'
  UNION SELECT ad.membership_id FROM public.fr_v23_admission ad JOIN public.cycles c ON c.id=ad.cycle_id WHERE c.tenant_id=p_tenant AND c.status<>'LIQUIDADO'
 ) used)>lim.members_limit
 OR (SELECT count(*) FROM public.quotas q WHERE q.tenant_id=p_tenant AND q.status='ATIVA')
 + (SELECT coalesce(sum(ad.quotas),0) FROM public.fr_v23_admission ad JOIN public.cycles c ON c.id=ad.cycle_id WHERE c.tenant_id=p_tenant AND c.status<>'LIQUIDADO')+p_quotas>lim.quotas_limit
 THEN RAISE EXCEPTION 'capacity' USING ERRCODE='23514'; END IF;
 INSERT INTO public.fr_v23_admission(cycle_id,membership_id,acceptance_id,consent_id,joined,quotas) VALUES(p_cycle,p_member,acc,consent,p_joined,p_quotas);
 INSERT INTO public.contributions(tenant_id,cycle_id,membership_id,competence,due_date,amount_due)
 SELECT p_tenant,p_cycle,p_member,to_char(d,'YYYY-MM'),d,p.quota_cents*p_quotas::numeric/100
 FROM (SELECT (p.first_due+make_interval(months=>i))::date d FROM generate_series(0,119) i) q WHERE d>=p_joined AND d<=p.last_due;
 GET DIAGNOSTICS n=ROW_COUNT; RETURN n;
END $$;
CREATE FUNCTION public.fr_v23_state(p_id uuid) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
 SELECT CASE WHEN EXISTS(SELECT 1 FROM public.fr_v23_events WHERE receipt_id=p_id AND action='REVERSE') THEN 'REVERSED'
 WHEN EXISTS(SELECT 1 FROM public.fr_v23_events WHERE receipt_id=p_id AND action='CONTEST') THEN 'CONTESTED'
 WHEN EXISTS(SELECT 1 FROM public.fr_v23_events WHERE receipt_id=p_id AND action='CONFIRM') THEN 'CONFIRMED' ELSE 'PENDING' END
$$;
-- Both channels acquire the same tenant lock. Canonical Pix intent only;
-- no PSP settlement is accepted for V2.3 until a trusted worker is reviewed.
CREATE FUNCTION public.fr_v23_pix_exclusion() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE c record;
BEGIN
 IF TG_OP='UPDATE' THEN
 IF EXISTS(SELECT 1 FROM public.contributions co JOIN public.fr_v23_policy p ON p.cycle_id=co.cycle_id WHERE co.id=OLD.contribution_id)
 AND (OLD.tenant_id,OLD.contribution_id,OLD.loan_installment_id,OLD.payer_user_id,OLD.amount_cents,OLD.idempotency_key)
 IS DISTINCT FROM (NEW.tenant_id,NEW.contribution_id,NEW.loan_installment_id,NEW.payer_user_id,NEW.amount_cents,NEW.idempotency_key)
 THEN RAISE EXCEPTION 'intent scope immutable' USING ERRCODE='23514'; END IF;
 IF OLD.status IN ('EXPIRADO','REJEITADO') AND NEW.status NOT IN ('EXPIRADO','REJEITADO')
 AND EXISTS(SELECT 1 FROM public.contributions co JOIN public.fr_v23_policy p ON p.cycle_id=co.cycle_id WHERE co.id=OLD.contribution_id)
 THEN RAISE EXCEPTION 'terminal intent' USING ERRCODE='23514'; END IF;
 END IF;
 SELECT co.tenant_id,co.id,co.cycle_id,p.mode,cy.status,m.user_id INTO c
 FROM public.contributions co JOIN public.fr_v23_policy p ON p.cycle_id=co.cycle_id
 JOIN public.cycles cy ON cy.id=co.cycle_id JOIN public.memberships m ON m.id=co.membership_id
 WHERE co.id=NEW.contribution_id;
 IF NOT FOUND THEN RETURN NEW; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(c.tenant_id::text,41320));
 IF NEW.tenant_id IS DISTINCT FROM c.tenant_id OR NEW.payer_user_id IS DISTINCT FROM c.user_id
 OR NEW.loan_installment_id IS NOT NULL OR c.mode='MANUAL' OR c.status<>'ABERTO'
 THEN RAISE EXCEPTION 'intent scope/mode' USING ERRCODE='23514'; END IF;
 IF NEW.status='LIQUIDADO_CONFIRMADO' THEN RAISE EXCEPTION 'trusted PSP settlement unavailable' USING ERRCODE='23514'; END IF;
 IF NEW.status NOT IN ('EXPIRADO','REJEITADO') THEN
 IF EXISTS(SELECT 1 FROM public.fr_v23_receipts r WHERE r.contribution_id=c.id AND public.fr_v23_state(r.id)<>'REVERSED')
 OR EXISTS(SELECT 1 FROM public.pix_payment_intents i WHERE i.contribution_id=c.id AND i.id<>NEW.id AND i.status NOT IN ('EXPIRADO','REJEITADO'))
 OR NEW.amount_cents>(SELECT (co.amount_due-co.amount_paid)*100 FROM public.contributions co WHERE co.id=c.id)
 THEN RAISE EXCEPTION 'exclusive channel or amount' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER fr_v23_pix_channel BEFORE INSERT OR UPDATE ON public.pix_payment_intents
 FOR EACH ROW EXECUTE FUNCTION public.fr_v23_pix_exclusion();
CREATE FUNCTION public.fr_v23_pix_no_delete() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM public.contributions co JOIN public.fr_v23_policy p ON p.cycle_id=co.cycle_id WHERE co.id=OLD.contribution_id)
 THEN RAISE EXCEPTION 'intent history immutable' USING ERRCODE='23514'; END IF;
 RETURN OLD;
END $$;
CREATE TRIGGER fr_v23_pix_history BEFORE DELETE ON public.pix_payment_intents FOR EACH ROW EXECUTE FUNCTION public.fr_v23_pix_no_delete();
CREATE FUNCTION public.fr_v23_record(p_token text,p_tenant uuid,p_request uuid,p_contribution uuid,p_cents bigint,p_method text,p_date date,p_ref text,p_evidence text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;c record;prior record;rid uuid;pending bigint;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,true);PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,41320));
 SELECT * INTO prior FROM public.fr_v23_receipts WHERE tenant_id=p_tenant AND request_id=p_request;
 IF FOUND THEN IF (prior.actor,prior.contribution_id,prior.cents,prior.method,prior.occurred,prior.reference,prior.evidence) IS DISTINCT FROM (a,p_contribution,p_cents,p_method,p_date,p_ref,p_evidence)
 THEN RAISE EXCEPTION 'idempotency conflict' USING ERRCODE='23505'; END IF; RETURN prior.id; END IF;
 SELECT co.*,cy.settlement_date,p.mode,ad.joined INTO c FROM public.contributions co JOIN public.cycles cy ON cy.id=co.cycle_id
 JOIN public.fr_v23_policy p ON p.cycle_id=co.cycle_id JOIN public.fr_v23_admission ad ON ad.cycle_id=co.cycle_id AND ad.membership_id=co.membership_id
 WHERE co.id=p_contribution AND co.tenant_id=p_tenant AND cy.tenant_id=p_tenant AND cy.status='ABERTO' FOR UPDATE OF co;
 IF NOT FOUND OR c.mode='MERCADO_PAGO' THEN RAISE EXCEPTION 'scope/mode' USING ERRCODE='42501'; END IF;
 IF p_request IS NULL OR p_cents IS NULL OR p_cents NOT BETWEEN 1 AND 100000000 OR p_date IS NULL OR p_date<c.joined OR p_date>c.settlement_date
 OR p_method IS NULL OR p_method NOT IN ('DINHEIRO','PIX_EXTERNO','TRANSFERENCIA','DEPOSITO')
 OR p_ref IS NULL OR btrim(p_ref)<>p_ref OR length(p_ref) NOT BETWEEN 3 AND 100 OR p_evidence IS NULL OR btrim(p_evidence)<>p_evidence OR length(p_evidence) NOT BETWEEN 3 AND 160
 THEN RAISE EXCEPTION 'invalid receipt' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM public.pix_payment_intents WHERE contribution_id=c.id AND status NOT IN ('EXPIRADO','REJEITADO')) THEN RAISE EXCEPTION 'PSP review' USING ERRCODE='23514'; END IF;
 SELECT coalesce(sum(cents),0) INTO pending FROM public.fr_v23_receipts WHERE contribution_id=c.id AND public.fr_v23_state(id)='PENDING';
 IF p_cents+pending>(c.amount_due-c.amount_paid)*100 THEN RAISE EXCEPTION 'overpayment' USING ERRCODE='23514'; END IF;
 INSERT INTO public.fr_v23_receipts(tenant_id,cycle_id,contribution_id,request_id,actor,cents,method,occurred,reference,evidence)
 VALUES(p_tenant,c.cycle_id,c.id,p_request,a,p_cents,p_method,p_date,p_ref,p_evidence) RETURNING id INTO rid;RETURN rid;
END $$;
CREATE FUNCTION public.fr_v23_review(p_token text,p_tenant uuid,p_receipt uuid,p_action text,p_request uuid,p_date date,p_evidence text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;r record;c record;prior record;st text;tx uuid;cash uuid;capital uuid;delta bigint;
BEGIN
 IF p_action IS NULL OR p_action NOT IN ('CONFIRM','CONTEST','REVERSE') THEN RAISE EXCEPTION 'invalid action' USING ERRCODE='22023'; END IF;
 a:=public.fr_v23_actor(p_token,p_tenant,p_action<>'CONTEST');PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,41320));
 SELECT * INTO r FROM public.fr_v23_receipts WHERE id=p_receipt AND tenant_id=p_tenant;
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 SELECT co.*,cy.settlement_date,p.mode,m.user_id INTO c FROM public.contributions co JOIN public.cycles cy ON cy.id=co.cycle_id
 JOIN public.fr_v23_policy p ON p.cycle_id=co.cycle_id JOIN public.memberships m ON m.id=co.membership_id
 WHERE co.id=r.contribution_id AND co.tenant_id=p_tenant AND cy.status='ABERTO' FOR UPDATE OF co;
 IF NOT FOUND OR (p_action='CONTEST' AND (c.user_id<>a OR NOT EXISTS(SELECT 1 FROM public.sessions s WHERE s.token_hash=encode(public.digest(p_token,'sha256'),'hex') AND s.active_role='TENANT_MEMBER')))
 THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 SELECT * INTO prior FROM public.fr_v23_events WHERE tenant_id=p_tenant AND request_id=p_request;
 IF FOUND THEN IF (prior.actor,prior.receipt_id,prior.action,prior.occurred,prior.evidence) IS DISTINCT FROM (a,p_receipt,p_action,p_date,p_evidence)
 THEN RAISE EXCEPTION 'idempotency conflict' USING ERRCODE='23505'; END IF; RETURN public.fr_v23_state(p_receipt); END IF;
 st:=public.fr_v23_state(p_receipt);
 IF p_request IS NULL OR p_date IS NULL OR p_date<r.occurred OR p_date>c.settlement_date OR p_evidence IS NULL OR btrim(p_evidence)<>p_evidence OR length(p_evidence) NOT BETWEEN 3 AND 160
 OR EXISTS(SELECT 1 FROM public.fr_v23_events WHERE receipt_id=p_receipt AND occurred>p_date)
 THEN RAISE EXCEPTION 'invalid review' USING ERRCODE='22023'; END IF;
 IF (p_action='CONFIRM' AND st<>'PENDING') OR (p_action='CONTEST' AND st<>'CONFIRMED') OR (p_action='REVERSE' AND st NOT IN ('CONFIRMED','CONTESTED'))
 THEN RAISE EXCEPTION 'transition' USING ERRCODE='23514'; END IF;
 IF p_action<>'CONTEST' THEN
 IF c.mode='MERCADO_PAGO' OR EXISTS(SELECT 1 FROM public.pix_payment_intents WHERE contribution_id=c.id AND status NOT IN ('EXPIRADO','REJEITADO'))
 THEN RAISE EXCEPTION 'PSP review' USING ERRCODE='23514'; END IF;
 delta:=CASE WHEN p_action='CONFIRM' THEN r.cents ELSE -r.cents END;
 IF c.amount_paid*100+delta NOT BETWEEN 0 AND c.amount_due*100 THEN RAISE EXCEPTION 'balance' USING ERRCODE='23514'; END IF;
 -- Preserve the legacy 20-character account code. A truncated UUID collision
 -- raises a unique violation; it never selects or credits a different cycle.
 INSERT INTO public.ledger_accounts(tenant_id,cycle_id,cycle_account_kind,account_code,account_name,account_type,balance_cents)
 VALUES(p_tenant,r.cycle_id,'MANUAL_DOCUMENTED','V23M'||left(replace(r.cycle_id::text,'-',''),16),'Recebimentos manuais documentados (não bancário)','ASSET',0),
       (p_tenant,r.cycle_id,'MEMBER_CAPITAL','V23C'||left(replace(r.cycle_id::text,'-',''),16),'Capital de membros documentado','EQUITY',0)
 ON CONFLICT(tenant_id,cycle_id,cycle_account_kind) DO NOTHING;
 SELECT id INTO cash FROM public.ledger_accounts WHERE tenant_id=p_tenant AND cycle_id=r.cycle_id AND cycle_account_kind='MANUAL_DOCUMENTED' AND account_type='ASSET' FOR UPDATE;
 SELECT id INTO capital FROM public.ledger_accounts WHERE tenant_id=p_tenant AND cycle_id=r.cycle_id AND cycle_account_kind='MEMBER_CAPITAL' AND account_type='EQUITY' FOR UPDATE;
 IF cash IS NULL OR capital IS NULL THEN RAISE EXCEPTION 'canonical accounts absent'; END IF;
 IF delta<0 AND EXISTS(SELECT 1 FROM public.ledger_accounts WHERE id=cash AND balance_cents< -delta) THEN RAISE EXCEPTION 'cash' USING ERRCODE='23514'; END IF;
 INSERT INTO public.ledger_transactions(tenant_id,cycle_id,transaction_date,description,reference_id)
 VALUES(p_tenant,r.cycle_id,(CASE WHEN delta>0 THEN r.occurred ELSE p_date END)::timestamp AT TIME ZONE 'America/Belem','V2.3 manual documentado sem prova bancária','V23:'||p_receipt||':'||p_action) RETURNING id INTO tx;
 INSERT INTO public.ledger_entries(tenant_id,transaction_id,account_id,entry_type,amount_cents) VALUES
 (p_tenant,tx,cash,CASE WHEN delta>0 THEN 'DR' ELSE 'CR' END,abs(delta)),(p_tenant,tx,capital,CASE WHEN delta>0 THEN 'CR' ELSE 'DR' END,abs(delta));
 UPDATE public.ledger_accounts SET balance_cents=balance_cents+delta WHERE id IN (cash,capital);
 UPDATE public.contributions SET amount_paid=amount_paid+delta::numeric/100,
 payment_status=CASE WHEN amount_paid+delta::numeric/100=amount_due THEN 'QUITADA' WHEN amount_paid+delta::numeric/100=0 THEN 'PENDENTE' ELSE 'PARCIAL' END,
 due_status=CASE WHEN amount_paid+delta::numeric/100=amount_due AND due_date<p_date THEN 'REGULARIZADA' WHEN amount_paid+delta::numeric/100<amount_due AND due_date<p_date THEN 'VENCIDA' ELSE 'NO_PRAZO' END,
 paid_at=CASE WHEN amount_paid+delta::numeric/100=amount_due THEN p_date::timestamp AT TIME ZONE 'America/Belem' ELSE NULL END WHERE id=c.id;
 END IF;
 INSERT INTO public.fr_v23_events(receipt_id,tenant_id,request_id,actor,action,occurred,evidence,ledger_id) VALUES(p_receipt,p_tenant,p_request,a,p_action,p_date,p_evidence,tx);
 RETURN public.fr_v23_state(p_receipt);
END $$;
CREATE FUNCTION public.fr_v23_receipt(p_token text,p_tenant uuid,p_id uuid)
RETURNS TABLE(receipt_id uuid,contribution_id uuid,cycle_id uuid,amount_cents bigint,method text,occurred date,state text,origin text,bank_reconciled boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,false);
 RETURN QUERY SELECT r.id,r.contribution_id,r.cycle_id,r.cents,r.method,r.occurred,public.fr_v23_state(r.id),'MANUAL'::text,false
 FROM public.fr_v23_receipts r JOIN public.contributions c ON c.id=r.contribution_id JOIN public.memberships m ON m.id=c.membership_id
 WHERE r.id=p_id AND r.tenant_id=p_tenant AND (m.user_id=a OR EXISTS(SELECT 1 FROM public.sessions s WHERE s.token_hash=encode(public.digest(p_token,'sha256'),'hex') AND s.active_role='TENANT_ADMIN'));
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
END $$;
-- M41330: summaries deliberately distinguish accounting from bank proof.
CREATE FUNCTION public.fr_v23_cycle_summary(p_token text,p_tenant uuid,p_cycle uuid)
RETURNS TABLE(cycle_id uuid,obligation_cents bigint,paid_cents bigint,manual_documented_cents bigint,
 member_capital_documented_cents bigint,manual_pending_cents bigint,contested_receipts bigint,bank_reconciled boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 PERFORM public.fr_v23_actor(p_token,p_tenant,true);
 IF NOT EXISTS(SELECT 1 FROM public.fr_v23_policy p WHERE p.tenant_id=p_tenant AND p.cycle_id=p_cycle)
 THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT p_cycle,
 (SELECT coalesce(sum(c.amount_due)*100,0)::bigint FROM public.contributions c WHERE c.tenant_id=p_tenant AND c.cycle_id=p_cycle),
 (SELECT coalesce(sum(c.amount_paid)*100,0)::bigint FROM public.contributions c WHERE c.tenant_id=p_tenant AND c.cycle_id=p_cycle),
 (SELECT coalesce(sum(a.balance_cents),0)::bigint FROM public.ledger_accounts a WHERE a.tenant_id=p_tenant AND a.cycle_id=p_cycle AND a.cycle_account_kind='MANUAL_DOCUMENTED'),
 (SELECT coalesce(sum(a.balance_cents),0)::bigint FROM public.ledger_accounts a WHERE a.tenant_id=p_tenant AND a.cycle_id=p_cycle AND a.cycle_account_kind='MEMBER_CAPITAL'),
 (SELECT coalesce(sum(r.cents),0)::bigint FROM public.fr_v23_receipts r WHERE r.tenant_id=p_tenant AND r.cycle_id=p_cycle AND public.fr_v23_state(r.id)='PENDING'),
 (SELECT count(*) FROM public.fr_v23_receipts r WHERE r.tenant_id=p_tenant AND r.cycle_id=p_cycle AND public.fr_v23_state(r.id)='CONTESTED'),
 false;
END $$;
-- No extra ledger. Read managerial reserves and documented cash from the same cycle.
CREATE FUNCTION public.fr_v23_reserve_snapshot(p_tenant uuid,p_cycle uuid)
RETURNS TABLE(documented_cents bigint,contested_cents bigint,reserved_cents bigint,unreserved_documented_cents bigint,
 reserve_deficit_cents bigint,bank_available_cents bigint,bank_reconciled boolean,payout_authorized boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
 WITH amounts AS (
 SELECT
 (SELECT coalesce(sum(a.balance_cents),0)::bigint FROM public.ledger_accounts a WHERE a.tenant_id=p_tenant AND a.cycle_id=p_cycle AND a.cycle_account_kind='MANUAL_DOCUMENTED') d,
 (SELECT coalesce(sum(r.cents),0)::bigint FROM public.fr_v23_receipts r WHERE r.tenant_id=p_tenant AND r.cycle_id=p_cycle AND public.fr_v23_state(r.id)='CONTESTED') c,
 (SELECT coalesce(sum(h.cents),0)::bigint FROM public.fr_v23_reservation_events h WHERE h.tenant_id=p_tenant AND h.cycle_id=p_cycle AND h.action='HOLD'
 AND NOT EXISTS(SELECT 1 FROM public.fr_v23_reservation_events e WHERE e.related_hold=h.id AND e.action='RELEASE')) r
 )
 SELECT d,c,r,greatest(d-c-r,0),greatest(r-(d-c),0),0::bigint,false,false FROM amounts
$$;
CREATE FUNCTION public.fr_v23_reserves(p_token text,p_tenant uuid,p_cycle uuid)
RETURNS TABLE(documented_cents bigint,contested_cents bigint,reserved_cents bigint,unreserved_documented_cents bigint,
 reserve_deficit_cents bigint,bank_available_cents bigint,bank_reconciled boolean,payout_authorized boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 PERFORM public.fr_v23_actor(p_token,p_tenant,true);
 IF NOT EXISTS(SELECT 1 FROM public.fr_v23_policy p WHERE p.tenant_id=p_tenant AND p.cycle_id=p_cycle)
 THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT * FROM public.fr_v23_reserve_snapshot(p_tenant,p_cycle);
END $$;
CREATE FUNCTION public.fr_v23_reserve_event(p_token text,p_tenant uuid,p_cycle uuid,p_request uuid,p_action text,p_cents bigint,p_hold uuid,p_reason text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;prior record;h record;s record;eid uuid;cycle_status text;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,true);
 PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,41320));
 SELECT c.status INTO cycle_status FROM public.cycles c JOIN public.fr_v23_policy p ON p.cycle_id=c.id WHERE c.tenant_id=p_tenant AND c.id=p_cycle;
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 IF p_request IS NULL OR p_action IS NULL OR p_action NOT IN ('HOLD','RELEASE') OR p_cents IS NULL OR p_cents NOT BETWEEN 1 AND 100000000000
 OR p_reason IS NULL OR btrim(p_reason)<>p_reason OR length(p_reason) NOT BETWEEN 8 AND 160
 OR (p_action='HOLD')<>(p_hold IS NULL) THEN RAISE EXCEPTION 'invalid reserve' USING ERRCODE='22023'; END IF;
 SELECT * INTO prior FROM public.fr_v23_reservation_events WHERE tenant_id=p_tenant AND request_id=p_request;
 IF FOUND THEN
 IF (prior.actor,prior.cycle_id,prior.action,prior.cents,prior.related_hold,prior.reason) IS DISTINCT FROM (a,p_cycle,p_action,p_cents,p_hold,p_reason)
 THEN RAISE EXCEPTION 'reservation conflict' USING ERRCODE='23505'; END IF; RETURN prior.id; END IF;
 IF p_action='HOLD' THEN
 IF cycle_status<>'ABERTO' THEN RAISE EXCEPTION 'cycle not open' USING ERRCODE='23514'; END IF;
 SELECT * INTO s FROM public.fr_v23_reserve_snapshot(p_tenant,p_cycle);
 IF p_cents>s.unreserved_documented_cents THEN RAISE EXCEPTION 'insufficient documented capacity' USING ERRCODE='23514'; END IF;
 ELSE
 SELECT * INTO h FROM public.fr_v23_reservation_events WHERE id=p_hold AND tenant_id=p_tenant AND cycle_id=p_cycle AND action='HOLD';
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 IF h.cents<>p_cents OR EXISTS(SELECT 1 FROM public.fr_v23_reservation_events WHERE related_hold=p_hold)
 THEN RAISE EXCEPTION 'release conflict' USING ERRCODE='23514'; END IF;
 END IF;
 INSERT INTO public.fr_v23_reservation_events(tenant_id,cycle_id,request_id,actor,action,cents,related_hold,reason)
 VALUES(p_tenant,p_cycle,p_request,a,p_action,p_cents,p_hold,p_reason) RETURNING id INTO eid; RETURN eid;
END $$;
CREATE FUNCTION public.fr_v23_member_summary(p_token text,p_tenant uuid,p_cycle uuid)
RETURNS TABLE(cycle_id uuid,membership_id uuid,obligation_cents bigint,paid_cents bigint,
 manual_pending_cents bigint,contested_receipts bigint,bank_reconciled boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;m uuid;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,false);
 SELECT me.id INTO m FROM public.memberships me JOIN public.fr_v23_admission ad ON ad.membership_id=me.id
 JOIN public.fr_v23_policy p ON p.cycle_id=ad.cycle_id
 JOIN public.sessions s ON s.user_id=me.user_id AND s.active_tenant_id=me.tenant_id
 WHERE me.user_id=a AND me.tenant_id=p_tenant AND me.role='TENANT_MEMBER' AND me.status='ATIVA'
 AND s.token_hash=encode(public.digest(p_token,'sha256'),'hex') AND s.active_role='TENANT_MEMBER'
 AND p.tenant_id=p_tenant AND p.cycle_id=p_cycle;
 IF m IS NULL THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT p_cycle,m,
 (SELECT coalesce(sum(c.amount_due)*100,0)::bigint FROM public.contributions c WHERE c.tenant_id=p_tenant AND c.cycle_id=p_cycle AND c.membership_id=m),
 (SELECT coalesce(sum(c.amount_paid)*100,0)::bigint FROM public.contributions c WHERE c.tenant_id=p_tenant AND c.cycle_id=p_cycle AND c.membership_id=m),
 (SELECT coalesce(sum(r.cents),0)::bigint FROM public.fr_v23_receipts r JOIN public.contributions c ON c.id=r.contribution_id WHERE r.tenant_id=p_tenant AND r.cycle_id=p_cycle AND c.membership_id=m AND public.fr_v23_state(r.id)='PENDING'),
 (SELECT count(*) FROM public.fr_v23_receipts r JOIN public.contributions c ON c.id=r.contribution_id WHERE r.tenant_id=p_tenant AND r.cycle_id=p_cycle AND c.membership_id=m AND public.fr_v23_state(r.id)='CONTESTED'),
 false;
END $$;
DO $$ DECLARE f regprocedure; BEGIN
 FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname LIKE 'fr_v23_%' LOOP
 EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role',f);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.fr_v23_cycle(text,uuid,uuid,date,date,date,date,bigint,int,int,int,text,uuid,text),
 public.fr_v23_preview(text,uuid,uuid,date,date,date,date,bigint,int,int,int,text,uuid),
 public.fr_v23_read_policy(text,uuid,uuid),public.fr_v23_accept_policy(text,uuid,uuid,text,date,int),
 public.fr_v23_admit(text,uuid,uuid,uuid,date,int),public.fr_v23_record(text,uuid,uuid,uuid,bigint,text,date,text,text),
 public.fr_v23_review(text,uuid,uuid,text,uuid,date,text),public.fr_v23_receipt(text,uuid,uuid),
 public.fr_v23_cycle_summary(text,uuid,uuid),public.fr_v23_member_summary(text,uuid,uuid),
 public.fr_v23_reserves(text,uuid,uuid),public.fr_v23_reserve_event(text,uuid,uuid,uuid,text,bigint,uuid,text) TO frcaixinha_pg18_app;
COMMIT;
