# M24100 — porta de gravação criptografada OAuth (sandbox)

**FR Finance AI Studio somente.** Nenhuma implantação na OCI, nenhum token real e nenhuma aplicação de SQL no Termux 5433.

## Código

- \`backend/app/mp_oauth_staging_credential_store.py\` introduz \`StagingProtectedCredentialStore\`, uma implementação preparatória do contrato \`ProtectedCredentialStore\` usado pelo M23500.
- Usa \`StagingSellerCASRegistry.consent_generation(tenant, actor, seller)\` do M23900. Se a geração for inexistente, inválida, antiga, revogada ou o worker não estiver autenticado, a operação é bloqueada.
- Exige \`EncryptedRevisionWriter\` **injetado**, um protocolo sem implementação OCI. É responsabilidade futura do escritor cifrar credenciais, manter metadados duráveis e provar a identidade/escopo do tenant. NENHUM token é gravado no PostgreSQL; o contrato retorna somente referência protegida opaca, revisão aleatória e geração.
- \`StagingOAuthTokenSink\` ainda registra a revisão como PENDING por meio do worker M23800 antes da ativação CAS SQL M23600, protegido pela compensação fail-closed M24000.
- Não conecta à Oracle nem ao Mercado Pago, não cria endpoints e inicia **disabled by default**.
- A referência permanece no armazenamento, sem tentativa de exclusão automática, quando o escritor ou PostgreSQL fornecem confirmação ambígua; requer fila durável de reconciliação antes de produção. A implementação de teste usa armazenamento simulado e não oferece criptografia real.

## Testes CI

Suíte \`test_m24100_oauth_protected_store_port_ci.py\`: caminho sandbox completo, consentimento ausente, tenant cruzado, token live recusado, falha de escritor, referência inválida, perda de ACK após ativação, rejeição CAS com limpeza condicionada, token não exposto a SQL, registro forjado, falha de descarte e bloqueio por padrão.

## Bloqueios ainda verdadeiros

O pacote não elimina sozinho os bloqueios financeiros 9.2–9.9 do contrato: ainda faltam integração OCI Vault/KMS real (com análise de custos), emissor de consentimento autenticado, política durável de limpeza de órfãos, TLS público, callbacks/webhooks testados, conta MP por caixinha, autorização Money Out, conciliação bancária independente e homologação E2E AT-01 a AT-50. O Pix real permanece desligado. A PR #2 fica DRAFT e não será feito merge.

O catálogo histórico do M24000 conserva os 50 bloqueios e 34 itens sem verificação por **falta de evidência integral**, sem promoção automática de cláusula.
