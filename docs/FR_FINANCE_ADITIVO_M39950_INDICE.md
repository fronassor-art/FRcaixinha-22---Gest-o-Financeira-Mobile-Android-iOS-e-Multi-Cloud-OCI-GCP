# FR Finance — Aditivo M39950 ao contrato de engenharia

Esta adição complementa os índices documentais
`docs/FR_FINANCE_ADITIVOS_M39900_M39920_INDICE.md` e
`docs/FR_FINANCE_ADITIVOS_M39930_M39940_INDICE.md`.

**O Caderno Mestre e o Contrato Técnico Mestre selados pelo M39100
não foram reescritos**. Os 330 requisitos/2310 etapas previamente
indexados permanecem com hashes originais e prova separada;
esse aditivo não é uma nova autorização comercial, jurídica ou bancária.

## M39950 — Revisão documental não autenticada

- O documento por evento, tenant, fingerprint de diário e digest de
  conteúdo é associado a **duas declarações de revisão propostas**.
- São recusados mesma pessoa alegada como preparador e revisor,
  repetição de revisor, revisão de outro tenant, hash incompatível
  e decisões que indiquem pagamento ou aprovação definitiva.
- A versão CI do catálogo experimental usa FK composta, unicidade
  de referência, RLS/FORCE, role de somente leitura, gatilhos
  que bloqueiam edições e `ROLLBACK` completo.
- **Nenhuma afirmação ou hash se torna prova de assinatura, poderes
  do usuário, recebimento do provedor, saldo, rateio devido ou saque.**
- A execução ocorre exclusivamente no PostgreSQL 18 descartável
  `frcaixinha_ci` do GitHub Actions, não no FR Finance original
  (porta 5433) nem no banco separado do FR Caixinha 2.2.
- Documento técnico:
  `docs/FR_FINANCE_M39950_CADEIA_REVISAO_EVIDENCIAS.md`.

**Bloqueios:** `MIGRACOES_LOCAIS=NONE`,
`DB_WRITES_ORIGINAL=NONE`, `PIX_REAL=OFF`,
`PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`,
`PRODUCAO=BLOCKED`. Qualquer persistência real exigirá
projeto novo de migração, RLS server-authenticated, provas,
backup e autorização específica antes de tocar nos bancos locais.
