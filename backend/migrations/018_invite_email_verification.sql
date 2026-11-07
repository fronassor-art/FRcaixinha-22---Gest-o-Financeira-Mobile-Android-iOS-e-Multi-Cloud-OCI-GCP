-- AI Studio 018: identidade e prova de titularidade para ingresso por convite.
-- Somente estrutura; nao cria usuarios nem envia e-mail.
ALTER TABLE public.users
 ADD COLUMN email_verified_at timestamptz;
CREATE UNIQUE INDEX users_email_normalized_unique
 ON public.users(lower(email));
ALTER TABLE public.invitations
 ADD COLUMN required_document_id uuid REFERENCES public.contract_documents(id),
 ADD COLUMN delivery_attempts integer NOT NULL DEFAULT 0
   CHECK(delivery_attempts BETWEEN 0 AND 10),
 ADD COLUMN last_delivery_attempt_at timestamptz;
-- Validacao de titularidade por convite nao deve conceder MASTER.
CREATE TABLE public.invite_email_verification (
 id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
 invitation_id uuid NOT NULL REFERENCES public.invitations(id) ON DELETE CASCADE,
 recipient_email varchar(255) NOT NULL,
 token_hash char(64) NOT NULL UNIQUE CHECK(token_hash ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 revoked_at timestamptz,
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '48 hours'),
 CHECK(consumed_at IS NULL OR revoked_at IS NULL)
);
CREATE INDEX invite_email_verification_active
 ON public.invite_email_verification(invitation_id,expires_at)
 WHERE consumed_at IS NULL AND revoked_at IS NULL;
ALTER TABLE public.invite_email_verification ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invite_email_verification FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.invite_email_verification
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
-- Garantir que o papel app nao consiga marcar email como verificado.
REVOKE UPDATE(email_verified_at) ON public.users FROM PUBLIC,frcaixinha_app_role;
DO $$
BEGIN
 IF has_column_privilege('frcaixinha_app_role','public.users','email_verified_at','UPDATE')
    OR has_table_privilege('frcaixinha_app_role','public.invite_email_verification','SELECT')
    OR has_table_privilege('frcaixinha_auth_role','public.invite_email_verification','INSERT')
 THEN
   RAISE EXCEPTION 'Acesso privilegiado a verificacao de e-mail indevido';
 END IF;
END $$;
