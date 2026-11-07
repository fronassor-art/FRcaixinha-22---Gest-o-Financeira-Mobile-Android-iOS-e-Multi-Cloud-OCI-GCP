-- FR Caixinha AI Studio M1881-M2040: diario persistente DE TESTE, nao financeiro.
-- MIGRATION 031: somente banco CI descartavel frcaixinha_ci (PostgreSQL 16/18).
-- No banco Termux frcaixinha_aistudio_dev esta migration DEVE FALHAR.
-- Nao existe webhook, credencial de provedor, saldo ou efeito contábil aqui.
DO $ci_only$
BEGIN
 IF current_database() <> 'frcaixinha_ci'
    OR current_setting('frcaixinha.ci_sandbox', true) IS DISTINCT FROM '1' THEN
   RAISE EXCEPTION 'BLOQUEADO M031: somente ambiente CI descartavel autorizado';
 END IF;
END $ci_only$;

CREATE TABLE public.mp_sandbox_evidence_events (
  event_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
  tenant_id uuid NOT NULL,
  membership_id uuid NOT NULL,
  actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
  idempotency_key uuid NOT NULL,
  event_kind varchar(32) NOT NULL CHECK (
    event_kind IN ('APPROVED_FIXTURE','REFUND_FIXTURE',
                   'CHARGEBACK_FIXTURE','DISPUTE_FIXTURE')
  ),
  collector_id varchar(40) NOT NULL CHECK (collector_id ~ '^[0-9]{1,40}$'),
  provider_payment_id varchar(40) NOT NULL
    CHECK (provider_payment_id ~ '^[0-9]{1,40}$'),
  external_reference varchar(100) NOT NULL
    CHECK (external_reference ~ '^[A-Za-z0-9._:-]{1,100}$'),
  amount_cents bigint NOT NULL CHECK (amount_cents BETWEEN 0 AND 999999999999),
  evidence_reference varchar(120) NOT NULL
    CHECK (evidence_reference ~ '^[A-Za-z0-9._:-]{8,120}$'),
  source varchar(30) NOT NULL DEFAULT 'SYNTHETIC_FIXTURE_ONLY'
    CHECK (source='SYNTHETIC_FIXTURE_ONLY'),
  bank_reconciled boolean NOT NULL DEFAULT false CHECK (bank_reconciled=false),
  financial_effect_applied boolean NOT NULL DEFAULT false
    CHECK (financial_effect_applied=false),
  settlement_authorized boolean NOT NULL DEFAULT false
    CHECK (settlement_authorized=false),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (tenant_id,idempotency_key),
  UNIQUE (event_id,tenant_id),
  FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE RESTRICT,
  FOREIGN KEY (membership_id,tenant_id)
    REFERENCES public.memberships(id,tenant_id) ON DELETE RESTRICT,
  CHECK (
    (event_kind='DISPUTE_FIXTURE' AND amount_cents=0) OR
    (event_kind<>'DISPUTE_FIXTURE' AND amount_cents>0)
  )
);

-- Mesma identificacao nao pode ser credito em caixinha/conta diferente.
CREATE UNIQUE INDEX mp_sandbox_one_approval_per_provider_payment
 ON public.mp_sandbox_evidence_events(provider_payment_id)
 WHERE event_kind='APPROVED_FIXTURE';
CREATE UNIQUE INDEX mp_sandbox_one_dispute_per_payment
 ON public.mp_sandbox_evidence_events(tenant_id,provider_payment_id)
 WHERE event_kind='DISPUTE_FIXTURE';
CREATE UNIQUE INDEX mp_sandbox_one_chargeback_per_payment
 ON public.mp_sandbox_evidence_events(tenant_id,provider_payment_id)
 WHERE event_kind='CHARGEBACK_FIXTURE';
CREATE INDEX mp_sandbox_evidence_member_cursor
 ON public.mp_sandbox_evidence_events(tenant_id,membership_id,event_seq DESC);
CREATE INDEX mp_sandbox_evidence_tenant_cursor
 ON public.mp_sandbox_evidence_events(tenant_id,event_seq DESC);

ALTER TABLE public.mp_sandbox_evidence_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_sandbox_evidence_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.mp_sandbox_evidence_events
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
REVOKE ALL ON SEQUENCE public.mp_sandbox_evidence_events_event_seq_seq
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;

CREATE POLICY mp_sandbox_admin_read
 ON public.mp_sandbox_evidence_events FOR SELECT TO frcaixinha_app_role
 USING (
  tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
  AND current_setting('app.current_role',true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(
    NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id)
 );
CREATE POLICY mp_sandbox_member_read
 ON public.mp_sandbox_evidence_events FOR SELECT TO frcaixinha_app_role
 USING (
  tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
  AND current_setting('app.current_role',true)='TENANT_MEMBER'
  AND membership_id IN (
    SELECT public.rls_user_membership_ids(
      NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id)
  )
 );
GRANT SELECT ON public.mp_sandbox_evidence_events TO frcaixinha_app_role;

-- SECURITY DEFINER: unica escrita possivel ao app, exclusivamente SYNTHETIC.
-- Advisory lock por provider_id impede concorrencia em dois servidores.
-- Checagem de idempotencia ANTES do fluxo: mesma chave+payload => mesmo evento.
CREATE FUNCTION public.append_mp_sandbox_evidence_ci(
 p_tenant uuid, p_membership uuid, p_kind varchar,
 p_idempotency uuid, p_collector varchar, p_provider_id varchar,
 p_external varchar, p_amount bigint, p_evidence varchar
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 v_actor uuid;
 v_ctx_tenant uuid;
 v_role text;
 v_prior public.mp_sandbox_evidence_events%ROWTYPE;
 v_approval public.mp_sandbox_evidence_events%ROWTYPE;
 v_refunded bigint;
 v_chargeback bigint;
 v_id uuid;
BEGIN
 -- Segundo bloqueio: nunca habilitar por acidente em ambiente nao descartavel.
 IF current_database()<>'frcaixinha_ci'
    OR current_setting('frcaixinha.ci_sandbox',true) IS DISTINCT FROM '1' THEN
   RAISE EXCEPTION 'BLOQUEADO: gravacao somente CI sintética';
 END IF;
 v_actor:=NULLIF(current_setting('app.current_user_id',true),'')::uuid;
 v_ctx_tenant:=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid;
 v_role:=current_setting('app.current_role',true);

 IF v_actor IS NULL OR p_tenant IS NULL OR p_tenant<>v_ctx_tenant
    OR v_role<>'TENANT_ADMIN'
    OR NOT public.rls_is_tenant_admin(v_actor,p_tenant)
    OR p_membership IS NULL OR p_idempotency IS NULL
    OR p_kind NOT IN (
       'APPROVED_FIXTURE','REFUND_FIXTURE',
       'CHARGEBACK_FIXTURE','DISPUTE_FIXTURE'
    )
    OR p_collector IS NULL OR p_collector !~ '^[0-9]{1,40}$'
    OR p_provider_id IS NULL OR p_provider_id !~ '^[0-9]{1,40}$'
    OR p_external IS NULL OR p_external !~ '^[A-Za-z0-9._:-]{1,100}$'
    OR p_external NOT LIKE 'tenant:'||p_tenant::text||':%'
    OR p_amount IS NULL OR p_amount<0 OR p_amount>999999999999
    OR (p_kind='DISPUTE_FIXTURE' AND p_amount<>0)
    OR (p_kind<>'DISPUTE_FIXTURE' AND p_amount=0)
    OR p_evidence IS NULL OR p_evidence !~ '^[A-Za-z0-9._:-]{8,120}$'
    OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.id=p_membership AND m.tenant_id=p_tenant
        AND m.role='TENANT_MEMBER'
        AND m.status IN ('ATIVA','SUSPENSA')
    )
 THEN
   RAISE EXCEPTION 'BLOQUEADO: fixture sem contexto, membro ou papel valido';
 END IF;

 PERFORM pg_advisory_xact_lock(hashtextextended(
   'FRC-MP-SYNTHETIC|'||p_provider_id,0));

 SELECT * INTO v_prior FROM public.mp_sandbox_evidence_events e
 WHERE e.tenant_id=p_tenant AND e.idempotency_key=p_idempotency;
 IF FOUND THEN
    IF v_prior.actor_user_id<>v_actor
       OR v_prior.membership_id<>p_membership
       OR v_prior.event_kind<>p_kind
       OR v_prior.collector_id<>p_collector
       OR v_prior.provider_payment_id<>p_provider_id
       OR v_prior.external_reference<>p_external
       OR v_prior.amount_cents<>p_amount
       OR v_prior.evidence_reference<>p_evidence THEN
       RAISE EXCEPTION 'BLOQUEADO: chave de idempotencia com outro conteudo';
    END IF;
    RETURN v_prior.event_id;
 END IF;

 SELECT * INTO v_approval FROM public.mp_sandbox_evidence_events e
 WHERE e.provider_payment_id=p_provider_id AND e.event_kind='APPROVED_FIXTURE'
 LIMIT 1;

 IF p_kind='APPROVED_FIXTURE' THEN
   IF FOUND THEN
      RAISE EXCEPTION 'BLOQUEADO: aprovacao duplicada do provedor';
   END IF;
 ELSE
   IF NOT FOUND OR v_approval.tenant_id<>p_tenant
      OR v_approval.membership_id<>p_membership
      OR v_approval.collector_id<>p_collector
      OR v_approval.external_reference<>p_external THEN
      RAISE EXCEPTION 'BLOQUEADO: reversao/contestacao sem aprovacao original';
   END IF;

   IF p_kind='DISPUTE_FIXTURE' THEN
      IF EXISTS (
        SELECT 1 FROM public.mp_sandbox_evidence_events e
        WHERE e.tenant_id=p_tenant AND e.provider_payment_id=p_provider_id
          AND e.event_kind='DISPUTE_FIXTURE'
      ) THEN RAISE EXCEPTION 'BLOQUEADO: disputa duplicada'; END IF;
   ELSIF p_kind='CHARGEBACK_FIXTURE' THEN
      IF EXISTS (
        SELECT 1 FROM public.mp_sandbox_evidence_events e
        WHERE e.tenant_id=p_tenant AND e.provider_payment_id=p_provider_id
          AND e.event_kind='CHARGEBACK_FIXTURE'
      ) THEN RAISE EXCEPTION 'BLOQUEADO: chargeback duplicado'; END IF;
   END IF;

   IF p_kind IN ('REFUND_FIXTURE','CHARGEBACK_FIXTURE') THEN
      SELECT COALESCE(sum(amount_cents) FILTER
         (WHERE event_kind='REFUND_FIXTURE'),0),
             COALESCE(sum(amount_cents) FILTER
         (WHERE event_kind='CHARGEBACK_FIXTURE'),0)
        INTO v_refunded,v_chargeback
      FROM public.mp_sandbox_evidence_events e
      WHERE e.tenant_id=p_tenant AND e.provider_payment_id=p_provider_id;

      IF v_refunded+v_chargeback+p_amount>v_approval.amount_cents THEN
         RAISE EXCEPTION 'BLOQUEADO: reversao acima de credito sintetico';
      END IF;
   END IF;
 END IF;

 INSERT INTO public.mp_sandbox_evidence_events(
    tenant_id,membership_id,actor_user_id,idempotency_key,
    event_kind,collector_id,provider_payment_id,external_reference,
    amount_cents,evidence_reference
 ) VALUES (
    p_tenant,p_membership,v_actor,p_idempotency,
    p_kind,p_collector,p_provider_id,p_external,
    p_amount,p_evidence
 ) RETURNING event_id INTO v_id;
 RETURN v_id;
END $fn$;

REVOKE ALL ON FUNCTION public.append_mp_sandbox_evidence_ci(
 uuid,uuid,varchar,uuid,varchar,varchar,varchar,bigint,varchar)
 FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.append_mp_sandbox_evidence_ci(
 uuid,uuid,varchar,uuid,varchar,varchar,varchar,bigint,varchar)
 TO frcaixinha_app_role;

-- Garantia pós-migration: papel de app apenas SELECT e função controlada.
DO $guard$
BEGIN
 IF NOT EXISTS (
    SELECT 1 FROM pg_class
    WHERE oid='public.mp_sandbox_evidence_events'::regclass
      AND relrowsecurity AND relforcerowsecurity
 ) OR NOT has_table_privilege('frcaixinha_app_role',
      'public.mp_sandbox_evidence_events','SELECT')
   OR has_table_privilege('frcaixinha_app_role',
      'public.mp_sandbox_evidence_events','INSERT')
   OR has_table_privilege('frcaixinha_app_role',
      'public.mp_sandbox_evidence_events','UPDATE')
   OR has_table_privilege('frcaixinha_app_role',
      'public.mp_sandbox_evidence_events','DELETE')
   OR has_table_privilege('frcaixinha_auth_role',
      'public.mp_sandbox_evidence_events','SELECT')
   OR has_table_privilege('frcaixinha_verifier_role',
      'public.mp_sandbox_evidence_events','SELECT')
   OR NOT has_function_privilege('frcaixinha_app_role',
       'public.append_mp_sandbox_evidence_ci(uuid,uuid,varchar,uuid,varchar,varchar,varchar,bigint,varchar)',
       'EXECUTE')
   OR has_function_privilege('frcaixinha_auth_role',
       'public.append_mp_sandbox_evidence_ci(uuid,uuid,varchar,uuid,varchar,varchar,varchar,bigint,varchar)',
       'EXECUTE')
 THEN
   RAISE EXCEPTION 'BLOQUEADO: M031 sem RLS ou privilegios corretos';
 END IF;
END $guard$;
