# FR Finance M40720 — Ed25519 assinado pelo cliente + HTTP sintético / PostgreSQL descartável (NO-GO)

**Escopo:** somente protótipo isolado em GitHub Actions com PostgreSQL 18 descartável (CI), API ASGI sintética e credenciais fictícias. Não é autenticação implementada na aplicação real e não autoriza migrations, deploy, restart ou operações financeiras.

## Objetivo e fronteira de confiança

M40710 comprovou que uma assinatura HMAC emitida pelo backend e capturada **antes do uso** pode ser consumida por outro detentor do papel de autenticação SQL, mesmo com nonce. Além disso, o proprietário privilegiado do banco do fixture pode ler a chave HMAC armazenada na tabela.

M40720 acrescenta no fluxo **HTTP sintético** uma prova de posse Ed25519: o cliente fictício assina um texto canônico com domínio e versão FRF-M40720, método GET, path exato, digest SHA-256 do Bearer recebido pela API, tenant, nonce UUID, instante de expiração e escopo de leitura fixo. A chave **privada** Ed25519 permanece somente na instância do cliente fictício em memória, fora dos parâmetros SQL e registros do banco. O verificador usa uma tabela de chaves **públicas em memória** artificialmente vinculadas a digest+tenant, não uma etapa segura de enrollment. A chave pública não precisa permanecer secreta.

A API sintética valida assinatura, validade temporal e identidade de caminho **antes** de obter credenciais SQL independentes de autenticação e leitura. Após a verificação, o backend ainda emite um HMAC de escopo fixo para o **SQL antigo M40700** que gera ticket de leitura de uso único. A operação financeira permanece contida na função SQL sintética M40680, com checagem de sessão/vínculo e tenant. **O HMAC do fixture continua armazenado no banco protegido e extraível por papel privilegiado**. Portanto, a proteção do emissor independente do PostgreSQL ainda não foi alcançada.

## Matriz adversarial

- Bearer isolado, digest isolado, ausência de Ed25519, assinatura de outra chave, nonce/aditivo de expiração alterado, contexto cross-tenant, timeout ou pedido POST não autorizam a leitura.
- Assinatura correta com Bearer correspondente consegue ler somente dados da sessão de membro correspondente; membro B não vê membro A.
- GUC ou cabeçalhos supostamente administrativos não devem conceder privilégio.
- Reenvio simultâneo da mesma requisição assinada gera uma única leitura autorizada e cinco recusas, usando a proteção do nonce persistido no PostgreSQL descartável.
- A revogação da sessão após a assinatura e antes da chamada HTTP impede autorização.
- **Caso negativo deliberado:** um adversário com Bearer **mais** cabeçalhos Ed25519 completos capturados antes do primeiro uso pode enviar o pedido primeiro. Isso não demonstra proteção contra roubo do primeiro pedido nem vínculo físico ao dispositivo/canal.

## Bloqueios ainda existentes

A prova Ed25519 não confirma chave protegida por hardware, autenticação de matrícula/enrollment da chave pública, rotação, revogação e substituição de dispositivos, armazenamento seguro no Android, attestation, sessões multitenant concorrentes, controle de logs, anti-MITM, TLS, gerenciamento distribuído do nonce, limite de tentativas, auditoria de funções de escrita, ou segurança da API original. **O HMAC do lado do servidor continua no banco** e sua comparação SQL não é certificada em tempo constante; SQL logs e telemetria ainda podem reter digest, HMAC ou ticket. A vulnerabilidade GUC spoof da aplicação atual permanece **NOT_REMEDIATED**.

Nenhuma rota real FastAPI, frontend, banco original, migração, serviço, APK instalado ou pipeline de pagamentos foi alterado. O protótipo não acessa banco :5433; o serviço descartável da CI usa :55441 e banco de nome exclusivo. Chaves/tokens são sintéticos e não são impressos.

## Marcadores NO-GO

- M40720_VALID_ED25519_CLIENT_BOUND_HTTP_TO_SQL=PASS — somente sintético
- M40720_BEARER_ONLY_TAMPERED_PROOF_AND_CROSS_TENANT_DENIED=PASS
- M40720_SQL_AUTH_ROLE_WITHOUT_SIGNER_CANNOT_MINT=PASS
- M40720_STOLEN_BEARER_PLUS_PREUSE_POP_PROOF=CONFIRMED_NO_GO
- M40720_CONCURRENT_SIGNED_REQUEST_ONE_TIME=PASS
- M40720_ED25519_PRIVATE_KEY_SENT_TO_SQL=NONE
- M40720_SQL_HMAC_KEY_EXTRACTABLE_BY_DB_OWNER=CONFIRMED_NO_GO
- M40720_IN_MEMORY_PUBLIC_KEY_REGISTRY=NOT_PRODUCTION
- M40720_REQUEST_CAPTURE_REPLAY_BEFORE_USE=NOT_REMEDIATED
- M40720_REAL_FASTAPI_AND_PROD_ROUTES=NOT_MODIFIED
- M40720_EXISTING_GUC_SPOOF=NOT_REMEDIATED
- M40720_ORIGINAL_PG_5433=NOT_ACCESSED
- M40720_LOCAL_DB_WRITES=NONE; M40720_MIGRATIONS=NONE
- M40720_SERVICE_RESTARTS=NONE
- PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED

**A CI verde só aprova o comportamento adversarial do fixture, nunca produção.** PR #2 permanece draft; sincronizar Termux apenas código-fonte após conferência do commit e hashes.
