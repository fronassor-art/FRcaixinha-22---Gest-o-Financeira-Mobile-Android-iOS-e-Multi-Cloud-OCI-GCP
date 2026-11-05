# FR Caixinha AI Studio — M8000–M8600: prova declarada e recuperação somente leitura

Base conhecida Termux: M7900 f9a111e, FastAPI PID 13126, PostgreSQL 127.0.0.1:5433. Somente repositório AI Studio; não usar FRcaixinha 2.2.

Este incremento contém apenas **oráculos puros de diagnóstico**, sem banco, sem rede, sem autenticação efetiva de provedor, sem dinheiro real. Três documentos que parecem consistentes não provam extrato verdadeiro, recebimento, propriedade nem independência de fontes.

## Checklist de tarefas implementadas em código (não representa aceite financeiro)

### M8000 — estrutura e identidade das três fontes
- [x] 01. Criar contrato explícito de comparação de evidências alegadas.
- [x] 02. Separar leitura de provedor, relatório de settlement e extrato alegado.
- [x] 03. Validar UUID tenant não nulo.
- [x] 04. Validar seller_id decimal e formato.
- [x] 05. Validar ID de operação P_ hexadecimal.
- [x] 06. Validar Order ID e Payment ID estruturados.
- [x] 07. Validar SHA-256 minúsculo.
- [x] 08. Validar identificador documental sem campos pessoais.
- [x] 09. Exigir timestamp com timezone.
- [x] 10. Rejeitar valores monetários negativos, float ou boolean.

### M8100 — separação e centavos
- [x] 11. Rejeitar inconsistência bruto = líquido + taxa.
- [x] 12. Exigir bruto maior que zero e taxa menor que bruto.
- [x] 13. Bloquear alegação de fontes trocadas.
- [x] 14. Bloquear tenant divergente.
- [x] 15. Bloquear seller divergente.
- [x] 16. Bloquear operação divergente.
- [x] 17. Bloquear Order divergente.
- [x] 18. Bloquear Pay divergente.
- [x] 19. Identificar documentos com hash ou referência repetida.
- [x] 20. Detectar divergência em centavos e tarifas.

### M8200–M8300 — classificação e rastreabilidade
- [x] 21. Priorizar seller revogado.
- [x] 22. Priorizar provedora não confirmada.
- [x] 23. Reter disputa/chargeback pendentes.
- [x] 24. Reter reversão/estorno pendente.
- [x] 25. Identificar datas discrepantes superiores a trinta dias.
- [x] 26. Produzir impressão determinística por caso.
- [x] 27. Mudança documental altera impressão do caso.
- [x] 28. Não afirmar certificação de origem em fontes consistentes.
- [x] 29. Retornar hold=true em todos os resultados.
- [x] 30. Retornar false para baixa, ledger, conciliação, payout, fechamento.

### M8400–M8600 — circuito de consultas somente leitura
- [x] 31. Criar política independente de circuit breaker sem rede.
- [x] 32. Exigir conta e tenant íntegros.
- [x] 33. Rejeitar seller bloqueado e vínculo de tenant não validado.
- [x] 34. Limitar tentativas de recuperação a seis por caso.
- [x] 35. Abrir circuito ao chegar a cinco falhas em quinze minutos.
- [x] 36. Impedir reabertura automática sem lease autenticado.
- [x] 37. Calcula cooldown progressivo limitado a 300 segundos.
- [x] 38. Rejeitar datas e contadores inválidos.
- [x] 39. Nunca autorizar GET efetivo apenas pela política.
- [x] 40. Manter todas as flags de efeito financeiro desativadas.
- [x] 41. Adicionar regressão adversarial no job API.
- [x] 42. Expor somente rota health /api/health/features/m8600.
- [x] 43. Manter PR Draft, sem merge e sem migrações Termux.
- [x] 44. Preservar ausência de webhook e payout públicos.
- [x] 45. Não registrar credenciais, saldos reais, CPF nem chaves Pix.

Itens x = código e testes escritos; comprovação CI vem de workflow separado.

## P0 ainda necessários

- Persistência autorizada de revisões e eventos de incidentes em banco staging (migração futura, **não entregue aqui**).
- Identidade criptograficamente vinculada ao worker e tenant, autenticação de revisores e aprovação segregada.
- OAuth Connect homologado, cofre OCI, callbacks webhook HTTPS e GET real autenticado.
- Extrato bancário independente, fonte verificada de fees, saldo, estorno, disputa e settlement.
- Worker contábil serializável atomic_post_once, baixa e comprovantes por transação, autorização regulatória.
- Assinatura e homologação APK em aparelho, AT-01 a AT-50 e correção das divergências contratuais.

Nenhum apply OCI, nenhuma migração 034–040 aplicada no Termux; nenhuma autorização financeira habilitada.
