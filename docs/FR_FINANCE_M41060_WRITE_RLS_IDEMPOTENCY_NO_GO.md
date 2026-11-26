# FR Finance M41060 — RLS de escrita e idempotência (NO-GO)

Data-base: continuação do M41050, HEAD de origem `2fb90255bdbcd5f5c669219a55d5e0840146419c`. Evidência pretendida exclusivamente em PostgreSQL 18 descartável do GitHub Actions.

## Requisitos e prova

Este pacote amplia a evidência técnica dos CP26-0061 e CP26-0062 e mantém os IDs e as sete etapas de cada item da matriz 330/2.310. Não atualiza estado de aceite nem declara requisito concluído.

O fixture assina o escopo junto ao digest da sessão e ao tenant, registra o escopo pelo hash do ticket de uso único e o carrega até a capability curta consumida pelo papel SQL de aplicação. A tabela sintética usa FORCE ROW LEVEL SECURITY:

- leitura exige `READ_ENTRIES` e limita Membro ao próprio registro e Admin ao tenant;
- inserção exige `WRITE_TEST_ENTRY`, Admin ativo no tenant da linha e um Membro ativo daquele mesmo tenant;
- uma capability de leitura não escreve; uma capability de escrita não lê;
- escopo não listado, papel Membro, GUCs antigos falsificados e tenant cruzado são negados;
- o papel da aplicação recebe somente SELECT e INSERT. UPDATE e DELETE não têm grant nem policy;
- uma chave única por tenant impede duplicidade. Seis conexões concorrentes submetem a mesma chave e a verificação exige uma linha.

O código tocado é apenas fixture/teste sintético. O workflow exige o serviço PostgreSQL 18 efêmero, portas e banco próprios de CI, identidade de runner isolada e flags reais OFF. A suíte inclui os testes offline de M40700 e M41050. Não há rota FastAPI, tela de convite ou autorização de pagamento conectada ao fixture.

## Limites e decisões pendentes

M40710 ainda demonstra risco de extração da chave HMAC pelo owner/superuser e corrida de assinatura capturada antes do primeiro consumo. A capability permanece bearer dentro da sessão SQL. M40730 e a custódia independente do emissor/guarda continuam bloqueados. Master não recebe este escopo sintético. O teste não comprova staging, runtime, processo em memória, TLS, cofre de chaves, provedor, Android ou revisão independente.

Esta prova de CI não valida nem altera o PostgreSQL autoritativo, ACLs, roles, migrations, dados, ciclos, processos ou configurações do app. Não altera a matriz, não substitui gate, aceite jurídico ou evidência externa, e não fecha os itens P0 da issue #5.

M41060_RUNTIME=NOT_INTEGRATED; M41060_ORIGINAL_DATABASE=NOT_ACCESSED; M41060_MIGRATIONS=NONE; M41060_LOCAL_DB_WRITES=NONE; M41060_SERVICE_RESTARTS=NONE. PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED. M40840 permanece NO-GO e M40930 permanece HTTP 503.
