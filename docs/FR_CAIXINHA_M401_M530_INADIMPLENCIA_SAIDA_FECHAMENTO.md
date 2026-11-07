# FR Caixinha AI Studio — Macropacote M401–M530: 130 controles contratuais

**Data:** 04/11/2026. **Projeto exclusivo:** AI Studio / React + Capacitor / banco próprio. PR #2 Draft, branch `atualizacao-ai-studio-9b46a63187`. Ponto de partida: `30b1148acde8a1aa988c0cd13cd6abdfc478007c`.

## Fontes de verdade verificadas na CI
- `public/assets/aistudio/FRcaixinha_2.2___Caderno_Mestre_LIMPO___147_cl_usulas_94d2a15c.pdf`: 57 páginas, SHA-256 `94d2a15c54d3f5982c09fe78762ae0f1c76e03fa644cb05a6404f5c7b2feb0f6`.
- `public/assets/aistudio/FRcaixinha_2.2___Contrato_T_cnico_Mestre_ORIGINAL_LIMPO_7b28d5d5.pdf`: 38 páginas, SHA-256 `7b28d5d5cf773fb5c35194bce64ebfdfec4d67422bafac4595a6662b4f45f468`.
- Esses são arquivos versionados **neste repositório AI Studio**, com nomes históricos. Não utilizar o repositório, contrato, porta ou banco do projeto FRcaixinha 2.2 independente.

## Regras descobertas nos próprios documentos
**6.5 / 6.6 (Caderno p.20, Contrato p.12–13)**: no tenant inaugural, três contribuições *mensais consecutivas* vencidas e não quitadas provocam exclusão de lucros **de todo o ciclo**, com Capital-Dias=0, **se juridicamente validado**. Prova do histórico e eventual quitação posterior são preservadas. Principal comprovadamente pago é restituível, descontadas apenas obrigações legítimas/documentadas. Saída regular adimplente **preserva direitos adquiridos**. A consequência não pode ser copiada automaticamente para outros tenants. Os 90 dias citados pelo proprietário são alerta separado, não substituto das três competências.

**8.6 (Caderno p.24–25)**: para obrigações do crédito no tenant inaugural, multa única de R$10 por parcela vencida, mora simples 20%/30 sobre principal em atraso, a partir do dia seguinte, imputação à parcela mais antiga: juros vencidos → mora → multa → principal, sem capitalização, sem juros futuros indevidos. Não aplicar automaticamente à contribuição mensal por interpretação de código.

**10.1–10.6 (Caderno p.29–31)**: lucro=recebimentos realizados e conciliados menos custos/perdas/ajustes admitidos; **capital não é lucro**. Percentuais da caixinha do proprietário: 15% administração /85% membros; outras caixinhas usam política própria aceita e fixada por ciclo. Capital-Dias ao fim de cada dia em `America/Belem`; maiores restos, desempate por `membership_id`; carteira técnica segregada não se converte em lucro administrativo. Sem membros elegíveis: segregar a obrigação. Fechamento de 31/12 e liquidação condicional a partir de 10/01 com fases explícitas e provas financeiras.

## Entregas de código deste pacote
- `backend/app/member_cycle_rules.py`: competências, três não quitadas históricas, data de 90 dias separada, gatilho sujeito ao gate legal, principal preservado, saída voluntária, pesos diários e estados sem escrita.
- `backend/app/closing_contract_oracle.py`: apuração líquida com despesas, capital segregado, percentuais variáveis por tenant, maior resto, reserva de membros sem peso, carteira técnica e zero Pix.
- `backend/app/loan_arrears_contract.py`: multa única, mora simples contratual e imputação de parcial sem descapitalização fictícia.
- `backend/app/tenant_exit_rules.py`: encerramento corporativo distinto de cancelamento de licença e desligamento de membro; não extinguir caixinha com capital, dívida, Pix ou reserva pendentes.
- Testes unitários parametrizados: mais de **700 cenários individuais** no pytest, além dos testes históricos; integração PostgreSQL 16 e 18 com dados sintéticos relacionados ao livro e às contribuições.
- O código **não** faz migrations locais, fechamento, cobrança, concessão, estorno ou transferência. Não habilita produção.

## Matriz de 130 controles de auditoria
Um controle rastreável não significa uma feature comercial concluída. A coluna indica a frente de validação do pacote; só será considerada PASS quando CI no SHA final mostrar evidência.

| ID | Área | Controle | Evidência |
|---|---|---|---|
| M401 | Identidade e vínculos | Identidade pessoal única em diversos papéis | Código/CI a verificar |
| M402 | Identidade e vínculos | Vínculo do administrador também como membro | Código/CI a verificar |
| M403 | Identidade e vínculos | Tenant obrigatório em toda avaliação | Código/CI a verificar |
| M404 | Identidade e vínculos | ID distinto de membro em cada caixinha | Código/CI a verificar |
| M405 | Identidade e vínculos | Recusar movimento de tenant cruzado | Código/CI a verificar |
| M406 | Identidade e vínculos | Recusar contribuição de outro membro | Código/CI a verificar |
| M407 | Identidade e vínculos | Recusar duplicação de competência mensal | Código/CI a verificar |
| M408 | Identidade e vínculos | Recusar prova de obrigação duplicada | Código/CI a verificar |
| M409 | Identidade e vínculos | Recusar evento contábil duplicado | Código/CI a verificar |
| M410 | Identidade e vínculos | Não conceder acesso Master ao patrimônio de membros | Código/CI a verificar |
| M411 | Contribuições e evidências | Competência AAAA-MM estrita | Código/CI a verificar |
| M412 | Contribuições e evidências | Dia dez como vencimento central | Código/CI a verificar |
| M413 | Contribuições e evidências | R$ convertido somente em centavos inteiros | Código/CI a verificar |
| M414 | Contribuições e evidências | Parcial e vencida coexistem no histórico | Código/CI a verificar |
| M415 | Contribuições e evidências | Pagamento integral exige data de conciliação | Código/CI a verificar |
| M416 | Contribuições e evidências | QR Pix gerado não é capital confirmado | Código/CI a verificar |
| M417 | Contribuições e evidências | Provar evidência de cada competência | Código/CI a verificar |
| M418 | Contribuições e evidências | Preservar data de quitação tardia | Código/CI a verificar |
| M419 | Contribuições e evidências | Reversão somente por evento compensatório | Código/CI a verificar |
| M420 | Contribuições e evidências | Não gerar principal a partir de dívida pendente | Código/CI a verificar |
| M421 | Inadimplência histórica | Três meses consecutivos vencidos não quitados | Código/CI a verificar |
| M422 | Inadimplência histórica | Ausência de mês entre obrigações quebra sequência | Código/CI a verificar |
| M423 | Inadimplência histórica | Gatilho começa no dia seguinte ao terceiro vencimento | Código/CI a verificar |
| M424 | Inadimplência histórica | Mês quitado antes do gatilho impede sequência | Código/CI a verificar |
| M425 | Inadimplência histórica | Pagamento parcial não equivale a quitação | Código/CI a verificar |
| M426 | Inadimplência histórica | Quitação posterior não apaga gatilho pretérito | Código/CI a verificar |
| M427 | Inadimplência histórica | Retorno após quitação não recupera automaticamente rateio | Código/CI a verificar |
| M428 | Inadimplência histórica | Identificar primeiro evento de inadimplência do ciclo | Código/CI a verificar |
| M429 | Inadimplência histórica | Não apagar comprovantes que causaram bloqueio | Código/CI a verificar |
| M430 | Inadimplência histórica | Não distribuir rateio retroativo para excluído | Código/CI a verificar |
| M431 | Noventa dias e estados | Medir dias de atraso sem confundir com número de competências | Código/CI a verificar |
| M432 | Noventa dias e estados | 90 dias de uma parcela não são três mensais | Código/CI a verificar |
| M433 | Noventa dias e estados | Três mensais podem ocorrer antes de 90 dias | Código/CI a verificar |
| M434 | Noventa dias e estados | Distinguir atraso atual e histórico | Código/CI a verificar |
| M435 | Noventa dias e estados | Guardar maior idade de dívida aberta | Código/CI a verificar |
| M436 | Noventa dias e estados | Rejeitar contagem por dia futuro | Código/CI a verificar |
| M437 | Noventa dias e estados | Contribuição regularizada conserva atraso histórico | Código/CI a verificar |
| M438 | Noventa dias e estados | Status de leitura não é autorização financeira | Código/CI a verificar |
| M439 | Noventa dias e estados | Não bloquear todos os tenants pela regra especial | Código/CI a verificar |
| M440 | Noventa dias e estados | Cotas da caixinha Master não recebem regra do membro | Código/CI a verificar |
| M441 | Controle jurídico e versão contratual | Regra especial só para caixinha do proprietário | Código/CI a verificar |
| M442 | Controle jurídico e versão contratual | Efeito jurídico precisa da aprovação específica | Código/CI a verificar |
| M443 | Controle jurídico e versão contratual | Bloquear cálculo final com histórico não auditado | Código/CI a verificar |
| M444 | Controle jurídico e versão contratual | Bloquear cálculo final com regra legal pendente | Código/CI a verificar |
| M445 | Controle jurídico e versão contratual | Preservar principal mesmo quando sem direito a lucro | Código/CI a verificar |
| M446 | Controle jurídico e versão contratual | Cláusula 6.6 impede confisco automático | Código/CI a verificar |
| M447 | Controle jurídico e versão contratual | Política do outro tenant continua autônoma | Código/CI a verificar |
| M448 | Controle jurídico e versão contratual | Percentuais congelados por ciclo | Código/CI a verificar |
| M449 | Controle jurídico e versão contratual | Motivo e documento da exclusão devem persistir no futuro | Código/CI a verificar |
| M450 | Controle jurídico e versão contratual | Não interpretar 90 dias como sanção universal | Código/CI a verificar |
| M451 | Capital-Dias V2 | Fuso America/Belem explícito | Código/CI a verificar |
| M452 | Capital-Dias V2 | Ciclo 01/01–31/12 inclusive no corte | Código/CI a verificar |
| M453 | Capital-Dias V2 | Estado conciliado ao fim do dia local | Código/CI a verificar |
| M454 | Capital-Dias V2 | Aporte confirmado afeta somente dias futuros | Código/CI a verificar |
| M455 | Capital-Dias V2 | Reversão diminui capital apenas da data efetiva | Código/CI a verificar |
| M456 | Capital-Dias V2 | Restituição não gera dias retroativos negativos | Código/CI a verificar |
| M457 | Capital-Dias V2 | Saldo principal nunca fica negativo | Código/CI a verificar |
| M458 | Capital-Dias V2 | Timestamp com fuso obrigatório | Código/CI a verificar |
| M459 | Capital-Dias V2 | IDs de eventos de capital únicos | Código/CI a verificar |
| M460 | Capital-Dias V2 | Peso integral vai a zero no gatilho especial juridicamente validado | Código/CI a verificar |
| M461 | Saída voluntária individual | Pedido formal de saída com UUID | Código/CI a verificar |
| M462 | Saída voluntária individual | Data de pedido preservada | Código/CI a verificar |
| M463 | Saída voluntária individual | Saída sem prova segue em revisão | Código/CI a verificar |
| M464 | Saída voluntária individual | Saída adimplente não perde direitos adquiridos | Código/CI a verificar |
| M465 | Saída voluntária individual | Aprovação não equivale a restituição efetuada | Código/CI a verificar |
| M466 | Saída voluntária individual | Comprovação de obrigações pendentes exigida | Código/CI a verificar |
| M467 | Saída voluntária individual | Documento aceito identificado | Código/CI a verificar |
| M468 | Saída voluntária individual | Proibir data retroativa de encerramento | Código/CI a verificar |
| M469 | Saída voluntária individual | Reembolso só reduz capital quando conciliado | Código/CI a verificar |
| M470 | Saída voluntária individual | Não apagar histórico do membro desligado | Código/CI a verificar |
| M471 | Cancelamento empresarial da caixinha | Separar licença SaaS de caixa financeira do tenant | Código/CI a verificar |
| M472 | Cancelamento empresarial da caixinha | Distinguir saída do membro e liquidação do tenant | Código/CI a verificar |
| M473 | Cancelamento empresarial da caixinha | Conservar capital principal dos membros | Código/CI a verificar |
| M474 | Cancelamento empresarial da caixinha | Conservar lucros ainda exigíveis dos membros | Código/CI a verificar |
| M475 | Cancelamento empresarial da caixinha | Conservar remuneração administrativa legítima | Código/CI a verificar |
| M476 | Cancelamento empresarial da caixinha | Conservar créditos e empréstimos em aberto | Código/CI a verificar |
| M477 | Cancelamento empresarial da caixinha | Conservar valores contestados | Código/CI a verificar |
| M478 | Cancelamento empresarial da caixinha | Segregar reservas do ciclo anterior | Código/CI a verificar |
| M479 | Cancelamento empresarial da caixinha | Não fechar com Pix pendentes ou reconciliação ausente | Código/CI a verificar |
| M480 | Cancelamento empresarial da caixinha | Nem prova completa encerra tenant automaticamente | Código/CI a verificar |
| M481 | Empréstimo: mora e multa | Mora simples 20%/30 na política inaugural | Código/CI a verificar |
| M482 | Empréstimo: mora e multa | Multa única R$10 por obrigação inadimplida | Código/CI a verificar |
| M483 | Empréstimo: mora e multa | Contar dias civis após vencimento | Código/CI a verificar |
| M484 | Empréstimo: mora e multa | Não capitalizar juros vencidos | Código/CI a verificar |
| M485 | Empréstimo: mora e multa | Não cobrar juros sobre multas | Código/CI a verificar |
| M486 | Empréstimo: mora e multa | Juros remuneratórios vencidos têm prioridade | Código/CI a verificar |
| M487 | Empréstimo: mora e multa | Mora acumulada recebe segunda prioridade | Código/CI a verificar |
| M488 | Empréstimo: mora e multa | Multa única recebe terceira prioridade | Código/CI a verificar |
| M489 | Empréstimo: mora e multa | Principal vencido recebe quarta prioridade | Código/CI a verificar |
| M490 | Empréstimo: mora e multa | Só reduzir base futura da mora após principal efetivamente pago | Código/CI a verificar |
| M491 | Lucro realizado e despesas | Excluir cotas e capital próprio do lucro | Código/CI a verificar |
| M492 | Lucro realizado e despesas | Excluir promessa e QR ainda não pago | Código/CI a verificar |
| M493 | Lucro realizado e despesas | Exigir prova de receita realizada | Código/CI a verificar |
| M494 | Lucro realizado e despesas | Reconhecer despesa legítima documentada | Código/CI a verificar |
| M495 | Lucro realizado e despesas | Reconhecer perdas e ajustes admissíveis | Código/CI a verificar |
| M496 | Lucro realizado e despesas | Excluir eventos após 31/12 sem revisão | Código/CI a verificar |
| M497 | Lucro realizado e despesas | Separar data financeira de competência | Código/CI a verificar |
| M498 | Lucro realizado e despesas | Resultado líquido não positivo gera distribuição zero | Código/CI a verificar |
| M499 | Lucro realizado e despesas | Rejeitar evento de outro tenant | Código/CI a verificar |
| M500 | Lucro realizado e despesas | Rejeitar lançamento em duplicidade | Código/CI a verificar |
| M501 | Rateio e resíduos técnicos | Fixar percentuais admin+members igual 100 | Código/CI a verificar |
| M502 | Rateio e resíduos técnicos | Caixinha inaugural 15/85 | Código/CI a verificar |
| M503 | Rateio e resíduos técnicos | Outras caixinhas podem pactuar percentuais distintos | Código/CI a verificar |
| M504 | Rateio e resíduos técnicos | Repartir apenas lucro líquido elegível | Código/CI a verificar |
| M505 | Rateio e resíduos técnicos | Calcular membros por Capital-Dias | Código/CI a verificar |
| M506 | Rateio e resíduos técnicos | Excluir inadimplente no ciclo se legalmente aplicável | Código/CI a verificar |
| M507 | Rateio e resíduos técnicos | Truncar quota ao centavo antes de restos | Código/CI a verificar |
| M508 | Rateio e resíduos técnicos | Empate por membership_id estável | Código/CI a verificar |
| M509 | Rateio e resíduos técnicos | Resíduo técnico não vira receita Master | Código/CI a verificar |
| M510 | Rateio e resíduos técnicos | R$0,01 excedente integra rateio normal, não Pix separado | Código/CI a verificar |
| M511 | Fechamento e liberação | Congelar base temporal em 31/12 | Código/CI a verificar |
| M512 | Fechamento e liberação | Apuração documental de 01 a 09/01 | Código/CI a verificar |
| M513 | Fechamento e liberação | Não antecipar Pix de 10/01 | Código/CI a verificar |
| M514 | Fechamento e liberação | Separar principal, lucro, remuneração, reservas e disputas | Código/CI a verificar |
| M515 | Fechamento e liberação | Bloquear distribuição se ΣW=0 | Código/CI a verificar |
| M516 | Fechamento e liberação | Não liberar fechamento se evento sem conciliação | Código/CI a verificar |
| M517 | Fechamento e liberação | Não declarar FECHADO com obrigações remanescentes | Código/CI a verificar |
| M518 | Fechamento e liberação | Saldo do ciclo anterior não vira caixa livre seguinte | Código/CI a verificar |
| M519 | Fechamento e liberação | Não ativar Pix real em DEMO/CI | Código/CI a verificar |
| M520 | Fechamento e liberação | Master não autoriza fechamento de outra caixinha | Código/CI a verificar |
| M521 | CI, segurança e entrega | Conferir SHA dos dois documentos mestres | Código/CI a verificar |
| M522 | CI, segurança e entrega | Ler cláusulas aprovadas e impedir desvio textual | Código/CI a verificar |
| M523 | CI, segurança e entrega | Rodar centenas de datas e limites de atraso | Código/CI a verificar |
| M524 | CI, segurança e entrega | Rodar centenas de valores de mora | Código/CI a verificar |
| M525 | CI, segurança e entrega | Rodar centavos e desempate do rateio | Código/CI a verificar |
| M526 | CI, segurança e entrega | Rodar saída voluntária com e sem prova | Código/CI a verificar |
| M527 | CI, segurança e entrega | Rodar cancelamento de caixinha com passivos | Código/CI a verificar |
| M528 | CI, segurança e entrega | Rodar integração fictícia real PostgreSQL 16 | Código/CI a verificar |
| M529 | CI, segurança e entrega | Rodar integração fictícia real PostgreSQL 18 | Código/CI a verificar |
| M530 | CI, segurança e entrega | Compilar Android apenas após gates frontend/backend/PG | Código/CI a verificar |

## Gates que não podem ser artificialmente fechados
1. O efeito econômico de excluir lucro pelo triplo inadimplemento da caixinha do proprietário depende da **validação jurídica específica** prevista no Caderno. Codificação simulada não autoriza perda patrimonial.
2. **Saída voluntária**: a regra geral preserva direitos adquiridos. Valor exato de restituição, dívidas, reservas e limites requer apuração com extratos/política aceita, sem criar multa de saída inexistente.
3. **Fechamento real**: exige conciliação externa, eventos de reversão, patrimônio identificável, documentação, aprovação independente, banco/QR real autenticado e mecanismo de pagamentos de saída autorizado. As rotas atuais 503 permanecem.
4. **Encerramento total de tenant**: não confundir com cancelamento da licença SaaS nem permitir exclusão de vínculos ou dados contábeis para driblar obrigações.
5. **Segurança e implantação Oracle OCI**: sem segredos em código/Android/chat, TLS, auditoria de permissões e restauração, KYC/jurídico, sandbox Mercado Pago por recebedor e conclusão da homologação física.
6. A CI compila APK **somente depois** do êxito de frontend, API, PostgreSQL 16 e 18. Ainda não há homologação no aparelho do macropacote.

**Pendências permanecem identificadas, não apagadas; nenhum dinheiro real habilitado.**
