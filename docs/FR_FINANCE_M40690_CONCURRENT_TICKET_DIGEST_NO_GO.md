# FR Finance — M40690: concorrência de tickets e digest como credencial (NO-GO)

**Status:** Experimento sintético, exclusivamente em PostgreSQL 18 descartável no GitHub Actions. Não é migração, endpoint real, integração de autenticação ou autorização de produção. A PR #2 permanece draft.

## Escopo e hipótese

O M40680 demonstrou duas funções SQL segregadas: uma concede tickets curtos a partir de SHA-256 do Bearer na conexão autenticadora e a outra consome um ticket de uso único na conexão financeira. O M40690 examina duas propriedades distintas:

1. **Concorrência do ticket:** oito conexões independentes com o papel SQL financeiro tentam consumir simultaneamente o mesmo ticket. Cada rodada de teste exige precisamente uma resposta autorizada e sete negações. A prova repete a disputa três vezes no banco descartável para exercitar o bloqueio por linha do UPDATE e verificar que os dados retornados são do membro autorizado.
2. **Equivalência de credencial e risco confirmado:** o resumo SHA-256 do Bearer é enviado para uma função de autenticação e, sob o papel autenticador sintético, consegue emitir dois tickets diferentes para a mesma sessão ativa. Ambos podem ser consumidos. **Isso comprova que o digest vazado funciona como credencial de emissão enquanto o papel de autenticação estiver disponível**, mesmo que a API não envie o Bearer bruto ao banco.

O fixture também verifica privilégios independentes para emissão e consumo, falta de acesso direto a tabelas, bloqueio de tenant errado, sessão revogada após emissão e vínculo desativado após emissão. Não utiliza a API real ou dados existentes. Os valores, usuários, tickets, digest e credenciais do teste são fictícios e não são impressos nos logs.

## Conclusões e limites

Uma CI verde neste pacote **não significa que o vazamento de token esteja resolvido**. O ticket emitido tem natureza de capacidade de acesso sensível; um atacante que o obtenha pode consumi-lo primeiro. O resumo SHA-256 também é sensível porque a função de emissão aceita esse resumo. Um adversário que comprometa a credencial técnica do autenticador ou tenha acesso arbitrário às suas consultas poderá solicitar novas capacidades.

A prova de concorrência do PostgreSQL testa um processo e instância descartáveis com múltiplas conexões. **Não certifica a ausência de replay em clusters, sob falha/transação interrompida, timeouts, conexões compartilhadas, logs, telemetria ou outros caminhos SQL**. Não testa concorrência entre revogação e o SELECT já iniciado numa mesma transação. Não modifica o modelo de permissões das tabelas financeiras reais nem fecha o risco GUC spoof do backend atual. É necessária uma revisão independente da fronteira de confiança, provas de posse e segredo, gestão de capacidade, auditoria de privilégios, provas de isolamento de escrita, limites de requisição e logs sanitizados antes de qualquer implantação.

## Gates explícitos

- M40690_DIGEST_REPLAY_MINTS_MULTIPLE_TICKETS=CONFIRMED_NO_GO
- M40690_AUTH_DIGEST_CREDENTIAL_EQUIVALENCE=NOT_REMEDIATED
- M40690_SQL_LOG_LEAKAGE_AND_TELEMETRY=NOT_ATTESTED
- M40690_EXISTING_GUC_SPOOF=NOT_REMEDIATED
- M40690_HTTP_AND_REAL_SQL_ROUTES=NOT_MODIFIED
- M40690_ORIGINAL_PG_5433=NOT_ACCESSED
- M40690_LOCAL_DB_WRITES=NONE
- M40690_LOCAL_MIGRATIONS=NONE
- M40690_LOCAL_SERVICE_RESTARTS=NONE
- PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED

Nenhuma sincronização com o Termux ou alteração no banco original deve preceder a revisão de CI e de segurança. O FastAPI do aparelho não está atestado para reload ou restart.
