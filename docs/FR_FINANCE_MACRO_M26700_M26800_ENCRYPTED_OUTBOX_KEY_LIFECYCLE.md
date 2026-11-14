# FR Finance AI Studio — Macropacote M26700–M26800

## Checkpoint de entrada

M26600 `1f7ab5b`: GitHub Actions `42387413920` **6/6 PASS**,
Termux **54 testes PASS**, 86 arquivos SQL íntegros.
`M26400_TERMUX_AESGCM=DEPENDENCIA_PENDENTE`; a CI Linux já
aprovou os testes AES-GCM. PostgreSQL do AI Studio: porta exclusiva
`5433`, 46 tabelas locais atestadas anteriormente, **nenhuma
migração nova aplicada ao Termux**.

## M26700 — Envelope cifrado persistente e leitura restrita

`staging_migrations/055_invite_encrypted_envelope_staging_only.sql`
adiciona uma tabela **somente no PostgreSQL descartável de CI**.

- Persiste `tenant_id`, `event_id`, documento, papel, versão de
  chave, nonce, AES-256-GCM ciphertext, SHA-256 da representação
  cifrada, horários e um estado `SEALED_CI_NOT_SENT`.
- Não grava destinatário, token em claro, senha, CPF ou chaves privadas.
  A entidade de convite sintética já existente na fixture CI não foi
  transformada em uma conta real.
- Não aceita valores se o convite venceu, foi revogado, já foi aceito,
  se o contrato não está publicado, o tenant não está ativo ou se
  existe quarentena terminal.
- A função de escrita exige `frcaixinha_envelope_producer_ci`.
  Enfileiramento idêntico devolve `REPLAY`; mudanças na mesma
  identidade de evento são bloqueadas.
- A leitura está restrita a `frcaixinha_invite_dispatch_ci` com
  lease válido, convite ainda pendente e sem quarentena; devolve
  **somente o envelope cifrado**, não chave nem token descriptografado.
- A tabela tem RLS FORCE, sem políticas públicas ou grants diretos.
- `test_m26700_sealed_outbox_postgres_ci.py` é executado no banco
  descartável com duas roles segregadas: cifra usando chave sintética,
  grava, confere replay, recupera pelo lease e revalida AES-GCM.
- Depois da M26600, a CI restabelece por segundos a lease sintética e
  comprova que **mesmo assim** não é possível ler após quarentena.
- Os fluxos não chamam SMTP nem criam usuário, consentimento ou Pix real.

A migration 055 consta do catálogo com SHA Git e
`do_not_apply_source_to_termux=true`. O catálogo passa a
**87 arquivos SQL**. Nunca executar 055 manualmente no banco local,
na OCI nem em produção.

## M26800 — Ciclo de vida de chaves por caixinha

`backend/app/delivery_key_lifecycle.py` envolve os comandos de
AES-GCM com uma política de metadados de chave, segregada por tenant:

- `ACTIVE`: pode cifrar dentro da janela válida.
- `DECRYPT_ONLY`: não cifra novos envelopes; pode abrir os já emitidos
  dentro da janela de leitura permitida.
- `REVOKED`: não cifra nem abre.
- Qualquer referência inexistente, prazo vencido, tenant diferente,
  chave de substituição incorreta ou metadado inconsistente bloqueia.
- O módulo não mantém bytes da chave e não possui acesso a rede,
  variável de ambiente, banco ou OCI Vault. A fonte real dos
  metadados e das chaves ainda precisa de autenticação, auditoria,
  políticas OCI IAM/Vault e homologação de rotação.

**Limitação importante:** a migração de recriptografia dos envelopes
duráveis, a reconciliação com provedor real e o expurgo após retenção
ainda não foram implementados. Não confundir este módulo com integração
OCI Vault real nem com liberação dos cadastros.

## Recuperar a dependência criptográfica do Termux

No **Termux principal** (não no Debian PRoot), a biblioteca pode ser
instalada preferencialmente pelo repositório de pacotes nativos:

```bash
pkg show python-cryptography
pkg install python-cryptography
python3 -c 'from cryptography.hazmat.primitives.ciphers.aead import AESGCM; print("M26400_TERMUX_AESGCM=AVAILABLE")'
```

Isso é um passo opcional, sujeito a confirmação do operador, e não
faz alterações no PostgreSQL ou no código Git. Não usar
`pip install cryptography` como primeira opção nesse Termux:
extensões Rust compiladas para outras plataformas podem falhar.
O CI Linux já valida a criptografia sem depender dessa instalação.

## Próximas pendências para produção

1. OCI Vault/KMS provisionado, autenticação de máquina e IAM exclusivo
   para serviço de cifrar e serviço de decifrar, sem chaves no repo.
2. Persistência do envelope em migração **nova e revisada** do banco
   definitivo, com backup e rollback aprovados (não aplicar SQL CI).
3. Worker durável que confirma callback oficial do provedor, revoga
   envelopes após expiração, reconcilia ACK incerto e evita reenvio.
4. MFA Master, aprovação independente, prova real de e-mail,
   consentimento da versão jurídica pelo convidado e auditoria de
   identidade/tenant.
5. OCI HTTPS e RLS adversarial em staging real; restauração de backup.
6. Mercado Pago Connect/PIX real só após habilitação comercial, segregação
   de credenciais, conciliação e testes do ciclo financeiro.

**Status:** implementação e testes offline/CI, envio real DESATIVADO,
recuperação de senha pública DESATIVADA, Pix real DESATIVADO, OCI não
provisionada.

## Termux — sem aplicar SQL

```bash
(
set -e
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187"
test -z "$(git status --porcelain --untracked-files=no)"
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m26700_encrypted_outbox_policy_ci.py \
  backend/tests/test_m26800_key_lifecycle_ci.py \
  backend/tests/test_m26600_delivery_terminal_gate_ci.py \
  backend/tests/test_m26500_delivery_decision_ci.py \
  backend/tests/test_m19200_migration_inventory_ci.py \
  backend/tests/test_security_guards.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
bash -n backend/scripts/aistudio_staging_chain_ci.sh
git rev-parse --short HEAD
git status --short
echo "FR_FINANCE_M26800_TERMUX_POLICY=PASS"
)
```

Se o módulo `cryptography` não estiver instalado, executar primeiro
o teste de políticas sem AES e deixar os testes do envelope para a
CI. O arquivo `test_m26700_sealed_outbox_postgres_ci.py` roda
exclusivamente contra o PostgreSQL **descartável** no GitHub Actions.
