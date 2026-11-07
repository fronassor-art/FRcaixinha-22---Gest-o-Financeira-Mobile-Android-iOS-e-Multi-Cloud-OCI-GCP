# FR Finance AI Studio — M25100: catálogo de contratos publicados

## Objetivo

Permitir a uma identidade já autenticada identificar versões publicadas
do termo de adesão sem adivinhar UUID nem tratar hash como comprovante de aceite.

## Entrega

`POST /api/v1/invitations/preflight/contract-catalog`

Body (exemplo sintético; não contém destinatário, CPF, senha ou token):

```json
{
  "target_role": "TENANT_MEMBER",
  "tenant_id": "00000000-0000-4000-8000-000000000001"
}
```

- O endpoint exige sessão autenticada e conexão com contexto RLS.
- Master legítimo consulta prontidão para `TENANT_ADMIN`. Administrador com
  vínculo ativo só consulta prontidão de `TENANT_MEMBER` na própria caixinha.
  Membro não pode consultar este catálogo de emissão de convites.
- A caixinha precisa aparecer como `ATIVO` sob RLS; quando inativa ou
  invisível, a lista de documentos é vazia.
- Retorna no máximo 20 versões `TENANT_MEMBERSHIP` efetivamente publicadas,
  ordenadas por publicação; apenas `document_id`, `version`, `sha256` e
  `published_at`, além do estado de bloqueio.
- Não retorna `source_reference`, nomes pessoais nem o corpo do documento.
  **O corpo integral ainda não foi publicado pelo aplicativo**, e uma
  referência de origem não é evidência do texto visto pelo usuário.
- `status=BLOCKED`, `contract_body_available=false`,
  `acceptance_recorded=false`, `activation_authorized=false`,
  `writes_performed=false` inclusive quando existem documentos publicados.
- Não altera nenhuma tabela, não cria convite, não envia e-mail e não
  habilita Mercado Pago ou financiamento real.

## O que ainda falta para o cadastro real

1. Armazenamento e distribuição verificados do corpo imutável do contrato,
   provando que o SHA-256 da versão corresponde ao texto efetivamente exibido.
2. Titularidade do endereço e entrega real, OTP/token efêmero de uso único,
   limites de tentativas, expiração e revogação.
3. Consentimento explícito, registro transacional auditável e vinculação à
   identidade/caixinha com verificações de autorização no momento da escrita.
4. Master MFA/duplo controle para a ativação administrativa e revisão jurídica.
5. Ensaios integrados em PostgreSQL descartável e staging HTTPS; acesso
   independente às regras RLS e desenho dos papéis de escrita.

## Checkpoint no Termux

Somente após sincronizar:
```sh
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m25100_published_contract_catalog_ci.py \
  backend/tests/test_m25000_invitation_contract_readiness_ci.py \
  backend/tests/test_m24900_invitation_preflight_ci.py \
  backend/tests/test_m24600_invitation_document_binding_ci.py \
  backend/tests/test_aistudio_lifecycle_disabled.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```

Não instalar migrations nem reiniciar FastAPI neste pacote. Para expor a
nova rota no processo local, será necessária revisão da atualização do
runtime em uma etapa separada. CI e hash não comprovam funcionamento no APK.
