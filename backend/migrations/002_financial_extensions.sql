-- ==============================================================================
-- FRcaixinha 2.2 — Migração Incremental 002: Extensões Financeiras Oficiais
-- Contrato Técnico Mestre (Cláusulas 4.2, 4.5, 5.4, 6.3, 6.4, 8.2, 8.6, 8.8, 10.3, 10.4, 16.2 e 16.4)
--
-- ATENÇÃO:
-- 1. Todas as tabelas herdam FORCE ROW LEVEL SECURITY.
-- 2. Não contém credenciais, senhas literais ou segredos em texto claro.
-- 3. Aplica restrições estritas de chave estrangeira, unicidade e integridade transacional.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Tabela de Contribuições Mensais (Cotas por Competência)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contributions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    membership_id UUID NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    competence VARCHAR(7) NOT NULL, -- Ex: '2027-01'
    due_date DATE NOT NULL,
    amount_due NUMERIC(12, 2) NOT NULL CHECK (amount_due > 0),
    amount_paid NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (amount_paid >= 0),
    payment_status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE' CHECK (payment_status IN ('PENDENTE', 'PARCIAL', 'QUITADA')),
    due_status VARCHAR(20) NOT NULL DEFAULT 'NO_PRAZO' CHECK (due_status IN ('NO_PRAZO', 'VENCIDA', 'REGULARIZADA')),
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_membership_competence UNIQUE (tenant_id, membership_id, competence)
);

CREATE INDEX IF NOT EXISTS idx_contributions_tenant ON contributions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contributions_membership ON contributions(membership_id);
CREATE INDEX IF NOT EXISTS idx_contributions_competence ON contributions(competence);

-- ------------------------------------------------------------------------------
-- 2. Parcelas de Empréstimos — Tabela Price
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loan_installments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    due_date DATE NOT NULL,
    principal_due NUMERIC(12, 2) NOT NULL CHECK (principal_due >= 0),
    interest_due NUMERIC(12, 2) NOT NULL CHECK (interest_due >= 0),
    total_due NUMERIC(12, 2) NOT NULL CHECK (total_due > 0),
    paid_principal NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (paid_principal >= 0),
    paid_interest NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (paid_interest >= 0),
    paid_mora NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (paid_mora >= 0),
    paid_fine NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (paid_fine >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE' CHECK (status IN ('PENDENTE', 'PARCIAL', 'QUITADA', 'VENCIDA')),
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_loan_installment UNIQUE (tenant_id, loan_id, installment_number)
);

CREATE INDEX IF NOT EXISTS idx_loan_installments_tenant ON loan_installments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_loan_installments_loan ON loan_installments(loan_id);

-- ------------------------------------------------------------------------------
-- 3. Histórico de Pagamentos de Empréstimo com Imputação em 4 Etapas
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loan_payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    installment_id UUID REFERENCES loan_installments(id),
    amount_paid NUMERIC(12, 2) NOT NULL CHECK (amount_paid > 0),
    allocated_interest NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (allocated_interest >= 0),
    allocated_mora NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (allocated_mora >= 0),
    allocated_fine NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (allocated_fine >= 0),
    allocated_principal NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (allocated_principal >= 0),
    payment_type VARCHAR(30) NOT NULL DEFAULT 'REGULAR' CHECK (payment_type IN ('REGULAR', 'PARCIAL', 'QUITACAO_ANTECIPADA')),
    payment_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_loan_payments_tenant ON loan_payments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_loan_payments_loan ON loan_payments(loan_id);

-- ------------------------------------------------------------------------------
-- 4. Consentimentos Coletivos para Autoempréstimo de Administrador (Cláusula 5.4 / 16.4)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_self_loan_consents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    voter_membership_id UUID NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('FAVORAVEL', 'CONTRARIO', 'ABSTENCAO')),
    justification TEXT,
    voted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_loan_voter UNIQUE (tenant_id, loan_id, voter_membership_id)
);

CREATE INDEX IF NOT EXISTS idx_admin_consents_tenant ON admin_self_loan_consents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_admin_consents_loan ON admin_self_loan_consents(loan_id);

-- ------------------------------------------------------------------------------
-- 5. Fechamentos Anuais de Ciclo (Apuração Capital-Dias V2 e Maiores Restos)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cycle_closings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    closed_by_user_id UUID NOT NULL REFERENCES users(id),
    total_net_profit NUMERIC(12, 2) NOT NULL CHECK (total_net_profit >= 0),
    admin_share_amount NUMERIC(12, 2) NOT NULL CHECK (admin_share_amount >= 0),
    member_pool_amount NUMERIC(12, 2) NOT NULL CHECK (member_pool_amount >= 0),
    total_capital_dias_weights NUMERIC(18, 4) NOT NULL CHECK (total_capital_dias_weights >= 0),
    residual_cents_distributed INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'CONCLUIDO' CHECK (status IN ('EM_PROCESSAMENTO', 'CONCLUIDO', 'ESTORNADO')),
    closed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cycle_closing UNIQUE (tenant_id, cycle_id)
);

CREATE INDEX IF NOT EXISTS idx_cycle_closings_tenant ON cycle_closings(tenant_id);

-- ------------------------------------------------------------------------------
-- 6. Rateios Individuais de Lucro do Ciclo
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cycle_profit_distributions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_closing_id UUID NOT NULL REFERENCES cycle_closings(id) ON DELETE CASCADE,
    membership_id UUID NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    is_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    capital_dias_weight NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    exact_share NUMERIC(14, 4) NOT NULL DEFAULT 0.0000,
    truncated_share NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    bonus_centavos NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    final_profit_share NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_closing_membership UNIQUE (tenant_id, cycle_closing_id, membership_id)
);

CREATE INDEX IF NOT EXISTS idx_profit_dist_tenant ON cycle_profit_distributions(tenant_id);

-- ==============================================================================
-- 7. ATIVAÇÃO DE ROW LEVEL SECURITY (RLS) E FORCE RLS EM TODAS AS NOVAS TABELAS
-- ==============================================================================

ALTER TABLE contributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE contributions FORCE ROW LEVEL SECURITY;

ALTER TABLE loan_installments ENABLE ROW LEVEL SECURITY;
ALTER TABLE loan_installments FORCE ROW LEVEL SECURITY;

ALTER TABLE loan_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE loan_payments FORCE ROW LEVEL SECURITY;

ALTER TABLE admin_self_loan_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_self_loan_consents FORCE ROW LEVEL SECURITY;

ALTER TABLE cycle_closings ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_closings FORCE ROW LEVEL SECURITY;

ALTER TABLE cycle_profit_distributions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_profit_distributions FORCE ROW LEVEL SECURITY;

-- ==============================================================================
-- 8. POLÍTICAS DE RLS TENANT-AWARE
-- ==============================================================================

-- A. Contribuições
CREATE POLICY rls_contributions_select ON contributions
    FOR SELECT
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) != 'MASTER'
    );

CREATE POLICY rls_contributions_insert ON contributions
    FOR INSERT
    WITH CHECK (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );

CREATE POLICY rls_contributions_update ON contributions
    FOR UPDATE
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );

-- B. Parcelas de Empréstimos
CREATE POLICY rls_loan_installments_select ON loan_installments
    FOR SELECT
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) != 'MASTER'
    );

CREATE POLICY rls_loan_installments_admin_all ON loan_installments
    FOR ALL
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );

-- C. Pagamentos de Empréstimo
CREATE POLICY rls_loan_payments_select ON loan_payments
    FOR SELECT
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) != 'MASTER'
    );

CREATE POLICY rls_loan_payments_insert ON loan_payments
    FOR INSERT
    WITH CHECK (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) IN ('TENANT_ADMIN', 'TENANT_MEMBER')
    );

-- D. Consentimentos de Autoempréstimo
CREATE POLICY rls_admin_consents_select ON admin_self_loan_consents
    FOR SELECT
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) != 'MASTER'
    );

CREATE POLICY rls_admin_consents_insert ON admin_self_loan_consents
    FOR INSERT
    WITH CHECK (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) = 'TENANT_MEMBER'
    );

-- E. Fechamentos Anuais e Distribuição
CREATE POLICY rls_cycle_closings_select ON cycle_closings
    FOR SELECT
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) != 'MASTER'
    );

CREATE POLICY rls_cycle_closings_admin ON cycle_closings
    FOR ALL
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );

CREATE POLICY rls_profit_distributions_select ON cycle_profit_distributions
    FOR SELECT
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) != 'MASTER'
    );

CREATE POLICY rls_profit_distributions_admin ON cycle_profit_distributions
    FOR ALL
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );
