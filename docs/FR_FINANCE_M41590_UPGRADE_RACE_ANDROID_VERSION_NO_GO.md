# M41590 — Concorrência de upgrade/estorno e versionCode compartilhado (NO-GO)

Base: M41580 d54c40693082d711c7ac2955635527f633eb00e6. V2.3 §3.10, CP26-0142, CP26-0268, AT-20. Matriz inalterada; evidência independente pendente.

- Estorno sintético verifica a prova original, aceite, escopo e histórico da aplicação (autor, revisor, hashes, versão, capacidades, prazo, segmentos e auditoria) sem depender de vigência atual ou redução de obrigações.
- Teste PG18 descartável: duas conexões comprovam contenção por tenant, nas duas ordens (aplicação primeiro / estorno primeiro); prova de estorno idempotente, nenhuma reaplicação, auditoria única, capacidade base e períodos/ledger/ciclos preservados.
- M39065 e M39089: versão do APK debug principal derivada de 4.000.000 + distância first-parent ao SHA M41580. Checkout de SHA exato com histórico completo; mesma fonte gera mesmo versionCode em push, PR e repetição. O próximo commit na linha autorizada aumenta a versão; não há garantia entre branches divergentes, que não devem ser usados para distribuição. Não muda pacote, certificado ou instalação. O piso 4.000.000 supera a maior versão comprovada 3.911.027; a versão efetivamente instalada ainda exige aferição no aparelho.
- Testes de contrato preservam assinatura, identidade, rede e bloqueios; o teste de numeração passa a verificar o novo algoritmo em vez dos contadores independentes. Sem SQL modificado, migração, acesso ao banco original, restart, reload, PIX ou pagamentos reais, release ou autorização de produção. Issue #5 aberta. CI pendente até prova no SHA.
