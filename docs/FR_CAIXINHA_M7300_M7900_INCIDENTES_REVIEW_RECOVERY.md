# FR Caixinha AI Studio — M7300–M7900, incidentes e recuperação conservadora

Escopo: apenas repositório AI Studio, branch atualizacao-ai-studio-9b46a63187. Base confirmada do Termux: a90e838 (M7200), PostgreSQL local 5433 e FastAPI PID 31337. Este commit remoto não altera o processo Termux até sincronização posterior.

## Objetivo e limites

Criar **lógica testável de triagem e recuperação**, sem qualquer movimento de dinheiro. O registro persistente existente continua na migração 039 **exclusiva de OCI staging** (NÃO aplicada no Termux). O novo encadeamento de hash e a revisão dupla são **pré-visualizações locais**, NÃO possuem gravação autoritativa, assinatura independente ou liberação de hold. Não existe endpoint de pagamento, webhook ativo, token, Pix OUT ou OCI apply neste pacote.

## Entregas verificáveis — checklist de 40 itens

### M7300: classificação e identidade
- [x] 01. Introduzir contrato isolado de triagem de incidentes.
- [x] 02. Reutilizar a enumeração fechada de motivos da migração 039.
- [x] 03. Validar UUID não nulo do tenant.
- [x] 04. Validar operation_id P_ mais 32 caracteres hexadecimais.
- [x] 05. Validar seller_id numérico e com comprimento máximo.
- [x] 06. Exigir fingerprint SHA-256 minúsculo de 64 caracteres.
- [x] 07. Exigir data consciente de timezone.
- [x] 08. Classificar duplicidade e seller revogado como segurança crítica.
- [x] 09. Bloquear estados de pagamento/ledger/payout em todos os resultados.
- [x] 10. Rejeitar enumeração inválida em vez de fallback permissivo.

### M7400: revisão segregada e rastreabilidade
- [x] 11. Definir revisão por dois UUID de operadores distintos.
- [x] 12. Impedir que o relator revise seu próprio incidente.
- [x] 13. Impedir timestamp anterior à abertura.
- [x] 14. Exigir digest anterior válido.
- [x] 15. Gerar digest determinístico do caso e parecer, sem texto sensível.
- [x] 16. Detectar mudança de fingerprint através de hash diferente.
- [x] 17. Permitir encadeamento de revisões como prévia apenas.
- [x] 18. Registrar resultado sempre como HOLD_REMAINS.
- [x] 19. Não oferecer método de release de hold.
- [x] 20. Não registrar a revisão como prova bancária.

### M7500–M7600: listagem segura de divergências
- [x] 21. Receber somente uma caixinha por chamada ao oráculo.
- [x] 22. Recusar lista inteira que contenha tenant distinto.
- [x] 23. Detectar mesma chave com fingerprints conflitantes.
- [x] 24. Deduplicar replays idênticos na prévia.
- [x] 25. Ordenar casos críticos antes dos de revisão.
- [x] 26. Estabilizar a ordenação por tempo e operação.
- [x] 27. Limitar lotes a 1.000 registros e página a 100.
- [x] 28. Rejeitar paginação negativa, booleana ou fora do intervalo.

### M7700–M7900: recuperação segura de Orders
- [x] 29. Programar apenas decisão de GET, sem execução de rede.
- [x] 30. Tratar Order sem identificador conhecido como caso humano.
- [x] 31. Revogação de seller e HTTP 401/403 bloqueiam automaticamente.
- [x] 32. GET processed só encaminha para prova bancária independente.
- [x] 33. GET pending nunca autoriza quitar obrigação.
- [x] 34. Tratar timeout, HTTP 429 e HTTP 503 por retry limitado.
- [x] 35. Backoff exponencial, jitter determinístico e Retry-After limitado.
- [x] 36. Teto de seis tentativas e duas horas; depois escalonar.
- [x] 37. Recusar timestamps, seller, Order e status malformados.
- [x] 38. Incluir testes adversariais de todos os bloqueios.
- [x] 39. Expor saúde /api/health/features/m7900 sem afirmar deployment.
- [x] 40. Executar testes do módulo junto ao job CI da API.

Itens marcados com x indicam **código e testes incorporados ao pacote**, não substituem a evidência de CI, que precisa ser verificada separadamente. Nenhum desses itens encerra uma das 87 pendências operacionais de prova real.

## P0 ainda abertos

- Persistência de revisões com auditoria de operador autenticado, assinatura e trilha imutável real no staging OCI; política de acesso da fila e cursor de banco.
- OAuth Connect e cofre real isolado por tenant, callbacks HTTPS assinados e provedor homologado.
- Extrato autenticado independente, prova de settlement e saldo bancário; rollback e conciliação por PSP.
- Implementação formal e auditada de atomic_post_once; bloqueios de empréstimo, estorno e fechamento.
- Execução de CI, homologação em APK, IAM/Vault/TLS OCI, AT-01 a AT-50, LGPD e aceite jurídico.
- As cinco divergências contratuais 1.6, 1.8, 4.1, 5.3 e 8.2 permanecem abertas.

## Gates imutáveis

real_payments_enabled=false; bank_reconciled=false; ledger_written=false; financial_effect_applied=false; payout_authorized=false; financial_closing_authorized=false; staging_m039_applied_locally=false; oci_staging_deployed=false.

Nenhuma migração 034–039 é executada pelo pacote, nenhuma alteração em banco local é feita pelo código de revisão, a PR #2 permanece em Draft e nenhuma solicitação de merge/produção é feita.
