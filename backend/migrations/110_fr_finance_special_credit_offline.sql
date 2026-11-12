-- FR Finance AI Studio / M39012
-- MIGRATION CANDIDATE ONLY. GitHub CI with disposable PostgreSQL first.
-- NEVER apply on 127.0.0.1:5433/frcaixinha_aistudio_dev without explicit approval and backup.
-- No Pix, no loans, no email, no mobile-push dispatch.
-- M39020: SQL110+111 MUST run together with psql --single-transaction.
-- Standalone -f without explicit session gate is intentionally forbidden.
DO $$
DECLARE mode text := current_setting('frfinance.m39020_migration_mode',true);
BEGIN
 IF mode='CI_DISPOSABLE' THEN
   IF current_database()<>'frfinance_ci_credit' OR inet_server_port()<>5432
      OR session_user<>'postgres' THEN
     RAISE EXCEPTION 'M39020 CI must use disposable database';
   END IF;
 ELSIF mode='LOCAL_AUTHORIZED' THEN
   IF current_database()<>'frcaixinha_aistudio_dev'
      OR inet_server_port()<>5433 OR session_user<>'frc_ai_owner' THEN
     RAISE EXCEPTION 'M39020 local identity mismatch';
   END IF;
 ELSE
   RAISE EXCEPTION 'M39020 migration requires explicit atomic session gate';
 END IF;
END $$;


CREATE TABLE IF NOT EXISTS public.special_credit_grants (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 cycle_id uuid NOT NULL REFERENCES public.cycles(id),
 member_id uuid NOT NULL REFERENCES public.memberships(id),
 created_by uuid NOT NULL REFERENCES public.users(id),
 ceiling_brl numeric(15,2) NOT NULL CHECK (ceiling_brl > 0),
 reason varchar(2000) NOT NULL CHECK (length(btrim(reason)) >= 20),
 expires_at timestamptz NOT NULL,
 status varchar(12) NOT NULL DEFAULT 'ACTIVE'
   CHECK (status IN ('ACTIVE','REVOKED','EXPIRED')),
 request_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,created_by,request_id,member_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_special_active_member_cycle
 ON public.special_credit_grants (tenant_id,cycle_id,member_id)
 WHERE status='ACTIVE';
CREATE INDEX IF NOT EXISTS ix_special_grants_member
 ON public.special_credit_grants(tenant_id,member_id,expires_at);

CREATE TABLE IF NOT EXISTS public.special_credit_campaigns (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 cycle_id uuid NOT NULL REFERENCES public.cycles(id),
 created_by uuid NOT NULL REFERENCES public.users(id),
 title varchar(100) NOT NULL CHECK (length(btrim(title)) >= 4),
 body varchar(500) NOT NULL CHECK (length(btrim(body)) >= 10),
 expires_at timestamptz NOT NULL,
 status varchar(16) NOT NULL DEFAULT 'DRAFT'
   CHECK (status IN ('DRAFT','PUBLISHED','CANCELLED')),
 request_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz,
 UNIQUE(tenant_id,created_by,request_id)
);
CREATE INDEX IF NOT EXISTS ix_special_campaign_tenant
 ON public.special_credit_campaigns(tenant_id,created_at DESC);

CREATE TABLE IF NOT EXISTS public.special_credit_recipients (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 campaign_id uuid NOT NULL REFERENCES public.special_credit_campaigns(id),
 grant_id uuid NOT NULL REFERENCES public.special_credit_grants(id),
 member_id uuid NOT NULL REFERENCES public.memberships(id),
 user_id uuid NOT NULL REFERENCES public.users(id),
 response_status varchar(16) NOT NULL DEFAULT 'PENDING'
   CHECK (response_status IN ('PENDING','INTERESTED','DECLINED')),
 responded_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(campaign_id,member_id),
 UNIQUE(campaign_id,grant_id)
);
CREATE INDEX IF NOT EXISTS ix_special_recipients_user
 ON public.special_credit_recipients(tenant_id,user_id);

CREATE TABLE IF NOT EXISTS public.special_credit_preferences (
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 user_id uuid NOT NULL REFERENCES public.users(id),
 channel varchar(10) NOT NULL CHECK (channel IN ('PUSH','EMAIL','WHATSAPP','SMS')),
 opted_in boolean NOT NULL DEFAULT false,
 changed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,user_id,channel)
);

CREATE TABLE IF NOT EXISTS public.special_credit_outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 campaign_id uuid NOT NULL REFERENCES public.special_credit_campaigns(id),
 recipient_id uuid NOT NULL REFERENCES public.special_credit_recipients(id),
 channel varchar(10) NOT NULL CHECK (channel IN ('PUSH','EMAIL','WHATSAPP','SMS')),
 state varchar(24) NOT NULL DEFAULT 'BLOCKED_EXTERNAL'
   CHECK (state IN ('BLOCKED_EXTERNAL','DISPATCH_REVIEW','CANCELLED')),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(campaign_id,recipient_id,channel)
);
-- Deliberately no network sender, outbox worker or transition to SENT.

CREATE TABLE IF NOT EXISTS public.special_credit_audit (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 actor_id uuid NOT NULL REFERENCES public.users(id),
 entity_kind varchar(40) NOT NULL,
 entity_id uuid NOT NULL,
 action varchar(60) NOT NULL,
 detail varchar(250) NOT NULL,
 occurred_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_app') THEN
   RAISE EXCEPTION 'frc_ai_app role not provisioned; migration refused';
 END IF;
END $$;
GRANT USAGE ON SCHEMA public TO frc_ai_app;
GRANT SELECT,INSERT ON public.special_credit_grants TO frc_ai_app;
GRANT UPDATE(status,updated_at) ON public.special_credit_grants TO frc_ai_app;
GRANT SELECT,INSERT ON public.special_credit_campaigns TO frc_ai_app;
GRANT UPDATE(status,published_at) ON public.special_credit_campaigns TO frc_ai_app;
GRANT SELECT,INSERT ON public.special_credit_recipients TO frc_ai_app;
GRANT UPDATE(response_status,responded_at) ON public.special_credit_recipients TO frc_ai_app;
GRANT SELECT,INSERT ON public.special_credit_preferences TO frc_ai_app;
GRANT UPDATE(opted_in,changed_at) ON public.special_credit_preferences TO frc_ai_app;
GRANT SELECT,INSERT ON public.special_credit_outbox TO frc_ai_app;
GRANT SELECT,INSERT ON public.special_credit_audit TO frc_ai_app;

ALTER TABLE public.special_credit_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_grants FORCE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_campaigns FORCE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_recipients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_recipients FORCE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_preferences FORCE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_outbox FORCE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.special_credit_audit FORCE ROW LEVEL SECURITY;

-- Session context comes ONLY from backend get_rls_db_connection (SET LOCAL).
-- ADMIN role is additionally bound to actual tenants.admin_user_id.
CREATE POLICY sc_grant_read ON public.special_credit_grants
 FOR SELECT TO frc_ai_app USING (
 tenant_id::text = current_setting('app.current_tenant_id',true)
 AND (
  (current_setting('app.current_role',true)='TENANT_ADMIN'
   AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_grants.tenant_id
      AND t.admin_user_id::text=current_setting('app.current_user_id',true)))
  OR (current_setting('app.current_role',true)='TENANT_MEMBER'
      AND EXISTS (SELECT 1 FROM public.memberships m WHERE m.id=special_credit_grants.member_id
        AND m.user_id::text=current_setting('app.current_user_id',true)
        AND m.tenant_id=special_credit_grants.tenant_id AND m.status='ATIVA'))
 )
);
CREATE POLICY sc_grant_admin_insert ON public.special_credit_grants
 FOR INSERT TO frc_ai_app WITH CHECK (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND created_by::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_grants.tenant_id AND t.admin_user_id=special_credit_grants.created_by)
 AND EXISTS (SELECT 1 FROM public.memberships m WHERE m.id=special_credit_grants.member_id
     AND m.tenant_id=special_credit_grants.tenant_id AND m.status='ATIVA' AND m.role='TENANT_MEMBER')
 AND EXISTS (SELECT 1 FROM public.cycles c WHERE c.id=special_credit_grants.cycle_id AND c.tenant_id=special_credit_grants.tenant_id
     AND c.status='ABERTO')
);
CREATE POLICY sc_grant_admin_update ON public.special_credit_grants
 FOR UPDATE TO frc_ai_app
 USING (tenant_id::text=current_setting('app.current_tenant_id',true)
  AND current_setting('app.current_role',true)='TENANT_ADMIN'
  AND created_by::text=current_setting('app.current_user_id',true))
 WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true)
  AND current_setting('app.current_role',true)='TENANT_ADMIN'
  AND created_by::text=current_setting('app.current_user_id',true));

CREATE POLICY sc_campaign_read ON public.special_credit_campaigns
 FOR SELECT TO frc_ai_app USING (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND (
  (current_setting('app.current_role',true)='TENANT_ADMIN'
   AND created_by::text=current_setting('app.current_user_id',true))
  OR (current_setting('app.current_role',true)='TENANT_MEMBER'
      AND status='PUBLISHED'
      AND EXISTS (SELECT 1 FROM public.special_credit_recipients r
        WHERE r.campaign_id=special_credit_campaigns.id AND r.tenant_id=special_credit_campaigns.tenant_id
          AND r.user_id::text=current_setting('app.current_user_id',true)))
 ));
CREATE POLICY sc_campaign_insert ON public.special_credit_campaigns
 FOR INSERT TO frc_ai_app WITH CHECK (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND created_by::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_campaigns.tenant_id AND t.admin_user_id=special_credit_campaigns.created_by)
 AND EXISTS (SELECT 1 FROM public.cycles c WHERE c.id=special_credit_campaigns.cycle_id AND c.tenant_id=special_credit_campaigns.tenant_id AND c.status='ABERTO'));
CREATE POLICY sc_campaign_update ON public.special_credit_campaigns
 FOR UPDATE TO frc_ai_app
 USING (tenant_id::text=current_setting('app.current_tenant_id',true)
 AND created_by::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN')
 WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true)
 AND created_by::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN');

CREATE POLICY sc_recipient_read ON public.special_credit_recipients
 FOR SELECT TO frc_ai_app USING (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND (
  (current_setting('app.current_role',true)='TENANT_MEMBER'
   AND user_id::text=current_setting('app.current_user_id',true))
  OR (current_setting('app.current_role',true)='TENANT_ADMIN'
   AND EXISTS(SELECT 1 FROM public.tenants t WHERE t.id=special_credit_recipients.tenant_id
     AND t.admin_user_id::text=current_setting('app.current_user_id',true)))
 ));
CREATE POLICY sc_recipient_insert ON public.special_credit_recipients
 FOR INSERT TO frc_ai_app WITH CHECK (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_recipients.tenant_id
  AND t.admin_user_id::text=current_setting('app.current_user_id',true))
 AND EXISTS (SELECT 1 FROM public.special_credit_grants g WHERE g.id=special_credit_recipients.grant_id
   AND g.tenant_id=special_credit_recipients.tenant_id AND g.member_id=special_credit_recipients.member_id)
 AND EXISTS (SELECT 1 FROM public.memberships m WHERE m.id=special_credit_recipients.member_id
   AND m.tenant_id=special_credit_recipients.tenant_id AND m.user_id=special_credit_recipients.user_id AND m.status='ATIVA'));
CREATE POLICY sc_recipient_reply ON public.special_credit_recipients
 FOR UPDATE TO frc_ai_app
 USING (tenant_id::text=current_setting('app.current_tenant_id',true)
  AND user_id::text=current_setting('app.current_user_id',true)
  AND current_setting('app.current_role',true)='TENANT_MEMBER')
 WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true)
  AND user_id::text=current_setting('app.current_user_id',true)
  AND current_setting('app.current_role',true)='TENANT_MEMBER');

CREATE POLICY sc_pref_read ON public.special_credit_preferences
 FOR SELECT TO frc_ai_app USING (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND (user_id::text=current_setting('app.current_user_id',true)
 OR (current_setting('app.current_role',true)='TENANT_ADMIN'
  AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_preferences.tenant_id
       AND t.admin_user_id::text=current_setting('app.current_user_id',true))))
);
CREATE POLICY sc_pref_write ON public.special_credit_preferences
 FOR INSERT TO frc_ai_app WITH CHECK (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND user_id::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_MEMBER'
 AND EXISTS (SELECT 1 FROM public.memberships m WHERE m.tenant_id=special_credit_preferences.tenant_id
   AND m.user_id=special_credit_preferences.user_id AND m.status='ATIVA' AND m.role='TENANT_MEMBER')
);
CREATE POLICY sc_pref_update ON public.special_credit_preferences
 FOR UPDATE TO frc_ai_app
 USING (tenant_id::text=current_setting('app.current_tenant_id',true)
 AND user_id::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_MEMBER')
 WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true)
 AND user_id::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true)='TENANT_MEMBER');

CREATE POLICY sc_outbox_read ON public.special_credit_outbox
 FOR SELECT TO frc_ai_app USING (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_outbox.tenant_id
  AND t.admin_user_id::text=current_setting('app.current_user_id',true))
);
CREATE POLICY sc_outbox_insert ON public.special_credit_outbox
 FOR INSERT TO frc_ai_app WITH CHECK (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_outbox.tenant_id
  AND t.admin_user_id::text=current_setting('app.current_user_id',true))
 AND state='BLOCKED_EXTERNAL');

CREATE POLICY sc_audit_read ON public.special_credit_audit
 FOR SELECT TO frc_ai_app USING (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND EXISTS (SELECT 1 FROM public.tenants t WHERE t.id=special_credit_audit.tenant_id
  AND t.admin_user_id::text=current_setting('app.current_user_id',true))
);
CREATE POLICY sc_audit_insert ON public.special_credit_audit
 FOR INSERT TO frc_ai_app WITH CHECK (
 tenant_id::text=current_setting('app.current_tenant_id',true)
 AND actor_id::text=current_setting('app.current_user_id',true)
 AND current_setting('app.current_role',true) IN ('TENANT_ADMIN','TENANT_MEMBER')
);

