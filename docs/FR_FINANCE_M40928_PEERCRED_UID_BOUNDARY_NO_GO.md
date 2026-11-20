# FR Finance M40928 — verificação SO_PEERCRED e UID guardião isolado (NO-GO)

## Origem

O operador confirmou o M40927 sincronizado no Termux nativo, SHA \`e36c0f5\`, CI geral 7/7 e prova PG18 2/2 PASS, sem migrações, escrita no banco original nem reinícios. M40927 validou a separação em dois processos e assinatura Ed25519 no guardião, mas ambos continuavam sob o **mesmo UID** e o socket Unix não autenticava o processo chamador.

## Experimento exclusivo em GitHub Actions

M40928 cria uma conta Linux efêmera \`frf_m40928_guardian\` no runner Ubuntu e executa um processo guardião com EUID distinto do gateway de teste. O processo recebe apenas DSN sintético do guardião e registro de chaves **públicas** por arquivo JSON \`0600\`, cujo dono é o UID guardião. Não há chaves privadas, DSN superuser, emissor nem app no ambiente ou argv do guardião. O diretório temporário é do guardião e o runner recria essas credenciais em cada execução.

O socket Unix usa \`SO_PEERCRED\` Linux para extrair PID/UID/GID reais da conexão. Somente o UID gateway esperado pode solicitar selos; uma chamada por \`nobody\` deve obter recusa. A fixture deixa o socket conectável por todos **de propósito**, exclusivamente para comprovar que \`SO_PEERCRED\` rejeita o UID errado; isso NÃO é uma recomendação de permissões para produção.

Além dessa nova fronteira, o experimento reutiliza as garantias M40927 no PostgreSQL 18 descartável: assinatura Ed25519, vínculo de tenant/sessão/ação/corpo, nonce único em memória, dupla custódia SQL, DRAFT/PUBLISH/CANCEL, revogação de Master, concorrência e 503 quando o guardião está indisponível. A PR #2 continua Draft, sem merge.

## Riscos obrigatórios (NO-GO)

Este modelo **não** oferece segurança de produção: todo atacante no **mesmo UID do gateway** continua podendo abrir o socket (sem \`SO_PEERSEC\` ou outro atestado de processo); a autorização opaca atravessa o socket e pode sofrer ataque de uso antecipado. Uma conta com privilégios root ou controle do host consegue contornar a separação. O orquestrador CI ainda conhece todas as credenciais sintéticas e pode executar \`sudo\`, e a criação do usuário Linux ocorre só no runner efêmero, nunca no Termux.

A CI também exige uma prova adversarial de que a captura das **três** credenciais SQL e do Bearer Master permite contornar Ed25519 mesmo com \`SO_PEERCRED\`, pois a assinatura não é obrigatória no banco. O socket é \`0666\` somente nesta fixture adversarial; produção demandaria ACL mais restrita, identidade de processo/serviço independente, proteção contra hijack/replay, configurações de SELinux/AppArmor, auditoria, rotação e proteção de segredo por Vault/KMS/HSM.

M40570 (GUC), M40730 (emissor legado), atestação do FastAPI real, segurança do Android físico, TLS e revisão de pagamentos permanecem NO-GO. Este pacote é código de **teste**, não migration nem integração em FastAPI real.

MIGRATIONS=NONE; ORIGINAL_DB_CONNECTIONS=NONE; ORIGINAL_ACL_CHANGES=NONE; LOCAL_DB_WRITES=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
