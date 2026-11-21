# FR Caixinha AI Studio — M9500–M10200: isolamento de incidentes integrados

## Base
- Base homologada localmente no Termux: \`34dbdb8\` (M9400), FastAPI PID \`19970\`, PostgreSQL porta \`5433\`.
- Projeto independente **AI Studio**; não misturar repositório/banco FRcaixinha 2.2.
- Esta entrega é de **consistência de claims, em memória e sem I/O**, NÃO de autenticação de fontes, banco, reconhecimento contábil ou pagamento.
- Não existe worker real de conciliação, lease distribuído, assinatura de evento ou trilha imutável criada por este pacote.

## 50 verificações implementadas no código e na suíte automatizada

### M9500 — integridade integrada de cinco componentes
- [x] 01. Reunir incidente, trilha, claims, recovery e circuito em um único pré-voo.
- [x] 02. Exigir tipagem estrita da composição.
- [x] 03. Revalidar incidente e seu fingerprint.
- [x] 04. Revalidar a linha do tempo completa.
- [x] 05. Revalidar fontes declaradas contra regras de centavos.
- [x] 06. Revalidar recuperação M7900.
- [x] 07. Revalidar circuito M8600.
- [x] 08. Vincular tenant de todas as partes.
- [x] 09. Vincular operação de todas as partes.
- [x] 10. Vincular conta seller de todas as partes.

### M9600 — conflitos e cronologia
- [x] 11. Exigir igualdade total do incidente referenciado pela recuperação.
- [x] 12. Bloquear IDs de Orders divergentes.
- [x] 13. Permitir Order ausente somente com investigação manual.
- [x] 14. Bloquear observação de circuito em outro instante.
- [x] 15. Bloquear declarações contraditórias de seller autorizado.
- [x] 16. Bloquear declarações contraditórias de vínculo do tenant.
- [x] 17. Bloquear trilha com evento posterior ao snapshot de recuperação.
- [x] 18. Bloquear evidência alegada com data futura.
- [x] 19. Recusar digest alterado após criação do evento.
- [x] 20. Recusar claims provenientes de outro tenant.

### M9700 — recuperação e hold
- [x] 21. Manter hold ativo em qualquer resultado.
- [x] 22. Não propor GET simples para seller revogado.
- [x] 23. Não propor GET simples para disputa pendente.
- [x] 24. Não propor GET simples para estorno pendente.
- [x] 25. Não propor GET simples para evidência duplicada.
- [x] 26. Não propor GET simples para Order já processada.
- [x] 27. Exigir aprovação simultânea de ambas as políticas para candidato GET.
- [x] 28. Marcar GET como candidato **somente teórico**.
- [x] 29. Retornar false para execução GET real.
- [x] 30. Retornar false para liquidar, ledger, baixa e payout.

### M9800–M9900 — auditoria e relatórios
- [x] 31. Gerar hash composto determinístico por caso.
- [x] 32. Incluir fingerprint da trilha no hash composto.
- [x] 33. Incluir fingerprint das claims no hash composto.
- [x] 34. Incluir decisões conservadoras de recovery/circuit.
- [x] 35. Limitar relatórios agregados a 100 casos.
- [x] 36. Deduplicar casos literalmente idênticos.
- [x] 37. Bloquear replay da operação com histórico diferente.
- [x] 38. Bloquear casos de outra caixinha em resumo agregado.
- [x] 39. Não incluir seller, Order ou operação nos totais agregados.
- [x] 40. Contar prioridades, candidatos teóricos e casos bloqueados.

### M10000–M10200 — fila, CI e governança
- [x] 41. Endurecer M9400 contra snapshots com horários diferentes.
- [x] 42. Endurecer M9400 contra divergência de autenticação declarada.
- [x] 43. Preservar semântica de replay exato.
- [x] 44. Separar candidatos adiados dos bloqueados na fila.
- [x] 45. Testar truncamento por limite de candidatos.
- [x] 46. Testar inconsistência de tenant/seller/Order/horário.
- [x] 47. Testar ausência de autorização econômica mesmo para claims coerentes.
- [x] 48. Adicionar testes M10200 à CI da API.
- [x] 49. Expor contrato de saúde M10200, sem endpoints de operação.
- [x] 50. Preservar bloqueios OCI, autenticação bancária, Pix OUT e merge.

## Pendências P0 não encerradas

1. Autenticação criptograficamente verificável de fontes bancárias; OAuth Connect por tenant; acesso a extrato e settlement independentemente validados.
2. Identidade e segregação reais dos revisores, persistência append-only no banco autorizado, detecção de alterações e prova de restauração.
3. Worker transacional integrado com rate limit persistido e lease, tratamento de timeout e idempotência; SQL staging validado e aplicado apenas após aprovação em ambiente segregado.
4. \`atomic_post_once\`, ledger fechado a dupla entrada, reconciliação, emissão de comprovantes, estornos, limites financeiros e Pix OUT só após autorização.
5. OCI IAM/Vault/TLS/backup e runbooks; testes de APK em três perfis, AT-01 a AT-50 e divergências contratuais.

**Sem migração nova; sem acesso financeiro real; sem SQL local; sem OCI apply.**
