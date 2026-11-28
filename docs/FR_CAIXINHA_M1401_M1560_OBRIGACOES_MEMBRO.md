# FR Caixinha AI Studio — M1401–M1560 (160 controles)

**Data:** 04/11/2026. **Baseline validada no Termux:** `2d818051f5ea8ca57671ca0f132f5ef6b092878c` (M1400, CI #235 6/6 PASS). Branch `atualizacao-ai-studio-9b46a63187`, PR #2 DRAFT. Projeto AI Studio independente de qualquer FRcaixinha 2.2 privado.

## Entrega de implementação

### Novo motor `backend/app/member_obligation_audit.py`
- Calcula **apenas saldos e cronogramas cadastrados** por tenant/ciclo/membro, com centavos inteiros, referências únicas e validação estrita.
- Distingue contribuições futuras, atualmente exigíveis pelo calendário, e vencidas sem quitação registrada; pagamento registrado NÃO comprova banco.
- Distingue empréstimos **SOLICITADO/APROVADO/RESERVADO** de **DESEMBOLSADO/INADIMPLENTE**. Mesmo com parcelas na tabela, proposta **não** vira dívida.
- Nos empréstimos marcados como desembolsados, separa **principal/juros com vencimento na data ou anterior** de principal/juros agendados para o futuro. Mora e multa seguem INDETERMINADAS (nem zero nem lançadas) sem cálculo específico conciliado.
- Rejeita parcelas órfãs, duplicadas, fora do tenant e status quitado com saldo aberto. Empréstimo desembolsado sem cronograma informa `INCOMPLETE_REGISTERED_LOAN_SCHEDULE`.
- Não decide elegibilidade para lucro, não desconta do capital do membro e não determina restituição: `net_exit_restitution_cents=null`; `bank_reconciled=false`; `sanction_applied=false`; `closing_authorized=false`; `payout_authorized=false`.

### Backend e UI integrados
- `GET /api/v1/tenants/{tenant_id}/cycles/{year}/member-obligations/me?as_of=YYYY-MM-DD`: acesso ao próprio vínculo, somente papel membro.
- `GET /api/v1/tenants/{tenant_id}/cycles/{year}/member-obligations/members/{membership_id}?as_of=YYYY-MM-DD`: acesso administrativo restrito ao tenant. MASTER e cross-tenant bloqueados.
- SQL SELECT + RLS nas tabelas já migradas localmente; **nenhuma migration adicional** é necessária para esta prévia, e nenhuma query grava dados.
- `src/services/memberObligationsBoundary.ts`: parser de contrato fechado, sem saldo bancário, renda Master, autorização de pagamento ou restituição.
- `src/components/MemberObligationsPanel.tsx`: prévia individual/administrativa com seletor de membro e data, detalhes de contribuições, propostas, parcelas atuais/futuras e ausência de conciliação. Integrada em `MemberAnnualPreviewView`.

### Evidências de teste previstas no SHA do pacote
- Testes puros Python parametrizados com centenas de combinações de centavos, datas, propostas e parcelas; API TestClient/unitário sem banco garantindo 403, 404, 422, 503 e SELECT-only; parser TypeScript com dados malformados e centenas de variantes seguras.
- Integração PostgreSQL 16/18 **somente CI efêmero**: duas caixinhas e três perfis; confere que proposta sintética de R$ 500 não gera dívida; atualiza um empréstimo sintético para estado desembolsado no laboratório para verificar o cronograma, comparando SQL independente com a API.
- CI executa seis gates: frontend, API, PostgreSQL 16, PostgreSQL 18, ZIP fonte e APK Android. **Não declarar PASS antes de verificar o resultado da CI no SHA exato.**

## Separação de aprovação jurídica e desenvolvimento
Implementação e testes podem avançar antes da fase jurídica. A fase de dinheiro real deve aguardar homologação técnica, avaliação jurídica e autorizações. Nenhuma movimentação Pix, cobrança, liberação de empréstimo ou liquidação foi feita neste pacote. O CI usa `frcaixinha_ci` na porta 5432, não o banco Termux 5433.

## Matriz de controles

`IMPLEMENTADO/TESTE NOVO, CI PENDENTE` indica que o comportamento foi codificado e submetido a verificações, mas precisa de execução PASS. `PENDENTE DE INTEGRAÇÃO OPERACIONAL` significa que o fluxo completo ainda não foi entregue; não promover a concluído pela simples inclusão na matriz.

| ID | Frente | Controle | Estado |
|---|---|---|---|
| M1401 | Segurança e identidade | Consulta autenticada por sessão | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1402 | Segurança e identidade | Master não consulta obrigações de membro | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1403 | Segurança e identidade | Membro só consulta o próprio vínculo | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1404 | Segurança e identidade | Administrador seleciona membro do próprio tenant | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1405 | Segurança e identidade | RLS aplicado às contribuições | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1406 | Segurança e identidade | RLS aplicado aos empréstimos | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1407 | Segurança e identidade | RLS aplicado às parcelas | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1408 | Segurança e identidade | Tenant/ciclo/membro verificados | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1409 | Segurança e identidade | Limite de 500 linhas sem truncamento | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1410 | Segurança e identidade | Nenhuma escrita SQL na prévia | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1411 | Contribuições por competência | Conferir competência AAAA-MM | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1412 | Contribuições por competência | Validar data e ano da competência | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1413 | Contribuições por competência | Conferir valor devido exato | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1414 | Contribuições por competência | Conferir valor registrado pago | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1415 | Contribuições por competência | Rejeitar pagamento maior que obrigação | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1416 | Contribuições por competência | Rejeitar quitação com pagamento parcial | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1417 | Contribuições por competência | Rejeitar status PENDENTE com pagamento | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1418 | Contribuições por competência | Rejeitar competência duplicada | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1419 | Contribuições por competência | Separar saldo aberto futuro | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1420 | Contribuições por competência | Contar parcelas vencidas ainda abertas | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1421 | Empréstimos | Distinguir SOLICITADO de desembolsado | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1422 | Empréstimos | Distinguir APROVADO de desembolsado | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1423 | Empréstimos | Distinguir RESERVADO de desembolsado | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1424 | Empréstimos | Considerar DESEMBOLSADO no cronograma | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1425 | Empréstimos | Considerar INADIMPLENTE no cronograma | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1426 | Empréstimos | Não cobrar empréstimo proposto | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1427 | Empréstimos | Exigir data real de desembolso para estado ativo | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1428 | Empréstimos | Não somar juros futuros aos devidos atuais | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1429 | Empréstimos | Separar principal atual do futuro | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1430 | Empréstimos | Rejeitar empréstimo quitado com saldo de parcela aberto | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1431 | Integridade de parcelas | Exigir ID e tenant válidos | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1432 | Integridade de parcelas | Validar numeração de parcela | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1433 | Integridade de parcelas | Rejeitar ID repetido | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1434 | Integridade de parcelas | Rejeitar número repetido por empréstimo | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1435 | Integridade de parcelas | Conferir total de principal e juros | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1436 | Integridade de parcelas | Não admitir principal pago acima do previsto | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1437 | Integridade de parcelas | Não admitir juros pagos acima do previsto | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1438 | Integridade de parcelas | Evitar multa alterar principal | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1439 | Integridade de parcelas | Rejeitar parcelas órfãs | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1440 | Integridade de parcelas | Detectar empréstimo ativo sem cronograma | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1441 | Calendário e moeda | Centavos inteiros no motor | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1442 | Calendário e moeda | Conversão Decimal estrita na API | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1443 | Calendário e moeda | Vencimento na data conta como atual | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1444 | Calendário e moeda | Vencimento após a data é futuro | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1445 | Calendário e moeda | Vencimento anterior conta como atraso | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1446 | Calendário e moeda | Taxas não capitalizadas pela prévia | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1447 | Calendário e moeda | Juros futuros apenas informativos | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1448 | Calendário e moeda | Totais acima do limite são bloqueados | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1449 | Calendário e moeda | Data de referência configurável | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1450 | Calendário e moeda | Fuso Belem para referência padrão | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1451 | Android e automação | Parser fechado do contrato | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1452 | Android e automação | Rejeitar saldo conciliado inventado | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1453 | Android e automação | Rejeitar restituição líquida inventada | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1454 | Android e automação | Rejeitar permissão de Pix | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1455 | Android e automação | Descarte após troca de sessão | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1456 | Android e automação | Seleção do membro somente para admin | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1457 | Android e automação | Painel legível das obrigações | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1458 | Android e automação | Aviso para empréstimo sem cronograma | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1459 | Android e automação | Teste de contrato do serviço | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1460 | Android e automação | Testes PG16 e PG18 com duas caixinhas | IMPLEMENTADO/TESTE NOVO, CI PENDENTE |
| M1461 | Histórico financeiro | Vincular comprovante do provedor às cotas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1462 | Histórico financeiro | Confirmar efetiva liquidação por contribuição | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1463 | Histórico financeiro | Reconciliar estornos e chargebacks | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1464 | Histórico financeiro | Vincular reembolso ao lançamento original | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1465 | Histórico financeiro | Gerar extrato pessoal por evento | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1466 | Histórico financeiro | Reconstruir capital conciliado por membro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1467 | Histórico financeiro | Preservar comprovante de cada prestação | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1468 | Histórico financeiro | Detectar pagamentos duplicados do provedor | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1469 | Histórico financeiro | Aplicar reserva de disputas bancárias | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1470 | Histórico financeiro | Testar reconciliação sob falha de rede | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1471 | Inadimplência operacional | Avaliar três competências consecutivas após conciliação | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1472 | Inadimplência operacional | Separar 90 dias de atraso da regra contratual | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1473 | Inadimplência operacional | Revisar política aceita por ciclo | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1474 | Inadimplência operacional | Notificar ciência do membro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1475 | Inadimplência operacional | Registrar contestação e documentos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1476 | Inadimplência operacional | Persistir decisão independente | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1477 | Inadimplência operacional | Aplicar bloqueio autorizado de novas operações | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1478 | Inadimplência operacional | Preservar direitos ao capital | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1479 | Inadimplência operacional | Calcular efeitos no lucro após aprovação cabível | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1480 | Inadimplência operacional | Regularizar bloqueios com trilha imutável | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1481 | Amortização e juros | Confirmar Price por cronograma | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1482 | Amortização e juros | Imputar juros remuneratórios vencidos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1483 | Amortização e juros | Imputar mora simples | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1484 | Amortização e juros | Aplicar multa única com histórico | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1485 | Amortização e juros | Imputar principal por último | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1486 | Amortização e juros | Começar pela parcela vencida mais antiga | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1487 | Amortização e juros | Não antecipar juros futuros na quitação | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1488 | Amortização e juros | Gerar recibo de amortização parcial | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1489 | Amortização e juros | Prevenir anatocismo por reprocessamento | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1490 | Amortização e juros | Persistir evento de quitação reconciliado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1491 | Saída voluntária | Consolidar capital confirmado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1492 | Saída voluntária | Consolidar obrigações contratuais | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1493 | Saída voluntária | Separar dívida contestada da confirmada | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1494 | Saída voluntária | Apurar restituição sem juros futuros | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1495 | Saída voluntária | Respeitar direito adquirido ao lucro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1496 | Saída voluntária | Obter revisão independente | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1497 | Saída voluntária | Registrar decisão e aceite | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1498 | Saída voluntária | Notificar calendário de restituição | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1499 | Saída voluntária | Executar Pix apenas em sandbox de testes | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1500 | Saída voluntária | Conciliar estorno e comprovante da restituição | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1501 | Receitas e despesas | Separar cotas do lucro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1502 | Receitas e despesas | Reconciliar juros realizados | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1503 | Receitas e despesas | Reconciliar multas realizadas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1504 | Receitas e despesas | Registrar despesas dedutíveis | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1505 | Receitas e despesas | Registrar perdas documentadas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1506 | Receitas e despesas | Não reclassificar capital como receita | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1507 | Receitas e despesas | Apurar resultado líquido por competência | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1508 | Receitas e despesas | Separar receitas SaaS Master | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1509 | Receitas e despesas | Tratar ajustes e reversões com trilha | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1510 | Receitas e despesas | Exigir aprovação independente de ajuste | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1511 | Capital-Dias e rateio | Reconstruir movimentos diários conciliados | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1512 | Capital-Dias e rateio | Calcular peso por fuso America/Belem | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1513 | Capital-Dias e rateio | Respeitar instante do evento | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1514 | Capital-Dias e rateio | Usar percentuais contratuais do tenant | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1515 | Capital-Dias e rateio | Administradora 15% sobre lucro válido | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1516 | Capital-Dias e rateio | Pool de membros 85% quando aplicável | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1517 | Capital-Dias e rateio | Ponderar Capital-Dias V2 | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1518 | Capital-Dias e rateio | Aplicar maiores restos com desempate estável | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1519 | Capital-Dias e rateio | Guardar resíduos técnicos segregados | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1520 | Capital-Dias e rateio | Não distribuir se existem disputas abertas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1521 | Mercado Pago multiempresa | Implementar OAuth Connect por tenant | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1522 | Mercado Pago multiempresa | Guardar credenciais no backend apenas | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1523 | Mercado Pago multiempresa | Separar cobrador da plataforma | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1524 | Mercado Pago multiempresa | Validar recebedor do tenant | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1525 | Mercado Pago multiempresa | Gerar intenção Pix com chave de idempotência | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1526 | Mercado Pago multiempresa | Consultar status por GET autoritativo | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1527 | Mercado Pago multiempresa | Autenticar webhook e deduplicar | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1528 | Mercado Pago multiempresa | Tratar expiração, estorno e disputa | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1529 | Mercado Pago multiempresa | Conferir valor em centavos exatos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1530 | Mercado Pago multiempresa | Homologar sem dinheiro real | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1531 | Oracle OCI | Infraestrutura de staging isolada | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1532 | Oracle OCI | Banco de homologação independente | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1533 | Oracle OCI | TLS/HTTPS com domínio | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1534 | Oracle OCI | Controle de acesso à rede | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1535 | Oracle OCI | Segredos no OCI Vault | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1536 | Oracle OCI | Backup criptografado verificável | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1537 | Oracle OCI | Restauração em banco descartável | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1538 | Oracle OCI | Testes de fila e concorrência | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1539 | Oracle OCI | Testes de desempenho e observabilidade | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1540 | Oracle OCI | Teste de recuperação de indisponibilidade | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1541 | Fechamento e entrega | Conferir histórico de cada membro | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1542 | Fechamento e entrega | Reconciliar passivos de empréstimos | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1543 | Fechamento e entrega | Reconciliar capital confirmado | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1544 | Fechamento e entrega | Reconciliar caixa de cada empresa | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1545 | Fechamento e entrega | Validar política aceita do exercício | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1546 | Fechamento e entrega | Autorizar fechamento somente após evidências | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1547 | Fechamento e entrega | Gerar rateio e comprovantes | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1548 | Fechamento e entrega | Testar APK no aparelho real | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1549 | Fechamento e entrega | Auditar todos os endpoints e perfis | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1550 | Fechamento e entrega | Concluir homologação OCI antes do jurídico | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1551 | Governança do projeto | Manter PR #2 Draft | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1552 | Governança do projeto | Validar CI do SHA exato | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1553 | Governança do projeto | Não forçar push | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1554 | Governança do projeto | Não migrar banco Termux 5433 | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1555 | Governança do projeto | Não executar pagamentos reais | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1556 | Governança do projeto | Preservar projeto AI Studio separado de FR 2.2 | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1557 | Governança do projeto | Registrar pendências operacionais não entregues | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1558 | Governança do projeto | Não confundir simulação com conciliação | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1559 | Governança do projeto | Abrir fase jurídica após homologação técnica | PENDENTE DE INTEGRAÇÃO OPERACIONAL |
| M1560 | Governança do projeto | Solicitar autorização antes do go-live real | PENDENTE DE INTEGRAÇÃO OPERACIONAL |

## Pendências prioritárias seguintes

1. Reconciliação autoritativa Mercado Pago sandbox para cada recebedor, incluindo plataforma SaaS em caixa separado, assinaturas de webhooks e idempotência.
2. Apuração reconciliada de principal e encargos de empréstimos e obrigações de desligamento; impedir cobrança de juros futuros e preservação de capital.
3. Fechamento anual líquido com evidência bancária real, política vigente, capital-dias e rateio em centavos; não usar status de teste como prova bancária.
4. Implantar Oracle OCI staging isolado e validar backup/restore, permissões, carga e Android com dados sintéticos; só depois realizar fase jurídica e eventual autorização de real-money.
5. PR #2 permanece Draft, sem merge; o banco local 5433 NÃO deve ser migrado por esta entrega.

**Contagem 160 = matriz de tarefas, não declaração de 160 funcionalidades prontas.**
