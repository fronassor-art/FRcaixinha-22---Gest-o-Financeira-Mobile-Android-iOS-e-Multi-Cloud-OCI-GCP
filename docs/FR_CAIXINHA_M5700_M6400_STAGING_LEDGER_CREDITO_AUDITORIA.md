# FR Caixinha AI Studio — M5700–M6400: ensaio SQL, Livro-Razão e crédito

**Frente:** FR Caixinha AI Studio independente, projeto SaaS de gestão financeira automatizada. **Não é banco nem custodiante.** Nunca aplicar este documento ao repositório antigo `FRcaixinha-2.2`.

**Base sincronizada pelo proprietário:** `7025295ca3b19fa529bea71b356b857acd13960f` (M5600, FastAPI PID 30631, PostgreSQL 18 Termux 127.0.0.1:5433). **M5700–M6400 não sincronizado no Termux até confirmação de comando e do SHA final**.

**Branch:** `atualizacao-ai-studio-9b46a63187`; PR #2 Draft, Issue #3 para os bloqueios. **Código:** checkpoint de desenvolvimento `3a1609b7ff5f55d8f77e4f82b784e23cb3c3a31c`. Estado da CI: vincular evidência do run concluído antes de considerar verificado.

## Resumo de arquitetura

**Roteiro correto:** (i) obrigação do membro, (ii) conta Mercado Pago de cada tenant autenticada, (iii) criação Orders idempotente, (iv) webhook HMAC apenas para despertar consulta, (v) GET Orders autenticado, (vi) **extrato/liquidação autenticado independente**, (vii) lançamento no Livro-Razão com transação serializável, comprovante único e reversão documentada.

Todas as funções novas de Livro-Razão/estorno são **planos puros, sem I/O**. O verificador de liquidez é uma **prévia**; os números nunca devem vir do cliente e não concedem crédito, não reservam saldo e não liberam Pix.

## Checklist — entregas versionadas deste pacote

### M5700: cadeia SQL de staging

- [x] 01. Proibir execução do ensaio fora do GitHub Actions descartável por verificações de variáveis, banco, porta e usuário.
- [x] 02. Exigir PostgreSQL em 127.0.0.1:5432 e banco `frcaixinha_ci` já provisionado exclusivamente na CI.
- [x] 03. Proibir se existir previamente banco `frcaixinha_staging` no executor.
- [x] 04. Criar papéis de worker separados, com `NOSUPERUSER` e `NOBYPASSRLS`.
- [x] 05. Clonar banco exclusivamente sintético para `frcaixinha_staging` em cada container temporário.
- [x] 06. Aplicar em ordem SQL 034, 035, 036, 037, 038 com as flags de staging, **sem OCI e sem Termux**.
- [x] 07. Envolver toda a migração 034 em `BEGIN/COMMIT`, evitando migração parcialmente publicada.
- [x] 08. Corrigir regex de Vault OCID em 034/035 sem exceder limite da engine PostgreSQL: sufixo ASCII e `char_length` entre 21 e 525.
- [x] 09. Se a cadeia ou fixtures falharem, falhar a CI e bloquear o APK.
- [x] 10. Verificar existência de SQL staging sem copiar os scripts para `backend/migrations` do Termux.

### M5800: transações e persistência

- [x] 11. Gerar em CI duas caixinhas, membros, ciclos, contribuições e sellers exclusivamente fictícios.
- [x] 12. Exercitar `mp_orders_staging_reserve` executando a função como worker sem privilégios.
- [x] 13. Testar `NEW` na primeira chamada e `EXISTS` no replay idempotente.
- [x] 14. Bloquear tentativa Pix concorrente ainda ativa para a mesma obrigação.
- [x] 15. Bloquear mistura de vendedor, membro, ciclo e tenant.
- [x] 16. Bloquear cobrança acima do saldo de obrigação.
- [x] 17. Gravar identificadores `ORD...`/`PAY...` e QR somente sob reserva válida; replay idêntico versus divergente.
- [x] 18. Impedir QR em reserva com resultado desconhecido/timeout; reconciliação humana do provedor antes de nova tentativa.

### M5900: webhook e papéis de acesso

- [x] 19. Executar como `frcaixinha_mp_webhook_ingest` as funções de resolução de seller e inserção de notification Order.
- [x] 20. Testar `INSERTED` e `REPLAY` sem duplicação em inbox.
- [x] 21. Rejeitar Order conflitante ou evento de outro tenant.
- [x] 22. Exigir que os workers não tenham `INSERT/UPDATE` direto em tabelas financeiras e Livro-Razão.
- [x] 23. Garantir que papel geral de aplicação não receba `EXECUTE` em função de webhook de staging.

### M6000: plano contábil sem efeitos

- [x] 24. Planejar contabilização de contribuição Pix: débito caixa líquido, débito taxa PSP, crédito capital do membro (total bruto).
- [x] 25. Planejar prestação de empréstimo: crédito de principal separado de juros remuneratórios, mora e multa.
- [x] 26. Validar **`débitos = créditos = valor bruto`**, sem float/centavos fracionários.
- [x] 27. Validar IDs da obrigação/Order/PAY e hash do extrato, com fingerprint determinístico do plano.
- [x] 28. Proibir rateio de empréstimo em contribuição ou plano de prestação sem imputação exata.
- [x] 29. Excluir linhas de valor zero e suportar taxas zero e totais na prévia.

### M6100: estorno não destrutivo

- [x] 30. Construir **prévia** de reversão completa invertendo as linhas, sem apagar histórico.
- [x] 31. Exigir prova final externa autenticada, IDs/tenant coincidentes e hash.
- [x] 32. Exigir também estorno total da taxa PSP; estornos parciais, taxa retida e chargebacks distintos permanecem bloqueados.
- [x] 33. Produzir referência idempotente distinta, sem executar baixa ou lançamento.

### M6200: crédito, saldo livre e consentimento

- [x] 34. Calcular saldo livre somente a partir do saldo externo comprovado, menos reservas, Pix pendentes e obrigações líquidas.
- [x] 35. Rejeitar prova bancária vencida (maior que 5 minutos), futura, falsa, outra conta ou outro tenant.
- [x] 36. Exigir aprovação administrativa, membro/ciclo ativos, beneficiário Pix verificado e consentimento atual.
- [x] 37. Impedir duplicidade de tentativa de payout e exigir consentimento coletivo de autoempréstimo.
- [x] 38. Exigir `requested <= saldo livre` e nunca reservar/transmitir valor automaticamente.
- [x] 39. Testar limites de saldo, fuso temporal, conta, titularidade e consentimento com variantes adversariais.

### M6300–M6400: CI, saúde e auditoria

- [x] 40. Acrescentar ensaio SQL aos jobs PostgreSQL 16 e PostgreSQL 18 descartáveis no GitHub Actions.
- [x] 41. Acrescentar testes da cadeia CI, das partidas dobradas, estornos e liquidez ao job de API.
- [x] 42. Criar contrato HTTP `/api/health/features/m6400`.
- [x] 43. Mostrar explicitamente operações reais, extrato externo, journal efetivo, OCI, Money Out e migrações locais como **false**.
- [x] 44. Preservar PR Draft, separação do Master e 147 requisitos no histórico, sem afirmar homologação total.

`[x]` significa **implementação em Git e teste correspondente**, não autorização de produção. Critérios de CI são declarados separadamente no checkpoint final; jamais inferir resultado de execução a partir de existência de código.

## Provas e limites

O ensaio de PostgreSQL no CI usa credenciais fictícias, conta fake de provedor e banco descartável que é destruído ao fim do job. Não demonstra conexão com OCI, capacidade de movimentação Pix, autorização comercial Mercado Pago, atualização de empréstimo após desembolso, ou persistência de ledger real. Os planos produzem `ready_for_database_commit=false`, `ledger_written=false` e `financial_effect_applied=false`. A existência do HTTP health não configura produção.

## Pendências P0 que continuam abertas

- [ ] **P0-01** Autorização para OCI staging, backups, IAM/Vault, monitoramento e configuração da infraestrutura (não executar sem autorização).
- [ ] **P0-02** Revisar as roles reais de staging e as FKs/constraints em ensaio pós-migração antes de qualquer aplicação na OCI. Roles locais `frc_ai_*` não são roles de produção nem worker externo.
- [ ] **P0-03** OAuth Connect real por tenant: PKCE, escopo `offline_access`, rotação Vault, revogação e prova de seller.
- [ ] **P0-04** Runtime Orders de cobrança, notificações HMAC e worker GET autenticado, com recuperação de timeouts.
- [ ] **P0-05** Fonte real independente e autenticada de extrato de transações liquidadas, taxa PSP, correlação e prova imutável.
- [ ] **P0-06** Repositório real de ledger em transação serializável, dupla entrada, idempotência, RLS e recibo único; construir função de posting com provas não forjáveis.
- [ ] **P0-07** Reversões parciais, taxa PSP retida, chargebacks e ajustes contábeis após análise das regras do PSP.
- [ ] **P0-08** Reserva de saldo efetiva no banco, lock por tenant/crédito, limite de caixa e consistência com status de payout.
- [ ] **P0-09** Cadastro, atualização, revogação e verificação de destinatário Pix do membro, minimizando dados pessoais.
- [ ] **P0-10** Money Out com autorização comercial específica para desembolso de empréstimos, assinatura digital do corpo em produção e prova final.
- [ ] **P0-11** Cronograma Price definitivo e atualização de valores do contrato exclusivamente após desembolso efetivo confirmado.
- [ ] **P0-12** Fechamentos anuais com conciliação, distribuição, restituições e estornos reais protegidos.
- [ ] **P0-13** Homologação Android/iOS, perfis Master/Admin/Membro, ataques de tenant e aceites AT-01–AT-50.
- [ ] **P0-14** Avaliação jurídica/regulatória/tributária LGPD do modelo de caixinha e concessão de crédito.
- [ ] **P0-15** Backups cifrados, restauração em staging real, testes de incidentes e custos OCI.
- [ ] **P0-16** Formalizar divergências documentais 1.6, 1.8, 4.1, 5.3, 8.2 na frente AI Studio sem reabrir a frente antiga.

**Referência mestre:** `docs/AUDITORIA_GERAL_M4800_CHECKLIST_147_2026-11-04.md` com 147 cláusulas. Esta auditoria incremental dá baixa apenas em controles de código/CI e não reclassifica cláusulas financeiras como operacionalmente cumpridas.

**Segurança operacional:** não levar `backend/ci_migrations/033–035` nem `backend/scripts/aistudio_staging_chain_ci.sh` ao banco local. Os artefatos CI são para runner GitHub, nunca Termux/OCI real. O script possui guarda fail-closed de ambiente, banco, porta e usuário.
