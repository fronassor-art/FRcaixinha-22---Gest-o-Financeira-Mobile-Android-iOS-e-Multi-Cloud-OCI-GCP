# FR Finance AI Studio — M37381–M37400 | Local E2E read-only smoke

## Base real homologada
- Commit 02d9590, M37370: 22/22 testes e 106 SQL íntegros;
  PostgreSQL 18 local na porta 5433 respondendo;
  estruturas lifecycle 028–030, inbox 031, parity 034–041,
  mínimo R$150 em M043 e autenticação M22600 STRUCTURAL_PRESENT.
- FastAPI ativo no Termux em 127.0.0.1:8000.
- M37380: /api/health 200; /api/health/ready 200;
  /api/health/features/m19000 200; app FR Finance, auth sandbox,
  inbox/schema prontos; PIX_REAL=OFF e ativação real OFF.

## Escopo do M37400
O script de homologação faz **oito GETs estritamente para 127.0.0.1:8000**.
Confirma:
1. Identidade FR Finance e configuração de banco.
2. Autenticação local pronta para teste, nunca produção.
3. Inbox local M19000 pronta, com email/push/WhatsApp e efeitos
   financeiros desligados.
4. Flags financeiras globais desligadas.
5. Modo de autenticação TEST_MODE com PostgreSQL de homologação.
6. Sem cookie e sem token, /auth/me e os dois endpoints privados
   /notifications/capabilities e /notifications/readiness devem rejeitar
   o acesso com HTTP 401 ou 403.

Nenhum POST/PUT/DELETE, token, senha, cookie, escrita SQL, evento de
notificação, chamada OCI ou chamada Mercado Pago. Respostas e exceções
não são impressas; apenas nomes fixos de estados e códigos sanitizados.
O cliente não segue redirects e não envia dados pessoais.

**Interpretação:** M37400_SMOKE=PASS confirma somente os contratos
GET de infraestrutura, configuração e recusa anônima naquele momento.
Não prova login com senha, isolamento entre membros/administradores,
entrega real de notificações, restauro de backup, webhook, Pix ou OCI.

## Execução, após GitHub Actions aprovado
No Termux, **fora do Debian**, deixar PostgreSQL 5433 e FastAPI 8000
em execução; sincronizar o GitHub; testar os módulos:

PYTHONPATH=backend python -m pytest -q backend/tests/test_m37381_m37400_local_runtime_smoke_ci.py

A consulta local estritamente read-only é:

PYTHONDONTWRITEBYTECODE=1 python backend/scripts/aistudio_local_runtime_smoke_readonly.py

O comando só produz PASS ou BLOCKED e motivos não sensíveis.
Não compartilhar logs de banco, variáveis de ambiente nem credenciais.
A passagem não autoriza ativar usuário real, Pix real ou infraestrutura
paga da OCI. Nenhuma migração local aplicada; catálogo SQL 106 inalterado.
