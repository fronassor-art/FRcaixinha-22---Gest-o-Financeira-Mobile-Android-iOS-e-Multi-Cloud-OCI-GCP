# FR Finance M37440 — diagnostico seguro do preflight bloqueado

O M37439 parou no preflight: SYNTHETIC_BASELINE_CHANGED. A transação
de exclusão NÃO foi iniciada e o banco original permaneceu intacto.

O aplicador compara 18 contagens, nem todas atestadas pelos inventários
anteriores, incluindo ledger_entries, a revisão PENDING_REVIEW e as
restrições PostgreSQL de mínimo R$150. O M37440 não assume a causa:
passa a mostrar somente as contagens agregadas que divergirem, com
valores esperados e observados. Não imprime CPF, usuário, senha,
tokens, IDs ou conteúdos de eventos.

IMPORTANTE: permanece o mesmo bloqueio da migração em qualquer
divergência. O comando preflight só realiza SELECT na base original.
Nenhum banco novo, relaxamento de auditoria ou escrita foi incluído.

Depois de GitHub Actions 6/6, sincronizar Termux fast-forward e
executar APENAS:
  PYTHONDONTWRITEBYTECODE=1 python backend/scripts/aistudio_dev_price_fixture_reset_guarded.py preflight

Se houver divergências, o diagnóstico deve mostrar códigos
M37440_..._EXPECTED e M37440_..._OBSERVED e terminar BLOCKED.
Não executar apply até atualizar a candidata e homologar todos
os controles financeiros e de auditoria.
