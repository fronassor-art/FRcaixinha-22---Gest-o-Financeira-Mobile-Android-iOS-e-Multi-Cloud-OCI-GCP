# FR Finance M40925 — comando Ed25519 e autorização SQL de uso único (NO-GO)

## Contexto e limites do laboratório

O M40924 foi sincronizado no Termux nativo no commit \`ede3ad33\`, source-only, com CI dedicada PG18 2/2 e CI geral 7/7. Nenhuma migração ou escrita no PostgreSQL original. O M40924 havia impedido app SQL + Bearer Master de escrever sem uma aprovação de uso único, mas o emissor SQL da aprovação era um superuser sintético não integrado à assinatura M40923.

O M40925 combina, **somente no laboratório CI**, um gateway ASGI FastAPI sintético, os verificadores Ed25519 em memória M40923 e os wrappers SQL M40924 no PostgreSQL 18 efêmero \`fr_m39067_disposable_ci\` (127.0.0.1:55433). A chave privada Ed25519 e o registro da chave pública existem exclusivamente na memória Python do teste, nunca em tabelas SQL. Os endpoints ASGI fictícios são \`POST /master/saas-promotions/draft\` e \`POST /master/saas-promotions/transition\`. Não há listen TCP/HTTPS real, Android Keystore, onboarding confiável, IAM externo ou uso da aplicação instalada.

## Fluxo testado

1. Cliente fictício apresenta Bearer e assinatura Ed25519 do objeto canônico M40923: ator, tenant, token digest, ação, rota, revisão, campaign_id, corpo integral, nonce e vencimento curto.
2. Gateway Python verifica a assinatura, o contexto, a sessão recebida e bloqueia nonce usado na memória; os parâmetros SQL são extraídos de um corpo sem campos extras.
3. Com SQL login emissor dedicado, **distinto do login app**, insere somente o SHA-256 de uma autorização aleatória na tabela protegida M40924. Emissor pode \`INSERT\` em colunas restritas, não pode consultar ou alterar sessões, assumir a role app, ler auditoria nem executar funções de promoção.
4. O app SQL login chama somente \`m40924.gated_draft\` ou \`m40924.gated_transition\` com autorização nova, sessão e parâmetros; o wrapper confere sessão MASTER, ator, tenant, digest dos parâmetros, vigência, consumo único e transação/auditoria.

Os testes esperados incluem DRAFT/PUBLISH/CANCEL completos com Ed25519+SQL, assinatura errada, Bearer sem assinatura, alteração de preço, tenant e path, reprodução/replay, membro sem MASTER, revogação da sessão e seis pedidos concorrentes com um nonce assinado. Uma conexão direta com credencial app e token Master, sem autorização, continua negada no PostgreSQL sintético.

## Teste adversarial de contorno — NO-GO obrigatório

Um **emissor de aprovação SQL comprometido** pode inserir arbitrariamente um digest de autorização para qualquer Bearer Master conhecido sem possuir a chave Ed25519; se o atacante também controla o SQL login app e possui token Master válido, consegue consumir a autorização e chamar o wrapper. A CI demonstra esse contorno deliberadamente e o classifica como NO-GO.

O modelo **não** atesta um emissor independente resistente a roubo de credencial, não protege contra uso antecipado de aprovação roubada, não comprova TLS/device attestation/enrollment/keystore, não persiste nem distribui o controle de nonce da API, não tem proteção de log/telemetria e não remedia proprietário/superuser PostgreSQL. A existência de um protótipo FastAPI não significa rotas reais integradas ou serviço de produção. Os M40570 (GUC em outros caminhos) e M40730 (emissor legado) seguem NO-GO. As flags financeiras permanecem inalteradas.

**Não migrar este fixture nem alterar ACL no banco original sem nova autorização expressa e revisão independente.** PR #2 continua Draft.

MIGRATIONS=NONE; ORIGINAL_DB_CONNECTIONS=NONE; ORIGINAL_ACL_CHANGES=NONE; LOCAL_DB_WRITES=NONE; SERVICE_RESTARTS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
