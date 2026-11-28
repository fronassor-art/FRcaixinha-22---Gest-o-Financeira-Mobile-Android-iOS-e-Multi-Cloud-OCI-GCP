-- FR Caixinha AI Studio — migration 030: nova rodada de pedido de ciclo.
-- CI PostgreSQL DESCARTAVEL somente. Nao aplicar ao banco Termux 5433.
-- Nova solicitacao so apos ultima revisao documental terminada; nenhuma
-- decisao por si cria sanção, rateio, restituição ou movimentação financeira.

-- O indice 028 impedia toda nova solicitacao durante o mesmo ciclo, mesmo
-- apos conclusao documental. A funcao definer usa lock transacional por chave
-- para permitir no maximo UMA rodada tecnicamente pendente por ciclo/tipo.
DROP INDEX IF EXISTS public.member_lifecycle_one_pending_per_cycle_kind;

CREATE INDEX member_lifecycle_case_round_lookup
  ON public.member_lifecycle_requests
  (tenant_id,cycle_id,membership_id,request_kind,requested_at DESC,id DESC);

CREATE OR REPLACE FUNCTION public.lifecycle_submit_request_sandbox(
    p_tenant uuid,p_cycle uuid,p_membership uuid,
    p_kind varchar,p_idempotency uuid,p_policy_reference varchar
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 v_user uuid;
 v_ctx_tenant uuid;
 v_role text;
 v_prior public.member_lifecycle_requests%ROWTYPE;
 v_latest public.member_lifecycle_requests%ROWTYPE;
 v_last_event text;
 v_new_id uuid;
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
   RAISE EXCEPTION 'BLOQUEADO: pedido sem identidade, contexto ou evidencia';
 END IF;
 IF NOT EXISTS (
    SELECT 1 FROM public.cycles c
    WHERE c.id=p_cycle AND c.tenant_id=p_tenant
      AND c.status IN ('ABERTO','CONGELADO','EM_APURACAO')
 ) THEN
    RAISE EXCEPTION 'BLOQUEADO: ciclo nao admite novos pedidos de revisao';
 END IF;
 IF p_kind='VOLUNTARY_EXIT' THEN
    IF v_role<>'TENANT_MEMBER' OR NOT EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.id=p_membership AND m.tenant_id=p_tenant
        AND m.user_id=v_user AND m.role='TENANT_MEMBER'
        AND m.status='ATIVA'
    ) THEN
      RAISE EXCEPTION 'BLOQUEADO: somente membro ativo pede saida voluntaria';
    END IF;
 ELSE
    IF v_role<>'TENANT_ADMIN'
       OR NOT public.rls_is_tenant_admin(v_user,p_tenant)
       OR NOT EXISTS (
        SELECT 1 FROM public.memberships m
        WHERE m.id=p_membership AND m.tenant_id=p_tenant
          AND m.role='TENANT_MEMBER' AND m.status IN ('ATIVA','SUSPENSA')
       )
    THEN
       RAISE EXCEPTION 'BLOQUEADO: somente admin do tenant solicita revisao';
    END IF;
 END IF;

 -- Serialize as tentativas de abertura para (tenant/ciclo/membro/tipo),
 -- inclusive quando ainda nao ha linha nova para FOR UPDATE.
 PERFORM pg_advisory_xact_lock(hashtextextended(
   'FRC-LIFECYCLE|'
    ||p_tenant::text||'|'||p_cycle::text||'|'
    ||p_membership::text||'|'||p_kind,0
 ));

 -- Uma chave anteriormente usada e sempre idempotente, mesmo apos abertura
 -- de outra rodada. Nao devolver pedido historico de outro ciclo/ator/politica.
 SELECT r.* INTO v_prior
 FROM public.member_lifecycle_requests r
 WHERE r.tenant_id=p_tenant AND r.membership_id=p_membership
   AND r.request_kind=p_kind AND r.idempotency_key=p_idempotency
 LIMIT 1;
 IF FOUND THEN
   IF v_prior.cycle_id<>p_cycle
      OR v_prior.requested_by_user_id<>v_user
      OR v_prior.policy_reference<>p_policy_reference THEN
      RAISE EXCEPTION 'BLOQUEADO: idempotencia historica conflitante';
   END IF;
   RETURN v_prior.id;
 END IF;

 SELECT r.* INTO v_latest
 FROM public.member_lifecycle_requests r
 WHERE r.tenant_id=p_tenant AND r.cycle_id=p_cycle
   AND r.membership_id=p_membership AND r.request_kind=p_kind
 ORDER BY r.requested_at DESC,r.id DESC
 LIMIT 1;

 IF FOUND THEN
   SELECT e.event_kind INTO v_last_event
   FROM public.member_lifecycle_review_events e
   WHERE e.tenant_id=p_tenant AND e.request_id=v_latest.id
   ORDER BY e.event_seq DESC LIMIT 1;

   IF v_last_event IS NULL OR v_last_event NOT IN (
        'ADMIN_REVIEW_ACCEPTED_SANDBOX',
        'ADMIN_REVIEW_REJECTED_SANDBOX'
   ) THEN
     IF v_latest.policy_reference IS DISTINCT FROM p_policy_reference
        OR v_latest.requested_by_user_id IS DISTINCT FROM v_user THEN
       RAISE EXCEPTION 'BLOQUEADO: rodada pendente de outra autoria/politica';
     END IF;
     RETURN v_latest.id;
   END IF;
 END IF;

 INSERT INTO public.member_lifecycle_requests (
    tenant_id,cycle_id,membership_id,requested_by_user_id,
    request_kind,idempotency_key,policy_reference
 ) VALUES (
    p_tenant,p_cycle,p_membership,v_user,p_kind,p_idempotency,p_policy_reference
 ) RETURNING id INTO v_new_id;

 RETURN v_new_id;
END
$fn$;

-- Reforcar restricoes sem alterar os outros roles ou rotas.
REVOKE ALL ON FUNCTION public.lifecycle_submit_request_sandbox(
 uuid,uuid,uuid,varchar,uuid,varchar
) FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.lifecycle_submit_request_sandbox(
 uuid,uuid,uuid,varchar,uuid,varchar
) TO frcaixinha_app_role;

DO $guard$
BEGIN
 IF EXISTS (
   SELECT 1 FROM pg_indexes WHERE schemaname='public'
     AND indexname='member_lifecycle_one_pending_per_cycle_kind'
 ) OR NOT EXISTS (
   SELECT 1 FROM pg_indexes WHERE schemaname='public'
     AND indexname='member_lifecycle_case_round_lookup'
 ) OR NOT has_function_privilege(
   'frcaixinha_app_role',
   'public.lifecycle_submit_request_sandbox(uuid,uuid,uuid,varchar,uuid,varchar)',
   'EXECUTE'
 ) OR has_function_privilege(
   'frcaixinha_auth_role',
   'public.lifecycle_submit_request_sandbox(uuid,uuid,uuid,varchar,uuid,varchar)',
   'EXECUTE'
 ) OR has_table_privilege(
   'frcaixinha_app_role','public.member_lifecycle_requests','INSERT'
 ) OR has_table_privilege(
   'frcaixinha_app_role','public.member_lifecycle_requests','UPDATE'
 ) OR has_table_privilege(
   'frcaixinha_app_role','public.member_lifecycle_requests','DELETE'
 ) THEN
   RAISE EXCEPTION 'BLOQUEADO: nova rodada sem idempotencia ou isolamento';
 END IF;
END
$guard$;
