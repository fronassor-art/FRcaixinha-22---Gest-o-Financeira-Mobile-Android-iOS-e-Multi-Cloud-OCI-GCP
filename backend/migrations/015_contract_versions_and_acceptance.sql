-- AI Studio 015: documentos versionados e aceite auditável, ainda SEM habilitar aceite público.
-- Os arquivos originais não são recriados. O hash SHA-256 refere-se à versão aprovada.
CREATE TABLE public.contract_documents (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  document_kind varchar(32) NOT NULL CHECK(document_kind IN ('PLATFORM_LICENSE','TENANT_MEMBERSHIP')),
  version_label varchar(60) NOT NULL,
  sha256 char(64) NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
  source_reference text NOT NULL CHECK(length(trim(source_reference)) >= 8),
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(document_kind,version_label),
  UNIQUE(id,document_kind)
);
CREATE TABLE public.contract_acceptances (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  document_id uuid NOT NULL REFERENCES public.contract_documents(id),
  document_kind varchar(32) NOT NULL,
  user_id uuid NOT NULL REFERENCES public.users(id),
  tenant_id uuid REFERENCES public.tenants(id),
  accepted_at timestamptz NOT NULL DEFAULT now(),
  evidence_hash char(64) NOT NULL CHECK(evidence_hash ~ '^[0-9a-f]{64}$'),
  evidence_method varchar(32) NOT NULL CHECK(evidence_method IN ('CI_VERIFIED_IDENTITY','PROVIDER_VERIFIED')),
  UNIQUE NULLS NOT DISTINCT (document_id,user_id,tenant_id),
  FOREIGN KEY (document_id,document_kind) REFERENCES public.contract_documents(id,document_kind),
  CHECK ((document_kind='PLATFORM_LICENSE' AND tenant_id IS NULL) OR
         (document_kind='TENANT_MEMBERSHIP' AND tenant_id IS NOT NULL))
);
CREATE INDEX contract_acceptances_actor ON public.contract_acceptances(user_id,accepted_at DESC);
ALTER TABLE public.contract_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE public.contract_acceptances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_acceptances FORCE ROW LEVEL SECURITY;

-- Permite somente examinar versões publicadas, não inventar novos termos via API.
CREATE POLICY contract_documents_authenticated_read
ON public.contract_documents FOR SELECT TO frcaixinha_app_role
USING (
  published_at IS NOT NULL
  AND NULLIF(current_setting('app.current_user_id',true),'') IS NOT NULL
  AND (
    (current_setting('app.current_role',true)='MASTER'
      AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid))
    OR (
      current_setting('app.current_role',true) IN ('TENANT_ADMIN','TENANT_MEMBER')
      AND NULLIF(current_setting('app.current_tenant_id',true),'')::uuid IN
       (SELECT public.rls_user_active_tenants(
          NULLIF(current_setting('app.current_user_id',true),'')::uuid
       ))
    )
  )
);
-- Cada pessoa consulta apenas seu próprio aceite. MASTER não herda aceite de terceiros.
CREATE POLICY contract_acceptances_own_read
ON public.contract_acceptances FOR SELECT TO frcaixinha_app_role
USING (
  user_id = NULLIF(current_setting('app.current_user_id',true),'')::uuid
  AND (
    (tenant_id IS NULL AND (
      (current_setting('app.current_role',true)='MASTER'
        AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid))
      OR (document_kind='PLATFORM_LICENSE'
        AND current_setting('app.current_role',true)='TENANT_ADMIN'
        AND public.rls_is_tenant_admin(
          NULLIF(current_setting('app.current_user_id',true),'')::uuid,
          NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
        ))
    ))
    OR (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
      AND current_setting('app.current_role',true) IN ('TENANT_ADMIN','TENANT_MEMBER')
      AND tenant_id IN (
        SELECT public.rls_user_active_tenants(
          NULLIF(current_setting('app.current_user_id',true),'')::uuid
        )
      )
    )
  )
);
GRANT SELECT ON public.contract_documents,public.contract_acceptances TO frcaixinha_app_role;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON public.contract_documents,public.contract_acceptances
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
-- Imutabilidade também para eventuais permissões futuras, exceto operador privilegiado CI.
CREATE OR REPLACE FUNCTION public.reject_contract_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Documento/aceite imutável. Publique nova versão em vez de editar.';
END $$;
REVOKE ALL ON FUNCTION public.reject_contract_mutation() FROM PUBLIC;
CREATE TRIGGER contract_documents_immutable
  BEFORE UPDATE OR DELETE ON public.contract_documents
  FOR EACH ROW EXECUTE FUNCTION public.reject_contract_mutation();
CREATE TRIGGER contract_acceptances_immutable
  BEFORE UPDATE OR DELETE ON public.contract_acceptances
  FOR EACH ROW EXECUTE FUNCTION public.reject_contract_mutation();
