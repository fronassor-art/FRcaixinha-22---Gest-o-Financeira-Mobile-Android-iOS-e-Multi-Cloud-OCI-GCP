# FR Finance AI Studio — M26000: recuperação segura de senha em staging

## Implementação de staging descartável

Nova migration `backend/staging_migrations/051_password_reset_staging_only.sql`
cria **somente** um registro de auditoria e uma função transacional,
`password_reset_rotate_staging_ci`, que:
- exige identidade de trabalhador segregada e flag exclusiva de staging;
- requer digest SHA-256 de token de 64 caracteres e hash Argon2id;
- bloqueia token inexistente, revogado, vencido, consumido ou ainda
  `PENDING_DELIVERY`;
- usa bloqueio `SELECT ... FOR UPDATE` para evitar dois usos concorrentes;
- exige usuário ativo e credencial existente, e troca o hash na mesma transação;
- consome o token, revoga os demais tokens pendentes e todas as sessões;
- persiste um evento auditável de conclusão, sem token/senha/e-mail no registro.

O retorno `ROTATED` só é possível no **banco descartável
`frcaixinha_staging` da CI**. O trabalhador `frcaixinha_account_recovery_ci`
não recebe acesso SELECT/UPDATE direto à tabela de tokens nem à auditoria.

O hash de senha usado no ensaio é **sintético**; a validação da resistência
e do armazenamento do segredo real compete ao serviço de autenticação
protegido e à infraestrutura de implantação. Os outros testes já
existentes no repositório validam Argon2id, credenciais e revogação.

## Testes

- `backend/ci_migrations/048_password_reset_fixture_ci_only.sql`: usuário,
  vínculo, sessão, token válido, duplicado, vencido e não entregue, todos
  sintéticos;
- `backend/ci_migrations/049_password_reset_worker_probe_ci_only.sql`: nega
  expiração, não entrega, token desconhecido, hash inválido e replay;
- `aistudio_staging_chain_ci.sh`: migração negativa no banco errado,
  atualização válida na role CI, revogação da sessão, tokens e log de auditoria;
- `backend/tests/test_m26000_recovery_staging_policy_ci.py`: teste de
  permissões, escopo e contrato sem banco, também exigido no job de API.

## Isolamento e limites

Esses três arquivos foram registrados no catálogo de migrações da frente
AI Studio com hashes de blob Git e `do_not_apply_source_to_termux=true`.
Os arquivos 051/048/049 não são migráveis para o Termux. O total do catálogo
passou a **79 SQL**; a base local de 46 tabelas **não** é alterada.

A rota pública `POST /api/v1/auth/forgot-password` continua 503.
Para implantá-la corretamente ainda faltam comprovação real de domínio/
remetente, outbox cifrado via vault, worker com rate limit distribuído,
confirmação de posse de e-mail, token opaco de uso único e antifraude.
O teste do token com flag `DELIVERED` é uma *simulação em CI*, nunca
prova de entrega real.

## O que executar no Termux após GitHub Actions PASS

```bash
(
set -e
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187"
test -z "$(git status --porcelain --untracked-files=no)"
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
 backend/tests/test_m25900_staging_outbox_contract_ci.py \
 backend/tests/test_m26000_recovery_staging_policy_ci.py \
 backend/tests/test_m25700_local_attestation_guard_ci.py \
 backend/tests/test_m25600_launch_readiness_ci.py \
 backend/tests/test_m25500_onboarding_smtp_transport_ci.py \
 backend/tests/test_security_guards.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
echo "FR_FINANCE_M26000_TERMUX_TESTS=PASS"
)
```

**Não executar** `psql -f` para os SQL de CI/staging, nem reaplicar o
instalador inicial: as 46 tabelas locais e as estruturas 028–044 já foram
atestadas em modo somente leitura pelo operador.

Os próximos passos são implementar delivery com KMS, worker durável,
callbacks de confirmação e autorização RLS por usuário autenticado,
homologar no OCI e somente depois retirar o 503 com autorização formal.
