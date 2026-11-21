# FR Finance M40360 — ligação do login original à rota de Crédito Especial

Checkpoint: M40350 sincronizado pelo Termux, commit e07e97f. O celular
atestou o processo original PostgreSQL em execução, conexão 127.0.0.1:5433
aceitando e FastAPI ONLINE. Não foram realizadas migrações nem reinícios.

## Aproveitamento do trabalho existente

A suíte original `backend/tests/test_rls_isolation_ci.py` já verifica
Argon2id, prova efêmera vinculada à credencial, as funções PostgreSQL
`auth_issue_pending_session`, `auth_promote_pending_session`,
`auth_active_memberships` e a revogação original. M40340 e M40350
comprovaram seis RLS SQL110 com tokens pré-semeados, além da higiene da
pool, mas utilizaram funções auxiliares SQL sintéticas.

M40360 **não** cria workflow, banco local, diretório ou rota. Acrescenta
um teste à suíte de integração original e o executa no PostgreSQL 16
descartável já utilizado pela CI, e também no job PostgreSQL 18
`postgres18-preflight` já existente.

## Escopo da prova

- Cinco identidades sintéticas (administradores de A/B, membros de A/B
  e Master) autenticam pela rota real `POST /api/v1/auth/login`.
- A senha é verificada pela função original do backend usando a role
  verificadora; hash/prova/token/sessão são emitidos pelas funções
  reais SQL da suíte original, não pelos substitutos do M40340.
- Aplicação, autenticação e verificação utilizam **o mesmo banco
  descartável**, com diferentes roles técnicas; não há DB duplicado.
- A sessão resultante chama a rota original
  `/special-credit/capabilities`, confere o próprio tenant, nega
  outro tenant e nega acesso Master. O sandbox e todas as comunicações
  e operações reais continuam OFF.
- A consulta administrativa `/special-credit/grants` com o sandbox
  fechado retorna 503. Após logout, o token não pode acessar a rota.
  Uma tentativa de escalada de tenant/papel falha no login.

## Limites explícitos

Este teste valida **login real com senha, funções SQL originais e
controles HTTP das rotas de Crédito Especial** no mesmo ambiente de CI.
Não testa acesso a linhas SQL110 no mesmo banco autenticado, pois
essas tabelas são verificadas por M40340 em um outro runner
efêmero. Não há certificação do APK real, da identidade do banco
original em Termux nem de emissão de sessão financeira em produção.
Nenhuma credencial verdadeira é utilizada.

## Proteções

FR Finance no celular permanece um único diretório, repositório e banco
`frcaixinha_aistudio_dev` na porta 5433. SQL110/111 já aplicadas
localmente não devem ser reaplicadas. Nenhum reinício autorizado.
PR #2 Draft. PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF,
ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED.
