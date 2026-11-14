# FR Finance AI Studio — M25300 — revisão de contrato na interface

## Objetivo

Disponibilizar **ao responsável autenticado** uma conferência do termo de
adesão antes da futura emissão de convites. Esta NÃO é a tela de aceite
do convidado e NÃO cria assinatura, documento, conta, vínculo ou prova jurídica.

## Entrega funcional

- `src/components/ContractReviewPanel.tsx` aparece de forma recolhível na
  tela Master de preparação administrativa após informar UUID válido da
  caixinha e na tela **Membros e Cotas** do administrador autenticado.
- A tela utiliza duas rotas existentes da API:
  - `POST /api/v1/invitations/preflight/contract-catalog` para listar
    até 20 versões documentais publicadas com IDs, versão e SHA-256;
  - `POST /api/v1/invitations/preflight/contract-text` para comparar o
    **texto UTF-8 exato** fornecido com o SHA-256 da versão escolhida.
- O cliente valida role, UUIDs, texto não vazio e limite 64 KiB; o servidor
  revalida papel, tenant, documento publicado e digest sob PostgreSQL RLS.
- Os parsers recusam respostas que anunciem convite emitido, aceite gravado
  ou ativação liberada. Qualquer falha não desbloqueia comandos.
- Alterar texto ou documento invalida o resultado anterior. Retornos de
  requisições antigas são descartados; o contexto de sessão também é
  verificado em `financialApi.request`.
- O texto não é persistido pelo componente nem usado para preencher
  um contrato fictício. A própria API recebe o texto apenas para
  comparação técnica: usar versão aprovada, não dados pessoais.
- O Master nunca herda acesso a saldos, cotas, empréstimos ou dados pessoais
  de membros através dessa tela; membros não recebem o painel de preparação.

## Limites explícitos

Não há download autoritativo do corpo contratual hospedado nem garantia
de que o texto foi mostrado ao convidado. Hash coincidente não equivale a
exibição, aceite, assinatura ou ativação. Convite e reset de senha
públicos continuam bloqueados (503). Nenhuma integração SMTP/OCI/Pix,
registro de conta ou migração foi efetuada.

**Próximas condições para cadastro real:** documento canônico imutável
publicado e servido via HTTPS; entrega e validação do e-mail; token de uso
único, expiração e antifraude; autorização transacional por tenant e papel;
consentimento informado da própria identidade vinculada ao documento;
auditoria completa e testes adversariais em staging. A confirmação de
segurança e operação deve anteceder a abertura de qualquer rota de escrita.

## Testes

- `src/tests/m25300_contract_review_ui_ci.test.ts`: parser que falha
  de forma fechada, política de papel, fluxo de tela e ausência de aceite.
- `npm run lint`: tipagem TypeScript obrigatória na CI.
- Regressões anteriores da API `M24900`–`M25200` e do PostgreSQL
  descartável continuam exigidas na CI.
- O APK debug é compilado na CI após os jobs de frontend/API/RLS.

## Checkpoint do Termux

```sh
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

O teste TypeScript completo e a compilação do APK ocorrem no GitHub Actions,
pois o Termux atual não dispõe de um NodeJS estável. A simples sincronização
não reinicia o FastAPI; a nova interface exige o APK compilado e instalado
para validação visual no celular.
