# FR Caixinha AI Studio — M8700–M9400: trilha de incidentes e fila GET prévia

**Base local comprovada pelo Termux:** M8600, commit 336fd12; FastAPI PID 28350; PostgreSQL 127.0.0.1:5433. **Escopo exclusivo AI Studio.** Não usar FRcaixinha 2.2 nem seu banco.

O código versionado aqui é apenas um **oráculo determinístico e sem I/O**. Um hash encadeado pode detectar adulteração dentro de um conjunto de entradas fornecidas, mas não prova assinatura digital, identidade autenticada, presença em armazenamento imutável ou conciliação com o banco. Listas de possíveis GET não conferem permissão para executar GET no provedor.

## Checklist incremental — 55 tarefas de código

### M8700 — trilha de eventos e identidade
- [x] 01. Identificar operação, tenant e motivo de incidente.
- [x] 02. Reutilizar a validação rígida do M7900.
- [x] 03. Criar conjunto fechado de seis ações documentais.
- [x] 04. Exigir primeiro evento OPENED.
- [x] 05. Exigir relator como autor do evento inicial.
- [x] 06. Exigir digest zero inicial.
- [x] 07. Exigir índice sequencial de 1 a 1.000.
- [x] 08. Exigir UUID de autor não nulo.
- [x] 09. Recusar data sem timezone.
- [x] 10. Normalizar datas UTC no fingerprint.

### M8800 — revisão dupla e controles de integridade
- [x] 11. Exigir revisores diferentes em DUAL_REVIEW_RECORDED.
- [x] 12. Impedir que relator atue como revisor.
- [x] 13. Recusar revisor adicional nas outras ações.
- [x] 14. Bloquear índice booleano ou negativo.
- [x] 15. Bloquear reabertura indevida da trilha.
- [x] 16. Recusar hash anterior malformado.
- [x] 17. Recusar digest adulterado.
- [x] 18. Recusar payload de outro tenant.
- [x] 19. Recusar alteração de motivo ou evidência.
- [x] 20. Recusar autor diferente sem recomputação.

### M8900–M9000 — validação integral da trilha
- [x] 21. Verificar a sequência de todos os eventos.
- [x] 22. Conferir vínculo de digest entre eventos.
- [x] 23. Recusar datas retroativas na linha do tempo.
- [x] 24. Recusar reordenação e repetições.
- [x] 25. Recusar trilha vazia.
- [x] 26. Limitar verificação a 1.000 eventos.
- [x] 27. Comparar fingerprints em tempo constante.
- [x] 28. Preservar hold ativo após revisão.
- [x] 29. Não afirmar identidade de operador autenticada.
- [x] 30. Não habilitar escritura, quitação, payout ou liberação.

### M9100–M9200 — contadores seguros por caixinha
- [x] 31. Gerar apenas contagens agregadas, sem operação, seller ou hash.
- [x] 32. Exigir tenant explícito.
- [x] 33. Impedir mistura de tenants.
- [x] 34. Detectar duplicata com metadados modificados.
- [x] 35. Deduplicar cópias exatas.
- [x] 36. Resumir motivos e níveis de prioridade.
- [x] 37. Limitar lote a 1.000 incidentes.
- [x] 38. Não afirmar autenticação das fontes dos contadores.
- [x] 39. Bloquear efeitos financeiros nos resumos.
- [x] 40. Impedir dados pessoais no relatório agregado.

### M9300–M9400 — fila segura GET-only
- [x] 41. Criar previsão de consulta por tenant e seller.
- [x] 42. Cruzar política de recuperação M7900 e circuito M8600.
- [x] 43. Exigir contexto igual entre os dois oráculos.
- [x] 44. Bloquear seleção por seller revogado.
- [x] 45. Não selecionar Order processada como candidato simples GET.
- [x] 46. Não selecionar circuito aberto.
- [x] 47. Recusar lotes acima de 100.
- [x] 48. Limitar candidaturas padrão a três.
- [x] 49. Limitar configuração de 1 a 10 candidaturas.
- [x] 50. Recusar repetição de operação com payload divergente.
- [x] 51. Deduplicar replay idêntico.
- [x] 52. Impedir alegação de GET executado e rate limit persistido.
- [x] 53. Registrar contrato HTTP somente de capacidades M9400.
- [x] 54. Incluir testes adversariais no job CI da API.
- [x] 55. Manter PR em Draft e zero migração, OCI, PSP, dinheiro real.

**A marcação de tarefas acima representa funcionalidades preparadas e testáveis, não autorização operacional.** Verificar GitHub Actions separadamente após o commit.

## Pendências P0 preservadas

- Persistência e assinatura autenticada da trilha de auditoria em banco staging autorizado, com verificação real da identidade e segregação dos operadores.
- Worker que consulta provedor com conexão/credenciais seguras, rate limit distribuído, lease, idempotência e escopo tenant/seller.
- OAuth Connect, Vault, webhook HTTPS assinado, GET Orders autenticado, extrato bancário e settlement independentes.
- Contabilização transacional atomic_post_once, estornos reais, saldos, comprovantes, Pix OUT e consentimento jurídico.
- RLS, testes de estresse, backups/restore OCI, APK em três perfis, AT-01 a AT-50 e cinco divergências contratuais.

**Não inclui migração 040 nem qualquer SQL novo.** Nenhum banco local é alterado e nenhuma operação bancária é realizada.
