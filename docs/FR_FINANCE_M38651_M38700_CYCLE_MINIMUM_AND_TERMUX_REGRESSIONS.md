# FR Finance AI Studio — M38651–M38700 | Piso contratual R$ 150 e regressões Termux

## Evidência de entrada (11/11/2026)

- M38650: commit `ce474d4` sincronizado no Termux.
- Regressão completa: **12.554 passed, 130 skipped, 4 warnings, 0 failed**.
- SQL 043 e 044 constam no catálogo, mas ainda não há prova de aplicação local (`local_evidence=null`).
- E-mail real, Pix real, pagamentos reais, ativação de usuários e produção seguem **OFF/BLOCKED**.

## Escopo de segurança e contrato

A contribuição de cada membro/ciclo deve ser definida explicitamente pelo **administrador da caixinha**, em centavos inteiros, com piso de **15.000 centavos (R$150)**. Esse piso **não** significa uma mensalidade fixa de R$150, nem autoriza alterar o histórico. Os arquivos 043/044 já contêm a implementação SQL de referência; este pacote adiciona proteção de regressão **estática**, sem afirmar que o esquema local está homologado.

As migrações 043 e 044 são migracões locais candidatas e **não devem ser aplicadas automaticamente**. A aplicação exige revisão de precondições, backup verificável, credencial de operador autorizado e verificação posterior da base real; a simples aprovação de CI não é autorização de migração.

### Guardas incluídas

- Verificar 043: remoção dos defaults históricos de R$100; constraints para novas políticas e quotas com `>= 150`, marcadas `NOT VALID` para preservar linhas antigas; wrapper autenticado `cycle_price_change` exige entre 15.000 e 1.000.000 centavos **antes** de delegar ao método legado.
- Verificar revogação do método `cycle_price_change_legacy_m20400` para o papel de aplicação e segregação dos papéis de autenticação.
- Verificar 044: `cycle_open_create` autentica o administrador da caixinha, exige valor explícito no piso, impede conflito de idempotência, mantém auditoria imutável e RLS.
- Confirmar que o 042, usado para histórico, mantém registro e auditoria antiga sem reescrita automática.
- Impedir que auditoria de código seja confundida com licença, consentimento real, identidade real, recebimento bancário ou liberação operacional.

### Qualidade de teste

- `test_m20100_local_parity_schema_ci.py`: troca um iterador `zip` por `list(zip(...))`, compatível com pytest 10; não altera teste SQL.
- `test_m22300_cookie_origin_guard_ci.py`: usa cookie persistente no `TestClient`, em vez do parâmetro obsoleto `cookies=` por requisição; as regras anti-CSRF e respostas 403/503 permanecem exigidas.
- Avisos de dependência externa `anyio.abc.BlockingPortal`/Starlette podem persistir; não atualizar dependências fundamentais sem testes de compatibilidade específicos.

## Execução offline

```sh
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q -p no:cacheprovider backend/tests/test_m38651_cycle_minimum_contract_drift_ci.py backend/tests/test_m20100_local_parity_schema_ci.py backend/tests/test_m22300_cookie_origin_guard_ci.py
python -m pytest -q -p no:cacheprovider backend/tests
```

As verificações listadas não executam o SQL, não conectam à OCI, não fazem requisições à Brevo e não abrem Pix.

## Condições ainda pendentes antes de operação real

1. Prova de versão e estado reais de 043/044 no PostgreSQL original, com validação read-only — nunca presumir aplicação a partir de fontes SQL.
2. Conferir contrato assinado e aderência da interface de abertura de caixinha ao piso e preço variável.
3. Comprovar identidade, consentimento, licença, notificações, integridade financeira e fornecedores de pagamentos em ambiente autorizado.
4. Infraestrutura OCI, TLS/DNS/SMTP, webhooks e condições de uso real dos provedores.
5. Provas funcionais Android ponta a ponta, seguidas de decisão expressa de liberação.

## Limitações

O guard estático detecta alterações indevidas nos arquivos SQL oficiais. Ele **não examina dados financeiros reais**, **não prova deploy**, **não substitui testes de API/Android**, **não declara o catálogo aplicado** e **não desbloqueia ativação**. A aplicação permanece bloqueada para transações reais.
