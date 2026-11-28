-- FR Finance M39600 — SaaS Master vs Admin cashbox in disposable PG16.
-- NEVER execute against Termux/original database. This file intentionally
-- ROLLBACKs all synthetic fixtures. The workflow enforces PGDATABASE,
-- PGPORT, GitHub Actions, and a dedicated ephemeral Postgres instance.
\set ON_ERROR_STOP on
\if :{?CI_M39600_DISPOSABLE}
\else
\echo 'M39600_BLOCKED_DISPOSABLE_GATE_MISSING'
\quit 2
\endif
SELECT CASE WHEN current_database()='frcaixinha_ci'
                 AND inet_server_port()=5432
                 AND session_user='postgres'
                 AND current_setting('frfinance.m39600_ci',true)='DISPOSABLE_ONLY'
            THEN 'true' ELSE 'false' END AS is_disposable
\gset
\if :is_disposable
\else
\echo 'M39600_BLOCKED_WRONG_DATABASE'
\quit 2
\endif

BEGIN;

-- Synthetic principals and two independent tenants.
INSERT INTO public.users(id,email,full_name,cpf,phone,is_master)
VALUES
 ('a1111111-1111-4111-8111-111111111111','m39600-master@example.invalid','CI Master','39600000000001','00000000001',true),
 ('a2222222-2222-4222-8222-222222222222','m39600-admin-a@example.invalid','CI Admin A','39600000000002','00000000002',false),
 ('a3333333-3333-4333-8333-333333333333','m39600-admin-b@example.invalid','CI Admin B','39600000000003','00000000003',false),
 ('a4444444-4444-4444-8444-444444444444','m39600-member-a@example.invalid','CI Member A','39600000000004','00000000004',false);

INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id,status)
VALUES
 ('b1111111-1111-4111-8111-111111111111','CI Caixa A','ci-contract-a','a2222222-2222-4222-8222-222222222222','ATIVO'),
 ('b2222222-2222-4222-8222-222222222222','CI Caixa B','ci-contract-b','a3333333-3333-4333-8333-333333333333','ATIVO');
INSERT INTO public.memberships(id,tenant_id,user_id,role,status)
VALUES
 ('c1111111-1111-4111-8111-111111111111','b1111111-1111-4111-8111-111111111111','a2222222-2222-4222-8222-222222222222','TENANT_ADMIN','ATIVA'),
 ('c2222222-2222-4222-8222-222222222222','b2222222-2222-4222-8222-222222222222','a3333333-3333-4333-8333-333333333333','TENANT_ADMIN','ATIVA'),
 ('c3333333-3333-4333-8333-333333333333','b1111111-1111-4111-8111-111111111111','a4444444-4444-4444-8444-444444444444','TENANT_MEMBER','ATIVA');
INSERT INTO public.ledger_transactions(id,tenant_id,description,reference_id)
VALUES
 ('d1111111-1111-4111-8111-111111111111','b1111111-1111-4111-8111-111111111111','CI Synthetic A','ci-a-1'),
 ('d2222222-2222-4222-8222-222222222222','b2222222-2222-4222-8222-222222222222','CI Synthetic B','ci-b-1');

-- Documentary SaaS preparations are not revenue. No real provider or payment.
INSERT INTO public.contract_documents(
 id,document_kind,version_label,sha256,source_reference,published_at)
VALUES ('e1111111-1111-4111-8111-111111111111','PLATFORM_LICENSE',
 'm39600-ci-v1',repeat('a',64),'CI contract sample',now());
INSERT INTO public.contract_acceptances(
 id,document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method)
VALUES
 ('f1111111-1111-4111-8111-111111111111',
  'e1111111-1111-4111-8111-111111111111','PLATFORM_LICENSE',
  'a2222222-2222-4222-8222-222222222222',NULL,repeat('b',64),
  'CI_VERIFIED_IDENTITY'),
 ('f2222222-2222-4222-8222-222222222222',
  'e1111111-1111-4111-8111-111111111111','PLATFORM_LICENSE',
  'a3333333-3333-4333-8333-333333333333',NULL,repeat('c',64),
  'CI_VERIFIED_IDENTITY');
INSERT INTO public.saas_subscription_preparations(
 id,tenant_id,admin_user_id,plan_tier,price_version_id,billing_period,
 contract_acceptance_id,status)
SELECT 'd3333333-3333-4333-8333-333333333333',
 'b1111111-1111-4111-8111-111111111111',
 'a2222222-2222-4222-8222-222222222222','ESSENCIAL',
 p.id,'MONTHLY','f1111111-1111-4111-8111-111111111111','PENDING_PAYMENT'
FROM public.platform_license_price_versions p
WHERE p.plan_tier='ESSENCIAL' ORDER BY p.created_at,p.id LIMIT 1;
INSERT INTO public.saas_subscription_preparations(
 id,tenant_id,admin_user_id,plan_tier,price_version_id,billing_period,
 contract_acceptance_id,status)
SELECT 'd4444444-4444-4444-8444-444444444444',
 'b2222222-2222-4222-8222-222222222222',
 'a3333333-3333-4333-8333-333333333333','ESSENCIAL',
 p.id,'MONTHLY','f2222222-2222-4222-8222-222222222222','PENDING_PAYMENT'
FROM public.platform_license_price_versions p
WHERE p.plan_tier='ESSENCIAL' ORDER BY p.created_at,p.id LIMIT 1;
INSERT INTO public.saas_payment_intents(
 id,preparation_id,tenant_id,admin_user_id,price_version_id,
 expected_amount_cents,external_reference,idempotency_key,
 platform_collector_id,live_mode,status)
SELECT 'e2222222-2222-4222-8222-222222222222',s.id,s.tenant_id,
 s.admin_user_id,s.price_version_id,9999,'m39600-a','m39600-intent-a','123456789',false,'PENDING'
FROM public.saas_subscription_preparations s
WHERE s.id='d3333333-3333-4333-8333-333333333333';
INSERT INTO public.saas_payment_intents(
 id,preparation_id,tenant_id,admin_user_id,price_version_id,
 expected_amount_cents,external_reference,idempotency_key,
 platform_collector_id,live_mode,status)
SELECT 'e3333333-3333-4333-8333-333333333333',s.id,s.tenant_id,
 s.admin_user_id,s.price_version_id,19999,'m39600-b','m39600-intent-b','123456789',false,'PENDING'
FROM public.saas_subscription_preparations s
WHERE s.id='d4444444-4444-4444-8444-444444444444';

-- The test principal is the same no-login role used by SaaS RLS policies.
-- The financial backend's actual login role inherits this role in the
-- post-migration roles manifest, which is separately audited.
SET LOCAL ROLE frcaixinha_app_role;
SELECT set_config('app.current_user_id','a1111111-1111-4111-8111-111111111111',true);
SELECT set_config('app.current_role','MASTER',true);
SELECT set_config('app.current_tenant_id','',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM public.saas_subscription_preparations)<>2
    OR (SELECT count(*) FROM public.saas_payment_intents)<>2 THEN
  RAISE EXCEPTION 'M39600 Master SaaS visibility mismatch';
 END IF;
 IF (SELECT count(*) FROM public.ledger_transactions)<>0 THEN
  RAISE EXCEPTION 'M39600 Master can see a tenant ledger';
 END IF;
END $$;

SELECT set_config('app.current_user_id','a2222222-2222-4222-8222-222222222222',true);
SELECT set_config('app.current_role','TENANT_ADMIN',true);
SELECT set_config('app.current_tenant_id','b1111111-1111-4111-8111-111111111111',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM public.saas_subscription_preparations)<>1
    OR (SELECT count(*) FROM public.saas_payment_intents)<>1 THEN
  RAISE EXCEPTION 'M39600 admin A SaaS leak';
 END IF;
 IF (SELECT count(*) FROM public.ledger_transactions)<>1
    OR (SELECT count(*) FROM public.ledger_transactions
        WHERE tenant_id='b2222222-2222-4222-8222-222222222222')<>0 THEN
  RAISE EXCEPTION 'M39600 admin A ledger leak';
 END IF;
END $$;

SELECT set_config('app.current_user_id','a3333333-3333-4333-8333-333333333333',true);
SELECT set_config('app.current_role','TENANT_ADMIN',true);
SELECT set_config('app.current_tenant_id','b2222222-2222-4222-8222-222222222222',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM public.saas_subscription_preparations)<>1
    OR (SELECT count(*) FROM public.saas_payment_intents)<>1
    OR (SELECT count(*) FROM public.ledger_transactions)<>1 THEN
  RAISE EXCEPTION 'M39600 admin B tenancy leak';
 END IF;
END $$;

SELECT set_config('app.current_user_id','a4444444-4444-4444-8444-444444444444',true);
SELECT set_config('app.current_role','TENANT_MEMBER',true);
SELECT set_config('app.current_tenant_id','b1111111-1111-4111-8111-111111111111',true);
DO $$
BEGIN
 IF (SELECT count(*) FROM public.saas_payment_intents)<>0
    OR (SELECT count(*) FROM public.saas_subscription_preparations)<>0
    OR (SELECT count(*) FROM public.ledger_transactions)<>0 THEN
  RAISE EXCEPTION 'M39600 member can view exclusive cashboxes';
 END IF;
END $$;

-- ROLLBACK guarantees no synthetic money, contracts or actors survive.
ROLLBACK;
\echo 'M39600_CASHBOX_RLS_2_TENANTS=PASS'
\echo 'M39600_MASTER_NO_TENANT_LEDGER=PASS'
\echo 'M39600_MEMBER_NO_EXCLUSIVE_FUNDS=PASS'
\echo 'M39600_SYNTHETIC_DATA_PERSISTED=NONE'
\echo 'M39600_PRODUCTION=BLOCKED'
