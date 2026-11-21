-- AI Studio: ciclo de vida seguro de convite e recuperação de conta.
-- Esquema de PREPARAÇÃO. Nenhum endpoint público é habilitado por esta migration.
-- Não gera e-mails, contas, vínculos ou tokens reais automaticamente.
ALTER TABLE public.invitations
  ADD COLUMN revoked_at timestamptz,
  ADD COLUMN delivered_at timestamptz,
  ADD COLUMN accepted_user_id uuid REFERENCES public.users(id),
  ADD COLUMN accepted_membership_id uuid REFERENCES public.memberships(id),
  ADD COLUMN delivery_status varchar(30) NOT NULL DEFAULT 'PENDING_DELIVERY'
    CHECK (delivery_status IN ('PENDING_DELIVERY','DELIVERED','DELIVERY_FAILED'));

ALTER TABLE public.invitations
  ADD CONSTRAINT invitations_not_revoked_and_accepted
    CHECK (revoked_at IS NULL OR accepted_at IS NULL),
  ADD CONSTRAINT invitations_acceptance_metadata
    CHECK (
      (accepted_at IS NULL AND accepted_user_id IS NULL AND accepted_membership_id IS NULL)
      OR (accepted_at IS NOT NULL AND accepted_user_id IS NOT NULL
          AND accepted_membership_id IS NOT NULL)
    ),
  ADD CONSTRAINT invitations_member_requires_tenant
    CHECK (target_role <> 'TENANT_MEMBER' OR tenant_id IS NOT NULL),
  ADD CONSTRAINT invitations_delivery_before_acceptance
    CHECK (accepted_at IS NULL OR delivery_status='DELIVERED');

CREATE INDEX invitations_pending_target_lookup
  ON public.invitations(lower(target_email), expires_at)
  WHERE accepted_at IS NULL AND revoked_at IS NULL;

ALTER TABLE public.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invitations FORCE ROW LEVEL SECURITY;
-- Intencionalmente SEM política para app/auth: só operador de CI descartável
-- pode testar mutações; concessões posteriores dependem de revisão de segurança.
REVOKE ALL ON TABLE public.invitations
  FROM PUBLIC, frcaixinha_app_role, frcaixinha_auth_role;

CREATE TABLE public.password_reset_tokens (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  token_hash char(64) NOT NULL UNIQUE
    CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  requested_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  revoked_at timestamptz,
  delivery_status varchar(30) NOT NULL DEFAULT 'PENDING_DELIVERY'
    CHECK (delivery_status IN ('PENDING_DELIVERY','DELIVERED','DELIVERY_FAILED')),
  CHECK (expires_at > requested_at AND expires_at <= requested_at + interval '30 minutes'),
  CHECK (consumed_at IS NULL OR revoked_at IS NULL),
  CHECK (consumed_at IS NULL OR delivery_status='DELIVERED')
);

CREATE INDEX reset_pending_by_user
  ON public.password_reset_tokens(user_id, expires_at)
  WHERE consumed_at IS NULL AND revoked_at IS NULL;

ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_tokens FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.password_reset_tokens
  FROM PUBLIC, frcaixinha_app_role, frcaixinha_auth_role;

DO $verify_lifecycle$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_roles r
    WHERE r.rolname IN ('frcaixinha_app_role','frcaixinha_auth_role')
      AND (
        has_table_privilege(r.rolname,'public.invitations','SELECT')
        OR has_table_privilege(r.rolname,'public.invitations','INSERT')
        OR has_table_privilege(r.rolname,'public.password_reset_tokens','SELECT')
        OR has_table_privilege(r.rolname,'public.password_reset_tokens','INSERT')
      )
  ) THEN
    RAISE EXCEPTION 'BLOQUEADO: credencial app/auth pode acessar tokens ainda sem fluxo aprovado';
  END IF;
END
$verify_lifecycle$;
