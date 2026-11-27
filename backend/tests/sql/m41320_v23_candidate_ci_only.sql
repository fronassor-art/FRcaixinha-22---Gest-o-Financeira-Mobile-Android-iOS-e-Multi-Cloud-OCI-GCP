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
CREATE TABLE public.fr_v23_policy(
 cycle_id uuid PRIMARY KEY,tenant_id uuid NOT NULL,request_id uuid NOT NULL,
 actor uuid NOT NULL REFERENCES public.users(id),document_id uuid NOT NULL REFERENCES public.contract_documents(id),
 first_due date NOT NULL,last_due date NOT NULL,quota_cents bigint NOT NULL CHECK(quota_cents BETWEEN 1 AND 100000000),
 admin_bps int NOT NULL CHECK(admin_bps BETWEEN 0 AND 10000),late_days int NOT NULL CHECK(late_days BETWEEN 1 AND 3650),
 late_competences int NOT NULL CHECK(late_competences BETWEEN 1 AND 120),
 mode text NOT NULL CHECK(mode IN ('MANUAL','MERCADO_PAGO','HYBRID')),
 UNIQUE(tenant_id,request_id),FOREIGN KEY(cycle_id,tenant_id) REFERENCES public.cycles(id,tenant_id)
);
CREATE TABLE public.fr_v23_admission(
 cycle_id uuid NOT NULL REFERENCES public.fr_v23_policy(cycle_id),membership_id uuid NOT NULL REFERENCES public.memberships(id),
 acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id),joined date NOT NULL,
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
CREATE FUNCTION public.fr_v23_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN RAISE EXCEPTION 'immutable V23'; END $$;
DO $$ DECLARE t regclass; BEGIN
 FOR t IN SELECT unnest(ARRAY['public.fr_v23_policy'::regclass,'public.fr_v23_admission'::regclass,'public.fr_v23_receipts'::regclass,'public.fr_v23_events'::regclass]) LOOP
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
CREATE FUNCTION public.fr_v23_cycle(p_token text,p_tenant uuid,p_request uuid,p_start date,p_first date,p_last date,p_close date,p_quota bigint,p_bps int,p_late int,p_comp int,p_mode text,p_doc uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;c uuid;prior record;n int;
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
 SELECT p.*,cy.start_date,cy.settlement_date INTO prior FROM public.fr_v23_policy p JOIN public.cycles cy ON cy.id=p.cycle_id WHERE p.tenant_id=p_tenant AND p.request_id=p_request;
 IF FOUND THEN
 IF (prior.actor,prior.start_date,prior.first_due,prior.last_due,prior.settlement_date,prior.quota_cents,prior.admin_bps,prior.late_days,prior.late_competences,prior.mode,prior.document_id)
 IS DISTINCT FROM (a,p_start,p_first,p_last,p_close,p_quota,p_bps,p_late,p_comp,p_mode,p_doc)
 THEN RAISE EXCEPTION 'idempotency conflict' USING ERRCODE='23505'; END IF; RETURN prior.cycle_id; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.contract_acceptances x JOIN public.contract_documents d ON d.id=x.document_id
 WHERE x.user_id=a AND x.tenant_id=p_tenant AND d.id=p_doc AND d.document_kind='TENANT_MEMBERSHIP' AND d.published_at IS NOT NULL)
 THEN RAISE EXCEPTION 'contract missing' USING ERRCODE='42501'; END IF;
 INSERT INTO public.cycles(tenant_id,year,start_date,end_date,settlement_date,status) VALUES(p_tenant,extract(year FROM p_start)::int,p_start,p_close,p_close,'ABERTO') RETURNING id INTO c;
 INSERT INTO public.fr_v23_policy VALUES(c,p_tenant,p_request,a,p_doc,p_first,p_last,p_quota,p_bps,p_late,p_comp,p_mode);
 RETURN c;
END $$;
CREATE FUNCTION public.fr_v23_admit(p_token text,p_tenant uuid,p_cycle uuid,p_member uuid,p_joined date,p_quotas int)
RETURNS int LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a uuid;p record;acc uuid;prior record;n int;
BEGIN
 a:=public.fr_v23_actor(p_token,p_tenant,true);PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant::text,41320));
 SELECT pol.*,c.start_date INTO p FROM public.fr_v23_policy pol JOIN public.cycles c ON c.id=pol.cycle_id WHERE pol.tenant_id=p_tenant AND pol.cycle_id=p_cycle AND c.status='ABERTO';
 IF NOT FOUND THEN RAISE EXCEPTION 'scope' USING ERRCODE='42501'; END IF;
 IF p_joined IS NULL OR p_joined<p.start_date OR p_joined>p.last_due OR p_quotas IS NULL OR p_quotas NOT BETWEEN 1 AND 400 OR p.quota_cents*p_quotas>100000000
 THEN RAISE EXCEPTION 'invalid admission' USING ERRCODE='22023'; END IF;
 SELECT x.id INTO acc FROM public.memberships m JOIN public.contract_acceptances x ON x.user_id=m.user_id AND x.tenant_id=m.tenant_id
 WHERE m.id=p_member AND m.tenant_id=p_tenant AND m.role='TENANT_MEMBER' AND m.status='ATIVA' AND x.document_id=p.document_id AND m.joined_at<=p_joined;
 IF acc IS NULL THEN RAISE EXCEPTION 'member acceptance missing' USING ERRCODE='42501'; END IF;
 SELECT * INTO prior FROM public.fr_v23_admission WHERE cycle_id=p_cycle AND membership_id=p_member;
 IF FOUND THEN IF (prior.joined,prior.quotas,prior.acceptance_id) IS DISTINCT FROM (p_joined,p_quotas,acc) THEN RAISE EXCEPTION 'admission conflict' USING ERRCODE='23505'; END IF;
 RETURN (SELECT count(*)::int FROM public.contributions WHERE cycle_id=p_cycle AND membership_id=p_member); END IF;
 -- Ampliado capability demonstration only: no license activation.
 IF (SELECT count(DISTINCT ad.membership_id) FROM public.fr_v23_admission ad JOIN public.cycles c ON c.id=ad.cycle_id WHERE c.tenant_id=p_tenant AND c.status<>'LIQUIDADO' AND ad.membership_id<>p_member)>=200
 OR (SELECT coalesce(sum(ad.quotas),0) FROM public.fr_v23_admission ad JOIN public.cycles c ON c.id=ad.cycle_id WHERE c.tenant_id=p_tenant AND c.status<>'LIQUIDADO')+p_quotas>400
 THEN RAISE EXCEPTION 'capacity' USING ERRCODE='23514'; END IF;
 INSERT INTO public.fr_v23_admission VALUES(p_cycle,p_member,acc,p_joined,p_quotas);
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
 INSERT INTO public.ledger_accounts(tenant_id,account_code,account_name,account_type,balance_cents)
 VALUES(p_tenant,'1.1.2','Caixa manual documentado (não bancário)','ASSET',0) ON CONFLICT(tenant_id,account_code) DO NOTHING;
 SELECT id INTO cash FROM public.ledger_accounts WHERE tenant_id=p_tenant AND account_code='1.1.2' AND account_type='ASSET' FOR UPDATE;
 SELECT id INTO capital FROM public.ledger_accounts WHERE tenant_id=p_tenant AND account_code='2.1.1' AND account_type='EQUITY' FOR UPDATE;
 IF cash IS NULL OR capital IS NULL THEN RAISE EXCEPTION 'canonical accounts absent'; END IF;
 IF delta<0 AND EXISTS(SELECT 1 FROM public.ledger_accounts WHERE id=cash AND balance_cents< -delta) THEN RAISE EXCEPTION 'cash' USING ERRCODE='23514'; END IF;
 INSERT INTO public.ledger_transactions(tenant_id,transaction_date,description,reference_id)
 VALUES(p_tenant,(CASE WHEN delta>0 THEN r.occurred ELSE p_date END)::timestamp AT TIME ZONE 'America/Belem','V2.3 manual documentado sem prova bancária','V23:'||p_receipt||':'||p_action) RETURNING id INTO tx;
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
DO $$ DECLARE f regprocedure; BEGIN
 FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname LIKE 'fr_v23_%' LOOP
 EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role',f);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.fr_v23_cycle(text,uuid,uuid,date,date,date,date,bigint,int,int,int,text,uuid),
 public.fr_v23_admit(text,uuid,uuid,uuid,date,int),public.fr_v23_record(text,uuid,uuid,uuid,bigint,text,date,text,text),
 public.fr_v23_review(text,uuid,uuid,text,uuid,date,text),public.fr_v23_receipt(text,uuid,uuid) TO frcaixinha_pg18_app;
COMMIT;
