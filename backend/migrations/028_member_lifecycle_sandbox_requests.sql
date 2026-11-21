-- FR Caixinha AI Studio — migration 028: fila imutável de EVENTOS DE TESTE
-- Desenvolvimento de fluxo jurídico/técnico permitido. Nenhum bloqueio
-- patrimonial, exclusão de lucro, alteração de memberships ou dinheiro real.
-- Aplicar SOMENTE em PostgreSQL descartável CI nesta etapa; NÃO usar no 5433.
CREATE TABLE public.member_lifecycle_requests (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
  cycle_id uuid NOT NULL,
  membership_id uuid NOT NULL,
  requested_by_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  request_kind varchar(32) NOT NULL
    CHECK (request_kind IN ('VOLUNTARY_EXIT','DELINQUENCY_REVIEW')),
  idempotency_key uuid NOT NULL,
  policy_reference varchar(120) NOT NULL
    CHECK (policy_reference ~ '^[A-Za-z0-9._:-]{8,120}$'),
  status varchar(40) NOT NULL DEFAULT 'PENDING_REVIEW'
    CHECK (status = 'PENDING_REVIEW'),
  requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  bank_reconciled boolean NOT NULL DEFAULT false
    CHECK (bank_reconciled = false),
  financial_effect_applied boolean NOT NULL DEFAULT false
    CHECK (financial_effect_applied = false),
  UNIQUE (tenant_id,membership_id,request_kind,idempotency_key),
  FOREIGN KEY (cycle_id,tenant_id)
    REFERENCES public.cycles(id,tenant_id) ON DELETE RESTRICT,
  FOREIGN KEY (membership_id,tenant_id)
    REFERENCES public.memberships(id,tenant_id) ON DELETE RESTRICT
);
-- A trilha da solicitação só recebe novos eventos; a aplicação não pode
-- alterar status ou excluir solicitações passadas. Operador CI pode limpar.
CREATE UNIQUE INDEX member_lifecycle_one_pending_per_cycle_kind
ON public.member_lifecycle_requests
  (tenant_id,cycle_id,membership_id,request_kind)
WHERE status='PENDING_REVIEW';
CREATE INDEX member_lifecycle_tenant_cycle_queue
ON public.member_lifecycle_requests(tenant_id,cycle_id,requested_at DESC,id);
CREATE INDEX member_lifecycle_own_queue
ON public.member_lifecycle_requests(tenant_id,requested_by_user_id,requested_at DESC);

ALTER TABLE public.member_lifecycle_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.member_lifecycle_requests FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.member_lifecycle_requests
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;

-- Master não herda consulta financeira de nenhum tenant.
CREATE POLICY member_lifecycle_admin_select
ON public.member_lifecycle_requests FOR SELECT TO frcaixinha_app_role
USING (
  tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
  AND current_setting('app.current_role',true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(
    NULLIF(current_setting('app.current_user_id',true),'')::uuid,
    tenant_id
  )
);
-- Membro vê SOMENTE suas próprias solicitações, não as de outros usuários.
CREATE POLICY member_lifecycle_own_select
ON public.member_lifecycle_requests FOR SELECT TO frcaixinha_app_role
USING (
  tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
  AND current_setting('app.current_role',true)='TENANT_MEMBER'
  AND requested_by_user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
  AND membership_id IN (
    SELECT public.rls_user_membership_ids(
      NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id
    )
  )
);
GRANT SELECT ON public.member_lifecycle_requests TO frcaixinha_app_role;

-- Apenas função restrita cria pedido em homologação. Inexistem UPDATE/DELETE.
-- Params jamais contêm user_id/role/status: origem é a sessão autenticada.
CREATE FUNCTION public.lifecycle_submit_request_sandbox(
    p_tenant uuid,p_cycle uuid,p_membership uuid,
    p_kind varchar,p_idempotency uuid,p_policy_reference varchar
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE
 v_user uuid; v_ctx_tenant uuid; v_role text;
 v_id uuid; v_old_policy varchar; v_old_actor uuid;
BEGIN
 v_user:=NULLIF(current_setting('app.current_user_id',true),'')::uuid;
 v_ctx_tenant:=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid;
 v_role:=current_setting('app.current_role',true);
 IF v_user IS NULL OR p_tenant IS NULL OR p_tenant<>v_ctx_tenant
    OR p_cycle IS NULL OR p_membership IS NULL OR p_idempotency IS NULL
    OR p_kind NOT IN ('VOLUNTARY_EXIT','DELINQUENCY_REVIEW')
    OR p_policy_reference IS NULL
    OR p_policy_reference !~ '^[A-Za-z0-9._:-]{8,120}$'
 THEN
    RAISE EXCEPTION 'BLOQUEADO: solicitacao sem contexto ou evidencia';
 END IF;
 IF NOT EXISTS (
    SELECT 1 FROM public.cycles c
    WHERE c.id=p_cycle AND c.tenant_id=p_tenant
      AND c.status IN ('ABERTO','CONGELADO','EM_APURACAO')
 ) THEN
    RAISE EXCEPTION 'BLOQUEADO: ciclo encerrado, inexistente ou de outro tenant';
 END IF;
 IF p_kind='VOLUNTARY_EXIT' THEN
    IF v_role<>'TENANT_MEMBER' OR NOT EXISTS (
      SELECT 1 FROM public.memberships m WHERE m.id=p_membership
      AND m.tenant_id=p_tenant AND m.user_id=v_user
      AND m.role='TENANT_MEMBER' AND m.status='ATIVA'
    ) THEN
      RAISE EXCEPTION 'BLOQUEADO: somente o proprio membro ativo solicita saida';
    END IF;
 ELSIF p_kind='DELINQUENCY_REVIEW' THEN
    IF v_role<>'TENANT_ADMIN'
      OR NOT public.rls_is_tenant_admin(v_user,p_tenant)
      OR NOT EXISTS (
        SELECT 1 FROM public.memberships m
        WHERE m.id=p_membership AND m.tenant_id=p_tenant
          AND m.role='TENANT_MEMBER' AND m.status IN ('ATIVA','SUSPENSA')
      ) THEN
      RAISE EXCEPTION 'BLOQUEADO: somente administrador do tenant solicita revisao';
    END IF;
 END IF;
 -- A política é uma etiqueta de controle. O pedido NÃO aplica sanções,
 -- não presume aceite documental nem confirma direito financeiro.
 INSERT INTO public.member_lifecycle_requests (
    tenant_id,cycle_id,membership_id,requested_by_user_id,
    request_kind,idempotency_key,policy_reference
 ) VALUES (
    p_tenant,p_cycle,p_membership,v_user,p_kind,p_idempotency,p_policy_reference
 )
 ON CONFLICT DO NOTHING RETURNING id INTO v_id;
 IF v_id IS NULL THEN
   SELECT id,policy_reference,requested_by_user_id INTO v_id,v_old_policy,v_old_actor
   FROM public.member_lifecycle_requests
   WHERE tenant_id=p_tenant AND cycle_id=p_cycle
      AND membership_id=p_membership AND request_kind=p_kind
      AND status='PENDING_REVIEW';
   IF v_id IS NULL OR v_old_policy IS DISTINCT FROM p_policy_reference
       OR v_old_actor IS DISTINCT FROM v_user THEN
     RAISE EXCEPTION 'BLOQUEADO: idempotencia/politica conflitante';
   END IF;
 END IF;
 RETURN v_id;
END $$;

REVOKE ALL ON FUNCTION public.lifecycle_submit_request_sandbox(
 uuid,uuid,uuid,varchar,uuid,varchar
) FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.lifecycle_submit_request_sandbox(
 uuid,uuid,uuid,varchar,uuid,varchar
) TO frcaixinha_app_role;

DO $guard$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE
    oid='public.member_lifecycle_requests'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR NOT has_table_privilege(
    'frcaixinha_app_role','public.member_lifecycle_requests','SELECT'
 ) OR has_table_privilege(
    'frcaixinha_app_role','public.member_lifecycle_requests','INSERT'
 ) OR has_table_privilege(
    'frcaixinha_app_role','public.member_lifecycle_requests','UPDATE'
 ) OR has_table_privilege(
    'frcaixinha_app_role','public.member_lifecycle_requests','DELETE'
 ) OR has_table_privilege(
    'frcaixinha_auth_role','public.member_lifecycle_requests','SELECT'
 ) OR NOT has_function_privilege(
    'frcaixinha_app_role',
    'public.lifecycle_submit_request_sandbox(uuid,uuid,uuid,varchar,uuid,varchar)',
    'EXECUTE'
 ) OR has_function_privilege(
    'frcaixinha_auth_role',
    'public.lifecycle_submit_request_sandbox(uuid,uuid,uuid,varchar,uuid,varchar)',
    'EXECUTE'
 ) THEN
    RAISE EXCEPTION 'BLOQUEADO: filas de ciclo sem segregacao/RLS';
 END IF;
END $guard$;
