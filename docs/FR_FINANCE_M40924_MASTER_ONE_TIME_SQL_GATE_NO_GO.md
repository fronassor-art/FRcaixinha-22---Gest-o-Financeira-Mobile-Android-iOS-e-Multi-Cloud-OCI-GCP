# FR Finance M40924 — autorização SQL de uso único para escrita Master (NO-GO)

## Origem e proposta

M40923 foi sincronizado no Termux em \`e4f98ce\`, sem mudanças de schema no intervalo, escritas, migrations ou reinícios. A prova M40923 demonstrou a falha de controle: um SQL app login vazado **mais um Bearer Master válido** chama diretamente as funções M40920 sem passar por Ed25519 ou autorização de comando.

M40924 adiciona, **somente em PostgreSQL 18 descartável na CI**, um bloqueio experimental na borda SQL: funções legadas M40920 perdem o EXECUTE da role app; um wrapper SECURITY DEFINER com dono NOLOGIN isolado exige uma autorização opaca de uso único para cada DRAFT, PUBLISH ou CANCEL. O PostgreSQL armazena apenas o SHA-256 da autorização, o digest de sessão, ator, tenant, ação, campanha, revisão, fingerprint dos parâmetros reais, expiração e data de consumo. A aplicação não possui SELECT/INSERT/UPDATE/DELETE nessa tabela.

O wrapper confere sessão MASTER, allowlist, tenant, parâmetros, expiração e consumo não repetido, consome a autorização numa UPDATE atômica e invoca a função M40920 com as regras append-only e auditoria já existentes. A transação PostgreSQL garante que falha na auditoria desfaça também o consumo. No ensaio concorrente seis chamadas com a mesma autorização devem produzir exatamente uma escrita.

O ensaio negativo tenta diretamente M40920, emite SQL sem autorização, falsifica GUC, reutiliza autorização, altera parâmetros e usa sessão revogada. O emissor de aprovações é o **superuser fictício do banco descartável**, apenas para teste. Não é uma identidade ou serviço externo pronto.

## Limites explícitos / NÃO USAR EM PRODUÇÃO

**NO-GO:** O M40924 NÃO conecta a aprovação SQL ao verificador Ed25519 M40923, não implementa emissor externo com identidade própria, prova de não exportação de credencial, autenticação de dispositivo, TLS, registro distribuído de nonces ou auditoria externa. A posse da autorização opaca **antes do primeiro uso** continua permitindo sua utilização antecipada por alguém que tenha também a sessão Master e a credencial SQL app. Uma aprovação emitida por superuser/owner comprometido também pode ser forjada. O SQL app role consegue executar o wrapper se possuir autorização roubada — isso não atesta um fluxo HTTP seguro.

M40570 permanece NO-GO por outros caminhos SQL GUC. M40730 permanece NO-GO por comprometimento do emissor de tickets legado. O código FastAPI real continua sem migração para esse wrapper. O ambiente original, o FR Caixinha 2.2 e o processo do Android não são consultados. A PR #2 fica Draft e não deve sofrer merge.

São necessários engenharia de autorização entre serviços, fonte auditável de aprovações, revisão adversarial, plano de migração reversível, backup e atestação do FastAPI, além de homologação física e critérios jurídicos/operacionais antes de qualquer produção.

**MIGRATIONS=NONE; ORIGINAL_ACL_CHANGES=NONE; ORIGINAL_DB_CONNECTIONS=NONE; LOCAL_DB_WRITES=NONE; SERVICE_RESTARTS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.**
