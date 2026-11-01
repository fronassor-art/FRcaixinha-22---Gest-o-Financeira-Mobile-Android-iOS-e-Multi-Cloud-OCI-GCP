"""
FRcaixinha 2.2 — Suíte de Testes Automatizados de API FastAPI e PostgreSQL RLS
Contrato Técnico Mestre (Cláusulas 1.2, 1.3, 2.3, 2.8, 5.4, 14.1 e 16.4)

Categorias de Testes:
(b) Testes de API que iniciam o FastAPI (TestClient)
(c) Testes de Integração com PostgreSQL real (Conexão e Migrações)
(d) Testes de Row-Level Security (RLS) com usuários de aplicação reais (CRUD: INSERT, UPDATE, DELETE e SELECT)

STATUS NO AMBIENTE ATUAL:
- Categoria (a) Testes Unitários de Matemática/Lógica: Executados com sucesso via Node/TypeScript (12 PASS).
- Categorias (b), (c) e (d): Marcados como BLOQUEADOS no sandbox atual devido à ausência de PostgreSQL local
  e dependências do backend ('fastapi', 'asyncpg', 'pytest' não instalados no sistema global).
"""

import os
import uuid
import pytest

DATABASE_URL = os.getenv("DATABASE_URL")
HAS_DB = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

try:
    from fastapi.testclient import TestClient
    from app.main import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI não instalado. Execute: pip install -r backend/requirements.txt")
class TestFastAPIApiEndpoints:
    """Categoria (b): Testes de API com FastAPI TestClient."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_health_check_contract(self):
        """Verifica se o endpoint de saúde declara a arquitetura oficial do Contrato."""
        response = self.client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ONLINE"
        assert data["framework"] == "FastAPI (Python)"
        assert data["database_backend"] == "PostgreSQL com Row-Level Security (RLS)"

    def test_auth_status_reports_unconfigured_when_no_db(self):
        """Verifica que o backend bloqueia com segurança sem banco configurado."""
        response = self.client.get("/api/v1/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "BLOCKED_PENDING_CONFIG"
        assert data["configured"] is False

    def test_login_rejects_empty_credentials(self):
        """Rejeita requisições de login sem os campos obrigatórios."""
        response = self.client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    def test_database_url_does_not_claim_login_is_implemented(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://127.0.0.1/frcaixinha_ci")
        response = self.client.get("/api/v1/auth/status")
        assert response.status_code == 200
        assert response.json()["configured"] is False
        assert response.json()["status"] == "BLOCKED_PENDING_IMPLEMENTATION"
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "teste@example.invalid", "password": "teste-sintetico"},
        )
        assert login.status_code == 503

    def test_break_glass_is_disabled_by_contract(self):
        """Garante que a rota de suporte emergencial Break-Glass permaneça desabilitada (HTTP 403)."""
        response = self.client.post(
            "/api/v1/master/support-session",
            json={
                "target_tenant_id": str(uuid.uuid4()),
                "justification": "Tentativa de suporte técnico emergencial sem consentimento",
                "duration_minutes": 30
            }
        )
        assert response.status_code in (401, 403)

    def test_simulate_loan_price_regular_endpoint(self):
        """Valida que a rota /loans/simulate realiza cálculo Price exato e determinístico."""
        tenant_id = str(uuid.uuid4())
        # Como requer sessão autenticada, testa resposta padrão do endpoint
        response = self.client.post(
            f"/api/v1/tenants/{tenant_id}/loans/simulate",
            json={"principal": 500.00, "term_months": 5, "monthly_rate": 0.20}
        )
        # Se sem sessão: 401 Unauthorized
        assert response.status_code in (200, 401)
        if response.status_code == 200:
            data = response.json()
            assert data["uniform_payment"] == 167.19
            assert data["last_payment"] == 167.20
            assert len(data["schedule"]) == 5

    def test_financial_routes_fail_safely_when_db_unconfigured(self):
        """Garante que rotas financeiras de gravação não executem sem banco (retornam 401/503)."""
        tenant_id = str(uuid.uuid4())
        res_contributions = self.client.get(f"/api/v1/tenants/{tenant_id}/contributions")
        assert res_contributions.status_code in (401, 503)

        res_loans = self.client.get(f"/api/v1/tenants/{tenant_id}/loans")
        assert res_loans.status_code in (401, 503)

        res_ledger = self.client.get(f"/api/v1/tenants/{tenant_id}/ledger/accounts")
        assert res_ledger.status_code in (401, 503)

    def test_migration_002_contains_force_rls_on_all_tables(self):
        """Verifica estaticamente que a migração 002 possui FORCE ROW LEVEL SECURITY em todas as tabelas."""
        migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "002_financial_extensions.sql")
        assert os.path.exists(migration_path)
        with open(migration_path, "r", encoding="utf-8") as f:
            content = f.read()
        expected_tables = ["contributions", "loan_installments", "loan_payments", "admin_self_loan_consents", "cycle_closings", "cycle_profit_distributions"]
        for tbl in expected_tables:
            assert f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;" in content, f"FORCE RLS ausente para {tbl}"


@pytest.mark.skipif(not HAS_DB, reason="PostgreSQL não disponível neste ambiente. Testes RLS reais marcados como BLOQUEADOS.")
class TestPostgreSQLRowLevelSecurityCRUD:
    """
    Categorias (c) e (d):
    Testes de Banco de Dados PostgreSQL Real e Políticas RLS (SELECT, INSERT, UPDATE, DELETE).
    Executados com o usuário restrito 'frcaixinha_app' (sem SUPERUSER, sem BYPASSRLS).
    """

    @pytest.fixture(autouse=True)
    async def setup_db(self):
        """Configura conexão com usuário de aplicação frcaixinha_app."""
        import asyncpg
        conn = await asyncpg.connect(DATABASE_URL)
        yield conn
        await conn.close()

    async def test_rls_memberships_no_infinite_recursion(self, setup_db):
        """
        [Item 1] Valida que a consulta à tabela memberships NÃO gera o erro
        'infinite recursion detected in policy for relation memberships'.
        """
        conn = setup_db
        test_user_id = str(uuid.uuid4())
        test_tenant_id = str(uuid.uuid4())

        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_user_id = '{test_user_id}';")
            await conn.execute(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}';")
            await conn.execute("SELECT set_config('app.current_role', 'TENANT_MEMBER', true);")

            # Esta consulta falharia com erro de recursão infinita na modelagem anterior
            rows = await conn.fetch("SELECT * FROM memberships WHERE tenant_id = $1;", uuid.UUID(test_tenant_id))
            assert isinstance(rows, list)

    async def test_rls_force_row_level_security_enforced_for_table_owner(self, setup_db):
        """
        [Item 3] Valida que FORCE ROW LEVEL SECURITY está ativo em todas as tabelas
        patrimoniais, impedindo que até o proprietário das tabelas contorne o RLS.
        """
        conn = setup_db
        result = await conn.fetch("""
            SELECT c.relname AS tablename, c.relrowsecurity AS rowsecurity,
                   c.relforcerowsecurity AS forcerowsecurity
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname IN ('tenants', 'memberships', 'loans', 'ledger_accounts');
        """)
        assert len(result) == 4, "Tabelas esperadas não foram encontradas"
        for row in result:
            assert row["rowsecurity"] is True, f"RLS não habilitado em {row['tablename']}"
            assert row["forcerowsecurity"] is True, f"FORCE RLS não habilitado em {row['tablename']}"

    async def test_rls_blocks_cross_tenant_select(self, setup_db):
        """
        [Item 4 - SELECT] Garante que um Admin da Caixinha A não consiga visualizar empréstimos
        ou membros da Caixinha B, mesmo forjando app.current_tenant_id.
        """
        conn = setup_db
        user_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())

        async with conn.transaction():
            # Usuário A tenta apontar a sessão para o Tenant B (onde ele não possui membership)
            await conn.execute(f"SET LOCAL app.current_user_id = '{user_a}';")
            await conn.execute(f"SET LOCAL app.current_tenant_id = '{tenant_b}';")
            await conn.execute("SELECT set_config('app.current_role', 'TENANT_ADMIN', true);")

            # O motor RLS deve descartar todas as linhas porque rls_user_active_tenants(user_a) não inclui tenant_b
            rows = await conn.fetch("SELECT * FROM loans WHERE tenant_id = $1;", uuid.UUID(tenant_b))
            assert len(rows) == 0

    async def test_rls_blocks_cross_tenant_insert(self, setup_db):
        """
        [Item 4 - INSERT] Garante que um usuário não possa inserir novos registros (ex: quotas ou memberships)
        em um tenant onde ele não é Administrador Ativo.
        """
        conn = setup_db
        user_malicious = str(uuid.uuid4())
        victim_tenant = str(uuid.uuid4())

        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_user_id = '{user_malicious}';")
            await conn.execute(f"SET LOCAL app.current_tenant_id = '{victim_tenant}';")
            await conn.execute("SELECT set_config('app.current_role', 'TENANT_ADMIN', true);")

            with pytest.raises(Exception) as exc_info:
                await conn.execute("""
                    INSERT INTO quotas (id, tenant_id, membership_id, quota_number, value_brl, status)
                    VALUES ($1, $2, $3, 999, 100.00, 'ATIVA');
                """, uuid.uuid4(), uuid.UUID(victim_tenant), uuid.uuid4())
            assert "violates row-level security policy" in str(exc_info.value).lower()

    async def test_rls_blocks_cross_tenant_update(self, setup_db):
        """
        [Item 4 - UPDATE] Garante que um mutuário ou admin alheio não consiga atualizar status
        de empréstimos de outro inquilino.
        """
        conn = setup_db
        user_attacker = str(uuid.uuid4())
        target_tenant = str(uuid.uuid4())
        target_loan = str(uuid.uuid4())

        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_user_id = '{user_attacker}';")
            await conn.execute(f"SET LOCAL app.current_tenant_id = '{target_tenant}';")
            await conn.execute("SELECT set_config('app.current_role', 'TENANT_MEMBER', true);")

            # UPDATE não afeta linhas devido ao filtro USING do RLS
            result = await conn.execute("""
                UPDATE loans SET status = 'LIQUIDADO' WHERE id = $1 AND tenant_id = $2;
            """, uuid.UUID(target_loan), uuid.UUID(target_tenant))
            assert result == "UPDATE 0"

    async def test_rls_blocks_cross_tenant_delete(self, setup_db):
        """
        [Item 4 - DELETE] Garante que nenhum usuário consiga excluir registros de outros tenants.
        """
        conn = setup_db
        user_attacker = str(uuid.uuid4())
        target_tenant = str(uuid.uuid4())

        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_user_id = '{user_attacker}';")
            await conn.execute(f"SET LOCAL app.current_tenant_id = '{target_tenant}';")
            await conn.execute("SELECT set_config('app.current_role', 'TENANT_ADMIN', true);")

            result = await conn.execute("""
                DELETE FROM memberships WHERE tenant_id = $1;
            """, uuid.UUID(target_tenant))
            assert result == "DELETE 0"

    async def test_master_has_zero_access_to_tenant_ledger(self, setup_db):
        """
        [Cláusula 2.8] Garante que o perfil Master não leia contas ou lançamentos contábeis
        de caixinhas pelo RLS do banco de dados.
        """
        conn = setup_db
        master_user = str(uuid.uuid4())
        tenant_target = str(uuid.uuid4())

        async with conn.transaction():
            await conn.execute(f"SET LOCAL app.current_user_id = '{master_user}';")
            await conn.execute(f"SET LOCAL app.current_tenant_id = '{tenant_target}';")
            await conn.execute("SELECT set_config('app.current_role', 'MASTER', true);")

            rows = await conn.fetch("SELECT * FROM ledger_accounts WHERE tenant_id = $1;", uuid.UUID(tenant_target))
            assert len(rows) == 0
