# FR Finance — M30900–M31300: contratação SaaS e licenças por caixinha

**Objetivo:** avançar os controles 3.1–3.11 por meio de código real de
PostgreSQL descartável e algoritmo de vigência, mas sem afirmar implantação
produtiva ou aceitar pessoas/pagamentos reais.

## Novas entregas

- **M30900:** função SQL `saas_prepare_enrollment_staging_ci` para criar
  uma preparação de licença com vínculo de administrador, tenant,
  oferta/preço versionado e aceite de `PLATFORM_LICENSE` já publicado.
- **M31000:** bloqueio `FOR UPDATE` na linha do tenant, `request_id`
  imutável e replay idempotente. Pedido divergente retorna DENIED.
- **M31100:** `saas_contract_gate.py` avalia expiração com
  tolerância **zero dia**, status ativo, reembolso, prova autenticada do
  provedor, conta recebedora da plataforma, integridade da versão do
  contrato e limites comerciais. Resultado positivo significa apenas
  `STAGING_PREFLIGHT_ONLY`; nenhuma autorização real.
- **M31200:** laboratório PostgreSQL 18/15 descartável da CI:
  matrícula válida, duplicidade, replay alterado, aceite não publicado,
  tenant incorreto, papel indevido e ausência de faturamento/entitlement.
  Papel `frcaixinha_saas_enroll_ci` não lê/grava tabelas diretamente.
- **M31300:** documentação, testes parametrizados, catálogo de migrações
  e CI com controles negativos.

## Situação dos requisitos 3.1–3.11

O código existente já continha preço e planos (011), aceites (015),
preparações (016), cobranças e licença (017), e motor de conciliação
`saas_billing_ci.py`. O novo pacote cobre a **preparação transacional**
que faltava, além de uma verificação independente de tempo e capacidade.

**Nenhuma cláusula é automaticamente homologada:** faltam contratos
assinados e revisados, provedor MP homologado, política comercial
aprovada, cenários E2E reais, bloqueios de plano efetivamente
integrados aos endpoints transacionais e infraestrutura OCI.

O Caixa Master recebe somente dados de licença. A função SQL não
cria receita, Pix, fatura, lançamento no Livro-Razão nem entitlement;
os fundos das caixinhas ficam intocados.

**NUNCA aplicar** `backend/staging_migrations/059_saas_enrollment_staging_only.sql`
ou `backend/ci_migrations/058_saas_enrollment_fixture_ci_only.sql`
no Termux porta `5433`, OCI ou produção. Esses arquivos têm guardas
de banco e papéis exclusivos de CI.

Termux oficial `~/fr-finance`; sincronizar Git apenas após CI verde,
executar testes Python e verificar catálogo. Migração local separada
somente quando existir equivalente próprio, backup restaurável e
autorização expressa. `REAL_PIX=OFF`; `REAL_USERS=OFF`.
