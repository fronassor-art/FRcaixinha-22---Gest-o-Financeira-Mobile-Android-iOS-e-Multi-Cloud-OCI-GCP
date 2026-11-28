-- AI Studio M19300: LOCAL Termux PG18 or explicitly isolated CI only.
-- This DDL creates records of REQUEST/REVIEW, NEVER sanctions, Pix, payout or ledger.
DO $local_migration_guard$
BEGIN
 IF NOT (
    (current_database()='frcaixinha_aistudio_dev'
      AND current_user='frc_ai_owner'
      AND session_user='frc_ai_owner'
      AND inet_server_port()=5433
      AND current_setting('data_directory')=
        '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
      AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999)
   OR
    (current_database()='frcaixinha_ci'
      AND session_user='postgres'
      AND current_setting('is_superuser')='on'
      AND current_setting('frcaixinha.lifecycle_local_ci',true)='1')
  ) THEN
  RAISE EXCEPTION 'M19300 migration denied outside approved AI Studio local/isolated CI';
 END IF;
END $local_migration_guard$;

-- FR Caixinha AI Studio — migration 029: revisão e contestação de pedidos.
-- Fork local para homologacao: aplicacao controlada com backup e guard de sessao.
-- Não altera membros, capital, rateio, fechamento, pix ou aprovação jurídica.
ALTER TABLE public.member_lifecycle_requests
  ADD CONSTRAINT member_lifecycle_request_id_tenant_unique UNIQUE (id,tenant_id);

CREATE TABLE public.member_lifecycle_review_events (
  event_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
  tenant_id uuid NOT NULL,
  request_id uuid NOT NULL,
  membership_id uuid NOT NULL,
  actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  idempotency_key uuid NOT NULL,
  event_kind varchar(40) NOT NULL CHECK (
    event_kind IN (
      'ADMIN_DOCUMENTS_REQUESTED',
      'ADMIN_REVIEW_ACCEPTED_SANDBOX',
      'ADMIN_REVIEW_REJECTED_SANDBOX',
      'MEMBER_CONTESTED'
    )
  ),
  evidence_reference varchar(120) NOT NULL
    CHECK (evidence_reference ~ '^[A-Za-z0-9._:-]{8,120}$'),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  financial_effect_applied boolean NOT NULL DEFAULT false
    CHECK (financial_effect_applied=false),
  bank_reconciled boolean NOT NULL DEFAULT false
    CHECK (bank_reconciled=false),
  UNIQUE (tenant_id,request_id,actor_user_id,idempotency_key),
  FOREIGN KEY (request_id,tenant_id)
    REFERENCES public.member_lifecycle_requests(id,tenant_id) ON DELETE RESTRICT,
  FOREIGN KEY (membership_id,tenant_id)
    REFERENCES public.memberships(id,tenant_id) ON DELETE RESTRICT
);

CREATE INDEX member_lifecycle_review_request_order
ON public.member_lifecycle_review_events(tenant_id,request_id,event_seq DESC);
CREATE INDEX member_lifecycle_review_actor_order
ON public.member_lifecycle_review_events(tenant_id,actor_user_id,event_seq DESC);

ALTER TABLE public.member_lifecycle_review_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.member_lifecycle_review_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.member_lifecycle_review_events
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;

CREATE POLICY member_lifecycle_review_admin_read
ON public.member_lifecycle_review_events FOR SELECT TO frcaixinha_app_role
USING (
  tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
  AND current_setting('app.current_role',true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(
    NULLIF(current_setting('app.current_user_id',true),'')::uuid,
    tenant_id
  )
);
CREATE POLICY member_lifecycle_review_member_read
ON public.member_lifecycle_review_events FOR SELECT TO frcaixinha_app_role
USING (
  tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
  AND current_setting('app.current_role',true)='TENANT_MEMBER'
  AND membership_id IN (
    SELECT public.rls_user_membership_ids(
      NULLIF(current_setting('app.current_user_id',true),'')::uuid,
      tenant_id
    )
  )
);
-- Em 028 o membro via status PENDING via apenas seus pedidos iniciados.
-- Ao receber revisão de inadimplência aberta pelo admin, agora pode ver
-- a solicitação que lhe diz respeito e apresentar contestação.
CREATE POLICY member_lifecycle_subject_read
ON public.member_lifecycle_requests FOR SELECT TO frcaixinha_app_role
USING (
  tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
  AND current_setting('app.current_role',true)='TENANT_MEMBER'
  AND membership_id IN (
    SELECT public.rls_user_membership_ids(
      NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id
    )
  )
);

GRANT SELECT ON public.member_lifecycle_review_events TO frcaixinha_app_role;

-- SECURITY DEFINER sempre verifica sessão, tenant, sujeito, autoria e papéis.
-- Bloqueio de linha serializa decisões simultâneas sobre a mesma solicitação.
CREATE FUNCTION public.lifecycle_append_review_event_sandbox(
 p_tenant uuid, p_request uuid, p_event_kind varchar,
 p_idempotency uuid, p_evidence_reference varchar
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 v_actor uuid;
 v_ctx_tenant uuid;
 v_role text;
 v_req public.member_lifecycle_requests%ROWTYPE;
 v_prev text;
 v_existing public.member_lifecycle_review_events%ROWTYPE;
 v_id uuid;
BEGIN
 v_actor:=NULLIF(current_setting('app.current_user_id',true),'')::uuid;
 v_ctx_tenant:=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid;
 v_role:=current_setting('app.current_role',true);
 IF v_actor IS NULL OR p_tenant IS NULL OR p_tenant<>v_ctx_tenant
    OR p_request IS NULL OR p_idempotency IS NULL
    OR p_evidence_reference IS NULL
    OR p_evidence_reference !~ '^[A-Za-z0-9._:-]{8,120}$'
    OR p_event_kind NOT IN (
      'ADMIN_DOCUMENTS_REQUESTED','ADMIN_REVIEW_ACCEPTED_SANDBOX',
      'ADMIN_REVIEW_REJECTED_SANDBOX','MEMBER_CONTESTED'
    )
 THEN
    RAISE EXCEPTION 'BLOQUEADO: evento sem identidade, politica ou contexto';
 END IF;
 SELECT * INTO v_req FROM public.member_lifecycle_requests
 WHERE id=p_request AND tenant_id=p_tenant FOR UPDATE;
 IF NOT FOUND OR v_req.status<>'PENDING_REVIEW' THEN
    RAISE EXCEPTION 'BLOQUEADO: solicitacao nao encontrada ou estado incompativel';
 END IF;

 IF p_event_kind='MEMBER_CONTESTED' THEN
   IF v_role<>'TENANT_MEMBER' OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.id=v_req.membership_id AND m.tenant_id=p_tenant
        AND m.user_id=v_actor AND m.role='TENANT_MEMBER'
        AND m.status IN ('ATIVA','SUSPENSA')
   ) THEN
      RAISE EXCEPTION 'BLOQUEADO: somente o membro sujeito pode contestar';
   END IF;
 ELSE
   IF v_role<>'TENANT_ADMIN'
      OR NOT public.rls_is_tenant_admin(v_actor,p_tenant)
      OR v_actor=v_req.requested_by_user_id
      OR EXISTS (
        SELECT 1 FROM public.memberships m
        WHERE m.id=v_req.membership_id AND m.user_id=v_actor
      )
   THEN
      RAISE EXCEPTION 'BLOQUEADO: revisao exige administrador independente';
   END IF;
 END IF;

 -- Repetição idempotente é verificada ANTES do estado terminal.
 SELECT * INTO v_existing FROM public.member_lifecycle_review_events e
 WHERE e.tenant_id=p_tenant AND e.request_id=p_request
   AND e.actor_user_id=v_actor AND e.idempotency_key=p_idempotency;
 IF FOUND THEN
    IF v_existing.event_kind<>p_event_kind
       OR v_existing.evidence_reference<>p_evidence_reference THEN
       RAISE EXCEPTION 'BLOQUEADO: chave reaproveitada com outro conteudo';
    END IF;
    RETURN v_existing.event_id;
 END IF;

 SELECT e.event_kind INTO v_prev
 FROM public.member_lifecycle_review_events e
 WHERE e.tenant_id=p_tenant AND e.request_id=p_request
 ORDER BY e.event_seq DESC LIMIT 1;

 IF p_event_kind='MEMBER_CONTESTED' THEN
    IF NOT (
       (v_req.request_kind='DELINQUENCY_REVIEW' AND v_prev IS NULL)
       OR v_prev IN ('ADMIN_DOCUMENTS_REQUESTED',
                     'ADMIN_REVIEW_REJECTED_SANDBOX')
    ) THEN
       RAISE EXCEPTION 'BLOQUEADO: contestacao repetida ou fora de fase';
    END IF;
 ELSE
    IF v_prev IN ('ADMIN_REVIEW_ACCEPTED_SANDBOX',
                  'ADMIN_REVIEW_REJECTED_SANDBOX') THEN
       RAISE EXCEPTION 'BLOQUEADO: decisao final; somente contestacao admissivel';
    END IF;
 END IF;

 INSERT INTO public.member_lifecycle_review_events (
    tenant_id,request_id,membership_id,actor_user_id,
    idempotency_key,event_kind,evidence_reference
 ) VALUES (
    p_tenant,p_request,v_req.membership_id,v_actor,
    p_idempotency,p_event_kind,p_evidence_reference
 ) RETURNING event_id INTO v_id;
 RETURN v_id;
END
$fn$;

REVOKE ALL ON FUNCTION public.lifecycle_append_review_event_sandbox(
 uuid,uuid,varchar,uuid,varchar
) FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.lifecycle_append_review_event_sandbox(
 uuid,uuid,varchar,uuid,varchar
) TO frcaixinha_app_role;

DO $guard$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class
   WHERE oid='public.member_lifecycle_review_events'::regclass
     AND relrowsecurity AND relforcerowsecurity
 ) OR NOT has_table_privilege(
   'frcaixinha_app_role','public.member_lifecycle_review_events','SELECT'
 ) OR has_table_privilege(
   'frcaixinha_app_role','public.member_lifecycle_review_events','INSERT'
 ) OR has_table_privilege(
   'frcaixinha_app_role','public.member_lifecycle_review_events','UPDATE'
 ) OR has_table_privilege(
   'frcaixinha_app_role','public.member_lifecycle_review_events','DELETE'
 ) OR has_table_privilege(
   'frcaixinha_auth_role','public.member_lifecycle_review_events','SELECT'
 ) OR NOT has_function_privilege(
   'frcaixinha_app_role',
   'public.lifecycle_append_review_event_sandbox(uuid,uuid,varchar,uuid,varchar)',
   'EXECUTE'
 ) OR has_function_privilege(
   'frcaixinha_auth_role',
   'public.lifecycle_append_review_event_sandbox(uuid,uuid,varchar,uuid,varchar)',
   'EXECUTE'
 ) THEN
   RAISE EXCEPTION 'BLOQUEADO: revisao sem RLS, privilegios corretos ou funcao';
 END IF;
END
$guard$;
