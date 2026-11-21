# FR Finance M40830 — proteção adicional de leitura cifrada fora do SQL (PROTÓTIPO NO-GO)

**Base:** M40821 `198aa39`, sincronizado pelo operador em Termux sem delta SQL, DB writes ou reinícios. O processo original FastAPI segue `RUNTIME_OWNER=NOT_ATTESTED`.

## Problema em aberto

M40570 demonstrou que quem já consegue executar SQL arbitrário como role app pode falsificar `app.current_user_id`, `app.current_role` e `app.current_tenant_id` (GUC). M40730 demonstrou que quem captura o SQL login do emissor consegue gerar tickets sem prova Ed25519, e que DB owner privilegiado supera ACLs. A solução **não pode** consistir apenas em mais uma declaração de role ou booleano na API. Uma migração precipitada da base original não corrigiria todas as rotas nem a custódia de chaves.

## Experimento M40830

Este módulo totalmente **desconectado das rotas reais** usa AES-256-GCM para proteger, em memória, um valor monetário fictício de membro. A chave não é persistida no PostgreSQL nem é enviada ao SQL. O AAD autenticado liga cada ciphertext a tenant, membro, registro, revisão e domínio/versão; adulterar metadata/ciphertext impede decifração. A aplicação experimental exige uma sessão de membro com formato verificado e identidade coerente antes de usar a chave. Uma credencial SQL com GUC falso, isoladamente, não consegue decifrar o conteúdo sintético. O experimento não possui emissor de ticket SQL e não usa a login `m40730_signer_login`.

## Riscos observáveis deliberadamente NÃO eliminados

1. **Captura da chave AES:** quem rouba a chave de leitura consegue decifrar. Nenhum Vault/KMS/HSM/TEE nem atestação de código foi implementado.
2. **Replay de ciphertext anterior:** AAD com revisão impede troca entre revisões, mas não compara a versão com autoridade confiável; uma revisão antiga íntegra ainda é decifrável. Necessário contador persistido e protegido, revogação, rotação e auditoria.
3. **Sessão Python falsificada:** `require_verified_rls_session` valida forma de campos, não sua origem criptográfica; só um runtime confiável ligado ao auth real pode usar esse controle.
4. **Dados legados:** o PostgreSQL original **continua com tabelas plaintext existentes** e políticas GUC; nenhuma rota foi conectada, migrada ou bloqueada neste pacote. Portanto **M40570 e M40730 continuam NO-GO** para o produto real.
5. **DBA e metadados:** cifra não impede exclusão, alteração de índices, vazamento de metadados, análise de tráfego, DoS ou bypass por endpoints não revisados.

## Próximos requisitos antes de qualquer migração real

Mapeamento de todas as leituras e escritas financeiras; decisão formal de autoridade de chaves fora do DB, ciclo de vida e recuperação; migração transacional com dual-read/fence e rollback ensaiados; revogação e versionamento atômico protegido; validação em OCI staging isolado com chaves reais gerenciadas, MFA, pen-test, prova das credenciais, rede, logs, latência, custo e testes físicos. Sem essas evidências, **não existe SQL de migração aplicável** originado por este protótipo.

CI somente offline, sem SQL/DB/serviços/rede/Termux/Android. PR #2 Draft; main preservada. `MIGRATIONS=NONE`; `DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
