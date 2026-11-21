# AI Studio M2701–M2800 — conectores reais OCI Secret e OAuth Mercado Pago

## Objetivo de engenharia

Construir **código de integração executável em servidor**, preparado para ser ativado somente quando houver conta Oracle provisionada, aplicação Mercado Pago registrada e consentimento de cada vendedor. **Não habilita dinheiro real nem cria servidores**.

## Componentes de servidor entregues

- `backend/app/oci_secret_bridge.py`: adaptador OCI SDK real para `SecretsClient.get_secret_bundle(secret_id, stage="CURRENT")`, com signer de *instance principal* (sem arquivo de API key ou credenciais de usuário no servidor), decodificação de segredo BASE64, limite de tamanho e erros redigidos. SDK OCI é dependência **opcional só do servidor**: não é importado ao iniciar FastAPI nem instalado no APK. A credencial do servidor deve vir de referência de segredo associada ao tenant **no banco com RLS**, nunca de OCID enviado por cliente.
- `backend/app/mp_connect_http_runtime.py`: cliente HTTP real para **POST https://api.mercadopago.com/oauth/token**, tanto autorização `authorization_code` + PKCE como renovação `refresh_token`, com `test_token=true`, URL fixa, timeout, sem redirects, TLS padrão, `trust_env=False`, JSON estrito, recusa `live_mode=true`, recusa seller divergente e ausência de consentimento registrado. Nenhuma chamada acontece automaticamente; para abrir rede é necessário configurar o servidor e autorização explícita.
- Token de retorno fica somente em memória na operação demonstrada; campos sensíveis têm representação redigida e nunca aparecem no diagnóstico HTTP. **Ainda não foi implementada a escrita/rotação cifrada em OCI Vault após o OAuth**.
- Testes em `backend/tests/test_m2800_oci_mp_connectors_ci.py`: falsos clientes OCI e `httpx.MockTransport`; a CI não fala com Oracle nem Mercado Pago.
- Rota `/api/health/features/m2800`: somente diagnóstico de presença de código, flags de conexão permanecem `false`.

## Fluxo definitivo que será ligado depois

1. O Administrador TENANT_ADMIN dá consentimento para sua conta seller e inicia OAuth com `state` persistido, hash, `code_verifier` guardado com criptografia e expiração/consumo atômico em banco seguro.
2. O servidor na OCI adquire o `client_secret` da aplicação no OCI Secret Management com instance principal. **Nunca no frontend ou APK**.
3. Callback HTTPS protegido conclui OAuth, confere `state` e titularidade do tenant, faz POST OAuth e valida seller id/escopo e live_mode.
4. Armazenamento cifrado por tenant de access/refresh tokens, versionamento, rotação e revogação; testes de recuperação e IAM restrito.
5. Notificação oficial `x-signature` chega ao servidor, cuja assinatura e seller são verificados; inbox PostgreSQL durável com idempotência, seguida de GET autenticado no seller correto.
6. Conferência independente com extrato e ledger, em transação atômica, antes de **qualquer** baixa/fechamento financeiro. Nunca apenas um webhook ou status aprovado.

## Bloqueios reais que permanecem

A PR #2 deve permanecer Draft sem merge. A [Issue #3](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/issues/3) acompanha a execução futura. OCI ainda não provisionada; aplicação Mercado Pago e endpoints HTTPS ainda não criados/registrados; segredos e tokens não foram inseridos; não existem migrações novas no Termux nem chamadas reais. **OAuth transacional só deve ser conectado a uma rota depois que houver prova durável de consumo do state e proteção da sessão; o booleano `consumed_by_durable_store` sozinho não é evidência.**

### Fontes oficiais

- https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation
- https://www.mercadopago.com.br/developers/pt/reference/authentication/oauth/_oauth_token/post
- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/secrets/client/oci.secrets.SecretsClient.html
- https://docs.oracle.com/en-us/iaas/Content/Identity/callresources/callingservicesfrominstances.htm
