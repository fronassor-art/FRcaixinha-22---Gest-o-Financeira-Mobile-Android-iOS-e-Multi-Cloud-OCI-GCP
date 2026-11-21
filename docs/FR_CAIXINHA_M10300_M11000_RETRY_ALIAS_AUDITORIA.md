# FR Caixinha AI Studio — Macropacote M10300–M11000 (auditoria offline)

**Ponto de partida comprovado pelo proprietário:** M10200 \`38fa81f\`, FastAPI \`29587\`, PostgreSQL \`127.0.0.1:5433\`, contratos M7900/M8600/M9400/M10200 PASS. Frente **AI Studio somente**, sem qualquer vínculo com FRcaixinha 2.2.

## Alcance e limites

Este pacote corrige problemas reais de **integridade da prévia operacional em memória** e acrescenta dezenas de testes adversariais sintéticos. Não autentica bancos, não chama Mercado Pago, não movimenta capital e não fornece evidência independente de recebimento.

- A impressão SHA256 de um snapshot NÃO é assinatura digital nem trilha de banco imutável.
- O registro de duplicidade funciona apenas **dentro do lote** inspecionado; não é índice persistente entre chamadas, tenants, servidores ou bancos.
- Valores \`seller_approved\` e \`tenant_binding_verified\` ainda são declarações de entrada; um serviço autenticado deverá vinculá-las à sessão e conta reais.
- \`read_candidate_policy_only\` continua sendo **candidato teórico**; jamais concede permissão de executar HTTP GET real.

## M10300–M11000 — 52 verificações de código e CI

### M10300 — fingerprint composto seguro
- [x] 01. Substituir concatenação parcial por serialização JSON canônica ordenada.
- [x] 02. Adicionar domínio/versionamento explícito da impressão M11000.
- [x] 03. Incluir identidade do relator e abertura do incidente.
- [x] 04. Incluir quantidade de eventos de revisão.
- [x] 05. Incluir último tipo de evento.
- [x] 06. Incorporar o hash final da trilha.
- [x] 07. Incorporar o digest das fontes alegadas.
- [x] 08. Incorporar prioridade, motivo e conta seller.
- [x] 09. Incorporar status do GET.
- [x] 10. Incorporar contagem de tentativas.

### M10400 — cronologia e repetição
- [x] 11. Incorporar \`retry_after_seconds\`.
- [x] 12. Incorporar próximo momento de retry.
- [x] 13. Incorporar limites da janela de circuito.
- [x] 14. Incorporar quantidade de falhas observadas.
- [x] 15. Incorporar instante de última falha.
- [x] 16. Incorporar contagem do circuito.
- [x] 17. Normalizar instantes UTC nos campos novos.
- [x] 18. Preservar \`hold_active=true\`.
- [x] 19. Incluir explicitamente ausência de autorização econômica.
- [x] 20. Produzir digest determinístico para mesma entrada.

### M10500 — segurança da fila por conta
- [x] 21. Exigir igualdade dos contadores M7900 e M8600.
- [x] 22. Exigir essa igualdade no oráculo integrado.
- [x] 23. Rejeitar contradição temporal já detectada no M10200.
- [x] 24. Rejeitar seller diferente já detectado no M10200.
- [x] 25. Rejeitar tenant diferente já detectado no M10200.
- [x] 26. Rejeitar duas operações que reutilizam o mesmo Order ID no lote de fila.
- [x] 27. Deduplicar replay da própria operação.
- [x] 28. Preservar GET como candidato não executável.
- [x] 29. Preservar os limites de página e de candidatos.
- [x] 30. Preservar contadores elegível, adiado e bloqueado.

### M10600 — duplicidade em lote
- [x] 31. Vincular Order ID à operação por seller.
- [x] 32. Vincular Payment ID à operação por seller.
- [x] 33. Rejeitar Order repetido com operação diferente.
- [x] 34. Rejeitar Payment repetido com operação diferente.
- [x] 35. Permitir duas operações sintéticas com IDs realmente diferentes.
- [x] 36. Preservar replay literalmente idêntico.
- [x] 37. Bloquear replay alterado.
- [x] 38. Recusar cruzamento de tenant.
- [x] 39. Recusar lote acima de 100 casos.
- [x] 40. Preservar apenas totais agregados em retornos de relatório.

### M10700–M10900 — testes adversariais
- [x] 41. Parametrizar contagens distintas de retry e verificar novo hash.
- [x] 42. Parametrizar discordância de tentativas e exigir bloqueio.
- [x] 43. Parametrizar falhas de circuito e verificar hash.
- [x] 44. Verificar mutação de backoff sem mudança de decisão.
- [x] 45. Verificar mutação da janela de circuito.
- [x] 46. Verificar alteração de status GET mesmo com bloqueio mantido.
- [x] 47. Verificar compartilhamento malicioso de Order.
- [x] 48. Verificar compartilhamento malicioso de Payment.
- [x] 49. Gerar tenants sintéticos adicionais contra mistura.
- [x] 50. Gerar IDs sintéticos adicionais sem colisão.

### M11000 — CI e governança
- [x] 51. Adicionar suíte M11000 à CI da API.
- [x] 52. Expor somente contrato de saúde M11000, com flags de finanças reais em \`false\`.

**Aviso:** itens com [x] são alterações preparadas em código. A aprovação técnica requer confirmação **separada** dos seis jobs GitHub Actions, inclusive APK.

## Pendências P0 não concluídas

- Persistência real append-only de casos/revisões com RLS forte e identidade de operadores autenticada; reconstrução e recuperação após falhas.
- Índices globais e transacionais para Order ID/Payment ID/idempotência; serialização real e leases distribuídos.
- OAuth Connect e segurança de credenciais do Mercado Pago, GET Orders autenticado, webhook assinado e validação independente de extrato/settlement.
- Escrituração \`atomic_post_once\`, reconciliação bancária verdadeira, Pix OUT e fechamento apenas após aprovações jurídicas e técnicas.
- OCI Vault/IAM/TLS/backup/restore, homologação em aparelho dos três perfis e critérios AT-01 a AT-50.

**Sem novas migrações; sem OCI apply; sem conectores financeiros; sem merge para main; nenhum dinheiro real.**
