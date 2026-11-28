# FR Finance — M40926: dupla custódia SQL para autorização Master (NO-GO)

## Checkpoint de entrada

M40925 sincronizado no Termux nativo no commit \`98b1183\`, sem conexões ao PostgreSQL original, escritas, migrações ou reinícios. A prova M40925 Ed25519 + SQL de uso único foi aprovada em PostgreSQL 18 descartável, mas também demonstrou um desvio: credenciais vazadas do emissor SQL e do app SQL, junto a um token Master válido, conseguem emitir e consumir aprovações sem a assinatura do cliente.

## Experimento de segurança M40926

M40926 acrescenta, **somente no PostgreSQL 18 descartável do GitHub Actions**, um segundo registro de custódia, totalmente separado da tabela de autorizações M40924 e do emissor M40925. Um guardian SQL login, associado a \`m40926_guardian_writer\`, pode somente inserir um registro \`m40926.seals\` com os campos vinculados a cada autorização opaca. A tabela guarda digest da autorização e sessão, ator, tenant, ação, campanha, revisão esperada, fingerprint dos parâmetros, expiração e consumo; possui RLS forçada, owner NOLOGIN e nenhum privilégio direto de app/emissor.

O wrapper M40924 existente continua com autorização de uso único e regras append-only. Um **trigger BEFORE UPDATE OF consumed_at** na tabela M40924 exige, de forma transacional, um selo do guardian ainda não utilizado, com exatamente o mesmo contexto de operação e prazo não inferior ao da autorização. O trigger é SECURITY DEFINER com owner NOLOGIN independente que tem apenas SELECT e UPDATE(consumed_at) no registro do guardian. A mesma transação consome ambos e desfaz ambos se a escrita/auditoria falhar. O app e o emissor não podem desabilitar o trigger nem assumir a role guardian.

O gateway FastAPI/ASGI *sintético* verifica o comando Ed25519 M40923, o token digest, payload, nonce e expiração curta. Em seguida cria o registro M40925 pelo SQL login emissor, o selo M40926 pela credencial guardian e chama o wrapper M40924 pelo SQL login app. Esses três logins são separados no laboratório, mas **suas credenciais ainda ficam no mesmo processo Python de teste**: não há isolamento operacional ou humano.

## Provas adversariais

- App SQL + emissor SQL + Bearer Master, **sem** guardian, não pode escrever.
- Guardian SQL + app SQL + Bearer Master, **sem** emissor, não pode escrever.
- Selo/autorizações casados a digest de sessão, tenant, ator, operação, revisão, corpo e expiração.
- DRAFT → PUBLISH → CANCEL com assinatura Ed25519 e dupla autorização; nega assinatura errada, body tampered, replay e token não Master.
- Falha de auditoria desfaz consumo de ambas as tabelas.
- Seis solicitações concorrentes com o mesmo nonce: no máximo uma operação.
- Sessão revogada bloqueia comando Master mesmo com ambas as autorizações.
- **NO-GO deliberado:** roubo conjunto dos três SQL logins mais Bearer Master permite emitir ambos os registros e contornar assinatura Ed25519.

## Limites e bloqueadores

A **dupla custódia não é dupla aprovação humana**, MFA nem HSM. Se o mesmo serviço detém emissor, guardian e app, o comprometimento desse processo anula o isolamento de papéis SQL; DB owner/superuser pode desabilitar trigger, alterar ACL ou dados. Uso antecipado de autorização roubada continua possível, e registro de nonce fica só em memória. Não há auditoria externa de concessão, enrollment atestado de chave pública, Android Keystore atestado, Vault/KMS, TLS real, separação de serviço protegida, rotação/recuperação ou avaliação operacional. Os bloqueadores históricos M40570 (GUC) e M40730 (emissor legado) continuam em **NO-GO**.

Nenhum arquivo do FastAPI real, frontend, banco de produção, migration, CI financeira, aplicativo instalado ou processo Termux foi alterado. O laboratório NÃO pode ser usado como migration sem autorização expressa, backup, desenho de identidade confiável e homologação independente. PR #2 permanece Draft.

**MIGRATIONS=NONE; ORIGINAL_DB_CONNECTIONS=NONE; ORIGINAL_ACL_CHANGES=NONE; LOCAL_DB_WRITES=NONE; SERVICE_RESTARTS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.**
