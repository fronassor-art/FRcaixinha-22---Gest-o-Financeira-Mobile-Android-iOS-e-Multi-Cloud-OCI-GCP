# FR Finance AI Studio — M27500–M27600: leitura pós-gravação em PostgreSQL descartável

## Entrada

M27402, commit `12b37f9`: Termux **186 testes PASS**, validação de sintaxe e
`M19200_REGISTRY_HASHES=PASS` para 91 arquivos SQL. AES-GCM disponível no
celular. Pix real desligado. PR #2 permanece em rascunho na branch
`atualizacao-ai-studio-9b46a63187`.

## M27500 — registro SQL confirmado por role de auditoria (CI)

`backend/staging_migrations/057_email_challenge_readback_staging_only.sql`
introduz somente uma função `SECURITY DEFINER` de leitura, sem criar
tabelas nem alterar dados. A função:
- exige exclusivamente `frcaixinha_staging` no PostgreSQL descartável,
  a role CI específica `frcaixinha_email_attestor_ci` e o gate de testes;
- lê o desafio M27100 **após commit**, exigindo `lease` ativa e válida,
  convite pendente, tenant ativo, documento publicado e envelope AES-GCM
  associado com prazo vigente;
- exige `failed_attempts=0`, token não consumido, prazo não vencido e
  ausência de quarentena M26600;
- devolve metadados JSONB necessários ao controle M27400 (IDs, hash, horários
  e estado), **nunca o token, destinatário, segredo AES ou chave do índice**;
- nega leitura da tabela diretamente para a role de auditoria, assim como
  as roles de emissão e consumo;
- **não confirma posse de e-mail, entrega SMTP, consentimento ou ativação**.

## M27600 — evidência da leitura em sessão independente

`backend/app/ci_committed_challenge_reader.py` exige o modo
`GITHUB_ACTIONS=true` e `FRCAIXINHA_CI_ISOLATED=1`, além de autenticar
`current_database()`, `session_user` e a porta do PostgreSQL `5432`.
O parser rejeita campos adicionais, tipos errados, JSON duplicado,
hash inválido e evento trocado. A origem de leitura é marcada no objeto
resultante `DISPOSABLE_POSTGRESQL_CI_READBACK`, que continua sendo apenas
evidência interna e não credencial assinada.

A CI usa um token **exclusivamente sintético** com formato de 384 bits
(`64` caracteres URL-safe), em alinhamento com a M27200; os três
arquivos SQL antigos de fixture M27100–M27101 foram atualizados e
seus SHA Git recalculados no catálogo.

`test_m27600_committed_challenge_postgres_ci.py` comprova:
1. emissão do desafio pela role da fila em sessão/processo separado;
2. nova conexão da role de auditoria, readback com escopo e lease;
3. confronto com `check_committed_challenge` e SHA-256 do token sintético;
4. recusa do desafio com token trocado, evento/lease errados;
5. tentativa de `SELECT` direto negada por privilégio;
6. após consumo, nova leitura retorna NULL mesmo com lease temporariamente
   válida; o consumo não libera identidade nem SMTP.

A execução completa do banco é feita no script
`backend/scripts/aistudio_staging_chain_ci.sh` **somente pela CI**.

## Limites / pendências não mascaradas

- A role CI só demonstra o contrato de leitura. Não existe ainda role
  equivalente nem migration aprovada no banco operacional OCI.
- O valor `source` é uma etiqueta interna **não uma assinatura**.
  A segurança exige usar a nova conexão autenticada e não aceitar
  estruturas de dados provenientes de HTTP como prova.
- O hash SHA-256 do token é adequado na CI porque ele é aleatório de
  alta entropia. O índice legado SHA-256 de e-mail continua requerendo
  migração para HMAC M27300, em staging real supervisionado.
- Sem domínio SPF/DKIM/DMARC, serviço de SMTP/API real, Vault e IAM
  provisionados, callback do provedor autenticado, reconciliação, MFA,
  aceite individual e aprovação administrativa, os fluxos de convite
  real/recuperação e ativação permanecem bloqueados.
- Nenhum usuário Master, administrador ou membro foi criado. Nenhum Pix,
  empréstimo ou dinheiro real foi processado.

## Termux

O catálogo passa a **92 arquivos SQL**. A migration `057` é
`STAGING_ONLY_NEEDS_PORT`, com
`do_not_apply_source_to_termux=true`; não deve ser executada no
PostgreSQL 18 local na porta `5433` nem em produção.

Após a CI homologar, executar `git pull --ff-only`, pytest dos testes
M27500/M27400/M27300/M27200 e `aistudio_migration_inventory.py repo-check`;
para o script `aistudio_staging_chain_ci.sh`, rodar **apenas `bash -n`**.

A PR #2 deve permanecer aberta como DRAFT até implantação operacional,
auditoria OCI e as autorizações explícitas.
