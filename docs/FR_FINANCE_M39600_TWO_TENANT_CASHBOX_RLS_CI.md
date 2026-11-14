# FR Finance — M39600 | Testes reais de segregação dos caixas (CI descartável)

**Data:** 14/11/2026  
**Projeto:** FR Finance AI Studio · branch `atualizacao-ai-studio-9b46a63187` · PR #2 Draft  
**Origem:** checkpoint M39500 `2e5228b` sincronizado no Termux nativo, `M39500_STATUS=PASS_OFFLINE_SOURCE_ONLY`.

## Objetivo

Avançar depois do checkpoint do operador, sem repetir sincronização/restart, sem aplicar migrações ao PostgreSQL original e sem dar falso PASS à liberação de produção.

## Contrato testado

- **Master:** vê evidências de `saas_subscription_preparations` e `saas_payment_intents` da plataforma, sob política RLS e sessão Master, **não** vê o Livro-Razão de administradores.
- **Administrador A:** vê somente os registros SaaS vinculados à sua identidade/caixinha e lançamentos de `ledger_transactions` do tenant A; não vê os do tenant B.
- **Administrador B:** igual, isolado no tenant B.
- **Membro:** não vê o caixa SaaS exclusivo nem o Livro-Razão administrativo.
- **Dinheiro:** intenções `PENDING` com `live_mode=false` são artificiais, não comprovam receita recebida, saldo, lucro ou autorização de transferência.

## Entregas

1. `backend/tests/sql/m39600_exclusive_cashbox_rls_disposable_ci.sql` usa **políticas RLS reais já aplicadas pela cadeia de migração CI** e dois tenants sintéticos. Somente executa com `CI_M39600_DISPOSABLE`, banco `frcaixinha_ci`, usuário `postgres`, porta 5432 **do serviço GitHub Actions descartável** e `PGOPTIONS` `frfinance.m39600_ci=DISPOSABLE_ONLY`. Prepara dados sintéticos em `BEGIN`, assume o papel `frcaixinha_app_role`, valida leitura e nega vazamentos, e termina em `ROLLBACK`.
2. O workflow `.github/workflows/validacao-atualizacao.yml` passa a executar o mesmo arquivo contra **PostgreSQL 16 e 18 descartáveis**, depois de aplicar as migrations **somente nos runners CI**, nunca no Termux.
3. `backend/tests/test_m39600_cashbox_rls_source_ci.py` garante duas execuções CI, proteção por ambiente, `ROLLBACK`, nenhum `COMMIT` nem comandos DDL, e falha se o contrato perder um dos perfis/caminhos.
4. `backend/app/routers/exclusive_cashboxes.py` adicionou `Cache-Control: private, no-store, max-age=0`, `Pragma: no-cache`, `Vary: Authorization` para as duas respostas financeiras por papel.
5. `backend/tests/test_m39090_exclusive_cashboxes_ci.py` passou a exigir os cabeçalhos de privacidade em ambos os endpoints.

## Limites dos testes

Os testes do PostgreSQL são úteis para validar separação lógica e **não** constituem homologação do banco do aparelho, conta bancária, extratos conciliados, rateio anual, crédito ou consentimentos.

A passagem pelos tests ainda **não** atesta o processo FastAPI rodando no telefone. O backend do aparelho só é considerado validado após observação real da resposta no ambiente FR Finance configurado.

## Política de sincronização

Uma vez que a CI geral esteja verde, retornar **um comando novo de fast-forward** no Termux nativo com o novo SHA. Não enviar novamente os comandos M39091 de restart nem reaplicar SQL 110–113. Os arquivos M39600 **não criam novas migrações SQL versionadas**, portanto `MIGRATIONS_NEW=NONE` no banco local.

**Estado de produção:** `PRODUCTION_RELEASE=BLOCKED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`.

**Atestações ainda exigidas:** 20 gates técnicos, sete provedores, AT-01…AT-50, legal/regulatório e operação financeira reconciliada. Sem habilitação automática por CI.
