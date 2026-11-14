-- ==============================================================================
-- FRcaixinha 2.2 — Migração Incremental 003: Plano de Contas Canônico e Intents Pix
-- Contrato Técnico Mestre (Cláusulas 1.2, 2.8, 4.5, 8.6, 14.1, 16.2 e 16.4)
--
-- ATENÇÃO:
-- 1. Migração incremental nova e estritamente idempotente.
-- 2. Não altera 001_initial_schema.sql nem 002_financial_extensions.sql.
-- 3. Não contém credenciais, senhas literais ou segredos em texto claro.
-- 4. Todas as novas tabelas herdam FORCE ROW LEVEL SECURITY.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Função Idempotente para Carga do Plano de Contas Canônico do Tenant
-- ------------------------------------------------------------------------------
-- Contas Canônicas Contratuais:
--   1.1.1 - Caixa Financeiro Reconciliado (ASSET)
--   1.2.1 - Crédito Interno a Receber (Principal de Empréstimos) (ASSET)
--   2.1.1 - Capital Confirmado dos Membros (Cotas Integralizadas) (EQUITY)
--   2.2.1 - Reserva Atômica de Desembolsos Pendentes (LIABILITY)
--   4.1.1 - Receita Realizada de Juros, Mora e Multas (REVENUE)
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ensure_tenant_canonical_ledger_accounts(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    -- 1.1.1 Caixa Financeiro Reconciliado
    INSERT INTO ledger_accounts (id, tenant_id, account_code, account_name, account_type, balance_cents)
    VALUES (uuid_generate_v4(), p_tenant_id, '1.1.1', 'Caixa Financeiro Reconciliado', 'ASSET', 0)
    ON CONFLICT (tenant_id, account_code) DO NOTHING;

    -- 1.2.1 Crédito Interno a Receber
    INSERT INTO ledger_accounts (id, tenant_id, account_code, account_name, account_type, balance_cents)
    VALUES (uuid_generate_v4(), p_tenant_id, '1.2.1', 'Crédito Interno a Receber (Principal)', 'ASSET', 0)
    ON CONFLICT (tenant_id, account_code) DO NOTHING;

    -- 2.1.1 Capital Confirmado dos Membros
    INSERT INTO ledger_accounts (id, tenant_id, account_code, account_name, account_type, balance_cents)
    VALUES (uuid_generate_v4(), p_tenant_id, '2.1.1', 'Capital Confirmado dos Membros', 'EQUITY', 0)
    ON CONFLICT (tenant_id, account_code) DO NOTHING;

    -- 2.2.1 Reserva Atômica de Desembolsos Pendentes
    INSERT INTO ledger_accounts (id, tenant_id, account_code, account_name, account_type, balance_cents)
    VALUES (uuid_generate_v4(), p_tenant_id, '2.2.1', 'Reserva Atômica de Desembolsos Pendentes', 'LIABILITY', 0)
    ON CONFLICT (tenant_id, account_code) DO NOTHING;

    -- 4.1.1 Receita Realizada de Juros, Mora e Multas
    INSERT INTO ledger_accounts (id, tenant_id, account_code, account_name, account_type, balance_cents)
    VALUES (uuid_generate_v4(), p_tenant_id, '4.1.1', 'Receita Realizada de Juros, Mora e Multas', 'REVENUE', 0)
    ON CONFLICT (tenant_id, account_code) DO NOTHING;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog, pg_temp;

-- ------------------------------------------------------------------------------
-- 2. Carga Idempotente para Tenants Já Existentes
-- ------------------------------------------------------------------------------
DO $$
DECLARE
    t_row RECORD;
BEGIN
    FOR t_row IN SELECT id FROM tenants LOOP
        PERFORM ensure_tenant_canonical_ledger_accounts(t_row.id);
    END LOOP;
END;
$$;

-- ------------------------------------------------------------------------------
-- 3. Trigger para Criação Automática do Plano de Contas em Novos Tenants
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_tenant_create_default_ledger_accounts()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM ensure_tenant_canonical_ledger_accounts(NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_catalog, pg_temp;

DROP TRIGGER IF EXISTS trg_after_insert_tenant_ledger ON tenants;
CREATE TRIGGER trg_after_insert_tenant_ledger
AFTER INSERT ON tenants
FOR EACH ROW
EXECUTE FUNCTION trg_tenant_create_default_ledger_accounts();

-- ------------------------------------------------------------------------------
-- 4. Tabela de Intenções de Pagamento Pix (Prevenção de Saldo Fictício)
-- Toda transação inicia como PENDENTE e NUNCA gera lançamento contábil
-- sem liquidação e webhook bancário comprovados.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pix_payment_intents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    contribution_id UUID REFERENCES contributions(id) ON DELETE CASCADE,
    loan_installment_id UUID REFERENCES loan_installments(id) ON DELETE CASCADE,
    payer_user_id UUID NOT NULL REFERENCES users(id),
    amount_cents BIGINT NOT NULL CHECK (amount_cents > 0),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDENTE'
        CHECK (status IN ('PENDENTE', 'PROCESSANDO', 'LIQUIDADO_CONFIRMADO', 'EXPIRADO', 'REJEITADO')),
    idempotency_key VARCHAR(120) NOT NULL,
    pix_copy_paste TEXT NOT NULL,
    pix_qr_code_url TEXT,
    end_to_end_id VARCHAR(100),
    reconciled_at TIMESTAMP WITH TIME ZONE,
    reconciliation_proof TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pix_intent_idempotency UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_pix_intents_tenant ON pix_payment_intents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pix_intents_status ON pix_payment_intents(status);
CREATE INDEX IF NOT EXISTS idx_pix_intents_contrib ON pix_payment_intents(contribution_id);
CREATE INDEX IF NOT EXISTS idx_pix_intents_inst ON pix_payment_intents(loan_installment_id);

-- ------------------------------------------------------------------------------
-- 5. Row-Level Security (RLS) Estrito na Tabela de Intenções Pix
-- ------------------------------------------------------------------------------
ALTER TABLE pix_payment_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE pix_payment_intents FORCE ROW LEVEL SECURITY;

CREATE POLICY rls_pix_intents_select ON pix_payment_intents
    FOR SELECT
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) != 'MASTER'
        AND (
            current_setting('app.current_role', true) = 'TENANT_ADMIN'
            OR payer_user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
        )
    );

CREATE POLICY rls_pix_intents_insert ON pix_payment_intents
    FOR INSERT
    WITH CHECK (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) IN ('TENANT_ADMIN', 'TENANT_MEMBER')
        AND payer_user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
    );

CREATE POLICY rls_pix_intents_update ON pix_payment_intents
    FOR UPDATE
    USING (
        tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::UUID))
        AND current_setting('app.current_role', true) = 'TENANT_ADMIN'
    );
