# FR Finance AI Studio — Macropacote M26400–M26600

## Base de trabalho comprovada

Termux M26300: commit `5923e36`, **82 testes PASS**, 84 SQL versionados
com `M19200_REGISTRY_HASHES=PASS`, sem mudanças locais sinalizadas.
CI `42385892022`: 6/6 jobs PASS com APK debug. PR #2 DRAFT.
PostgreSQL AI Studio na porta `5433` permanece exclusivo; nenhuma
migração SQL nova está autorizada ou foi executada nele.

## M26400 — envelope de entrega cifrado autenticado

`backend/app/delivery_envelope.py` usa AES-256-GCM da biblioteca
`cryptography==50.0.2` com nonce aleatório de 96 bits gerado para
cada envelope. O AAD inclui tenant UUID, evento UUID, documento UUID,
papel, finalidade, emissão, vencimento, ID da chave e versão. Alterar
qualquer desses campos invalida a autenticação. O payload cifrado contém
destinatário e token de uso único; não é gravado em banco neste pacote.

Não há chave em código, arquivo `.env` ou fallback: o chamador deve
fornecer um provedor de chaves separado, ainda **não ligado ao OCI Vault**.
O pacote limita tamanho, formato de token, validade, expiração e rejeita
corrupção da cifra, nonce incorreto, chave errada, troca de caixinha,
documento ou propósito. Os testes usam **somente chave efêmera sintética**.

Criptografar o envelope resolve a confidencialidade/integridade em
memória e trânsito de chamadas futuras, mas não prova armazenamento
durável, proteção de KMS, expurgo ou execução real do outbox.

## M26500 — decisões auditáveis de envio

`backend/app/onboarding_delivery_decision.py` define uma política
pura para o futuro trabalhador de entrega:

- `SMTP_ACCEPTED_UNVERIFIED`: suprime reenvio, mas **não** prova entrega;
- `SUBMISSION_TIMEOUT_UNKNOWN`: quarentena, **sem reenvio automático**;
- `AUTHENTICATED_CI_BOUNCE`: revisão, sem reenvio;
- falha *comprovadamente anterior à rede*: candidata à nova lease,
  após revalidar banco, enquanto houver menos de três tentativas;
- terceira falha pré-envio: esgotamento, sem nova tentativa.

Toda decisão mantém `can_auto_retry=false`, entrega falsa, verificação
de destinatário falsa, consentimento falso e conta não ativada. Um
cliente público nunca pode fornecer a evidência que autorizaria reenvio.

## M26600 — quarentena durável em PostgreSQL de CI

`staging_migrations/054_invite_delivery_terminal_gate_staging_only.sql`
e `ci_migrations/053_delivery_terminal_gate_probe_ci_only.sql`:
- criam tabela de terminalidade com RLS FORCE e sem grants diretos;
- registram **apenas** aceitação SMTP sintética com evento auditado,
  bounce sintético com evento auditado, ou timeout ambíguo;
- usam o mesmo advisory lock da M26100 para serializar verificação,
  resultado e nova tentativa;
- negam replays conflitantes e mantêm terminalidade sem possibilidade
  de marcar entregue/validado/aceito/ativado;
- revogam EXECUTE do ponto de entrada antigo da M26100 ao trabalhador;
  novo ponto protegido responde `QUARANTINED` após terminalidade;
- testam timeout persistido, tentativa concorrente suprimida, ACEITE
  sintético com ROLLBACK e falta de evidência do provedor.

**A migration M26600 roda apenas no banco frcaixinha_staging
descartável de GitHub Actions.** Nunca no Termux ou OCI. O catálogo
aumentou de 84 para **86 arquivos SQL** e os novos arquivos estão
classificados com `do_not_apply_source_to_termux=true`.

## Requisitos ainda ausentes para operação real

1. Prover chave AES-256 pelo OCI Vault/HSM, com identidade de trabalho,
   política de acesso e rotação de chave; sem credenciais no repositório.
2. Persistir envelopes cifrados e chaves de idempotência com
   referência atômica à fila, controle de concorrência e retenção.
3. Adaptar callback ao protocolo oficial do provedor escolhido,
   verificar assinatura, replay, lease, tenant e destinatário.
4. Reconciliar resposta ambígua com provedor antes de eventual retry;
   revisão e novo token quando necessário, jamais reenvio implícito.
5. Liberar emissão/aceite de convites apenas após MFA Master,
   dupla aprovação, documento aprovado servido ao convidado,
   comprovação de e-mail e auditoria transacional.
6. Implantar HTTPS/OCI, banco, backup-restauração e políticas RLS
   com testes adversariais; implementar recuperação de senha pública.
7. Pix real e pagamentos continuam desativados até PSP habilitar,
   OAuth e conciliação testados.

**Sem novas rotas públicas, sem envio real e sem alterações no
PostgreSQL local.** A CI completa é a evidência de implementação
desses controles, não de homologação operacional com provedores.

## Verificação local segura

Após a CI passar e o commit ser anunciado:

```bash
(
set -e
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187"
test -z "$(git status --porcelain --untracked-files=no)"
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m26500_delivery_decision_ci.py \
  backend/tests/test_m26600_delivery_terminal_gate_ci.py \
  backend/tests/test_m26300_mail_receipt_audit_policy_ci.py \
  backend/tests/test_m26100_dispatch_lease_policy_ci.py \
  backend/tests/test_m19200_migration_inventory_ci.py \
  backend/tests/test_security_guards.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
bash -n backend/scripts/aistudio_staging_chain_ci.sh
python3 - <<'PY'
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("M26400_TERMUX_AESGCM=DEPENDENCIA_A_INSTALAR_APOS_REVISAO")
else:
    print("M26400_TERMUX_AESGCM=AVAILABLE")
PY
git rev-parse --short HEAD
git status --short
)
```

Se `cryptography` estiver instalado no ambiente Termux, também pode
executar `PYTHONPATH=backend python3 -m pytest -q
backend/tests/test_m26400_delivery_envelope_ci.py`. Se não estiver,
a execução da suíte de AES-GCM é obrigatória e concluída no CI Linux;
não instalar dependências nativas indiscriminadamente no celular.
