-- FR Finance M39047: real RLS/DML/trigger flow with final ROLLBACK.
-- GITHUB ACTIONS POSTGRESQL DISPOSABLE ONLY: frfinance_ci_credit 127.0.0.1:5432.
-- NEVER run in Termux original PostgreSQL :5433 or in production.
-- Prerequisite: SQL110+111 and M39020 synthetic fixture CI executed successfully.
\set ON_ERROR_STOP on

DO $guard$
BEGIN
 IF current_database()<>'frfinance_ci_credit'
    OR inet_server_port()<>5432
    OR session_user<>'postgres'
    OR current_setting('frfinance.m39047_test_mode',true) IS DISTINCT FROM 'CI_DISPOSABLE'
 THEN
  RAISE EXCEPTION 'M39047 DISPOSABLE_CI_ONLY: incorrect database or approval gate';
 END IF;
 IF (SELECT count(*) FROM pg_class WHERE oid IN
      ('public.special_credit_grants'::regclass,
       'public.special_credit_campaigns'::regclass,
       'public.special_credit_recipients'::regclass,
       'public.special_credit_preferences'::regclass,
       'public.special_credit_outbox'::regclass,
       'public.special_credit_audit'::regclass)
      AND relrowsecurity AND relforcerowsecurity)<>6
 THEN RAISE EXCEPTION 'M39047 RLS_FORCE_6_REQUIRED'; END IF;
 IF EXISTS(SELECT 1 FROM public.special_credit_grants
           WHERE id='c1111111-1111-4111-8111-111111111111')
    OR EXISTS(SELECT 1 FROM public.special_credit_campaigns
           WHERE id='c2222222-2222-4222-8222-222222222222')
    OR EXISTS(SELECT 1 FROM public.special_credit_recipients
           WHERE id='c3333333-3333-4333-8333-333333333333')
 THEN RAISE EXCEPTION 'M39047 SYNTHETIC_FIXTURE_ALREADY_PRESENT'; END IF;
END
$guard$;

-- All fixture INSERT/UPDATE operations occur within this transaction only.
-- Any error with psql ON_ERROR_STOP causes disconnect and automatic rollback.
BEGIN;
SET LOCAL ROLE frc_ai_app;
SELECT set_config('app.current_tenant_id','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
SELECT set_config('app.current_user_id','11111111-1111-4111-8111-111111111111',true);
SELECT set_config('app.current_role','TENANT_ADMIN',true);

-- Admin creates a second active grant for the same member.
-- First M39020 grant was previously REVOKED in the disposable fixture.
INSERT INTO public.special_credit_grants(
 id,tenant_id,cycle_id,member_id,created_by,
 ceiling_brl,reason,expires_at,request_id
) VALUES (
 'c1111111-1111-4111-8111-111111111111',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111',
 5000.00,
 'Autorizacao ficticia para teste transacional com rollback integral',
 now()+interval '5 days',
 'c0000000-0000-4000-8000-000000000047'
);

INSERT INTO public.special_credit_campaigns(
 id,tenant_id,cycle_id,created_by,title,body,expires_at,request_id
) VALUES (
 'c2222222-2222-4222-8222-222222222222',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111',
 'Campanha M39047 de teste',
 'Mensagem ficticia: nenhuma liberacao, cobranca ou transferencia real.',
 now()+interval '2 days',
 'c0000000-0000-4000-8000-000000000048'
);

INSERT INTO public.special_credit_recipients(
 id,tenant_id,campaign_id,grant_id,member_id,user_id
) VALUES (
 'c3333333-3333-4333-8333-333333333333',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'c2222222-2222-4222-8222-222222222222',
 'c1111111-1111-4111-8111-111111111111',
 'aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '22222222-2222-4222-8222-222222222222'
);

-- Out-of-tenant destination must NOT be accepted even under an admin role.
SELECT public.sc_ci_must_deny($deny$
 INSERT INTO public.special_credit_recipients(
  tenant_id,campaign_id,grant_id,member_id,user_id
 ) VALUES (
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'c2222222-2222-4222-8222-222222222222',
 'c1111111-1111-4111-8111-111111111111',
 'bbbbeeee-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 '44444444-4444-4444-8444-444444444444'
 )
$deny$);

UPDATE public.special_credit_campaigns
 SET status='PUBLISHED',published_at=now()
 WHERE id='c2222222-2222-4222-8222-222222222222';

-- M39020 member had opted in to PUSH. Outbox remains BLOCKED_EXTERNAL only.
INSERT INTO public.special_credit_outbox(
 tenant_id,campaign_id,recipient_id,channel
) VALUES (
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'c2222222-2222-4222-8222-222222222222',
 'c3333333-3333-4333-8333-333333333333',
 'PUSH'
);
INSERT INTO public.special_credit_audit(
 tenant_id,actor_id,entity_kind,entity_id,action,detail
) VALUES (
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111',
 'CAMPAIGN',
 'c2222222-2222-4222-8222-222222222222',
 'M39047_ROLLBACK_ONLY',
 'Synthetic-only campaign; no external message or financial operation'
);

DO $admin$
BEGIN
 IF (SELECT count(*) FROM public.special_credit_outbox
     WHERE campaign_id='c2222222-2222-4222-8222-222222222222'
     AND state='BLOCKED_EXTERNAL')<>1
 THEN RAISE EXCEPTION 'M39047 OUTBOX_NOT_BLOCKED'; END IF;
 IF (SELECT count(*) FROM public.special_credit_campaigns
     WHERE id='c2222222-2222-4222-8222-222222222222'
     AND status='PUBLISHED')<>1
 THEN RAISE EXCEPTION 'M39047 PUBLISH_MISSING'; END IF;
END
$admin$;

-- Change only synthetic RLS session context: member sees own campaign/grant.
SELECT set_config('app.current_user_id','22222222-2222-4222-8222-222222222222',true);
SELECT set_config('app.current_role','TENANT_MEMBER',true);
DO $member$
BEGIN
 IF NOT EXISTS(
  SELECT 1 FROM public.special_credit_campaigns c
   JOIN public.special_credit_recipients r ON r.campaign_id=c.id
   JOIN public.special_credit_grants g ON g.id=r.grant_id
  WHERE c.id='c2222222-2222-4222-8222-222222222222'
    AND r.user_id='22222222-2222-4222-8222-222222222222'
    AND g.status='ACTIVE' AND c.status='PUBLISHED'
 ) THEN RAISE EXCEPTION 'M39047 MEMBER_CANNOT_SEE_OWN_CAMPAIGN'; END IF;
 IF EXISTS(SELECT 1 FROM public.special_credit_outbox
           WHERE campaign_id='c2222222-2222-4222-8222-222222222222')
 THEN RAISE EXCEPTION 'M39047 MEMBER_MUST_NOT_SEE_OUTBOX'; END IF;
END
$member$;

UPDATE public.special_credit_recipients
 SET response_status='INTERESTED',responded_at=now()
 WHERE id='c3333333-3333-4333-8333-333333333333';
SELECT public.sc_ci_must_deny($deny$
 UPDATE public.special_credit_recipients
 SET response_status='DECLINED',responded_at=now()
 WHERE id='c3333333-3333-4333-8333-333333333333'
$deny$);

-- A user of tenant B is not allowed to read or change tenant A's reply.
SELECT set_config('app.current_user_id','44444444-4444-4444-8444-444444444444',true);
DO $intruder$
DECLARE updated_count integer;
BEGIN
 IF EXISTS(SELECT 1 FROM public.special_credit_grants
           WHERE id='c1111111-1111-4111-8111-111111111111')
    OR EXISTS(SELECT 1 FROM public.special_credit_recipients
           WHERE id='c3333333-3333-4333-8333-333333333333')
 THEN RAISE EXCEPTION 'M39047 TENANT_MEMBER_LEAK'; END IF;
 UPDATE public.special_credit_recipients SET response_status='DECLINED'
 WHERE id='c3333333-3333-4333-8333-333333333333';
 GET DIAGNOSTICS updated_count=ROW_COUNT;
 IF updated_count<>0 THEN
   RAISE EXCEPTION 'M39047 INTRUDER_MODIFIED_RECIPIENT';
 END IF;
END
$intruder$;

-- Crucial: commit is forbidden in this test. Discard all synthetic mutations.
ROLLBACK;

-- Verify no synthetic fixture, recipient reply, outbox item, or audit survives.
DO $proof$
BEGIN
 IF EXISTS(SELECT 1 FROM public.special_credit_grants
            WHERE id='c1111111-1111-4111-8111-111111111111')
 OR EXISTS(SELECT 1 FROM public.special_credit_campaigns
            WHERE id='c2222222-2222-4222-8222-222222222222')
 OR EXISTS(SELECT 1 FROM public.special_credit_recipients
            WHERE id='c3333333-3333-4333-8333-333333333333')
 OR EXISTS(SELECT 1 FROM public.special_credit_outbox
            WHERE campaign_id='c2222222-2222-4222-8222-222222222222')
 OR EXISTS(SELECT 1 FROM public.special_credit_audit
            WHERE entity_id='c2222222-2222-4222-8222-222222222222'
              AND action='M39047_ROLLBACK_ONLY')
 THEN RAISE EXCEPTION 'M39047 ROLLBACK_INCOMPLETE'; END IF;
END
$proof$;
SELECT 'M39047_TRANSACTION_ROLLBACK=PASS' AS result;
SELECT 'M39047_PG_DISPOSABLE_ONLY=PASS' AS result;
SELECT 'M39047_NO_EXTERNAL_DISPATCH=PASS' AS result;
