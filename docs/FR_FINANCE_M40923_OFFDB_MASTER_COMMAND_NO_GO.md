# FR Finance M40923 — assinatura independente de comando Master e emissor SQL comprometido (NO-GO)

**Checkpoint operacional:** o operador confirmou M40922 no Termux nativo em \`0c346dd\`, \`NO_SCHEMA_DELTA\`, sem conexões ou escrita no banco original, migrations ou reinícios. O M40922 possui prova CI PG18 e CI geral 7/7 PASS. PR #2 continua Draft.

## Nova fronteira experimental

O pacote ensaia aprovação criptográfica externa ao SQL para comandos Master de campanhas SaaS, sem conexão a FastAPI real: uma chave Ed25519 privada e o registro da chave pública ficam exclusivamente na memória do processo Python CI. A assinatura cobre método HTTP, rota, usuário, tenant, digest do token, ação, campanha, revisão esperada, digest canônico do corpo, nonce, validade máxima de 20 segundos e versão do protocolo. Um registro de nonce em **memória** nega reutilização na mesma execução. Nenhuma assinatura/chave privada é inserida no PostgreSQL.

No PostgreSQL 18 descartável da CI, o ensaio reusa M40900/M40910/M40920/M40921/M40922 e cria um login fictício \`m40923_issuer_login\` sem privilégios Master/SaaS. Mesmo com um Bearer Master válido conhecido e GUC Master forjado, o emissor SQL não consegue ler sessões, emitir sessões, assumir role app nem chamar funções de escrita. Isso é isolamento **apenas desse papel sintético**, não atestação de um emissor real.

## Prova adversarial obrigatória de NO-GO

Depois de um comando assinado aprovado fora de SQL, a conexão legítima app role executa um DRAFT pelo broker. Em seguida, uma segunda chamada SQL com o mesmo token Master, **sem nenhuma assinatura**, também é aceita pelo broker original. O teste exige esse resultado negativo e registra \`M40923_STOLEN_APP_SQL_PLUS_MASTER_BEARER=NO_GO_BYPASS_CONFIRMED\`. Portanto a assinatura externa é uma defesa de aplicação desconectada e NÃO é um controle obrigatório dentro do banco. Um login SQL app comprometido com Bearer válido, um owner ou superuser PostgreSQL comprometido, ou uma conexão direta mal configurada ainda podem contornar o gateway.

Também permanecem: ataque de uso antecipado de assinatura capturada antes do cliente, registro de nonce não durável ou distribuído, dispositivo não atestado, ausência de segundo fator real, ausência de issuer/vault/KMS e supervisão de credenciais, falta de integração às rotas HTTP reais, perda de sessões, homologação física Android, OCI/TLS/PSP e revisão jurídica. M40570 (outros caminhos GUC) e M40730 (emissor SQL comprometido no desenho legado) seguem NO-GO.

**NÃO** usar este teste como migration ou garantia de produção. Para uma futura arquitetura, todo caminho de escrita precisa exigir prova não forjável e não contornável por credenciais SQL expostas, além de dupla verificação de identidade e rastreabilidade externa.

\`MIGRATIONS=NONE\`; \`ORIGINAL_ACL_CHANGES=NONE\`; \`ORIGINAL_DB_CONNECTIONS=NONE\`; \`LOCAL_DB_WRITES=NONE\`; \`SERVICE_RESTARTS=NONE\`; \`PIX_REAL=OFF\`; \`PAGAMENTOS_REAIS=OFF\`; \`ATIVACAO_REAL=OFF\`; \`PRODUCTION=BLOCKED\`.
