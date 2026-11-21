# FR Finance — M40927: guardião em processo separado via socket Unix (NO-GO)

## Checkpoint e propósito

O M40926 foi confirmado em Termux nativo no commit \`163e7ac\`, com CI geral 7/7 PASS, teste específico PostgreSQL 18 2/2 PASS, sem migrações, escritas ou reinícios no banco original. O M40926 introduziu um selo do guardian obrigatório antes de consumir a autorização Master, mas o gateway de teste ainda tinha as três credenciais SQL no mesmo processo. Esse ponto é vulnerável se o processo for comprometido.

O M40927 testa uma **separação real de processos, porém apenas dentro de um runner CI**: um worker Python filho executa um servidor de socket Unix efêmero em diretório temporário com permissão 0600. O subprocesso recebe um ambiente sanitizado contendo somente seu DSN SQL sintético de guardião, flags OFF e um registro de **chaves públicas** Ed25519. Ele não recebe o DSN PostgreSQL superuser, do emissor ou do app, nem chaves privadas. O gateway ASGI FastAPI sintético aceita apenas issuer/app DSNs e o caminho do socket. Nunca recebe guardian DSN ou lista de chaves públicas como argumento.

## Fluxo e verificações

O cliente sintético fornece token Bearer e assinatura Ed25519 do contexto M40923. O gateway verifica digest de Bearer e integridade do payload e envia o objeto de autorização ao worker; o worker valida novamente o corpo, papel, tenant, comando, expiração curta, nonce único em memória e assinatura Ed25519 independentemente. Sem a assinatura válida, ele não cria o selo SQL. Com assinatura válida, o próprio worker gera uma autorização aleatória (apenas o SHA-256 é persistido) e insere o selo na tabela m40926 sob seu login isolado. Em seguida entrega a capacidade opaca pelo socket ao gateway, que insere a autorização correspondente via login emissor e executa o wrapper SQL Master com login app. A verificação de sessão MASTER e a atomicidade/auditoria são mantidas no PostgreSQL 18 descartável.

Testes: DRAFT → PUBLISH → CANCEL; assinatura inválida, escopo/tenant alterado, membro sem MASTER, replay, concorrência de seis requisições para um nonce, sessão revogada e ausência do worker produzindo HTTP 503 sem caminho alternativo. Uma credencial SQL emissor roubada junto com SQL app e Master Bearer, sem assinatura Ed25519, não consegue gerar um selo pelo worker e não consegue escrever pelo wrapper.

## O que este ensaio NÃO garante

**NO-GO.** O orquestrador CI usa superuser sintético para montar e verificar a fixture, portanto a separação do worker não prova isolamento da aplicação real. Worker e gateway rodam no **mesmo UID** e no mesmo host; um adversário com acesso à conta/host pode tentar acesso ao socket Unix, substituição do processo, roubo do DSN no ambiente de processo ou manipulação da fixture. O socket não faz autenticação via SO_PEERCRED e não implementa mTLS; a autorização opaca cruza o socket até o gateway, sujeita a uso antecipado se capturada.

A CI demonstra deliberadamente: roubo dos **três** logins SQL (emissor, app, guardião), com Master Bearer válido, ainda permite emitir ambos os registros e contornar a assinatura. Um pedido assinado capturado antes de sua execução também pode competir pelo nonce. O registro de nonce é volátil, não distribuído; sem enrollment seguro, Android Keystore atestado, Vault/KMS/HSM, segregação de usuário/host/serviço, auditoria externa ou defesa contra owner/superuser PostgreSQL. A disponibilidade do worker único é um risco e a indisponibilidade nega acesso.

A implementação de FastAPI aqui é apenas um **gateway ASGI sintético**, não modifica rotas FastAPI reais ou o aplicativo Android. O M40570 (GUC em outros caminhos) e o M40730 (emissor legado) permanecem NO-GO, assim como a atestação da execução FastAPI, homologação Android física e aprovação operacional/jurídica. **A produção segue bloqueada.** PR #2 Draft, nenhum merge.

MIGRATIONS=NONE; ORIGINAL_DB_CONNECTIONS=NONE; ORIGINAL_ACL_CHANGES=NONE; LOCAL_DB_WRITES=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
