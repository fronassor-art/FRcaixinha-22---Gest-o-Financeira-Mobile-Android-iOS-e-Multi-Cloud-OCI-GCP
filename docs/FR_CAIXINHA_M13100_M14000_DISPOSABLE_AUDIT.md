# AI Studio — M13100–M14000: auditoria física de incidentes em PostgreSQL descartável

Checkpoint de origem: M13000 local \`0e28278\`, FastAPI PID \`27803\`, PostgreSQL local \`127.0.0.1:5433\`, sete contratos PASS.

## Alcance real

Novo projeto de migração \`backend/staging_migrations/040_orders_incident_audit_staging_only.sql\`, **não aplicado ao banco Termux nem à OCI**. O pipeline GitHub Actions executa essa migração APENAS na cópia sintética \`frcaixinha_staging\` criada a partir de \`frcaixinha_ci\`, em PostgreSQL 16 e 18. Sem ativação de Mercado Pago, sem saldo, sem Pix real.

- Tabela ligada por FK composta à retenção M039. Sem incidente retido, não há evento.
- PK \`tenant_id/operation_id/reason_code/sequence\`, índice de pesquisa por tenant e unicidade de digest/evento.
- RLS \`ENABLE\` e \`FORCE\`. Sem privilégios diretos para papéis de usuário, Master, auth, verificador, worker, webhook. Nenhuma política pública.
- Apenas a função \`SECURITY DEFINER\` autorizada ao papel técnico não-superusuário \`frcaixinha_mp_financial_worker\`, com checagem explícita de \`session_user\`, pode incluir eventos de auditoria de homologação, sem liberar hold.
- Encadeamento SHA256 **computado pelo PostgreSQL** com sequência monotônica, predecessor exato e bloqueio transacional por caso.
- Replays idênticos do último evento retornam marcador \`REPLAY\`; divergências e predecessores antigos são recusados.
- Triggers recusam \`UPDATE\`, \`DELETE\` e \`TRUNCATE\` ordinários. Superusuário/DBA ainda pode mudar triggers, função, schema, roles ou banco: **não é armazenamento inviolável nem raiz de confiança assinada**.
- A função não aceita \`RELEASE_HOLD\`, \`MARK_PAID\`, \`LEDGER_POST\`, \`PAYOUT\`. Campos \`bank_reconciled\`, \`financial_effect_applied\`, \`ledger_written\`, \`payout_authorized\` são \`false\` por \`CHECK\`.
- Identidade de operador/revisor não foi verificada; o evento é de origem técnica e só contém digest de uma **alegação**. Não há comprovante de banco nem integração PSP.

## Itens entregues ou ensaiados

1. Guardar DB exata de staging e GUC explícita.
2. Recusar sessão não-superusuária ao criar o esquema.
3. Exigir tabela M039 e dependências M034–039.
4. Exigir worker NOSUPERUSER e NOBYPASSRLS.
5. Isolar schema 040 das migrações locais 001–030.
6. Vincular FK composta à retenção em aberto.
7. Exigir ambiente HOMOLOGACAO nas novas gravações.
8. Exigir operação e tenant bem formados.
9. Exigir motivo de retenção conhecido.
10. Exigir SHA256 sintático de evidência.
11. Exigir SHA256 sintático de predecessor.
12. Fixar conjunto de eventos sem efeitos econômicos.
13. Criar chave composta com sequência monotônica.
14. Criar unicidade por digest.
15. Criar unicidade evento/evidência/predecessor.
16. Habilitar RLS.
17. Forçar RLS.
18. Revogar DML direto de papéis de aplicação.
19. Revogar acesso do Master e autenticação.
20. Revogar acesso do worker à tabela.
21. Habilitar exclusivamente RPC delimitada.
22. Validar session_user real.
23. Serializar concorrência por case com advisory transaction lock.
24. Validar predecessor GENESIS.
25. Validar predecessor anterior para append.
26. Impedir replay conflitante.
27. Retornar replay idêntico sem inserir.
28. Limitar o tamanho da sequência.
29. Computar SHA256 dentro do banco.
30. Criar bloqueio de update com trigger.
31. Criar bloqueio de delete com trigger.
32. Criar bloqueio de truncate com trigger.
33. Recusar eventos que indiquem pagamento.
34. Proibir gravar \`ledger_written=true\`.
35. Proibir gravar \`financial_effect_applied=true\`.
36. Proibir gravar \`bank_reconciled=true\`.
37. Proibir gravar \`payout_authorized=true\`.
38. Provar worker sem insert direto.
39. Provar worker sem select direto.
40. Provar worker sem privilégio de lançar ledger.
41. Provar RPC inacessível pelo papel geral do aplicativo.
42. Provar rejeição de tenant cruzado.
43. Provar rejeição de predecessor antigo.
44. Exercitar cadeia com 2 eventos reais sintéticos no SQL.
45. Testar concorrência para mesma referência em Python asyncpg.
46. Testar imutabilidade física PostgreSQL em transação descartável.
47. Testar controle de tenant e retenção sem vazamento.
48. Testar que rollback da transação cancela evento.
49. Executar os ensaios no pipeline do PostgreSQL 16.
50. Executar os ensaios no pipeline do PostgreSQL 18.
51. Expor rota health apenas diagnóstica M14000.
52. Preservar CI de backend/API, frontend, ZIP e APK.
53. Documentar explicitamente falta de operador autenticado.
54. Documentar explicitamente falta de banco de origem.
55. Documentar superusuário não protegido por RLS/triggers.
56. Documentar falta de integração OCI e de migração local.

## Pendências P0 ainda abertas

- Identidade autenticada e segregada de Master/Admin/Membro/revisores, vinculada à sessão e autorização RLS em banco REAL.
- Auditoria realmente protegida por âncora independente e retenção WORM/assinaturas; dados de staging com backup/restore verificados e chaves em Vault.
- Índices e leases realmente globais para checkout, provider, reembolsos, Order e Payment; atomicidade financeira sob concorrência real.
- OAuth Connect por seller, validação de webhook, statement bancário independente, escrituração e fechamento apenas com autorização.
- Homologação UI em dispositivo, Livro-Razão, Extrato, Anterior/Próxima, AT-01–AT-50.

**Nenhum SQL local/OCI, nenhum merge, nenhum GET real, nenhum dinheiro real.**