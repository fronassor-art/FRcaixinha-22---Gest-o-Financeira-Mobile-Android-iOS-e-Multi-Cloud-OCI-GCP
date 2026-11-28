# M25200 — FR Finance AI Studio — verificação de texto contratual exato

## Objetivo

Validar **apenas a integridade do corpo textual candidato** contra o SHA-256
já registrado para uma versão publicada no PostgreSQL. É um passo técnico
antes da entrega e aceite, **não** uma assinatura, consentimento, liberação
de convites ou comprovação de identidade.

## Implementação

`POST /api/v1/invitations/preflight/contract-text` (requer sessão
autenticada, papel autorizado e PostgreSQL sob contexto RLS).

Exemplo **fictício**:

```json
{
  "target_role": "TENANT_MEMBER",
  "tenant_id": "00000000-0000-4000-8000-000000000001",
  "required_document_id": "00000000-0000-4000-8000-000000000002",
  "contract_text": "Texto integral fictício.\nVersão de testes.\n"
}
```

A API executa, em transação RLS e com papel não privilegiado, somente duas
consultas: confirmar tenant ATIVO e obter SHA-256 da versão
TENANT_MEMBERSHIP publicada. Calcula o SHA-256 dos **bytes UTF-8 exatos**
do texto submetido e o compara em tempo constante com a versão do banco.
Não remove espaços, não converte CRLF para LF, não normaliza Unicode e
não aceita texto acima de 64 KiB ou caracteres Unicode inválidos.
O resultado divulga apenas flags de prontidão e bloqueios, **sem devolver
o corpo, o hash informado, IDs de tenant/documento ou dados pessoais**.

Rejeita campos de destinatário, como `target_email`. A API não grava
texto nem documento, não armazena nem transmite token de convite e não
cria conta. A verificação do hash não substitui armazenamento e
distribuição confiável do texto canônico, nem garante que ele foi lido
pelo usuário. O texto não pode ser de PDF: o cálculo refere-se somente
a bytes UTF-8, não ao binário de arquivo PDF.

Mesmo se `exact_utf8_document_digest_matched=true`, o resultado
permanece `status=BLOCKED`, `consent_verified=false`,
`acceptance_recorded=false`, `invitation_created=false`,
`activation_authorized=false`.

## Proteções obrigatórias posteriores

- Disponibilizar texto canônico imutável e sua origem controlada, sob
  HTTPS e com o SHA da versão, com conferência integral na tela.
- Preparar aceite explícito vinculado à identidade autenticada, ao hash,
  à versão e ao tenant, com carimbo e prova transacional.
- Validar destinatário por e-mail real, OTP/token de uso único, expiração,
  revogação e rate limit, sem reaproveitar executores CI em produção.
- Exigir MFA do Master e aprovação independente para administração
  conforme política aprovada; revalidar papel e tenant na escrita.
- Homologar no PostgreSQL descartável e staging OCI antes de acesso real.

## Testes

`backend/tests/test_m25200_contract_text_integrity_ci.py` cobre funções
puras e rota com conexão simulada, inclusive CRLF, Unicode, tamanho,
papéis, cross-tenant e nenhuma mutação ou eco de texto.

`backend/tests/test_rls_isolation_ci.py` contém
`test_m25200_contract_body_exact_digest_under_real_rls`, executado somente
na CI com PostgreSQL descartável na porta 5432 e rollback. O banco do
Termux `frcaixinha_aistudio_dev` na porta 5433 não é acessado por testes.

Checkpoint local sem alteração no banco:

```bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m25200_contract_text_integrity_ci.py \
  backend/tests/test_m25100_published_contract_catalog_ci.py \
  backend/tests/test_m25000_invitation_contract_readiness_ci.py \
  backend/tests/test_m24900_invitation_preflight_ci.py \
  backend/tests/test_security_guards.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```

Nenhuma migração, reinício FastAPI, provisionamento de OCI, envio de
e-mail ou operação real de Pix foi efetuada nesta etapa.
