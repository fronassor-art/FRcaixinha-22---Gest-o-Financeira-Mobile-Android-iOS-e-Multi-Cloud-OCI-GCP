# FR Finance — M40730: emissor SQL segregado sem chave privada no banco (NO-GO)

## Escopo de laboratório

Experimentação **sintética** no GitHub Actions com PostgreSQL 18 descartável na porta 55442, FastAPI/ASGI sintético, chaves Ed25519 e sessões fictícias. **Não** altera rotas reais, infraestrutura, banco original, Android instalado, migrações, operações financeiras ou serviços em execução.

## Alteração de fronteira em relação ao M40720

M40720 validou uma assinatura Ed25519 gerada pelo cliente, mas ainda utilizava um HMAC compartilhado com chave armazenada no banco fictício M40700 para solicitar um ticket de leitura.

M40730 retira inteiramente a tabela de chave HMAC daquele fluxo experimental. A chave privada Ed25519 pertence exclusivamente ao **cliente fictício em memória**; o verificador HTTP guarda a chave pública (mapeamento digest+tenant) em memória, e verifica a requisição GET, caminho, digest SHA-256 de Bearer, tenant, nonce, expiração e escopo. **Nenhuma assinatura Ed25519 ou chave privada/pública é escrita ou enviada como parâmetro SQL.** O banco sintético armazena somente digest da sessão, tenant, nonce, tickets descartáveis e dados sintéticos de membro.

Após a verificação criptográfica, o gateway usa uma credencial SQL **distinta** do autenticador e do financeiro: \`m40730_signer_login\` ativa somente \`m40730_signer\`, que pode chamar \`m40730.issue_if_unused\`. Esta função SECURITY DEFINER consome o nonce de forma atômica e chama a função sintética antiga \`m40680_issue\` que revalida sessão e vínculo. As funções legadas de emissão por digest são inacessíveis diretamente aos papéis de autenticação, financeiro e emissor. O financeiro recebe um ticket de uso único e revalida a sessão no consumo.

## O que o experimento deverá comprovar

- Chaves de assinatura e HMAC ausentes do esquema novo e dos parâmetros SQL: chave privada fictícia fora da fronteira PostgreSQL.
- Papéis de emissão, autenticação e financeiro segregados e conferidos por logins de menor privilégio e catálogo SQL.
- Bearer isolado ou prova Ed25519 incorreta/alterada negada; cruzamento de tenants negado; POST negado.
- Uma assinatura completa reutilizada ou concorrente perde a autorização depois da primeira emissão; seis chamadas concorrentes => uma autorização e cinco recusas.
- Revogação de sessão após emissão da assinatura impede acesso.
- **Falha estrutural NO-GO:** a credencial SQL do próprio emissor, se comprometida, permite emitir tickets para sessões conhecidas **sem passar pelo verificador Ed25519 HTTP**. Isso comprova que remover a chave privada do banco não impede um papel SQL de emissão comprometido.
- **Falha de confiança no banco NO-GO:** proprietário privilegiado do banco pode restaurar permissões, executar funções como proprietário ou manipular registros. A separação por ACL não elimina essa autoridade.

## Limites que não podem ser chamados de remediados

Não existe secret manager/Vault/KMS, emissor em serviço independente, custódia de credenciais SQL em hardware ou isolamento operacional verificável. O protótipo usa duas funções SECURITY DEFINER e um SQL login com autoridade de emissão; comprometer esse login equivale a conseguir tickets. O HTTP prova conhecimento da chave somente no gateway fictício, sem enrollment confiável da chave pública, Android Keystore atestado, TLS real, attestation, logs higienizados, rotação/recuperação de dispositivo nem prova de canal. **Bearer e assinatura Ed25519 capturados juntos antes da primeira utilização ainda podem ser usados antecipadamente.**

O código da aplicação real continua vulnerável à falsificação de GUC em determinadas rotas de segurança, e o processo FastAPI no aparelho não está atestado. O uso de PostgreSQL 18 descartável NÃO atesta o banco do usuário nem substitui auditoria de RLS/credenciais/observabilidade.

**Não copiar este fixture para migrações reais.** A PR #2 deve permanecer draft e sem merge até uma aprovação futura explícita.

## Marcadores

- M40730_NO_SIGNING_KEYS_OR_PROOFS_STORED_IN_SQL=PASS_SYNTHETIC
- M40730_AUTH_FINANCIAL_SIGNER_SQL_ROLE_SPLIT=PASS
- M40730_CLIENT_POP_AND_TENANT_BOUND_HTTP_GATE=PASS
- M40730_CONCURRENT_NONCE_SINGLE_ISSUE=PASS
- M40730_SESSION_REVOCATION_AFTER_POP=PASS
- M40730_PREUSE_CAPTURED_HTTP_REQUEST=CONFIRMED_NO_GO
- M40730_COMPROMISED_SIGNER_SQL_LOGIN_BYPASSES_POP=CONFIRMED_NO_GO
- M40730_PRIVILEGED_DB_OWNER_CAN_REGRANT_SIGNER=CONFIRMED_NO_GO
- M40730_SIGNER_LOGIN_AND_TICKET_LOG_LEAKAGE=NOT_REMEDIATED
- M40730_TLS_DEVICE_KEY_ENROLLMENT_ATTESTATION=NOT_ATTESTED
- M40730_ORIGINAL_GUC_SPOOF=NOT_REMEDIATED
- M40730_REAL_FASTAPI_SQL_APP=NOT_MODIFIED
- M40730_ORIGINAL_PG_5433=NOT_ACCESSED
- M40730_LOCAL_DB_WRITES=NONE; M40730_MIGRATIONS=NONE; M40730_SERVICE_RESTARTS=NONE
- PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED

Um teste verde apenas significa que os casos sintéticos **passaram**, inclusive os casos NO-GO deliberados. Sincronizar no Termux somente por script M40600 source-only e commit fixado após CI aprovada.
