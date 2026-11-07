# FR Finance AI Studio — M27000–M27101: comprovação de destinatário, CI isolada

## Checkpoint de entrada comprovado

M26900 `cbef834`: Termux 21 testes gerais + 67 AES/Vault,
`FR_FINANCE_M26900_TERMUX_CRYPTO=PASS`, 87 arquivos SQL com hashes
íntegros; `FR_FINANCE_PIX_REAL=DESATIVADO`. O workflow
`42389596776` foi aprovado nos 6 jobs, incluindo APK debug.
A PR #2 segue DRAFT e o repositório é exclusivamente AI Studio,
sem qualquer reaproveitamento do projeto independente FRcaixinha 2.2.

## M27000 — Validação da lease, destinatário e envelope (offline)

`backend/app/outbound_worker_preflight.py`:
- recebe uma *fotografia autenticada pelo banco* contendo tenant, convite,
  documento, papel, lease, prazo e número de tentativas;
- exige lease ativa e no máximo 3 tentativas, convite não vencido,
  estado pendente e ausência de quarentena terminal;
- reconfirma tenant, evento, documento e papel do envelope AES-GCM;
- recusa chave revogada/expirada por M26800 e ciphertext adulterado
  por M26400;
- compara o digest normalizado do destinatário decifrado com o digest
  já registrado pela fila; em produção esse valor só pode ser obtido
  de transação autenticada, **nunca de dados fornecidos pelo cliente**;
- devolve somente `CI_PAYLOAD_VERIFIED_NOT_SENT`: sem e-mail, token,
  chave, URI, autorização de entrega, usuário ativo ou consentimento.

Ainda não existe execução de envio conectada a esse módulo; o fluxo
é propositalmente offline. O digest SHA-256 atual do e-mail é legado
da fila M25900 e **não é um mecanismo de confidencialidade forte**
para endereços de e-mail. Em produção usar índice de correlação
protegido, com chave de serviço/HMAC, após migração aprovada.

## M27100 — desafio de e-mail de uso único (CI)

`backend/staging_migrations/056_email_ownership_challenge_staging_only.sql`
cria uma tabela de desafio com RLS FORCE e sem acesso direto,
vinculada ao evento da fila já existente e contrato publicado:
- armazena somente o **SHA-256 de token sintético de alta entropia**
  e o estado de uso, nunca o token em claro;
- emissão restrita a `frcaixinha_invite_queue_ci`;
- consumo restrito à role `frcaixinha_email_proof_ci`;
- validade máxima de 15 minutos;
- três erros no máximo; consumo correto marca apenas
  `CI_TOKEN_CONSUMED_NOT_PROOF`;
- um novo uso, tenant inativo, convite revogado, expirado ou terminal
  em quarentena é rejeitado;
- **não altera** `recipient_verified`, Master, usuários, credenciais,
  sessão, vínculo, aceite contratual ou ativação.

Esse desafio é aplicado apenas com tokens fictícios e **não comprova
posse de e-mail real**, pois o token não foi efetivamente entregue
por um provedor homologado.

## M27101 — regressão adversarial de 3 tentativas e expiração

Três arquivos em `backend/ci_migrations`:
- `054_email_challenge_issue_probe_ci_only.sql`;
- `055_email_challenge_consume_probe_ci_only.sql`;
- `056_email_challenge_lockout_probe_ci_only.sql`.

O pipeline cria banco descartável `frcaixinha_staging` (porta 5432),
prova bloqueio de aplicação em banco errado, repete emissão idêntica,
recusa evento ausente, rejeita token incorreto, consome um token
sintético uma vez e rejeita replay. Em rodada adversarial do mesmo
banco **sintético**, 3 erros bloqueiam um token válido, e um token
vencido também é rejeitado. O operador não recebe privilégios
diretos nas tabelas.

## Migrações e limites

O catálogo cresceu de 87 para **91 arquivos SQL**, com hashes Git
verificados e os novos arquivos classificados como
`do_not_apply_source_to_termux=true`. **Não aplicar** os SQL
056 de staging ou 054–056 de CI no banco local `5433` ou na OCI.

O Master atual, os administradores e membros existentes permanecem
inalterados. Sem e-mail de verdade, sem conta, sem Pix, sem cobrança,
sem migração local, sem OCI apply.

## Próximas provas necessárias para cadastrar usuários reais

1. Domínio, remetente e SPF/DKIM/DMARC do provedor real; SMTP/API TLS
   com credenciais protegidas no Vault e políticas IAM;
2. implantação do outbox real com worker segregado,
   idempotência durável, callback do provedor e quarentena de ACK
   ambíguo, com prova de entrega (distinta da posse do e-mail);
3. confirmação da posse de e-mail por desafio assinado, TTL, proteção
   distribuída contra abuso, uso único e auditoria, sem token em logs;
4. aceite *do convidado* do termo jurídico publicado, identidade
   verificada, MFA e aprovação dupla para administradores;
5. banco OCI com migrações específicas, backup restaurável, TLS,
   provas adversariais de RLS e plano de rollback;
6. ativação financeira só após consentimento do Mercado Pago,
   conciliação e autorização comercial para PIX Money Out.

## Comando seguro no Termux após CI PASS

```bash
(
set -e
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187"
test -z "$(git status --porcelain --untracked-files=no)"
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
 backend/tests/test_m27000_outbound_worker_preflight_ci.py \
 backend/tests/test_m27100_email_ownership_challenge_policy_ci.py \
 backend/tests/test_m26900_oci_vault_keys_ci.py \
 backend/tests/test_m26800_key_lifecycle_ci.py \
 backend/tests/test_m26700_encrypted_outbox_policy_ci.py \
 backend/tests/test_m26400_delivery_envelope_ci.py \
 backend/tests/test_security_guards.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
bash -n backend/scripts/aistudio_staging_chain_ci.sh
git rev-parse --short HEAD
git status --short
echo "FR_FINANCE_M27101_TERMUX=PASS"
echo "FR_FINANCE_PIX_REAL=DESATIVADO"
)
```

**Atenção:** o teste do PostgreSQL `frcaixinha_staging` roda apenas no
GitHub Actions. Não execute `aistudio_staging_chain_ci.sh` no celular.
