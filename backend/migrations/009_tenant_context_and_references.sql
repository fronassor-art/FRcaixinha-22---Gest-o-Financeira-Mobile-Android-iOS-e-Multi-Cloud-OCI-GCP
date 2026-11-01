-- Endurecimento incremental de leitura por contexto e integridade entre caixinhas.
-- Executar apenas após verificar relações existentes; o CI usa banco descartável.

DROP POLICY quotas_select_policy ON public.quotas;
CREATE POLICY quotas_select_policy ON public.quotas FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND (
    (current_setting('app.current_role', true) = 'TENANT_ADMIN'
     AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
    OR (current_setting('app.current_role', true) = 'TENANT_MEMBER'
     AND membership_id IN (SELECT public.rls_user_membership_ids(
       NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)))
  )
);

DROP POLICY rls_contributions_select ON public.contributions;
CREATE POLICY rls_contributions_select ON public.contributions FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND (
    (current_setting('app.current_role', true) = 'TENANT_ADMIN'
     AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
    OR (current_setting('app.current_role', true) = 'TENANT_MEMBER'
     AND membership_id IN (SELECT public.rls_user_membership_ids(
       NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)))
  )
);

DROP POLICY loans_select_policy ON public.loans;
CREATE POLICY loans_select_policy ON public.loans FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND (
    (current_setting('app.current_role', true) = 'TENANT_ADMIN'
     AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
    OR (current_setting('app.current_role', true) = 'TENANT_MEMBER'
     AND borrower_membership_id IN (SELECT public.rls_user_membership_ids(
       NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)))
  )
);

CREATE POLICY cycles_context_read ON public.cycles FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true) IN ('TENANT_ADMIN','TENANT_MEMBER')
  AND tenant_id IN (SELECT public.rls_user_active_tenants(
    NULLIF(current_setting('app.current_user_id', true), '')::uuid))
);
CREATE POLICY policies_context_read ON public.policies FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true) IN ('TENANT_ADMIN','TENANT_MEMBER')
  AND tenant_id IN (SELECT public.rls_user_active_tenants(
    NULLIF(current_setting('app.current_user_id', true), '')::uuid))
);

DROP POLICY rls_loan_installments_select ON public.loan_installments;
DROP POLICY rls_loan_installments_admin_all ON public.loan_installments;
CREATE POLICY loan_installments_read ON public.loan_installments FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND EXISTS (SELECT 1 FROM public.loans l WHERE l.id=loan_id AND l.tenant_id=loan_installments.tenant_id)
);
CREATE POLICY loan_installments_admin_insert ON public.loan_installments FOR INSERT WITH CHECK (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
);
CREATE POLICY loan_installments_admin_update ON public.loan_installments FOR UPDATE USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
);

DROP POLICY rls_loan_payments_select ON public.loan_payments;
DROP POLICY rls_loan_payments_insert ON public.loan_payments;
CREATE POLICY loan_payments_read ON public.loan_payments FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND EXISTS (SELECT 1 FROM public.loans l WHERE l.id=loan_id AND l.tenant_id=loan_payments.tenant_id)
);

DROP POLICY rls_profit_distributions_select ON public.cycle_profit_distributions;
DROP POLICY rls_profit_distributions_admin ON public.cycle_profit_distributions;
CREATE POLICY profit_distributions_read ON public.cycle_profit_distributions FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND (
    (current_setting('app.current_role', true)='TENANT_ADMIN'
     AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
    OR (current_setting('app.current_role', true)='TENANT_MEMBER'
     AND membership_id IN (SELECT public.rls_user_membership_ids(
       NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)))
  )
);
DROP POLICY rls_cycle_closings_select ON public.cycle_closings;
DROP POLICY rls_cycle_closings_admin ON public.cycle_closings;
CREATE POLICY cycle_closings_admin_read ON public.cycle_closings FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
);

DROP POLICY ledger_entries_policy ON public.ledger_entries;
DROP POLICY ledger_transactions_policy ON public.ledger_transactions;
CREATE POLICY ledger_entries_admin_read ON public.ledger_entries FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
);
CREATE POLICY ledger_transactions_admin_read ON public.ledger_transactions FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
);
REVOKE UPDATE, DELETE ON public.ledger_entries, public.ledger_transactions FROM frcaixinha_app_role;

-- As tabelas criadas em 002 não herdaram os GRANTs da 001.
GRANT SELECT ON public.loan_installments, public.loan_payments,
  public.admin_self_loan_consents, public.cycle_closings,
  public.cycle_profit_distributions TO frcaixinha_app_role;

-- Chaves compostas impedem referências entre tenants mesmo quando o ID existe.
ALTER TABLE public.memberships ADD CONSTRAINT memberships_id_tenant_uq UNIQUE (id, tenant_id);
ALTER TABLE public.cycles ADD CONSTRAINT cycles_id_tenant_uq UNIQUE (id, tenant_id);
ALTER TABLE public.policies ADD CONSTRAINT policies_id_tenant_uq UNIQUE (id, tenant_id);
ALTER TABLE public.loans ADD CONSTRAINT loans_id_tenant_uq UNIQUE (id, tenant_id);
ALTER TABLE public.quotas ADD CONSTRAINT quotas_membership_tenant_fk
  FOREIGN KEY (membership_id, tenant_id) REFERENCES public.memberships(id, tenant_id);
ALTER TABLE public.contributions ADD CONSTRAINT contributions_membership_tenant_fk
  FOREIGN KEY (membership_id, tenant_id) REFERENCES public.memberships(id, tenant_id);
ALTER TABLE public.contributions ADD CONSTRAINT contributions_cycle_tenant_fk
  FOREIGN KEY (cycle_id, tenant_id) REFERENCES public.cycles(id, tenant_id);
ALTER TABLE public.loans ADD CONSTRAINT loans_membership_tenant_fk
  FOREIGN KEY (borrower_membership_id, tenant_id) REFERENCES public.memberships(id, tenant_id);
ALTER TABLE public.loans ADD CONSTRAINT loans_cycle_tenant_fk
  FOREIGN KEY (cycle_id, tenant_id) REFERENCES public.cycles(id, tenant_id);
ALTER TABLE public.loans ADD CONSTRAINT loans_policy_tenant_fk
  FOREIGN KEY (policy_id, tenant_id) REFERENCES public.policies(id, tenant_id);
ALTER TABLE public.loan_installments ADD CONSTRAINT installments_loan_tenant_fk
  FOREIGN KEY (loan_id, tenant_id) REFERENCES public.loans(id, tenant_id);

-- A lista cadastral é privativa do administrador; o membro enxerga só seu vínculo.
DROP POLICY memberships_select_policy ON public.memberships;
CREATE POLICY memberships_select_policy ON public.memberships FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND (
    (current_setting('app.current_role', true)='TENANT_ADMIN'
     AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
    OR (current_setting('app.current_role', true)='TENANT_MEMBER'
     AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
  )
);

DROP POLICY rls_admin_consents_select ON public.admin_self_loan_consents;
CREATE POLICY admin_consents_context_read ON public.admin_self_loan_consents FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND (
    (current_setting('app.current_role', true)='TENANT_ADMIN'
     AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
    OR (current_setting('app.current_role', true)='TENANT_MEMBER'
     AND voter_membership_id IN (SELECT public.rls_user_membership_ids(
       NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)))
  )
);
DROP POLICY rls_pix_intents_select ON public.pix_payment_intents;
CREATE POLICY pix_intents_context_read ON public.pix_payment_intents FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND (
    (current_setting('app.current_role', true)='TENANT_ADMIN'
     AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id))
    OR (current_setting('app.current_role', true)='TENANT_MEMBER'
     AND payer_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
  )
);
DROP POLICY ledger_accounts_policy ON public.ledger_accounts;
CREATE POLICY ledger_accounts_admin_read ON public.ledger_accounts FOR SELECT USING (
  tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
  AND current_setting('app.current_role', true)='TENANT_ADMIN'
  AND public.rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
);
REVOKE UPDATE, DELETE ON public.ledger_accounts FROM frcaixinha_app_role;
