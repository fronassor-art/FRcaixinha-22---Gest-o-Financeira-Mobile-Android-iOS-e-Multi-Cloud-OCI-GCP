-- CI ONLY: PostgreSQL disposable, fixtures fictícias, sem Pix ou env reais.
-- Prerequisites: synthetic users/tenants/memberships/cycles, SQL 110 then 111.
\set ON_ERROR_STOP on

INSERT INTO public.users(id) VALUES
 ('11111111-1111-4111-8111-111111111111'),
 ('22222222-2222-4222-8222-222222222222'),
 ('33333333-3333-4333-8333-333333333333'),
 ('44444444-4444-4444-8444-444444444444');

INSERT INTO public.tenants(id,admin_user_id) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','33333333-3333-4333-8333-333333333333');
INSERT INTO public.cycles(id,tenant_id) VALUES
 ('aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('bbbbcccc-bbbb-4bbb-8bbb-bbbbbbbbbbbb','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO public.memberships(id,tenant_id,user_id) VALUES
 ('aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','22222222-2222-4222-8222-222222222222'),
 ('bbbbeeee-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','44444444-4444-4444-8444-444444444444');

-- Helper: a statement must produce an exception. It does not mask the
-- expected-failure sentinel; an erroneously permitted write FAILS CI.
CREATE OR REPLACE FUNCTION public.sc_ci_must_deny(statement text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE denied boolean := false;
BEGIN
 BEGIN
  EXECUTE statement;
 EXCEPTION WHEN others THEN
  denied := true;
 END;
 IF NOT denied THEN
  RAISE EXCEPTION 'M39020 SECURITY REGRESSION: accepted forbidden SQL: %', statement;
 END IF;
END $$;

SET ROLE frc_ai_app;
SELECT set_config('app.current_tenant_id','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',false);
SELECT set_config('app.current_user_id','11111111-1111-4111-8111-111111111111',false);
SELECT set_config('app.current_role','TENANT_ADMIN',false);

INSERT INTO public.special_credit_grants(
 id,tenant_id,cycle_id,member_id,created_by,ceiling_brl,reason,
 expires_at,request_id)
VALUES(
 'a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111',
 5000.00,'Análise demonstrativa de risco e liquidez de caixa',
 now()+interval '5 days','a0000000-0000-4000-8000-000000000001'
);
INSERT INTO public.special_credit_campaigns(
 id,tenant_id,cycle_id,created_by,title,body,expires_at,request_id)
VALUES (
 'a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '11111111-1111-4111-8111-111111111111',
 'Oportunidade especial','Simulação sujeita à análise final, sem crédito liberado.',
 now()+interval '2 days','a0000000-0000-4000-8000-000000000002'
);
INSERT INTO public.special_credit_recipients(
 id,tenant_id,campaign_id,grant_id,member_id,user_id)
VALUES (
 'a3333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '22222222-2222-4222-8222-222222222222'
);

-- A tenant A admin must NOT see tenant B data nor insert other member.
SELECT public.sc_ci_must_deny($sql$
 INSERT INTO public.special_credit_recipients(
 tenant_id,campaign_id,grant_id,member_id,user_id) VALUES(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'bbbbeeee-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 '44444444-4444-4444-8444-444444444444')
$sql$);

SELECT public.sc_ci_must_deny($sql$
 INSERT INTO public.special_credit_outbox(
 tenant_id,campaign_id,recipient_id,channel) VALUES(
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a3333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa','PUSH')
$sql$);

UPDATE public.special_credit_campaigns
 SET status='PUBLISHED',published_at=now()
 WHERE id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

SELECT public.sc_ci_must_deny($sql$
 UPDATE public.special_credit_campaigns SET status='DRAFT'
 WHERE id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
$sql$);

SELECT public.sc_ci_must_deny($sql$
 UPDATE public.special_credit_campaigns SET published_at=now()+interval '5 hours'
 WHERE id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
$sql$);

-- A member explicitly opts in to PUSH; no external delivery yet.
SELECT set_config('app.current_user_id','22222222-2222-4222-8222-222222222222',false);
SELECT set_config('app.current_role','TENANT_MEMBER',false);
INSERT INTO public.special_credit_preferences(tenant_id,user_id,channel,opted_in)
VALUES('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '22222222-2222-4222-8222-222222222222','PUSH',true);

-- Diagnostic E2E: verifies member can see published campaign and own grant
-- before a reply. Any missing scope is a CI failure, not a fake success.
DO $$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM public.special_credit_campaigns c
    JOIN public.special_credit_grants g
      ON g.id='a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
   WHERE c.id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
     AND c.status='PUBLISHED'
     AND g.status='ACTIVE'
     AND c.expires_at>now() AND g.expires_at>now()
 ) THEN
   RAISE EXCEPTION 'M39020 member RLS hid own published campaign or grant';
 END IF;
END $$;

UPDATE public.special_credit_recipients SET response_status='INTERESTED',
 responded_at=now() WHERE id='a3333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
SELECT public.sc_ci_must_deny($sql$
 UPDATE public.special_credit_recipients SET response_status='DECLINED',
 responded_at=now() WHERE id='a3333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
$sql$);

-- Member cannot cancel an admin campaign. A denied RLS update may
-- legitimately affect ZERO rows instead of raising, so check row count.
DO $
DECLARE changed bigint;
BEGIN
 UPDATE public.special_credit_campaigns SET status='CANCELLED'
 WHERE id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
 GET DIAGNOSTICS changed=ROW_COUNT;
 IF changed<>0 THEN
  RAISE EXCEPTION 'M39020 SECURITY REGRESSION: member changed campaign';
 END IF;
END $;

SELECT set_config('app.current_user_id','11111111-1111-4111-8111-111111111111',false);
SELECT set_config('app.current_role','TENANT_ADMIN',false);
INSERT INTO public.special_credit_outbox(
 tenant_id,campaign_id,recipient_id,channel)
VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 'a3333333-aaaa-4aaa-8aaa-aaaaaaaaaaaa','PUSH');
DO $$
BEGIN
 IF (SELECT state FROM public.special_credit_outbox
     WHERE campaign_id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa')<>'BLOCKED_EXTERNAL'
 THEN RAISE EXCEPTION 'external dispatch unexpectedly enabled'; END IF;
END $$;

-- Revocation must be one-way; published campaign cannot be republished.
UPDATE public.special_credit_grants SET status='REVOKED',updated_at=now()
 WHERE id='a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
SELECT public.sc_ci_must_deny($sql$
 UPDATE public.special_credit_grants SET status='ACTIVE',updated_at=now()
 WHERE id='a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
$sql$);
SELECT public.sc_ci_must_deny($sql$
 UPDATE public.special_credit_grants SET ceiling_brl=9000.00
 WHERE id='a1111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
$sql$);

UPDATE public.special_credit_campaigns SET status='CANCELLED'
 WHERE id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
SELECT public.sc_ci_must_deny($sql$
 UPDATE public.special_credit_campaigns SET status='PUBLISHED'
 WHERE id='a2222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
$sql$);

-- No one in tenant A has visibility into tenant B's private authorizations.
DO $$
BEGIN
 IF EXISTS (SELECT 1 FROM public.special_credit_grants
  WHERE tenant_id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb') THEN
  RAISE EXCEPTION 'TENANT_LEAK';
 END IF;
END $$;

RESET ROLE;
RESET ALL;
SELECT 'M39020_SQL_SECURITY_E2E=PASS' AS result;
