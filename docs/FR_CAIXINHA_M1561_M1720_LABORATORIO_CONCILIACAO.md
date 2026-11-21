# FR Caixinha AI Studio — M1561–M1720 (160 controles rastreados)

**Base de partida:** commit `ce33fe55ac629d95e3ab038f0dc29e0170e319bc` (M1560); branch `atualizacao-ai-studio-9b46a63187`, PR #2 Draft. Esta é exclusivamente a frente **AI Studio mobile**, não a FRcaixinha 2.2 privada.

## Entrega técnica de primeira etapa

- Novo motor puro `backend/app/financial_sandbox_reconciliation.py`, totalmente offline e sem SQL: compara fixtures tipadas de supostas respostas GET do provedor com pagamentos esperados por caixa, referência, recebedor, moeda, idempotência e centavos exatos. Registra duplicidade, resposta órfã, estorno integral sintético, disputa e replay de notificações HMAC com janela de tempo.
- Simulação separada de aplicação de valor em parcelas **já vencidas** de empréstimo com estado DESEMBOLSADO/INADIMPLENTE, por antiguidade e hierarquia juros remuneratórios → mora → multa → principal. Proposta e vencimento futuro não são dívida cobrável por esta prévia.
- Checklist de restituição: preserva capital e contestação, só relata declarações de prova e retorna sempre `net_exit_restitution_cents=null`; não calcula nem autoriza compensação ou Pix.
- Endpoint de saúde `/api/health/features/m1720`, não publicado no OpenAPI, fornece apenas contrato de capacidades sem expor saldos/segredos. Testes automatizados `backend/tests/test_m1720_financial_sandbox_ci.py` incluídos no job da API da CI.

**Limite fundamental:** `APPROVED_FIXTURE_ONLY` significa igualdade entre dados **sintéticos**, jamais prova bancária, comprovante oficial, caixa conciliado, autorização de crédito, cobrança, restituição ou fechamento. `simulation_only=True`, `bank_reconciled=False`, `real_payments_enabled=False` e `payout_authorized=False` são invariantes das saídas.

## Status da homologação

- A validação de código por CI no commit desta entrega deve ser verificada **após** o commit; esta matriz não presume PASS.
- Nenhum endpoint de pagamento novo, webhook real, OAuth Connect, migração SQL ou chamada HTTP externa foi criado.
- O banco Termux `5433`, o FastAPI em execução no aparelho, a PR #2 e a infraestrutura Oracle OCI não foram modificados por esta entrega GitHub.
- Para dinheiro real ainda faltam evidências de origem autenticada, armazenamento durable/idempotente e autorização documental/jurídica/operacional independente.

## Matriz — 160 tarefas e distinção de maturidade

`MOTOR_LOCAL` = condição coberta pelo código ou teste sintético deste pacote, **sem validação operacional**. `PENDENTE_OPERACIONAL` = contrato, integração ou operação ainda não entregue. Controles documentais preservados não equivalem a trabalho concluído.

| ID | Frente | Controle | Estado |
|---|---|---|---|
| M1561 | Recebimentos sandbox, segregação de caixas | Chave de operação única | MOTOR_LOCAL |
| M1562 | Recebimentos sandbox, segregação de caixas | Idempotência única no lote | MOTOR_LOCAL |
| M1563 | Recebimentos sandbox, segregação de caixas | Referência externa única no recebedor | MOTOR_LOCAL |
| M1564 | Recebimentos sandbox, segregação de caixas | ID de pagamento único entre tenants | MOTOR_LOCAL |
| M1565 | Recebimentos sandbox, segregação de caixas | Credencial nunca entra na prévia | MOTOR_LOCAL |
| M1566 | Recebimentos sandbox, segregação de caixas | Live mode true rejeitado | MOTOR_LOCAL |
| M1567 | Recebimentos sandbox, segregação de caixas | Collector da plataforma isolado | MOTOR_LOCAL |
| M1568 | Recebimentos sandbox, segregação de caixas | Collectors dos tenants únicos | MOTOR_LOCAL |
| M1569 | Recebimentos sandbox, segregação de caixas | Tenant obrigatório para cotas | MOTOR_LOCAL |
| M1570 | Recebimentos sandbox, segregação de caixas | Tenant obrigatório para parcelas | MOTOR_LOCAL |
| M1571 | Recebimentos sandbox, segregação de caixas | Identidade do recebedor na fixture | MOTOR_LOCAL |
| M1572 | Recebimentos sandbox, segregação de caixas | Referência externa na fixture | MOTOR_LOCAL |
| M1573 | Recebimentos sandbox, segregação de caixas | Moeda BRL na fixture | MOTOR_LOCAL |
| M1574 | Recebimentos sandbox, segregação de caixas | Centavos sem float binário | MOTOR_LOCAL |
| M1575 | Recebimentos sandbox, segregação de caixas | Status aprovado apenas como fixture | MOTOR_LOCAL |
| M1576 | Recebimentos sandbox, segregação de caixas | Resposta do provedor identificada | MOTOR_LOCAL |
| M1577 | Recebimentos sandbox, segregação de caixas | GET real com autenticação do tenant | PENDENTE_OPERACIONAL |
| M1578 | Recebimentos sandbox, segregação de caixas | Credenciais OAuth Connect por tenant | PENDENTE_OPERACIONAL |
| M1579 | Recebimentos sandbox, segregação de caixas | Intenção Pix persistida e idempotente | PENDENTE_OPERACIONAL |
| M1580 | Recebimentos sandbox, segregação de caixas | Confirmação financeira bancária real | PENDENTE_OPERACIONAL |
| M1581 | Webhooks, disputa e idempotência | Assinatura HMAC sintética | MOTOR_LOCAL |
| M1582 | Webhooks, disputa e idempotência | Timestamp de 10 ou 13 dígitos | MOTOR_LOCAL |
| M1583 | Webhooks, disputa e idempotência | Janela de cinco minutos | MOTOR_LOCAL |
| M1584 | Webhooks, disputa e idempotência | Assinatura adulterada bloqueada | MOTOR_LOCAL |
| M1585 | Webhooks, disputa e idempotência | Repetição de request-id identificada | MOTOR_LOCAL |
| M1586 | Webhooks, disputa e idempotência | Conflito de request-id detectado | MOTOR_LOCAL |
| M1587 | Webhooks, disputa e idempotência | Webhook sem GET não libera pagamento | MOTOR_LOCAL |
| M1588 | Webhooks, disputa e idempotência | Webhook para operação desconhecida rejeitado | MOTOR_LOCAL |
| M1589 | Webhooks, disputa e idempotência | Respostas GET repetidas rejeitadas | MOTOR_LOCAL |
| M1590 | Webhooks, disputa e idempotência | Respostas órfãs destacadas | MOTOR_LOCAL |
| M1591 | Webhooks, disputa e idempotência | Status pending bloqueado | MOTOR_LOCAL |
| M1592 | Webhooks, disputa e idempotência | Status in_process bloqueado | MOTOR_LOCAL |
| M1593 | Webhooks, disputa e idempotência | Status rejected bloqueado | MOTOR_LOCAL |
| M1594 | Webhooks, disputa e idempotência | Status cancelled bloqueado | MOTOR_LOCAL |
| M1595 | Webhooks, disputa e idempotência | Chargeback mantém hold | MOTOR_LOCAL |
| M1596 | Webhooks, disputa e idempotência | Mediação mantém hold | MOTOR_LOCAL |
| M1597 | Webhooks, disputa e idempotência | Estorno integral comparado em centavos | MOTOR_LOCAL |
| M1598 | Webhooks, disputa e idempotência | Estorno parcial mantém revisão | MOTOR_LOCAL |
| M1599 | Webhooks, disputa e idempotência | Inbox durável para replay com banco | PENDENTE_OPERACIONAL |
| M1600 | Webhooks, disputa e idempotência | Reconsulta autoritativa sob falha de rede | PENDENTE_OPERACIONAL |
| M1601 | Histórico, provas e livro-razão | Prévia não altera ledger | MOTOR_LOCAL |
| M1602 | Histórico, provas e livro-razão | Não classificar fixture como pagamento real | MOTOR_LOCAL |
| M1603 | Histórico, provas e livro-razão | Separar caixa Master de caixa tenant | MOTOR_LOCAL |
| M1604 | Histórico, provas e livro-razão | Não gerar saldo bancário de dados simulados | MOTOR_LOCAL |
| M1605 | Histórico, provas e livro-razão | Nulos explícitos para dados não comprovados | MOTOR_LOCAL |
| M1606 | Histórico, provas e livro-razão | Instrumentar identificador de documento externo | PENDENTE_OPERACIONAL |
| M1607 | Histórico, provas e livro-razão | Rastrear prova de GET com hash e origem | PENDENTE_OPERACIONAL |
| M1608 | Histórico, provas e livro-razão | Persistir evento autoritativo append-only | PENDENTE_OPERACIONAL |
| M1609 | Histórico, provas e livro-razão | Amarrar ID de evento ao lançamento | PENDENTE_OPERACIONAL |
| M1610 | Histórico, provas e livro-razão | Garantir débito/crédito em transação | PENDENTE_OPERACIONAL |
| M1611 | Histórico, provas e livro-razão | Reverter pagamento preservando trilha | PENDENTE_OPERACIONAL |
| M1612 | Histórico, provas e livro-razão | Conciliar estorno com fato gerador | PENDENTE_OPERACIONAL |
| M1613 | Histórico, provas e livro-razão | Auditar extrato por membro | PENDENTE_OPERACIONAL |
| M1614 | Histórico, provas e livro-razão | Comparar prova bancária e PostgreSQL | PENDENTE_OPERACIONAL |
| M1615 | Histórico, provas e livro-razão | Impedir duplicidade de comprovantes | PENDENTE_OPERACIONAL |
| M1616 | Histórico, provas e livro-razão | Consultar settlement final e transferências | PENDENTE_OPERACIONAL |
| M1617 | Histórico, provas e livro-razão | Verificar RLS e SQL não privilegiado | PENDENTE_OPERACIONAL |
| M1618 | Histórico, provas e livro-razão | Conferir diferenças no livro-razão | PENDENTE_OPERACIONAL |
| M1619 | Histórico, provas e livro-razão | Reconciliar histórico multiempresa | PENDENTE_OPERACIONAL |
| M1620 | Histórico, provas e livro-razão | Homologar restauração do livro-razão | PENDENTE_OPERACIONAL |
| M1621 | Crédito, mora e amortização | Excluir proposta de cobrança | MOTOR_LOCAL |
| M1622 | Crédito, mora e amortização | Exigir status desembolsado ou inadimplente | MOTOR_LOCAL |
| M1623 | Crédito, mora e amortização | Limitar leitura a 120 parcelas | MOTOR_LOCAL |
| M1624 | Crédito, mora e amortização | Ordenar pela data mais antiga | MOTOR_LOCAL |
| M1625 | Crédito, mora e amortização | Desempatar ordem por ID estável | MOTOR_LOCAL |
| M1626 | Crédito, mora e amortização | Somente vencimentos na data ou anteriores | MOTOR_LOCAL |
| M1627 | Crédito, mora e amortização | Juros futuros excluídos | MOTOR_LOCAL |
| M1628 | Crédito, mora e amortização | Principal futuro excluído | MOTOR_LOCAL |
| M1629 | Crédito, mora e amortização | Juros remuneratórios primeiro | MOTOR_LOCAL |
| M1630 | Crédito, mora e amortização | Mora simples depois | MOTOR_LOCAL |
| M1631 | Crédito, mora e amortização | Multa registrada depois | MOTOR_LOCAL |
| M1632 | Crédito, mora e amortização | Principal por último | MOTOR_LOCAL |
| M1633 | Crédito, mora e amortização | Centavos aplicados conservados | MOTOR_LOCAL |
| M1634 | Crédito, mora e amortização | Saldo excedente não é aplicado | MOTOR_LOCAL |
| M1635 | Crédito, mora e amortização | Inadimplência não se cria via prévia | MOTOR_LOCAL |
| M1636 | Crédito, mora e amortização | Nenhuma amortização contábil executada | MOTOR_LOCAL |
| M1637 | Crédito, mora e amortização | Vincular prova bancária à parcela | PENDENTE_OPERACIONAL |
| M1638 | Crédito, mora e amortização | Recalcular saldo após liquidação real | PENDENTE_OPERACIONAL |
| M1639 | Crédito, mora e amortização | Persistir recibo e reversão auditáveis | PENDENTE_OPERACIONAL |
| M1640 | Crédito, mora e amortização | Quitar antecipadamente sem juros futuros | PENDENTE_OPERACIONAL |
| M1641 | Saída voluntária e restituição | Identidade tenant/membro validada | MOTOR_LOCAL |
| M1642 | Saída voluntária e restituição | Capital registrado em centavos | MOTOR_LOCAL |
| M1643 | Saída voluntária e restituição | Dívida registrada exibida separadamente | MOTOR_LOCAL |
| M1644 | Saída voluntária e restituição | Disputa registrada separadamente | MOTOR_LOCAL |
| M1645 | Saída voluntária e restituição | Não descontar contestação automaticamente | MOTOR_LOCAL |
| M1646 | Saída voluntária e restituição | Não assumir banco conciliado | MOTOR_LOCAL |
| M1647 | Saída voluntária e restituição | Exigir declaração de prova bancária | MOTOR_LOCAL |
| M1648 | Saída voluntária e restituição | Exigir decisão contratual declarada | MOTOR_LOCAL |
| M1649 | Saída voluntária e restituição | Exigir revisão independente declarada | MOTOR_LOCAL |
| M1650 | Saída voluntária e restituição | Nunca inferir restituição líquida | MOTOR_LOCAL |
| M1651 | Saída voluntária e restituição | Nunca autorizar Pix com flags de cliente | MOTOR_LOCAL |
| M1652 | Saída voluntária e restituição | Preservar direitos sobre capital | MOTOR_LOCAL |
| M1653 | Saída voluntária e restituição | Anexar recibo bancário verificável | PENDENTE_OPERACIONAL |
| M1654 | Saída voluntária e restituição | Validar aceitação de cláusula do ciclo | PENDENTE_OPERACIONAL |
| M1655 | Saída voluntária e restituição | Avaliar dívidas efetivamente exigíveis | PENDENTE_OPERACIONAL |
| M1656 | Saída voluntária e restituição | Separar valor em contestação e confirmado | PENDENTE_OPERACIONAL |
| M1657 | Saída voluntária e restituição | Calcular restituição após prova independente | PENDENTE_OPERACIONAL |
| M1658 | Saída voluntária e restituição | Calendário formal de restituição | PENDENTE_OPERACIONAL |
| M1659 | Saída voluntária e restituição | Reversão de restituição por estorno | PENDENTE_OPERACIONAL |
| M1660 | Saída voluntária e restituição | Homologar fluxo completo de saída | PENDENTE_OPERACIONAL |
| M1661 | Fechamento anual líquido e Capital-Dias | Cotas não viram lucro SaaS | MOTOR_LOCAL |
| M1662 | Fechamento anual líquido e Capital-Dias | Não converter fixture em receita realizada | MOTOR_LOCAL |
| M1663 | Fechamento anual líquido e Capital-Dias | Prévia sem autorização de fechamento | MOTOR_LOCAL |
| M1664 | Fechamento anual líquido e Capital-Dias | Reconciliar juros efetivamente recebidos | PENDENTE_OPERACIONAL |
| M1665 | Fechamento anual líquido e Capital-Dias | Reconciliar perdas reconhecidas | PENDENTE_OPERACIONAL |
| M1666 | Fechamento anual líquido e Capital-Dias | Reconciliar despesas documentalmente | PENDENTE_OPERACIONAL |
| M1667 | Fechamento anual líquido e Capital-Dias | Travar ajuste sem aprovação independente | PENDENTE_OPERACIONAL |
| M1668 | Fechamento anual líquido e Capital-Dias | Calcular resultado por competência | PENDENTE_OPERACIONAL |
| M1669 | Fechamento anual líquido e Capital-Dias | Validar política vigente por ciclo | PENDENTE_OPERACIONAL |
| M1670 | Fechamento anual líquido e Capital-Dias | Segregar taxa administrativa 15% | PENDENTE_OPERACIONAL |
| M1671 | Fechamento anual líquido e Capital-Dias | Reservar 85% conforme contrato | PENDENTE_OPERACIONAL |
| M1672 | Fechamento anual líquido e Capital-Dias | Aplicar pesos Capital-Dias V2 | PENDENTE_OPERACIONAL |
| M1673 | Fechamento anual líquido e Capital-Dias | Estabilizar desempate maiores restos | PENDENTE_OPERACIONAL |
| M1674 | Fechamento anual líquido e Capital-Dias | Registrar carteira técnica segregada | PENDENTE_OPERACIONAL |
| M1675 | Fechamento anual líquido e Capital-Dias | Proteger reservas de disputas | PENDENTE_OPERACIONAL |
| M1676 | Fechamento anual líquido e Capital-Dias | Impedir fechamento com cronograma incompleto | PENDENTE_OPERACIONAL |
| M1677 | Fechamento anual líquido e Capital-Dias | Simular rateio sem distribuir | MOTOR_LOCAL |
| M1678 | Fechamento anual líquido e Capital-Dias | Aprovar conciliação anual independente | PENDENTE_OPERACIONAL |
| M1679 | Fechamento anual líquido e Capital-Dias | Emitir recibos com prova de liquidação | PENDENTE_OPERACIONAL |
| M1680 | Fechamento anual líquido e Capital-Dias | Habilitar fechamento apenas após homologações | PENDENTE_OPERACIONAL |
| M1681 | FastAPI, Android e controle de acesso | Endpoint de contrato m1720 read-only | MOTOR_LOCAL |
| M1682 | FastAPI, Android e controle de acesso | Não publicar fixtures no OpenAPI | MOTOR_LOCAL |
| M1683 | FastAPI, Android e controle de acesso | Não expor token do provedor em contrato | MOTOR_LOCAL |
| M1684 | FastAPI, Android e controle de acesso | No-store na rota de saúde | MOTOR_LOCAL |
| M1685 | FastAPI, Android e controle de acesso | Identidade AI Studio explícita | MOTOR_LOCAL |
| M1686 | FastAPI, Android e controle de acesso | Testar retorno do contrato de saúde | MOTOR_LOCAL |
| M1687 | FastAPI, Android e controle de acesso | Prévia de obrigações por membro preservada | PENDENTE_OPERACIONAL |
| M1688 | FastAPI, Android e controle de acesso | Master nunca lê saldos tenant | PENDENTE_OPERACIONAL |
| M1689 | FastAPI, Android e controle de acesso | Membro apenas seu vínculo | PENDENTE_OPERACIONAL |
| M1690 | FastAPI, Android e controle de acesso | Admin apenas seu tenant | PENDENTE_OPERACIONAL |
| M1691 | FastAPI, Android e controle de acesso | GET autorizado de conciliação futura | PENDENTE_OPERACIONAL |
| M1692 | FastAPI, Android e controle de acesso | Consulta bancária via backend apenas | PENDENTE_OPERACIONAL |
| M1693 | FastAPI, Android e controle de acesso | Nenhuma flag de Pix real no cliente | PENDENTE_OPERACIONAL |
| M1694 | FastAPI, Android e controle de acesso | Parser TypeScript de extrato conciliado | PENDENTE_OPERACIONAL |
| M1695 | FastAPI, Android e controle de acesso | Painel Android do estado de reconciliação | PENDENTE_OPERACIONAL |
| M1696 | FastAPI, Android e controle de acesso | Aviso visual de prova pendente | PENDENTE_OPERACIONAL |
| M1697 | FastAPI, Android e controle de acesso | Retorno seguro de falha de rede | PENDENTE_OPERACIONAL |
| M1698 | FastAPI, Android e controle de acesso | Sessão expirada limpa prévia | PENDENTE_OPERACIONAL |
| M1699 | FastAPI, Android e controle de acesso | Teste de APK no dispositivo | PENDENTE_OPERACIONAL |
| M1700 | FastAPI, Android e controle de acesso | Teste de isolamento em dois tenants reais de homologação | PENDENTE_OPERACIONAL |
| M1701 | CI, segurança, OCI e governança | Mais de 200 combinações de centavos | MOTOR_LOCAL |
| M1702 | CI, segurança, OCI e governança | Mais de 150 valores de imputação | MOTOR_LOCAL |
| M1703 | CI, segurança, OCI e governança | Testes de sandbox approved sem liquidação | MOTOR_LOCAL |
| M1704 | CI, segurança, OCI e governança | Testes de assinatura inválida | MOTOR_LOCAL |
| M1705 | CI, segurança, OCI e governança | Testes de webhook repetido | MOTOR_LOCAL |
| M1706 | CI, segurança, OCI e governança | Testes de reversão e disputa | MOTOR_LOCAL |
| M1707 | CI, segurança, OCI e governança | Testes multiempresa sem cruzamento | MOTOR_LOCAL |
| M1708 | CI, segurança, OCI e governança | Teste de tentativa live-mode | MOTOR_LOCAL |
| M1709 | CI, segurança, OCI e governança | Teste de saída sem desconto | MOTOR_LOCAL |
| M1710 | CI, segurança, OCI e governança | Teste do contrato de saúde m1720 | MOTOR_LOCAL |
| M1711 | CI, segurança, OCI e governança | Job pytest incluído na CI | MOTOR_LOCAL |
| M1712 | CI, segurança, OCI e governança | Rastrear matriz M1561–M1720 | MOTOR_LOCAL |
| M1713 | CI, segurança, OCI e governança | Manter PR 2 em Draft | PENDENTE_OPERACIONAL |
| M1714 | CI, segurança, OCI e governança | Não executar merge automático | PENDENTE_OPERACIONAL |
| M1715 | CI, segurança, OCI e governança | Não executar push forçado | PENDENTE_OPERACIONAL |
| M1716 | CI, segurança, OCI e governança | Não executar migração Termux 5433 | PENDENTE_OPERACIONAL |
| M1717 | CI, segurança, OCI e governança | Oracle OCI staging isolado | PENDENTE_OPERACIONAL |
| M1718 | CI, segurança, OCI e governança | Restore criptografado e teste de carga | PENDENTE_OPERACIONAL |
| M1719 | CI, segurança, OCI e governança | Homologação jurídica e operacional | PENDENTE_OPERACIONAL |
| M1720 | CI, segurança, OCI e governança | Go-live depende de autorização expressa | PENDENTE_OPERACIONAL |

## Pendências operacionais mais urgentes (não sanadas por fixtures)

1. Mercado Pago Connect OAuth segregado por tenant, com credenciais fora do app, HTTP seguro e prova GET **real** do recebedor correto; inbox persistente idempotente e tratamento de replay/chargeback sob transação SQL. Só implementar com sandbox oficial e contas de teste autorizadas.
2. Evidências independentes por competência de contribuição, parcelas de empréstimo e lançamentos de contrapartida. Não confundir valor registrado na API com instituição financeira.
3. Decisão contratual aplicável ao ciclo e direitos de membro em saída, incluindo contestação, autorização de desconto e confirmação bancária de restituição.
4. Receitas e despesas líquidas, Capital-Dias, rateio segregado, trilha de carteira de resíduos, retenções, provisões e bloqueios de fechamento.
5. Integração Android e testes com usuários sintéticos em ambos os perfis; Oracle OCI staging com segredos, TLS, backup, restore, RLS, carga e evidências.
6. Revisão jurídica e operacional antes de alterar qualquer bloqueio de dinheiro real; PR #2 deverá continuar Draft até autorização explícita.

**Inventário:** 160 controles; 89 classificados MOTOR_LOCAL (inclusive salvaguardas e testes), 71 ainda PENDENTE_OPERACIONAL. Isso não significa 89 integrações prontas.

## Verificação após sincronização (somente leitura)

`git rev-parse --short HEAD`; `curl -fsS http://127.0.0.1:8000/api/health/features/m1720` **após reiniciar FastAPI**; `PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m1720_financial_sandbox_ci.py`.

**Governança:** nenhuma alteração na porta 5433, nenhuma migration local, nenhum dinheiro real, PR Draft sem merge, sem force push e produto AI Studio isolado.