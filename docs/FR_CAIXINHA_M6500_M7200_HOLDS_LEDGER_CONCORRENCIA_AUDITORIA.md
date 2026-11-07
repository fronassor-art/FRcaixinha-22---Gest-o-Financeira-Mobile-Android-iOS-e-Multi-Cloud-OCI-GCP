# FR Caixinha AI Studio — M6500–M7200: auditoria incremental e pendências

**Escopo exclusivo:** repositório AI Studio `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`. Não trabalhar no projeto independente `FRcaixinha-2.2`, não misturar DBs nem usar sua documentação histórica como autorização de dinheiro real.

**Referência local confirmada antes desta rodada:** Termux `bc2fa520d226ace2eeb0841903477ed56cc4646f` (M6400), FastAPI PID `28527`, PostgreSQL 18 local `127.0.0.1:5433`. **Este pacote NÃO foi sincronizado no Termux até comprovante posterior.**

**Commit de código:** `f80cd1a3e0c354243a0c00dfed45df907f9d8d2d`. Branch `atualizacao-ai-studio-9b46a63187`; PR #2 Draft, não mesclada. [GitHub Actions código #41956305554](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41956305554). Validação final do commit com esta documentação será registrada separadamente.

**Inventário do commit de código:** 594 arquivos Git, 81 módulos Python no backend, 116 testes Python, 38 componentes React, 30 migrações locais, seis scripts SQL staging 034–039 e seis SQL CI. Inventário não equivale a cobertura integral por teste.

## Checklist de entregas M6500–M7200

Critério de baixa técnica: código versionado, teste correspondente e CI associada com resultado PASS. **Nenhuma baixa representa conexão real ao PSP, homologação financeira, acesso OCI ou aceite contratual integral.**

### M6500 — reconciliação sem baixa indevida

- [x] 01. Criar migração **039** exclusiva de staging OCI e explicitamente proibida no Termux.
- [x] 02. Exigir DBA, flag de staging, worker com `NOBYPASSRLS` e cadeia de migrações 034–038.
- [x] 03. Criar tabela de retenções de conciliação por `tenant_id + operation_id + reason_code` com FK composta.
- [x] 04. Tornar a tabela `ENABLE/FORCE ROW LEVEL SECURITY` e revogar permissões de escrita diretas dos workers, app, auth e webhook.
- [x] 05. Persistir apenas o código de motivo e hash de evidência, sem CPF, chave Pix, token, QR nem saldo pessoal.
- [x] 06. Exigir `financial_effect_applied=false`, `ledger_written=false`, `bank_reconciled=false`, `payout_authorized=false` como constraints de linha.
- [x] 07. Preservar retenções sem função de liberação e sem baixa de contribuição ou parcela por evento de webhook.

### M6600 — idempotência e registro de incidentes

- [x] 08. Criar a função SQL `mp_orders_staging_record_hold` com `SECURITY DEFINER` e `session_user` do worker homologado.
- [x] 09. Validar conta vinculada, status pendente/ambíguo, operação existente, ambiente e tenant.
- [x] 10. Proteger concorrência por chave de operação+motivo com `pg_advisory_xact_lock`.
- [x] 11. Repetição idêntica retorna `REPLAY`, conteúdo divergente resulta em exceção, sem atualizar evidência anterior.
- [x] 12. Rejeitar tentativas de adulterar motivo, operação de outro tenant ou hash inválido.
- [x] 13. Criar adaptador Python `StagingReconciliationHolds`, com identidade tenant/seller do servidor e transação de banco.
- [x] 14. Recusar erro de banco e falha de role como bloqueio, sem confirmar retenção fictícia.
- [x] 15. Exercitar comportamento no PostgreSQL 16 e 18 descartáveis como usuário `frcaixinha_mp_financial_worker`.

### M6700 — atomicidade e concorrência contábil descartável

- [x] 16. Executar **INSERT real** de transação e partidas dobradas em `ledger_transactions` e `ledger_entries` de banco CI sintético.
- [x] 17. Comprovar commit de dois lançamentos balanceados com isolação `SERIALIZABLE`.
- [x] 18. Rejeitar e fazer rollback de transação com débito diferente de crédito usando trigger diferido do PostgreSQL.
- [x] 19. Impedir lançamento referenciando conta de outra caixinha por FK composta.
- [x] 20. Impedir duas transações com mesmo `tenant_id + reference_id`.
- [x] 21. Submeter 12 gravações concorrentes à mesma referência e exigir exatamente uma transação com duas partidas.
- [x] 22. Verificar que o ensaio não gerou recibos de Pix real, nem provou movimentação bancária.
- [x] 23. Manter fixtures, credenciais falsas e SQL de ensaio restritos ao GitHub Actions PG16/PG18.

### M6800 — estorno parcial sem apagar histórico

- [x] 24. Criar prévia de estorno **parcial de contribuição** conservando o lançamento original.
- [x] 25. Comprovar débito de capital e crédito de caixa por valor retornado, com taxa PSP devolvida contabilizada em linha separada.
- [x] 26. Suportar PSP reter a taxa ou devolver parte dela, sem presumir equivalência entre bruto, líquido e taxa.
- [x] 27. Bloquear total de estornos maior que o valor original e soma de taxas devolvidas maior que a taxa original.
- [x] 28. Exigir origem autenticada, prova externa independente, data com timezone, referência única e hash.
- [x] 29. Produzir fingerprint determinístico, sem autorização de gravação, refund ou Pix OUT.
- [x] 30. Manter estornos parciais de **parcelas de empréstimo** bloqueados até haver alocação financeira persistida e estorno contábil formal.

### M6900 — reforço no fluxo Orders

- [x] 31. Exigir checkout **previamente persistido**, vinculado à mesma operação, tenant/quantia e `order_id`, antes de consultar o PSP.
- [x] 32. Exigir correspondência entre `payment_id` persistido e retornado no GET Orders.
- [x] 33. Recusar retorno criado do provedor que afirme `ledger_written=true` antes da conciliação.
- [x] 34. Exigir `processed/accredited` tanto para a Order quanto para a transação Pay ao validar prova bancária.
- [x] 35. Rejeitar `datetime` sem timezone efetivo e respostas de estados divergentes.
- [x] 36. Atualizar testes anteriores e acrescentar testes contra ordem ausente, Ordem/PAY adulterados e status pendente forjado.

### M7000–M7200 — CI, bloqueios e governança

- [x] 37. Integrar migração staging 039 e probe 036 de retenções à cadeia descartável.
- [x] 38. Executar o teste PostgreSQL de atomicidade e concorrência exclusivamente no executor GitHub, em ambos PG16 e PG18.
- [x] 39. Preservar a verificação de rollback da migração 034 no banco incorreto.
- [x] 40. Adicionar testes de retenção, estorno parcial, Order persistida e gates M7200 ao job API.
- [x] 41. Criar contrato HTTP de saúde `/api/health/features/m7200` com capacidades de código separadas de integrações operacionais.
- [x] 42. Preservar bloqueio completo de dinheiro real, baixa, payout, ledger de produção e fechamento.
- [x] 43. Manter PR #2 Draft, Issue #3 e rastreabilidade contratual sem merge automático.
- [x] 44. Publicar esta auditoria complementar com responsáveis técnicos e próximas prioridades.
- [x] 45. Não aplicar migrações 034–039 no PostgreSQL `frcaixinha_aistudio_dev` do Termux.
- [x] 46. Manter registros e movimentos reais da plataforma fora do banco fictício do CI.

## Evidências que NÃO equivalem à conclusão

O teste M6700 usa conta `postgres` **somente no container descartável de CI**. Isso exercita as constraints reais do Livro-Razão, mas **não implementa nem valida** o worker de produção, a autenticidade da prova bancária nem o `atomic_post_once` atualmente bloqueado. O teste de idempotência prova o comportamento do banco com fixture sintética, não confirma créditos recebidos.

A migração 039 somente cria **fila de retenção**; não grava prova final no ledger, não liquida uma cobrança, não cria recibo, não envia dinheiro e não autoriza fechar caixa. O método `StagingOrdersJournal.atomic_post_once` permanece explicitamente bloqueado.

O estorno parcial é uma prévia financeira com dados fornecidos ao motor. Em produção, o acumulado de restituições precisa vir do banco autenticado sob bloqueio transacional, e o fato bancário precisa ser confirmado por fonte externa independente.

## Atualização conservadora das 147 cláusulas

Matriz mestre: `docs/AUDITORIA_GERAL_M4800_CHECKLIST_147_2026-11-04.md`; fonte da numeração `docs/CHECKPOINT_CONTRATO_2026-11-01.md`. Não reclassificar nenhuma cláusula para CONCLUÍDO E TESTADO por esta rodada isolada.

| Domínio contratual | Nova evidência | Pendência que permanece |
|---|---|---|
| 2.x e 4.x acesso e isolamento | FKs/roles reais na fila staging; Orders/Pay/tenant conferidos | Worker compartilhado deve ser amarrado criptograficamente à identidade do tenant; auditoria RLS de todas as tabelas |
| 7.x Livro-Razão e tesouraria | Commit, rollback, referência duplicada e concorrência em CI PG16/18 | Worker com prove-seu-direito, saldos externos verdadeiros, lançamento atômico/recibo e reversões reais |
| 8.x empréstimos e Price | Plano contábil e liquidez do M6400 preservados; teste M6700 evita dupla entrada | Reserva financeira efetiva, beneficiário, Money Out autorizado, calendário Price comprovado |
| 9.x Pix/Orders | Checkout persistido obrigatório, PAY correlacionado e retenção de discrepância | Credenciais OAuth Connect/GET reais, webhook HTTPS, conciliação independente e baixa atômica |
| 12.x–14.x proteção e auditoria | Evidência sem PII, hash, FK composta, RLS FORCE e isolamento CI | Revisão independente, LGPD, segredos, backups OCI, logs operacionais |
| 16.x aceite e testes | CI adicional com banco descartável e 46 tarefas registradas | Testes AT-01 a AT-50, E2E reais, Android instalado, stress/pen-test e aceite contratual |

**As cinco divergências históricas continuam abertas:** 1.6 (rifa só demonstrativa), 1.8 (React/Capacitor vs documento Flutter), 4.1 (política tenant), 5.3 (suporte), 8.2 (12 vs 6 parcelas). Requerem aditivo formal para a frente AI Studio, sem mudar o repositório independente 2.2.

## Próximas pendências P0 sem baixa de produção

- [ ] **P0-A** OCI staging com IAM, TLS, Vault, role trust por tenant, backup criptografado, teste de restauração, observabilidade/custos, após autorização.
- [ ] **P0-B** Mercado Pago OAuth Connect real por tenant, prova de seller, PKCE, refresh, revogação e cofre isolado.
- [ ] **P0-C** Serviço de extrato autenticado e independente, com confirmação da efetiva liquidação Pix, taxas, identidade e timestamp.
- [ ] **P0-D** Implementar worker transacional real `atomic_post_once`, com prova bancária não forjável, lock por tenant/obrigação, saldo/recibo/baixa/partidas no mesmo commit.
- [ ] **P0-E** Fonte confiável do cumulativo de estornos/chargeback, alocação de prestações, duplicidade e saldo bancário.
- [ ] **P0-F** Criar fila operacional para revisão manual e resolução auditada de divergências, sem liberar pagamentos por clique.
- [ ] **P0-G** Beneficiário Pix validado, revogação segura, consentimento coletivo, reserva efetiva de caixa e controles por empréstimo.
- [ ] **P0-H** Aprovação comercial explícita do Money Out para concessão de crédito e assinatura digital exigida pelo PSP; testes em ambiente autorizado.
- [ ] **P0-I** Após confirmação de payout, registrar parcelas Price definitivas/ledger, conciliar taxa, mora, multa e inadimplência.
- [ ] **P0-J** Fechamentos anuais, rendimentos e restituições somente após conciliação real e validação de regras.
- [ ] **P0-K** Concluir fluxos Admin/Membro/Master no Android/iOS e homologar AT-01–AT-50.
- [ ] **P0-L** Governança LGPD, análise jurídica/tributária/regulatória e resolução das divergências documentais.

**Gates não negociáveis:** `real_payments_enabled=false`, `bank_reconciled=false`, `ledger_written=false`, `financial_effect_applied=false`, `payout_authorized=false`, `financial_closing_authorized=false`. O programa é SaaS de **gestão**; não deve atuar como banco, instituição de pagamento ou custodiante. Contas dos administradores/tenants permanecem distintas.

