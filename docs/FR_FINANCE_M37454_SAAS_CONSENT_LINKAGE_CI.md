# FR Finance — M37454: aceite SaaS explícito e vínculo de evidências (somente CI)

## Resultado anterior e alcance
- M37453: Termux `eb1eb1f`; 50 + 58 + 14 = 122 testes PASS; 
  GitHub Actions 6/6 PASS e PostgreSQL **descartável** somente leitura.
- 3 planos, 2 versões de preço, zero pagamentos, zero licenças ativas
  no último inventário M37450. Esses números não mudam neste pacote.
- `M37454` **não** implementa aceite contratual real nem nova infraestrutura.

## Política de correlação em modo CI

`backend/app/saas_consent_linkage_ci.py` compara quatro registros
hipotéticos (sessão, desafio, confirmação positiva e recibo) à
preparação previamente validada por `M37453`.

A verificação exige:
1. Administrador `TENANT_ADMIN`, tenant e sessão vinculados, ativos,
   com o atributo sintético de e-mail verificado.
2. Desafio único limitado a dez minutos, posterior à publicação,
   vinculado ao UUID do documento e hash SHA-256, versão do preço
   e UUID da preparação de assinatura.
3. Confirmação expressa em uma ação separada, com registro temporal
   posterior ao desafio, antes da expiração e ainda na sessão.
4. Recibo sintético com um consumo, sem replay/revogação, contagem de
   eventos e indicação de append-only **apenas como valores de teste**.
5. Comprovação de consistência do digest HMAC-SHA256 da ação,
   assinado por uma chave exclusivamente sintética em execução CI,
   incluindo identidade, versão e documento.
6. Vínculo entre digest sintético calculado e o campo
   `contract_acceptances.evidence_hash` do registro de teste.

## Lacuna proposital verificada

O fixture persistido original M30900 possui `evidence_hash` de
preenchimento sintético: **não** é um MAC relativo a ação de aceite.
Portanto, a rotina mais estrita retorna
`ACCEPTANCE_EVIDENCE_NOT_CRYPTOGRAPHICALLY_BOUND` para esse registro.
Esse resultado não é um bug e evita a falsa alegação de contrato firmado.

O teste positivo substitui o digest apenas na cópia **em memória**
do fixture, não no PostgreSQL, e retorna
`CI_CONSENT_LINKAGE_REVIEW_ONLY`. Um MAC conferido contra dados
sintéticos não prova a identidade ou ação real de uma pessoa;
não existem validações operacional ou jurídica.

## Bloqueios preservados

Qualquer resultado, inclusive o positivo, mantém:
`legal_consent_accepted=False`, `billing_authorized=False`,
`license_activated=False`, `user_activated=False`,
`pix_authorized=False`, `production_authorized=False`,
`writes_performed=False`. Não há chamada HTTP, SQL, aplicação de
migração, segredo comercial, autenticação real ou concessão de licença.

Assegurar a operação SaaS real exigirá prova de aceite capturada
em servidor autenticado, transação durável/idempotente no banco de
produção com RLS e logs append-only, atestação do provedor,
conciliação e autorização comercial de produção. A VM OCI ainda
é um pré-requisito operacional separado.

## Homologação local (sem acesso a banco de dados)

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37454_saas_consent_linkage_ci.py
python -m pytest -q backend/tests/test_m37453_saas_disposable_readback_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

O fluxo GitHub Actions executa os testes; quaisquer aprovações
devem ser verificadas antes de marcar o pacote como homologado.
