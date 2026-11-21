# FR Finance AI Studio — M37401–M37420 | Sessões inválidas e perfis forjados

## Base do checkpoint
M37400 em Termux: commit 53c0583; 50 testes locais PASS;
8 endpoints GET PASS; PostgreSQL 18 na porta 5433, FastAPI 8000;
autenticação sandbox e inbox local prontas.
PIX REAL OFF, usuários reais OFF e nenhum SQL aplicado.

## O que faz M37420
Uma auditoria **GET-only** no próprio Termux em 127.0.0.1:8000.
Três endpoints de controle verificam a identidade FR Finance, o status
local READY_FOR_TEST_AUTH e autenticação TEST_MODE/POSTGRES_TEST.
Depois, em seis rotas privadas (auth/me, auth/contexts, auth/sessions,
notifications/capabilities, notifications/readiness e notifications?limit=1),
ela exige HTTP 401 para cada uma destas condições:
- cabeçalhos X-Role/X-User-Role/X-User-Id/X-Tenant-Id forjados **sem sessão**;
- Bearer fixo sintético **nunca emitido**, sem usuário cadastrado.

Total 3 GETs de controle + 12 GETs de negação. Não imprime respostas
nem identificadores, não envia senhas reais, não guarda credenciais e
não faz POST, INSERT, migracoes, logout, refresh válido ou leitura de
dados de membros.

PASS significa apenas que falsificações simples e token inexistente
foram negados naquele processo e instante. Não comprova prova E2E com
administradores e membros autenticados, isolamento real entre tenants,
resistência a bypass de proxies nem proteção de todas as rotas. Essas
etapas exigem testes sintéticos separados em banco descartável,
não a criação de contas no banco local.

## Executar
Com PostgreSQL 5433 e FastAPI 8000 ativos, sincronizar a branch e rodar:

PYTHONPATH=backend python -m pytest -q backend/tests/test_m37401_m37420_local_session_boundary_ci.py

PYTHONDONTWRITEBYTECODE=1 python backend/scripts/aistudio_local_session_boundary_readonly.py

Se retornar BLOCKED, não alterar credenciais nem executar migrações;
apenas enviar os códigos sanitizados de erro.
O GitHub CI usa mocks e nunca chama o FastAPI local.

## Limites
Nenhuma migração nova. SQL versionados: 106. Oracle OCI, Vault, VM e IAM
inalterados. PIX real, MP real e ativação de usuários reais: OFF.
