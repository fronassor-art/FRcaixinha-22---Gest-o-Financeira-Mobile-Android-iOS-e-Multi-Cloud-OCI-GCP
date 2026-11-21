# FR Finance M39067 — preços independentes, promoções SaaS e migração conjunta

## Decisão prevalecente (12/11/2026)
- Administrador **MASTER** escolhe e modifica livremente preço mensal e anual
  da assinatura SaaS. Nenhuma fórmula 10× nem piso comercial fixado.
- O backend exige moeda positiva e no máximo 2 casas decimais; não altera o
  piso **R$150 por cota/ciclo** dos membros.
- Planos Essencial e Intermediário são editáveis; Ampliado continua bloqueado.
- Promoções anuais/mensais para **novos administradores**, com preço
  independente, benefício, título, elegibilidade, início/fim e justificativa.
- Preços históricos, ofertas já preparadas/aceitas, pagamentos e direitos
  antigos não são reescritos. Nenhuma campanha executa Pix, e-mail ou licença.
- Fontes oficiais atualizadas do **projeto AI Studio**:
  `docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md` (CTM-SAAS-01 a 09)
  e `docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md` (seção 8).
  Documentos originais FR Caixinha 2.2 permanecem íntegros e independentes.

## Código implementado
- SQL112: transforma anuidade gerada em coluna normal, **preservando valores
  históricos**; somente novas versões de preço gravam valores separados.
  Ver documentação oficial PostgreSQL `ALTER TABLE DROP EXPRESSION`.
- SQL113: tabela `public.platform_saas_promotion_revisions` de inserção
  imutável, FORCE RLS, política somente MASTER, gatilho de transição e de
  fidelidade à versão de plano, datas e exclusividade de campanhas.
  A função de leitura `public.frfinance_saas_new_admin_published_promotions()`
  retorna **somente** últimas revisões publicadas, vigentes, para usuário
  TENANT_ADMIN ativo sem contratação/preparação anterior. A função tem
  `SECURITY DEFINER`, `search_path` seguro e EXECUTE limitado ao papel app.
- API: `GET /api/v1/master/saas-promotions`,
  `POST /api/v1/master/saas-promotions/draft`,
  `POST /api/v1/master/saas-promotions/transition` e
  `GET /api/v1/tenants/{tenant_id}/saas-promotions`.
  Código em `backend/app/routers/saas_promotions.py`.
- Android: `src/components/SaasPromotionsPanel.tsx` integrado ao
  `MasterLicensingView.tsx`; exibe criação, lista, publicação/cancelamento
  no Master e ofertas elegíveis e informativas no TENANT_ADMIN. Sem botão
  de pagar/aceitar promoção; nem pré-aprovação de concessões.
- Concorrência: locks transacionais por campanha e por plano/período;
  revisão esperada/versão de preço evita gravações desatualizadas.
- `backend/migration_catalog_ai_studio.json` registra SHA Git blob dos
  dois SQL. **Não** aplicar `--apply` da M39066 isolada; agora bloqueado.

## CI e evidências exigidas
1. `frfinance-m39067-saas-promotions-ci.yml`: exige inventário hashes,
   testes de RBAC, API, transições, observação no Android e validação de tipo.
   Nenhum banco original conectado.
2. `frfinance-m39067-postgres18-disposable-runtime.yml`: sobe um servidor
   PostgreSQL 18 **descartável no GitHub, porta de CI 55433**. Executa a
   porção DDL dos SQL112/113 em base sintética após retirar SOMENTE os DO de
   identidade nativa, mantendo os SQL versionados intactos. Confere manutenção
   da anuidade histórica, nova anuidade independente, RLS, gatilho de bloqueio,
   publicação, elegibilidade e cancelamento. Não é prova de migração Termux.
3. As versões exatas, status e URL de runs devem ser verificadas antes da
   sincronização. CI concluída com sucesso não é autorização de produção.

## Como sincronizar e INSPECIONAR no Termux original
Use somente Android Termux nativo; **não** Debian/root, **não** PostgreSQL
da FR Caixinha 2.2 (porta 5432). Preserve servidor FastAPI e sessões.

```sh
(
set -e
export PYTHONDONTWRITEBYTECODE=1
cd "$HOME/fr-finance"
BRANCH="atualizacao-ai-studio-9b46a63187"
SHA="SUBSTITUIR_POR_SHA40_APROVADO_DO_GITHUB"
test "$HOME" = "/data/data/com.termux/files/home"
test "$(git branch --show-current)" = "$BRANCH"
test -z "$(git status --porcelain --untracked-files=all)"
git fetch --no-tags origin "$BRANCH"
test "$(git rev-parse FETCH_HEAD)" = "$SHA"
git merge --ff-only FETCH_HEAD
python3 -B backend/scripts/aistudio_migration_inventory.py repo-check
python3 -B -m pytest -q -p no:cacheprovider \
  backend/tests/test_m39066_master_independent_saas_prices_ci.py \
  backend/tests/test_m39067_master_saas_promotions_ci.py
AI_STUDIO_APPROVED_SHA="$SHA" \
  python3 -B -m backend.scripts.frfinance_m39067_apply_saas_prices_promotions_pg18 --inspect
)
```

A inspeção solicita senha de `frc_ai_owner` **oculta**; jamais mostrar senha
ou DSN. Resultados seguros: `M39067_SQL112=LEGACY_10X_GENERATED_READY_FOR_SQL112`
e `M39067_SQL113=SQL113_NOT_APPLIED`, ou ambos já aplicados.
Qualquer divergência de banco, role, PGDATA, catálogo, SHA, trigger ou
permissão bloqueia. Inspecionar não reinicia API ou banco.

## Migração real LOCAL — segunda autorização expressa
Somente após prova real das CI, preflight e revisão de backup/restauração
é permitido executar `--apply` do script M39067 (em novo comando), digitando
`APLICAR_SQL112_113_FR_FINANCE`. Ele verifica o original 127.0.0.1:5433,
faz backup privado PG18 custom + lista de arquivo e aplica **SQL112+SQL113
atomicamente**, com rollback transacional se falhar. O backup não é certificado
restaurável apenas por `pg_restore --list`: um teste de restauração separado
continua obrigatório antes de operação crítica/produção.

Depois, conferir `PASS_APPLIED_POSTCHECK`, reiniciar **somente** a FastAPI
local com procedimento supervisionado para carregar rotas novas, testar
401/403 sem credenciais, preços por Master, promoção elegível por admin,
não acesso por membro, e testes Android na APK recompilada com mesmo appId
e certificado original, versão crescente. Nenhum envio ou cobrança real.

## Limitações ainda bloqueadas
- Uma promoção publicada é apenas oferta **informativa dentro do app**;
  não se transforma automaticamente em desconto de checkout ou contrato.
- Produção exige vínculo de proposta a contrato versionado/aceite, licença
  válida, provedores e conciliação.
- E-mail, push, WhatsApp, SMS, cobrança SaaS e Pix permanecem desativados.
- Sem alteração nos dados financeiros de membros, decisões de crédito,
  contratos assinados ou condições retroativas de assinatura.
