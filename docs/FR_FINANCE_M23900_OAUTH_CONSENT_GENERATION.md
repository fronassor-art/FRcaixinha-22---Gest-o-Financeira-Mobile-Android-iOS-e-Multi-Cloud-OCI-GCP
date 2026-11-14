# FR Finance AI Studio — M23900 geração confiável de consentimento OAuth

Este pacote atende a pendência identificada no M23801: consultar a geração do consentimento antes de criar uma revisão protegida PENDING. **Não autentica o administrador por si só** e não torna a integração operacional.

## Banco de staging (somente CI descartável)

- Migração 047: função `public.mp_staging_oauth_generation(tenant,actor,seller)`, apenas no banco `frcaixinha_staging`, com flag DBA e worker técnico `frcaixinha_mp_oauth_worker`.
- A função usa `SECURITY DEFINER` com caminho de busca restrito, confere a associação ativa `TENANT_ADMIN`, e só retorna a geração quando o consentimento não está revogado. Caso contrário retorna NULL. Nenhum acesso direto às tabelas é concedido ao worker.
- Teste descartável 043: tenant A, tenant B, ator trocado, seller cruzado e ausência de leitura direta. Executa antes da revogação sintética; a migração 046 continua validando transacionalmente geração e revogação ao ativar.

## Backend

`StagingSellerCASRegistry.consent_generation()` consulta somente a função versionada, por conexão PostgreSQL 18 injetada, com banco e usuário de serviço exatos e **porta 5433 proibida**. Sem conexão pública, sem credenciais e sem dados no APK. O método retorna apenas inteiro PostgreSQL bigint válido ou NULL; erros não expõem segredos.

A leitura inicial **não** substitui `mp_staging_oauth_stage` nem `mp_staging_oauth_activate`. Ambas precisam conferir geração, consentimento e revogação em suas transações. Um contador obtido antes pode ficar obsoleto imediatamente.

## Limites

O `ProtectedCredentialStore` concreto ainda não está disponível; a escrita criptografada no OCI Vault/KMS, a confirmação da conta Mercado Pago, os custos e a reconciliação de operações ambíguas seguem pendentes. A integração permanece desligada, sem webhook público, hospedagem Oracle ou movimentação Pix real. Nenhuma migração será executada no Termux 5433. A PR #2 continua em rascunho.
