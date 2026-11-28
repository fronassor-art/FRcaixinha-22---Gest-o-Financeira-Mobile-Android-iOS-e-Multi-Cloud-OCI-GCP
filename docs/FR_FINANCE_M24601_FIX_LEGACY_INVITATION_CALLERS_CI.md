# M24601 — CI: correção de chamados legados de convite

Escopo: FR Finance AI Studio, ambiente isolado. Não ativa Pix, e-mail real, API pública ou migrações locais.

## Falha observada

O commit `a735b1e`, run GitHub Actions `42329789443`, teve falha nos jobs "Migrações e testes de RLS em PostgreSQL descartável" e "API sem banco configurado". Três chamadas antigas de `prepare_invitation_ci` ainda omitiam o novo argumento obrigatório `required_document_id`, gerando `TypeError`.

## Correção

- `test_aistudio_live_engines_ci.py`: ambos os cenários passam o documento de adesão publicado na criação, sem `UPDATE` posterior; assertions verificam a referência persistida.
- `test_aistudio_lifecycle_disabled.py`: argumento sintético obrigatório incluso, para permitir a proteção `_ci_only` produzir `LifecycleDenied`.
- `test_m24600_invitation_document_binding_ci.py`: regressão com AST garante que os três arquivos CI de convite não omitam `required_document_id` e não reintroduzam o remendo SQL.

A aprovação depende de nova execução completa do GitHub Actions. Os testes com PostgreSQL só rodam na base `frcaixinha_ci`, porta 5432, descartável do CI. O Termux porta 5433 permanece intocado.

## Conferência no Termux

```bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m24600_invitation_document_binding_ci.py backend/tests/test_aistudio_lifecycle_disabled.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```
