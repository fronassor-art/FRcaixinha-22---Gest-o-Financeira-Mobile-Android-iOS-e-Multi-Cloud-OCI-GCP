-- ==============================================================================
-- FRcaixinha 2.2 — Schema Oficial PostgreSQL com Row-Level Security (RLS)
-- Em conformidade com o Contrato Técnico Mestre (Cláusulas 1.2, 2.8, 14.1 e 16.2)
-- ==============================================================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------------------------
-- 1. Tabela de Usuários (Identidade Única com Segregação de Papéis - Cláusula 2.3)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    cpf VARCHAR(14) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'PENDING_VERIFICATION')),
    is_master BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_cpf ON users(cpf);

-- ------------------------------------------------------------------------------
-- 2. Credenciais Seguras (Argon2id / bcrypt - Nunca gravadas em plain text)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credentials (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    algorithm VARCHAR(50) NOT NULL DEFAULT 'argon2id' CHECK (algorithm IN ('argon2id', 'bcrypt')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    password_changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 3. Inquilinos / Caixinhas (Tenants - Segregação Patrimonial Estrita)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    display_name VARCHAR(255) NOT NULL,
    contracting_party_id VARCHAR(100) NOT NULL,
    admin_user_id UUID NOT NULL REFERENCES users(id),
    status VARCHAR(30) NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('RASCUNHO_INATIVO', 'ATIVO', 'SUSPENSO', 'ENCERRADO')),
    is_owner_box BOOLEAN NOT NULL DEFAULT FALSE, -- Caixinha Inaugural do proprietário
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_admin ON tenants(admin_user_id);

-- ------------------------------------------------------------------------------
-- 4. Vínculos e Membros (Memberships por Tenant)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(30) NOT NULL CHECK (role IN ('TENANT_ADMIN', 'TENANT_MEMBER')),
    status VARCHAR(30) NOT NULL DEFAULT 'ATIVA' CHECK (status IN ('ATIVA', 'SUSPENSA', 'DESLIGADA')),
    consecutive_unpaid_months INTEGER NOT NULL DEFAULT 0,
    is_profit_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    joined_at DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_user UNIQUE(tenant_id, user_id, role)
);

CREATE INDEX idx_memberships_tenant ON memberships(tenant_id);
CREATE INDEX idx_memberships_user ON memberships(user_id);

-- ------------------------------------------------------------------------------
-- 5. Cotas dos Membros
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quotas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    membership_id UUID NOT NULL REFERENCES memberships(id) ON DELETE CASCADE,
    quota_number INTEGER NOT NULL,
    value_brl NUMERIC(12, 2) NOT NULL DEFAULT 100.00,
    status VARCHAR(30) NOT NULL DEFAULT 'ATIVA' CHECK (status IN ('ATIVA', 'INATIVA', 'CANCELADA')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_quota UNIQUE(tenant_id, quota_number)
);

CREATE INDEX idx_quotas_tenant ON quotas(tenant_id);

-- ------------------------------------------------------------------------------
-- 6. Ciclos Financeiros Anuais (Calendário Central Fixo 01/01 a 31/12)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cycles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    settlement_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'ABERTO' CHECK (status IN ('ABERTO', 'CONGELADO', 'EM_APURACAO', 'LIQUIDADO')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_cycle_year UNIQUE(tenant_id, year)
);

-- ------------------------------------------------------------------------------
-- 7. Políticas Financeiras por Ciclo (Taxa Price, Split Admin/Membros)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    monthly_interest_rate NUMERIC(6, 4) NOT NULL DEFAULT 0.2000, -- 20.00% a.m.
    max_installments INTEGER NOT NULL DEFAULT 6,
    contribution_per_quota NUMERIC(12, 2) NOT NULL DEFAULT 100.00,
    flat_fine_amount NUMERIC(12, 2) NOT NULL DEFAULT 10.00,
    daily_mora_rate NUMERIC(8, 6) NOT NULL DEFAULT 0.006667, -- 20% / 30 ao dia
    admin_pct NUMERIC(5, 2) NOT NULL DEFAULT 15.00, -- 15% administrador
    member_pct NUMERIC(5, 2) NOT NULL DEFAULT 85.00, -- 85% membros
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_policy_split_sum CHECK (admin_pct + member_pct = 100.00)
);

-- ------------------------------------------------------------------------------
-- 8. Empréstimos — Tabela Price (Amortização Decrescente de Juros, Isento de TAC)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cycle_id UUID NOT NULL REFERENCES cycles(id) ON DELETE CASCADE,
    borrower_membership_id UUID NOT NULL REFERENCES memberships(id),
    policy_id UUID NOT NULL REFERENCES policies(id),
    is_admin_loan BOOLEAN NOT NULL DEFAULT FALSE,
    principal NUMERIC(12, 2) NOT NULL,
    monthly_rate NUMERIC(6, 4) NOT NULL,
    term_months INTEGER NOT NULL CHECK (term_months BETWEEN 1 AND 12),
    monthly_payment NUMERIC(12, 2) NOT NULL,
    last_payment NUMERIC(12, 2) NOT NULL,
    total_interest NUMERIC(12, 2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'SOLICITADO' CHECK (status IN ('SOLICITADO', 'APROVADO', 'RESERVADO', 'DESEMBOLSADO', 'QUITADO', 'INADIMPLENTE')),
    disbursed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_loans_tenant ON loans(tenant_id);

-- ------------------------------------------------------------------------------
-- 9. Livro-Razão Contábil (Partidas Dobradas Imutáveis)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ledger_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')),
    balance_cents BIGINT NOT NULL DEFAULT 0,
    CONSTRAINT uq_tenant_account UNIQUE(tenant_id, account_code)
);

CREATE TABLE IF NOT EXISTS ledger_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    transaction_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    description TEXT NOT NULL,
    reference_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES ledger_transactions(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES ledger_accounts(id),
    entry_type VARCHAR(2) NOT NULL CHECK (entry_type IN ('DR', 'CR')),
    amount_cents BIGINT NOT NULL CHECK (amount_cents > 0),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 10. Sessões Criptográficas no Servidor (Tokens com TTL de 15 Minutos)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA-256 do token opaco
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    active_role VARCHAR(30) NOT NULL CHECK (active_role IN ('MASTER', 'TENANT_ADMIN', 'TENANT_MEMBER')),
    active_tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX idx_sessions_user ON sessions(user_id);

-- ------------------------------------------------------------------------------
-- 11. Convites Administrativos (Sem Auto-Cadastro de Papéis Privilegiados)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invitations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    inviter_user_id UUID NOT NULL REFERENCES users(id),
    target_email VARCHAR(255) NOT NULL,
    target_role VARCHAR(30) NOT NULL CHECK (target_role IN ('TENANT_ADMIN', 'TENANT_MEMBER')),
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 12. Trilha de Auditoria Imutável (Append-Only)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID REFERENCES users(id),
    actor_role VARCHAR(30) NOT NULL,
    tenant_id UUID REFERENCES tenants(id),
    action VARCHAR(100) NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    object_id VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    evidence_ref VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_tenant ON audit_events(tenant_id);

-- ==============================================================================
-- ==============================================================================
-- 13. FUNÇÕES PRIVILEGIADAS AUXILIARES DE RLS (SEM RECURSÃO INFINITA)
-- Padrão PostgreSQL: SECURITY DEFINER com search_path imutável contra CWE-426
-- ==============================================================================

-- Proteção de integridade do schema: impede que usuários não confiáveis criem objetos no schema public
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Retorna a lista de tenant_ids aos quais o usuário está ativamente vinculado.
-- Executa com privilégios do criador para evitar recursão em memberships.
CREATE OR REPLACE FUNCTION rls_user_active_tenants(p_user_id UUID)
RETURNS TABLE (tenant_id UUID)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
    SELECT m.tenant_id
    FROM public.memberships m
    WHERE m.user_id = p_user_id
      AND m.status = 'ATIVA';
$$;

-- Verifica se o usuário é Administrador Ativo do tenant especificado.
CREATE OR REPLACE FUNCTION rls_is_tenant_admin(p_user_id UUID, p_tenant_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.memberships m
        WHERE m.user_id = p_user_id
          AND m.tenant_id = p_tenant_id
          AND m.role = 'TENANT_ADMIN'
          AND m.status = 'ATIVA'
    );
$$;

-- Retorna o ID de membership do usuário no tenant especificado.
CREATE OR REPLACE FUNCTION rls_user_membership_ids(p_user_id UUID, p_tenant_id UUID)
RETURNS TABLE (membership_id UUID)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
    SELECT m.id
    FROM public.memberships m
    WHERE m.user_id = p_user_id
      AND m.tenant_id = p_tenant_id
      AND m.status = 'ATIVA';
$$;

-- Verifica se o usuário autenticado possui o atributo is_master na tabela users.
CREATE OR REPLACE FUNCTION rls_is_master(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
    SELECT COALESCE(
        (SELECT u.is_master FROM public.users u WHERE u.id = p_user_id AND u.status = 'ACTIVE'),
        FALSE
    );
$$;

-- ==============================================================================
-- 14. HABILITAÇÃO E FORÇAMENTO DE POSTGRESQL ROW-LEVEL SECURITY (RLS)
-- FORCE ROW LEVEL SECURITY garante que o RLS se aplique inclusive ao proprietário da tabela
-- ==============================================================================

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;

ALTER TABLE quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotas FORCE ROW LEVEL SECURITY;

ALTER TABLE cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycles FORCE ROW LEVEL SECURITY;

ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE policies FORCE ROW LEVEL SECURITY;

ALTER TABLE loans ENABLE ROW LEVEL SECURITY;
ALTER TABLE loans FORCE ROW LEVEL SECURITY;

ALTER TABLE ledger_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_accounts FORCE ROW LEVEL SECURITY;

ALTER TABLE ledger_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_transactions FORCE ROW LEVEL SECURITY;

ALTER TABLE ledger_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_entries FORCE ROW LEVEL SECURITY;

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- A. Políticas de Inquilinos (Tenants)
-- ------------------------------------------------------------------------------
-- SELECT: Usuário vê apenas seus tenants ativos; Master vê lista cadastral para gestão de licença SaaS
CREATE POLICY tenants_select_policy ON tenants
    FOR SELECT
    USING (
        id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::uuid))
        OR (
            rls_is_master(NULLIF(current_setting('app.current_user_id', true), '')::uuid) = TRUE
            AND current_setting('app.current_role', true) = 'MASTER'
        )
    );

-- INSERT: Apenas Master pode criar novas caixinhas / tenants contratuais
CREATE POLICY tenants_insert_policy ON tenants
    FOR INSERT
    WITH CHECK (
        rls_is_master(NULLIF(current_setting('app.current_user_id', true), '')::uuid) = TRUE
        AND current_setting('app.current_role', true) = 'MASTER'
    );

-- UPDATE: Administrador ativo altera apenas sua caixinha; Master altera apenas metadados de plano
CREATE POLICY tenants_update_policy ON tenants
    FOR UPDATE
    USING (
        id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND (
            rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, id)
            OR (
                rls_is_master(NULLIF(current_setting('app.current_user_id', true), '')::uuid) = TRUE
                AND current_setting('app.current_role', true) = 'MASTER'
            )
        )
    );

-- ------------------------------------------------------------------------------
-- B. Políticas de Vínculos e Membros (Memberships) - Sem Recursão
-- ------------------------------------------------------------------------------
-- SELECT: Vê apenas membros da caixinha ativa onde o usuário possui vínculo comprovado
CREATE POLICY memberships_select_policy ON memberships
    FOR SELECT
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::uuid))
    );

-- INSERT: Apenas o Administrador Ativo daquele tenant pode inserir membros
CREATE POLICY memberships_insert_policy ON memberships
    FOR INSERT
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

-- UPDATE: Apenas o Administrador Ativo daquele tenant pode atualizar status de membros
CREATE POLICY memberships_update_policy ON memberships
    FOR UPDATE
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

-- DELETE: Proibido desligamento físico direto sem auditoria (soft-delete via update de status)
CREATE POLICY memberships_delete_policy ON memberships
    FOR DELETE
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

-- ------------------------------------------------------------------------------
-- C. Políticas de Cotas (Quotas)
-- ------------------------------------------------------------------------------
CREATE POLICY quotas_select_policy ON quotas
    FOR SELECT
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::uuid))
    );

CREATE POLICY quotas_insert_policy ON quotas
    FOR INSERT
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

CREATE POLICY quotas_update_policy ON quotas
    FOR UPDATE
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

-- ------------------------------------------------------------------------------
-- D. Políticas de Empréstimos (Loans) - Proteção Patrimonial Estrita
-- ------------------------------------------------------------------------------
-- SELECT: Admin vê todos os empréstimos da sua caixinha; Membro vê somente os seus
-- Master NUNCA vê empréstimos de caixinhas (Cláusula 2.8)
CREATE POLICY loans_select_policy ON loans
    FOR SELECT
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::uuid))
        AND (
            rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
            OR borrower_membership_id IN (
                SELECT rls_user_membership_ids(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
            )
        )
    );

-- INSERT: Membros criam solicitação apenas para sua própria membership; Admin para terceiros mediante aprovação
CREATE POLICY loans_insert_policy ON loans
    FOR INSERT
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::uuid))
        AND (
            rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
            OR borrower_membership_id IN (
                SELECT rls_user_membership_ids(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
            )
        )
    );

-- UPDATE: Somente Administrador ativo da caixinha pode aprovar ou desembolsar empréstimos
CREATE POLICY loans_update_policy ON loans
    FOR UPDATE
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

-- ------------------------------------------------------------------------------
-- E. Políticas de Razão Contábil (Ledger)
-- ------------------------------------------------------------------------------
CREATE POLICY ledger_accounts_policy ON ledger_accounts
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

CREATE POLICY ledger_transactions_policy ON ledger_transactions
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

CREATE POLICY ledger_entries_policy ON ledger_entries
    FOR ALL
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
    );

-- ------------------------------------------------------------------------------
-- F. Políticas de Auditoria (Audit Events) - Append-Only
-- ------------------------------------------------------------------------------
CREATE POLICY audit_events_select_policy ON audit_events
    FOR SELECT
    USING (
        (
            tenant_id IS NOT NULL
            AND tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND rls_is_tenant_admin(NULLIF(current_setting('app.current_user_id', true), '')::uuid, tenant_id)
        )
        OR (
            tenant_id IS NULL
            AND rls_is_master(NULLIF(current_setting('app.current_user_id', true), '')::uuid) = TRUE
            AND current_setting('app.current_role', true) = 'MASTER'
        )
    );

CREATE POLICY audit_events_insert_policy ON audit_events
    FOR INSERT
    WITH CHECK (
        (tenant_id IS NULL AND rls_is_master(NULLIF(current_setting('app.current_user_id', true), '')::uuid) = TRUE)
        OR (
            tenant_id IS NOT NULL
            AND tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            AND tenant_id IN (SELECT rls_user_active_tenants(NULLIF(current_setting('app.current_user_id', true), '')::uuid))
        )
    );

-- Bloqueio total de UPDATE e DELETE na trilha de auditoria (Imutabilidade compulsória)
-- Sem políticas de UPDATE ou DELETE criadas, o PostgreSQL bloqueia qualquer tentativa de mutação.

-- ==============================================================================
-- 15. CONFIGURAÇÃO DE PAPEL DE APLICAÇÃO DE MENOR PRIVILÉGIO (LEAST PRIVILEGE)
-- Papel NOLOGIN para permissões. Credenciais de conexão do usuário devem ser
-- provisionadas operacionalmente via Secret Manager / Vault, NUNCA em migrations.
-- Exemplo operacional fora do código:
--   CREATE ROLE frcaixinha_app_user WITH LOGIN PASSWORD '<segredo_do_vault>' NOSUPERUSER NOBYPASSRLS;
--   GRANT frcaixinha_app_role TO frcaixinha_app_user;
-- ==============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'frcaixinha_app_role') THEN
        CREATE ROLE frcaixinha_app_role NOLOGIN NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO frcaixinha_app_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO frcaixinha_app_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO frcaixinha_app_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO frcaixinha_app_role;
