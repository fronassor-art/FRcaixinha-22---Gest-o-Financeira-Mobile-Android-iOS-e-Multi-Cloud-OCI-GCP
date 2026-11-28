# FR Finance M40350 — prova de higiene da pool RLS, sem duplicar etapas

## Estado de origem

Commit M40340 `b350b1e`, GitHub Actions 81/81 PASS. Os testes de
login e funções SQL originais já existem na suíte integral de
`backend/tests/test_rls_isolation_ci.py`. Não recriar suas tarefas nem
instalar outra autenticação. O M40350 complementa a prova M40340
dentro do **mesmo workflow e mesmo banco PostgreSQL descartável da CI**.

## Novo teste

No TestClient da instância FastAPI original (apenas processo de CI):

- Após cada leitura RLS com Admin A, Admin B, membro A e membro B,
  adquirir conexão pelo pool original e exigir que três configurações
  de sessão estejam vazias;
- Provocar erro HTTP 409 dentro de uma transação RLS, confirmando rollback
  e ausência de contaminação após o erro;
- Alternar identidades sintéticas A, B, membro, Master e A, exigindo
  contexto de pool limpo em cada etapa;
- Conservar as 60 comprovações positivas/negativas M40340 e sem
  dependency overrides; sem writes externos, pagamentos ou mensagens.

## Diagnóstico de serviço do telefone

Reutiliza o script existente `backend/scripts/frfinance_m40300_termux_readonly.sh`,
sem criar outro diagnóstico. Uma regressão estática impede que a
indisponibilidade simultânea de PostgreSQL/FastAPI seja confundida com
perda do banco. O diagnóstico já observa `pg_ctl status`, `pg_isready`
na porta 5433 e a resposta HTTP na 8000.

O estado `SERVICES_INACTIVE_OR_UNVERIFIED_NOT_DATABASE_LOSS` não permite
recriação, inicialização nem reinício. O operador deve conferir o mesmo
PGDATA e a identidade dos processos antes de ação separadamente aprovada.
Falha de resposta não prova corrupção ou perda do PostgreSQL.

## Escopo de integração, não lançamento

Só há **um projeto local**: Termux `$HOME/fr-finance`, branch
`atualizacao-ai-studio-9b46a63187`, PostgreSQL original
`frcaixinha_aistudio_dev` em `127.0.0.1:5433`.
O banco de teste do runner do GitHub é efêmero e não configura um segundo
banco ou diretório no celular. As migrações SQL110/111 já constam como
aplicadas localmente e **não serão reaplicadas**.

O M40350 NÃO comprova login com senha no mesmo banco das seis tabelas:
M40340 continua usando funções auxiliares de autenticação sintéticas na CI.
Não usar isso como certificação de produção.

PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF,
PRODUCTION=BLOCKED. PR #2 permanece Draft. Nenhum restart.
