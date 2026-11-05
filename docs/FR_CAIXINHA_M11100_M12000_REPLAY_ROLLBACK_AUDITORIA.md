# FR Caixinha AI Studio — M11100 a M12000: histórico de incidentes e recuperação sem efeitos reais

**Checkpoint local de origem:** M11000, commit \`fc267d3\`, PostgreSQL local \`127.0.0.1:5433\`, FastAPI PID \`9069\`, contratos M7900–M11000 PASS. **Frente exclusiva AI Studio**, sem qualquer uso de \`FRcaixinha-2.2\`.

## Semântica de segurança

Os resultados desta etapa são **determinísticos e exclusivamente em memória**. A reconstrução de um histórico de entrada pode detectar retrocessos e alterações se **todas as amostras forem fornecidas**. Ela **NÃO** prova que as amostras vieram de um banco, que uma captura não foi omitida, que sobreviveram a reinicialização ou que foram autenticadas por operador/banco. Um SHA-256 encadeado sem chave e sem armazenamento imutável **não é assinatura digital**.

O motor não utiliza SQL, HTTP, serviço de Pix, Mercado Pago, ledger, webhook ou cloud. O status \`ORDER_PROCESSED\` e a existência de três claims de evidência **não** reconhecem recebimento bancário. Todos os campos de quitação e payout ficam permanentemente falsos.

## 60 verificações de implementação e regressão

### M11100 — identidade e origem de histórico
- [x] 01. Exigir tupla de histórico estrita.
- [x] 02. Rejeitar histórico vazio.
- [x] 03. Limitar histórico a 64 snapshots.
- [x] 04. Reutilizar pré-voo integrado M11000 para cada amostra.
- [x] 05. Exigir mesmo tenant em todas as amostras.
- [x] 06. Exigir mesmo seller.
- [x] 07. Exigir mesma operação.
- [x] 08. Exigir incidente de origem idêntico.
- [x] 09. Exigir mesma referência de Order.
- [x] 10. Exigir mesma referência de Payment.

### M11200 — cronologia e replay
- [x] 11. Impedir retrocesso do relógio de observação.
- [x] 12. Deduplicar replay idêntico na mesma data.
- [x] 13. Rejeitar mesmo instante com conteúdo divergente.
- [x] 14. Impedir redução do contador de tentativas.
- [x] 15. Impedir salto de múltiplas tentativas sem amostra correspondente.
- [x] 16. Permitir uma única progressão por observação.
- [x] 17. Permitir observações sem novas tentativas.
- [x] 18. Impedir alteração retroativa da trilha.
- [x] 19. Permitir acréscimo de evento posterior.
- [x] 20. Impedir perda de eventos anteriores.

### M11300 — credenciais e status sem ressuscitação
- [x] 21. Tratar GET 401 como bloqueio de credencial.
- [x] 22. Tratar GET 403 como bloqueio de credencial.
- [x] 23. Recusar recuperação silenciosa de GET 401/403.
- [x] 24. Permitir reobservação bloqueada de 401/403.
- [x] 25. Recusar downgrade de \`ORDER_PROCESSED\` para pendente.
- [x] 26. Permitir atualização pendente → processado como claim sem quitação.
- [x] 27. Recusar restauração de seller revogado sem novo vínculo autenticado.
- [x] 28. Recusar restauração de tenant desvinculado sem nova autenticação.
- [x] 29. Manter retenção durante estados revogados.
- [x] 30. Nunca atribuir autorização de GET real ao histórico.

### M11400 — circuito e resiliência offline
- [x] 31. Recusar retrocesso no início da janela de circuito.
- [x] 32. Recusar desaparecimento de falhas na mesma janela.
- [x] 33. Permitir zerar contagem apenas após nova janela.
- [x] 34. Respeitar validação temporal do circuito existente.
- [x] 35. Respeitar validação dos contadores cruzados existentes.
- [x] 36. Registrar ordem progressiva de snapshots.
- [x] 37. Registrar quantidade de replays suprimidos.
- [x] 38. Não afirmar lock persistente ou lease distribuído.
- [x] 39. Não afirmar autenticidade das revisões.
- [x] 40. Não criar trabalho de rede.

### M11500–M11600 — impressões e verificação
- [x] 41. Encadear SHA256 dos fingerprints por observação.
- [x] 42. Normalizar relógios UTC na composição.
- [x] 43. Incluir tenant, seller, operação, Order e Payment no vínculo.
- [x] 44. Incluir tentativa e instante em cada elo.
- [x] 45. Preservar digest anterior e índice sequencial.
- [x] 46. Recalcular cadeia a partir de todas as entradas.
- [x] 47. Detectar digest adulterado na exportação.
- [x] 48. Preservar indicadores de hold e ausência de efeitos.
- [x] 49. Não alegar assinatura criptográfica ou atestação bancária.
- [x] 50. Registrar que amostras omitidas não podem ser detectadas autonomamente.

### M11700–M12000 — resumo, CI e governança
- [x] 51. Gerar relatório agregado sem IDs de operações.
- [x] 52. Recusar relatórios mistos entre tenants.
- [x] 53. Deduplicar histórico exatamente repetido.
- [x] 54. Recusar histórico divergente na mesma operação.
- [x] 55. Recusar reutilização de Order ID por seller dentro do lote.
- [x] 56. Recusar reutilização de Payment ID por seller dentro do lote.
- [x] 57. Limitar lote a 100 históricos.
- [x] 58. Exercitar identidades sintéticas em testes parametrizados.
- [x] 59. Registrar suíte M12000 no job CI da API.
- [x] 60. Expor rota de capacidades \`m12000\` com todas as flags financeiras em false.

**A marcação de [x] indica implementação proposta em código**, não CI aprovada. Confirmar separadamente execução GitHub Actions antes de sincronizar Termux.

## P0 que continuam abertos

- Persistência **real** auditável, append-only e RLS; migrações de staging autorizadas e idempotência/índices transacionais globais.
- Autenticação efetiva de operadores e revisores, prova de origem bancária, credenciais Connect por tenant e PSP GET assinado.
- Consumo seguro de webhooks, OAuth seller, liquidação real, reconciliação independente, \`atomic_post_once\`, saldos e Pix OUT.
- OCI IAM/Vault/TLS, monitoramento, backup/restore; homologação no aparelho dos perfis Master/Admin/Membro, AT-01 a AT-50.

Não há novos SQL/migrações, OCI apply, Mercado Pago real, ledger ou dinheiro real. A PR deve permanecer Draft e sem merge.
