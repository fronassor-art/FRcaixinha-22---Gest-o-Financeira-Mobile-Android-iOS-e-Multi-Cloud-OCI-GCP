# FR Finance AI Studio — M25000: comprovação documental RLS (somente leitura)

## Entrega

Novo endpoint autenticado: `POST /api/v1/invitations/preflight/contracts`.

Consulta **de verdade** a base do ambiente configurado, utilizando
`get_current_session`, conexão `get_rls_db_connection` e políticas RLS já
existentes nas tabelas `public.tenants` e `public.contract_documents`.

A entrada é mínima e **não contém CPF, e-mail ou nome do destinatário**:

```json
{
  "target_role": "TENANT_MEMBER",
  "tenant_id": "00000000-0000-4000-8000-000000000001",
  "required_document_id": "00000000-0000-4000-8000-000000000002"
}
```

Os UUIDs acima são exemplos sintéticos; a consulta real só funciona com
uma sessão autorizada e dados existentes na base daquele ambiente.

## Comportamento

- Master autorizado solicita apenas prontidão de administrador;
  Administrador solicita apenas prontidão de membro da própria caixinha;
  Membro não consulta.
- Para perfil administrador, tenant diferente do contexto de sessão resulta em
  **403 antes de qualquer consulta**.
- O servidor consulta **se a caixinha está ATIVA** e **se a versão contratual
  do tipo TENANT_MEMBERSHIP está publicada** sob RLS.
- Mesmo com ambos os resultados verdadeiros, a resposta permanece
  `status=BLOCKED`, `activation_authorized=false`.
- Nenhum dado pessoal, UUID de documento ou UUID de tenant é ecoado.
- Não altera tabela alguma, não cria conta, não envia convite, não aciona
  SMTP, não publica contratos e não usa credenciais privilegiadas no código.
- A checagem de documento **não atesta que o convidado aceitou a versão**.
  Aprovação Master/MFA, titularidade do e-mail, entrega, token único, auditoria
  e reconfirmação no momento da escrita ainda faltam.
- A rota antiga `POST /api/v1/invitations` segue indisponível (HTTP 503).

## Segurança e limitações

A consulta usa o papel de aplicação já protegido por PostgreSQL RLS. Ela não
substitui revisão independente do modelo de permissões, nem a comprovação do
RLS no ambiente de staging. Uma referência sintaticamente válida não prova
direitos. O uso em produção depende de implantação OCI/TLS, autorização
operacional, esquema e testes reais de e-mail e trilhas auditáveis.

## Testes

`backend/tests/test_m25000_invitation_contract_readiness_ci.py` valida:
- consultas SELECT e filtros de estado/documento publicados;
- limites de perfil e tenant;
- nenhuma exposição de identificadores pessoais;
- status bloqueado mesmo com os dois objetos existentes;
- ausência de mutações e de executores exclusivos de CI.

A CI passa a exigir essa suíte; a regressão RLS em PostgreSQL descartável
permanece obrigatória.

Checkpoint Termux somente leitura de banco:
```sh
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m25000_invitation_contract_readiness_ci.py \
  backend/tests/test_m24900_invitation_preflight_ci.py \
  backend/tests/test_m24600_invitation_document_binding_ci.py \
  backend/tests/test_aistudio_lifecycle_disabled.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```

Não reiniciar o FastAPI em produção nem executar migrações automaticamente.
