# M40390 — Testes negativos Android e FastAPI (FR Finance)

Base: M40380. Este pacote complementa os 8/8 cenarios funcionais no APK.

- Frontend: 44 casos offline com transporte injetado (nenhuma rede):
  role Master/admin/membro, outra caixinha, URL maliciosa, 401/403/404/429/500/503,
  sesao obsoleta, perda de rede, sem repeticao automatica de POST,
  sinalizacao de canais externos e Pix reais sempre desligados.
- FastAPI: 20 decisoes de autorizacao negativas com login original e
  usuarios sinteticos, mais senha incorreta e bearer invalido.
- O backend executa somente no PostgreSQL18 **descartavel de CI**
  frfinance_ci_credit:5432, usando o gate CI_M40380_DISPOSABLE.
  A suite reaproveita as migracoes 001-027 e SQL110/111 ja existentes
  nesse banco efemero. A execucao confirma seis tabelas de credito intactas
  e outbox bloqueada. Nenhum dispatch e permitido.

Verificacoes manuais restantes no celular:
1. senha incorreta deve negar a sessao;
2. logout impede reentrada na tela protegida;
3. navegacao nao permite escalada de perfil;
4. Campanhas/Oportunidades exibem bloqueio sandbox;
5. rede indisponivel nao deve indicar perda do PostgreSQL.

**Nao desligar nem reiniciar FastAPI/PG para simular falha de rede** e nao
rodar este teste backend contra Termux. O M40190 passou em leitura,
mas nao atesta PID, bytecode ou Git SHA em memoria.

PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF;
FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO; PRODUCTION=BLOCKED.
PR #2 Draft; sem merge, migrações locais ou restart.
