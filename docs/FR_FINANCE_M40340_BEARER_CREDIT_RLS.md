# FR Finance M40340 — autenticação Bearer sintética e políticas RLS do Crédito Especial

M40330 (fe5ba82) e suas CIs do GitHub aprovadas. M40340 é somente
um teste de integração no PostgreSQL 18 descartável frfinance_ci_credit:5432.

Reutiliza as migrações SQL110/111 e a fixture M39020, sem migração
do aplicativo. Cria sete sessões sintéticas e dados não vazios nas seis
tabelas do Crédito Especial para as duas caixinhas fictícias. Uma rota
diagnóstica existe exclusivamente dentro do TestClient em memória,
sobre a instância FastAPI original e as dependências não substituídas
get_current_session e get_rls_db_connection.

Quatro sessões fictícias autenticadas (administradores A/B e membros
A/B) fazem 48 checagens positivas/negativas de visibilidade; Master
acrescenta 12 verificações negativas. Expiração, revogação,
anonimato, adulteração de cabeçalhos e acesso entre caixinhas são
negados. A API real de capabilities continua com Pix e crédito real OFF.

**Limitação essencial:** Os tokens são pré-semeados, não foram emitidos
via login por senha. As funções de autenticação SQL no runner são
substitutas sintéticas compatíveis com o contrato, não são as funções
reais do banco original. Resultado positivo não homologa o login de
produção, contas reais, APK, PIX, OCI ou operações financeiras.

O único local de execução é a CI descartável do GitHub Actions.
NÃO executar estes arquivos no Termux, Debian, PostgreSQL original
porta 5433, FR Caixinha 2.2 ou OCI. A PR #2 permanece Draft,
sem merge e sem reinício. PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF,
ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED.
