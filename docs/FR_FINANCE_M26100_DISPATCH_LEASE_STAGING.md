# FR Finance AI Studio — M26100: worker de despacho com lease (CI isolada)

## Situação inicial comprovada

Checkpoint M26002 `dba0e61`: 59 testes executados no Termux,
79 arquivos SQL versionados e 6/6 jobs CI `42382650663` aprovados.
A auditoria anterior da porta `5433` verificou estruturas/RLS das 46
tabelas locais. Nenhuma reexecução de migration foi autorizada.

## Implementação

Adicionados somente ao CI/staging descartável:
- `backend/staging_migrations/052_invite_dispatch_lease_staging_only.sql`;
- `backend/ci_migrations/050_invite_dispatch_first_probe_ci_only.sql`;
- `backend/ci_migrations/051_invite_dispatch_retry_probe_ci_only.sql`;
- `backend/tests/test_m26100_dispatch_lease_policy_ci.py`.

A migration exige banco `frcaixinha_staging`, operador privilegiado de
staging, flag CI, worker segregado e ausência de grants diretos ao papel
`frcaixinha_invite_dispatch_ci`. A função `invite_dispatch_lease_staging_ci`
confere novamente tenant ativo, destinatário/convite vinculado, documento
publicado, prazo, revogação, aceite e papel de convidante. A função obtém
lock transacional e só reserva o mesmo evento a um worker por vez, com
lease de **45 segundos** e até **três tentativas**.

Quando o worker repete o mesmo lease ainda válido, recebe `REPLAY`.
Outro worker durante a reserva recebe `DENIED`. Após a expiração,
um lease novo acrescenta registro de auditoria de tentativa. Depois
da terceira expiração, recebe `EXHAUSTED`; nenhuma quarta tentativa
é criada. Auditoria de tentativas append-only e contagens são validadas
com consultas de DBA somente no staging descartável.

**Não existe integração de envio** nessa etapa: estado sempre
`HELD_CI_NO_NETWORK`. Fila original continua `HELD_CI_NOT_SENT`.
Nenhum token, e-mail, CPF, senha, Pix ou mensagem real é transmitido.
O lease **não é confirmação de entrega**, nem de titularidade de e-mail,
nem de consentimento contratual.

Os arquivos são versionados no catálogo com seus hashes Git e marcados
`do_not_apply_source_to_termux=true`; catálogo agora tem **82 SQL**.
A CI executa teste negativo de banco errado, teste E2E com PostgreSQL
descartável, rejeição de SELECT direto, limites e idempotência.
A PR #2 permanece DRAFT, sem merge automático.

## Para operação real, ainda faltam

- worker de produção sob privilégio mínimo com criptografia autenticada
  de dados sensíveis, chave protegida em KMS/Vault e rotação;
- transição transacional real da fila, ACK do provedor e webhook de
  entrega assinado, com estados distintos (aceito, entregue, bounce);
- tratamento do caso de ACK ambíguo para **não reenviar** segredo de uso
  único; idempotência por evento e contato;
- validação do controle de e-mail por desafio, rate limit distribuído,
  política de revogação, aceite da versão contratual e auditoria;
- MFA e aprovação independente para administração;
- OCI staging com TLS/backup/restore e validação adversarial de RLS.

A rota pública de convites e a recuperação de senha permanecem
indisponíveis até a integração e autorização. Pix real segue off.

## Comando seguro no Termux (sem aplicar SQL)

```bash
(
set -e
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187"
test -z "$(git status --porcelain --untracked-files=no)"
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m26100_dispatch_lease_policy_ci.py \
  backend/tests/test_m26000_recovery_staging_policy_ci.py \
  backend/tests/test_m25900_staging_outbox_contract_ci.py \
  backend/tests/test_m19200_migration_inventory_ci.py \
  backend/tests/test_m24300_oauth_recovery_readonly_ci.py \
  backend/tests/test_security_guards.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
bash -n backend/scripts/aistudio_staging_chain_ci.sh
git rev-parse --short HEAD
git status --short
echo "FR_FINANCE_M26100_TERMUX=PASS"
echo "PIX_REAL=DESATIVADO"
)
```

**Não executar** as migrations `052/050/051` nem nenhuma outra
`staging_migrations` ou `ci_migrations` no Termux ou OCI. O banco
local já tem 46 tabelas; estes arquivos só testam a arquitetura futura.
