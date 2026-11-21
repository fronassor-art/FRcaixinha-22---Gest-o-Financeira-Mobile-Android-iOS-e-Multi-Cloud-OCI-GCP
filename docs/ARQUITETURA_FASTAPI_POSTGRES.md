# FRcaixinha 2.2 — Arquitetura Oficial: FastAPI + PostgreSQL (RLS)

Documento de Referência Técnica em conformidade com o **Contrato Técnico Mestre (Cláusulas 1.2, 1.3, 2.3, 2.8, 5.4, 14.1 e 16.2)**.

---

## 1. Visão Geral da Arquitetura

O sistema FRcaixinha 2.2 foi projetado sob o princípio da **Segregação Patrimonial e Isolamento Multi-Inquilino (Multi-Tenant)**:

1. **Frontend**: SPA em React 19 + TypeScript + Vite + Tailwind CSS, responsiva para web desktop e mobile (Android/iOS PWA). Na inicialização, valida a sessão obrigatoriamente via `GET /api/auth/me`. Se não houver confirmação HTTP 200 do servidor, renderiza exclusivamente a `LoginView`.
2. **Backend Oficial Contratual**: **FastAPI (Python 3.10+)** com Pydantic / PostgreSQL driver, estruturado em `/backend/app/`. Manifesto de dependências fixadas em `/backend/requirements.txt`.
3. **Persistência e Isolamento**: **PostgreSQL 15+** com **Row-Level Security (RLS)** nativo no banco de dados e **FORCE ROW LEVEL SECURITY** ativo para impedir bypass até mesmo pelo proprietário das tabelas.
4. **Scaffold de Fronteira no AI Studio**: Servidor `server.ts` (Express) operando como proxy reverso de desenvolvimento para servir a SPA e rotear requisições para o backend FastAPI quando `FASTAPI_BACKEND_URL` estiver configurado. Inclui propagação estrita de cookies (`Set-Cookie`), proteção CSRF para requisições de mutação e bloqueio seguro (HTTP 503) quando desconectado.

---

## 2. Segregação de Papéis e Perfis (RBAC no Servidor)

A autorização é validada exclusivamente pelo servidor em cada requisição. O cliente **nunca** determina ou eleva seu próprio papel.

| Perfil | Escopo Permitido | Restrições Rígidas (Cláusula 2.8 e LGPD) |
| :--- | :--- | :--- |
| **MASTER (Plataforma)** | Gerenciamento de planos SaaS, preços e faturamento de licenças. | **Sem acesso financeiro**: Não acessa saldos, extratos, contribuições, cotas de membros nem dados pessoais de caixinhas. |
| **TENANT_ADMIN** | Administração total da **sua** caixinha concedida. | **Isolamento de tenant**: Tentativa de consultar ou alterar outra caixinha retorna `HTTP 403 Forbidden` (`CROSS_TENANT_ACCESS_DENIED`). |
| **TENANT_MEMBER** | Consulta das próprias cotas, contribuições, empréstimos e rifas/bolões onde participa. | **Privacidade entre membros**: Não acessa dados cadastrais (CPF, telefone) nem financeiros de outros membros da mesma caixinha. |

---

## 3. Resolução da Recursão Infinita em RLS e Funções SECURITY DEFINER

Na modelagem inicial de RLS em PostgreSQL, uma política na tabela `memberships` que realizasse subconsultas na própria tabela `memberships` disparava o erro fatal:
`ERROR: infinite recursion detected in policy for relation "memberships"`

### Como foi corrigido:
1. **Funções Privilegiadas Auxiliares**: Criamos funções `STABLE SECURITY DEFINER` (`rls_user_active_tenants`, `rls_is_tenant_admin`, `rls_user_membership_ids` e `rls_is_master`).
2. **Proteção contra Search Path Hijacking (CWE-426)**: Todas as funções declaram expressamente `SET search_path = public, pg_catalog, pg_temp`, garantindo que objetos não possam ser substituídos maliciosamente.
3. **Eliminação de Recursão**: Ao rodar em contexto `SECURITY DEFINER`, as leituras internas da tabela de membros não disparam a re-avaliação cíclica das políticas de linha da consulta externa.
4. **Isolamento Inviolável**: As funções realizam apenas consultas de verificação de associação entre `app.current_user_id` e `tenant_id`. Um usuário sem registro ativo de `membership` em um determinado tenant tem retorno vazio, impedindo o acesso.

---

## 4. Contexto Transacional Seguro (`SET LOCAL`) e Limpeza de Conexão

Conforme exigência técnica de segurança:
1. `app.current_user_id`, `app.current_role` e `app.current_tenant_id` são definidos **exclusivamente pelo backend** após validação de token ou cookie de sessão seguro.
2. É **terminantemente proibido** aceitar esses parâmetros de cabeçalhos arbitrários ou payloads do cliente.
3. A injeção transacional (`backend/app/database.py`) utiliza `SET LOCAL`:
   ```sql
   SET LOCAL app.current_user_id = '<user_id_validado_no_servidor>';
   SET LOCAL app.current_role = '<role_validado_no_servidor>';
   SET LOCAL app.current_tenant_id = '<tenant_id_validado_no_servidor>';
   ```
4. Ao término da transação (`COMMIT` ou `ROLLBACK`), o escopo local é descartado pelo PostgreSQL.
5. Antes de devolver a conexão física ao pool de conexões, executa-se obrigatoriamente:
   ```sql
   RESET ALL; DISCARD TEMP;
   ```
   Isso elimina qualquer risco de contaminação cruzada de credenciais ou contexto entre requisições concorrentes.

---

## 5. Usuário de Aplicação de Menor Privilégio e FORCE ROW LEVEL SECURITY

1. **Role de Aplicação**: O backend conecta-se como `frcaixinha_app`, usuário sem privilégios administrativos (`NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `NOBYPASSRLS`).
2. **FORCE ROW LEVEL SECURITY**: Por padrão no PostgreSQL, o proprietário das tabelas (owner) não é submetido às políticas de RLS. Para eliminar essa brecha em ambientes onde o usuário da aplicação possa vir a ser o mesmo que executou as migrações, todas as tabelas patrimoniais possuem:
   ```sql
   ALTER TABLE <nome_tabela> FORCE ROW LEVEL SECURITY;
   ```
   Isso força a avaliação incondicional das regras de RLS para **qualquer usuário**, inclusive o proprietário da tabela.

---

## 6. Fluxo de Sessão pelo Proxy `server.ts`

1. **Origem da URL do Backend**: `server.ts` lê o endereço do backend exclusivamente da variável de ambiente confiável `process.env.FASTAPI_BACKEND_URL`. URLs fornecidas pelo cliente são sumariamente ignoradas.
2. **Propagação de Cookies (`Set-Cookie`)**: O proxy inspeciona a resposta do FastAPI e repassa fielmente todos os cabeçalhos `Set-Cookie` para o navegador do cliente, mantendo as diretivas `HttpOnly`, `SameSite=Lax` e `Secure`.
3. **Encaminhamento de Credenciais (`Cookie`)**: O cabeçalho `Cookie` do navegador é encaminhado de forma segura ao FastAPI.
4. **Proteção CSRF**: Requisições de mutação de estado (`POST`, `PUT`, `DELETE`, `PATCH`) exigem a presença de token de autorização Bearer, cabeçalho customizado (`X-Requested-With`) ou origem estritamente autorizada (`Origin`/`Referer`).
5. **Comportamento quando desconectado**: Sem `FASTAPI_BACKEND_URL`, o proxy bloqueia imediatamente com **HTTP 503 (`AUTH_UNCONFIGURED`)**, informando que a autenticação ainda não foi configurada e que nenhuma sessão foi iniciada.

---

## 7. Categorização e Status Rigoroso dos Testes

| Categoria | Arquivo | Comando | Resultado Observado | Status Atual |
| :--- | :--- | :--- | :--- | :--- |
| **(a) Testes Unitários de Lógica/Matemática** | `src/tests/auth_rbac.test.ts` | `npm run test:audit` | **12 PASS** | **Homologado** (Tabela Price R$ 167,19 / 167,20, HMAC e isolamento em memória). |
| **(b) Testes de API FastAPI** | `backend/tests/test_rls_and_api.py` | `pytest backend/tests` | Não executado | **BLOQUEADO** (depende de `pip install -r backend/requirements.txt`). |
| **(c) Testes com PostgreSQL Real** | `backend/tests/test_rls_and_api.py` | `pytest -m db` | Não executado | **BLOQUEADO** (depende de instância ativa de PostgreSQL). |
| **(d) Testes de RLS (CRUD) no Banco** | `backend/tests/test_rls_and_api.py` | `pytest -m rls` | Não executado | **BLOQUEADO** (depende de instância ativa de PostgreSQL). |
| **(e) Compilação e Build** | Codebase do Applet | `npm run build` | **Sucesso (0 erros)** | **Homologado**. |
