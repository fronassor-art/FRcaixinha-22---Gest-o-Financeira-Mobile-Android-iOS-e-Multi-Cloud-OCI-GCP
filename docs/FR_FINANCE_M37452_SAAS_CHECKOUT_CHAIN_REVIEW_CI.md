# FR Finance M37452 — cadeia contratual SaaS, revisão estritamente sintética

## Ponto de partida
O M37450 inventariou **3 planos, 2 versões de preço, 0 preparações,
0 pagamentos e 0 licenças** no PostgreSQL original. O M37451 retirou
o pró-rata e as datas fictícias da interface Master. A contratação real
**não** foi iniciada e o banco original não foi alterado.

## Implementação
Arquivo: `backend/app/saas_checkout_chain_ci.py`, função `review_checkout`.

A rotina encadeia, para **avaliação de consistência apenas**:

1. Tenant, identidade do administrador, documento publicado, aceite
   explícito, hash canônico e cronologia publicação → aceite → preparação.
2. Plano, categoria, período, versão de preço imutável, preço mensal,
   preço anual = 10 × mensal e preço do período em centavos inteiros.
3. Referência de intenção `saas:<UUID>`, titular, versão comercial,
   ID de pagamento do provedor, conta coletora da **plataforma**,
   valor e reembolso zero; `live_mode=False`.
4. Revisão de três fontes **sintética** com digestos distintos,
   IDs correlacionados, segregação de quatro atores e evidência recente.

O resultado evolui de `CONTRACT_OFFER_REVIEW_CI_ONLY` para
`PROVIDER_MATCH_REVIEW_CI_ONLY` e
`CI_CHECKOUT_CHAIN_CONSISTENT_REVIEW_ONLY` apenas quando há
consistência dos argumentos hipotéticos. Sem prova de pagamento,
o resultado **não** representa assinatura ou licença efetivada.
Os dados de teste usam valores artificiais, **não** preços comerciais.

## Limites de segurança obrigatórios

- As tags `CI_SYNTHETIC_...` e digestos **não autenticam** origem nem
  substituem PostgreSQL/RLS, consentimento durável, HTTP GET autenticado,
  extrato independente, revisão humana ou verificação operacional.
- Não há endpoint, chamada externa, abertura de conta, escrita em banco,
  emissão de fatura, baixa de pagamento, concessão ou renovação de licença.
- Todos os resultados têm `payment_settled=False`,
  `license_created=False`, `user_activated=False`,
  `pix_authorized=False`, `production_authorized=False` e
  `writes_performed=False`, inclusive o cenário positivo.
- Nenhuma migração deste macropacote deve ser executada no banco
  `frcaixinha_aistudio_dev`, nem em OCI produção.
- M37452 não aumenta a contagem de licenças nem habilita SaaS real.

## Homologação

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37452_saas_checkout_chain_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

A suíte está integrada à `.github/workflows/validacao-atualizacao.yml`.
A aprovação de GitHub Actions e a execução em Termux devem ser
confirmadas **separadamente** antes de declarar M37452 homologado.

## Próxima etapa isolada

M37453: integração de leitura em PostgreSQL **descartável e separado**
e contratos de captura de aceite/preparação por adaptadores autenticados,
com rollback e revisão de RLS; em paralelo, definir o futuro executor
transacional de entitlement e trilha de eventos. A autorização comercial,
infraestrutura OCI e validação de provedor real seguem pendentes.
