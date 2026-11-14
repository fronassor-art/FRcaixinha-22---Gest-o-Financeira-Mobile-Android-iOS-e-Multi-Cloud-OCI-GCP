# FR Caixinha AI Studio — M601–M760: 160 controles de integração financeira

Data 04/11/2026. Base validada: `6cf856ce3840f72760f4ce53e690f7712359d468`, CI #227 (6/6 PASS). Branch `atualizacao-ai-studio-9b46a63187`, PR #2 DRAFT. Projeto AI Studio independente de FRcaixinha 2.2.

## Meta
**Continuar o desenvolvimento integral das 147 cláusulas**, com testes sintéticos e depois homologação OCI, para submeter a parte jurídica após concluir o produto tecnicamente. A análise jurídica NÃO bloqueia implementar nem testar os motores. A liberação financeira real segue protegida até aprovação.

A presente entrega **não conclui as 160 tarefas**, apenas implementa os controles marcados `CI/AUDITORIA NO PACOTE` e rastreia as demais, que **não serão tratadas como sanadas** até demonstrar código operacional e prova de ponta a ponta.

## Arquitetura efetivamente implementada nesta etapa

- `backend/app/financial_integrity.py` — confronto determinístico entre identidades/vínculos, política versionada, contribuições e lançamentos DR/CR; todos os valores em centavos inteiros e percentuais Decimal. Detecta ausência da conta canônica, dupla política ativa, transação desbalanceada, contribuição sem razão, referência duplicada, inconsistência de valor e alteração de tenant.
- `backend/app/routers/financial_integrity_previews.py` — endpoint autenticado e escopo TENANT_ADMIN `GET /api/v1/tenants/{tenant_id}/cycles/{year}/financial-integrity/preview`. Consulta o PostgreSQL efetivo com RLS; não grava dados. Limite de 500 por conjunto com HTTP 503 em vez de demonstrar apenas uma parte como completa. Em tenants grandes, será necessário implementar paginação completa antes de homologação final.
- `backend/app/models.py` — contrato completo, sem campos de resultado bancário. `no_bank_evidence=true`, `bank_reconciled=false`, saldo disponível, receita Master e lucro pessoal todos `null`; `transfer_authorized=false` e `closing_authorized=false`.
- `src/services/financialIntegrityBoundary.ts` e `src/components/FinancialIntegrityPanel.tsx` — parser fechado e visualização administrativa de diferenças sem falsificar saldos.
- `backend/tests/test_financial_integrity_oracle_ci.py` — centenas de verificações individuais de valores e políticas; testes separados do banco produtivo. `backend/tests/test_financial_integrity_api_ci.py` — proteção de sessão/escopo. `backend/tests/test_aistudio_financial_lab_integrated_ci.py` — cenários A/B com R$3.825 de recebimentos fictícios e 26 transações sintéticas. **Não são dinheiro nem conciliação real.**
- Workflow CI: teste de frontend, API sem banco, PostgreSQL 16, PostgreSQL 18 e compilação Android **apenas após** os outros gates.

## Segurança e limites explícitos
1. Sem migração 028, nenhuma alteração no PostgreSQL Termux `5433`; banco e schema atuais permanecem.
2. Nenhum pagamento externo Mercado Pago, webhook ou ativação de operação. Somente dados registrados e testes falsos isolados.
3. Nenhuma tela nova pode chamar `close_cycle` ou declarar apropriação de lucros sem prova de efetiva conciliação.
4. Auditoria de R$0,00 ou partidas dobradas perfeitas NÃO equivale a caixa bancário disponível.
5. `REGISTERED_INTEGRITY_ONLY` significa consistência **apenas entre dados cadastrados**. `REVIEW_REQUIRED` significa falha/ausência documentada; indisponibilidade ou dados acima do limite respondem 503.
6. Leitura em múltiplos SELECTs está sob escopo de transação/RLS, mas sem snapshot bancário ou prova de consistência sob escrita concorrente. Não utilizar como certificação de fechamento.
7. A fase jurídica é posterior à homologação técnica. Aprovação jurídica continua pré-condição para ativar operações financeiras reais, não para codificar ou testar.

## Matriz M601–M760 de 160 controles

A coluna `CI/AUDITORIA NO PACOTE` indica cobertura automatizada prevista e só passa a PASS após resultado de CI verificado. `FLUXO OPERACIONAL A IMPLEMENTAR` permanece no backlog, inclusive Oracle OCI, OAuth, baixas, bloqueios e encerramentos.

| ID | Frente | Controle | Evidência / situação |
|---|---|---|---|
| M601 | Governança de perfis | Master não recebe dados individuais de caixa | CI/AUDITORIA NO PACOTE |
| M602 | Governança de perfis | Administrador consulta apenas a própria caixinha | CI/AUDITORIA NO PACOTE |
| M603 | Governança de perfis | Membro não consulta demonstrativo global | CI/AUDITORIA NO PACOTE |
| M604 | Governança de perfis | Vínculo de administrador e membro não duplica pessoa | CI/AUDITORIA NO PACOTE |
| M605 | Governança de perfis | RLS permanece ativo no PostgreSQL | CI/AUDITORIA NO PACOTE |
| M606 | Governança de perfis | Perfil autenticado vem da sessão server-side | CI/AUDITORIA NO PACOTE |
| M607 | Governança de perfis | Consulta sem token devolve HTTP 401 | CI/AUDITORIA NO PACOTE |
| M608 | Governança de perfis | Troca de sessão invalida resultado antigo | CI/AUDITORIA NO PACOTE |
| M609 | Governança de perfis | Consulta não cria permissões de financeiro | CI/AUDITORIA NO PACOTE |
| M610 | Governança de perfis | Admin com outra caixinha não consulta registros cruzados | CI/AUDITORIA NO PACOTE |
| M611 | Identidade de membros | Contagem total de vínculos | CI/AUDITORIA NO PACOTE |
| M612 | Identidade de membros | Contagem total de pessoas distintas | CI/AUDITORIA NO PACOTE |
| M613 | Identidade de membros | Separar papel TENANT_MEMBER de TENANT_ADMIN | CI/AUDITORIA NO PACOTE |
| M614 | Identidade de membros | Duas funções sob identidade única | CI/AUDITORIA NO PACOTE |
| M615 | Identidade de membros | Bloquear vínculos duplicados por papel | CI/AUDITORIA NO PACOTE |
| M616 | Identidade de membros | Recusar ID de tenant divergente | CI/AUDITORIA NO PACOTE |
| M617 | Identidade de membros | Identificar vínculos suspensos sem excluir histórico | CI/AUDITORIA NO PACOTE |
| M618 | Identidade de membros | Identificar vínculos desligados sem apagar capital | CI/AUDITORIA NO PACOTE |
| M619 | Identidade de membros | Não expor CPF ou e-mail nas métricas | CI/AUDITORIA NO PACOTE |
| M620 | Identidade de membros | Provar que painel não contém identidade bancária | CI/AUDITORIA NO PACOTE |
| M621 | Política do ciclo | Buscar ciclo pelo tenant e exercício | CI/AUDITORIA NO PACOTE |
| M622 | Política do ciclo | Exigir ano válido | CI/AUDITORIA NO PACOTE |
| M623 | Política do ciclo | Validar datas início/fim de exercício | CI/AUDITORIA NO PACOTE |
| M624 | Política do ciclo | Localizar política ativa | CI/AUDITORIA NO PACOTE |
| M625 | Política do ciclo | Recusar múltiplas políticas ativas | CI/AUDITORIA NO PACOTE |
| M626 | Política do ciclo | Preservar versões históricas superadas | CI/AUDITORIA NO PACOTE |
| M627 | Política do ciclo | Percentuais administrativos com Decimal | CI/AUDITORIA NO PACOTE |
| M628 | Política do ciclo | Admin e membros somando 100% | CI/AUDITORIA NO PACOTE |
| M629 | Política do ciclo | Cota por competência não fixa no código | CI/AUDITORIA NO PACOTE |
| M630 | Política do ciclo | Separar política dos demais tenants | CI/AUDITORIA NO PACOTE |
| M631 | Contribuições | Conferir total devido cadastrado | CI/AUDITORIA NO PACOTE |
| M632 | Contribuições | Conferir total pago registrado | CI/AUDITORIA NO PACOTE |
| M633 | Contribuições | Conferir saldo cadastral em aberto | CI/AUDITORIA NO PACOTE |
| M634 | Contribuições | Validar centavos exatos | CI/AUDITORIA NO PACOTE |
| M635 | Contribuições | Recusar contribuições negativas | CI/AUDITORIA NO PACOTE |
| M636 | Contribuições | Recusar valor pago acima do devido | CI/AUDITORIA NO PACOTE |
| M637 | Contribuições | Contar QUITADA, PARCIAL e PENDENTE | CI/AUDITORIA NO PACOTE |
| M638 | Contribuições | Detectar status inconsistente com pagamento | CI/AUDITORIA NO PACOTE |
| M639 | Contribuições | Garantir competência mensal única por membro | CI/AUDITORIA NO PACOTE |
| M640 | Contribuições | Garantir ciclo e papel de membro válidos | CI/AUDITORIA NO PACOTE |
| M641 | Livro-Razão | Contar transações por exercício | CI/AUDITORIA NO PACOTE |
| M642 | Livro-Razão | Verificar partidas DR e CR | CI/AUDITORIA NO PACOTE |
| M643 | Livro-Razão | Exigir pelo menos duas entradas por transação | CI/AUDITORIA NO PACOTE |
| M644 | Livro-Razão | Verificar somatório contábil por transação | CI/AUDITORIA NO PACOTE |
| M645 | Livro-Razão | Verificar somatório DR e CR por ciclo | CI/AUDITORIA NO PACOTE |
| M646 | Livro-Razão | Detectar conta contábil inválida | CI/AUDITORIA NO PACOTE |
| M647 | Livro-Razão | Verificar códigos canônicos presentes | CI/AUDITORIA NO PACOTE |
| M648 | Livro-Razão | Detectar transação sem entrada completa | CI/AUDITORIA NO PACOTE |
| M649 | Livro-Razão | Rejeitar referências contábeis duplicadas | CI/AUDITORIA NO PACOTE |
| M650 | Livro-Razão | RLS de entrada e conta sob o mesmo tenant | CI/AUDITORIA NO PACOTE |
| M651 | Vinculação contribuição→razão | Referencia da transação corresponde à obrigação | CI/AUDITORIA NO PACOTE |
| M652 | Vinculação contribuição→razão | Conferir caixa débito 1.1.1 contra pago | CI/AUDITORIA NO PACOTE |
| M653 | Vinculação contribuição→razão | Conferir capital crédito 2.1.1 contra pago | CI/AUDITORIA NO PACOTE |
| M654 | Vinculação contribuição→razão | Contar contribuições com lançamento | CI/AUDITORIA NO PACOTE |
| M655 | Vinculação contribuição→razão | Contar pagamentos registrados sem razão | CI/AUDITORIA NO PACOTE |
| M656 | Vinculação contribuição→razão | Contar lançamentos vinculados divergentes | CI/AUDITORIA NO PACOTE |
| M657 | Vinculação contribuição→razão | Confrontar total vinculado em centavos | CI/AUDITORIA NO PACOTE |
| M658 | Vinculação contribuição→razão | Não inventar referência em transação de crédito | CI/AUDITORIA NO PACOTE |
| M659 | Vinculação contribuição→razão | Recusar divergência de um centavo | CI/AUDITORIA NO PACOTE |
| M660 | Vinculação contribuição→razão | Não considerar vínculo contábil prova de banco | CI/AUDITORIA NO PACOTE |
| M661 | Caixa do administrador do tenant | Segregar recebimento do membro do Master | FLUXO OPERACIONAL A IMPLEMENTAR |
| M662 | Caixa do administrador do tenant | Identificar conta 1.1.1 apenas contabilmente | FLUXO OPERACIONAL A IMPLEMENTAR |
| M663 | Caixa do administrador do tenant | Não tratar saldo interno como dinheiro disponível | FLUXO OPERACIONAL A IMPLEMENTAR |
| M664 | Caixa do administrador do tenant | Separar capital da receita de juros | FLUXO OPERACIONAL A IMPLEMENTAR |
| M665 | Caixa do administrador do tenant | Registrar despesas próprias por competência | FLUXO OPERACIONAL A IMPLEMENTAR |
| M666 | Caixa do administrador do tenant | Aplicar custos elegíveis na apuração líquida | FLUXO OPERACIONAL A IMPLEMENTAR |
| M667 | Caixa do administrador do tenant | Reconciliar provedor e livro com identificador | FLUXO OPERACIONAL A IMPLEMENTAR |
| M668 | Caixa do administrador do tenant | Reversão contábil sem apagar original | FLUXO OPERACIONAL A IMPLEMENTAR |
| M669 | Caixa do administrador do tenant | Exibir extrato recebido vs liquidado | FLUXO OPERACIONAL A IMPLEMENTAR |
| M670 | Caixa do administrador do tenant | Concluir saldo financeiro apenas após conciliação externa | FLUXO OPERACIONAL A IMPLEMENTAR |
| M671 | Caixa do Master SaaS | Assinaturas exclusivamente no caixa da plataforma | FLUXO OPERACIONAL A IMPLEMENTAR |
| M672 | Caixa do Master SaaS | Caixa Master separado do capital de cotas | FLUXO OPERACIONAL A IMPLEMENTAR |
| M673 | Caixa do Master SaaS | Não incluir taxa 15% do lucro em mensalidade SaaS | FLUXO OPERACIONAL A IMPLEMENTAR |
| M674 | Caixa do Master SaaS | Preparar intents de cobrança comercial | FLUXO OPERACIONAL A IMPLEMENTAR |
| M675 | Caixa do Master SaaS | Confirmar token da conta recebedora Master | FLUXO OPERACIONAL A IMPLEMENTAR |
| M676 | Caixa do Master SaaS | Trazer tarifas do provedor para demonstrativo | FLUXO OPERACIONAL A IMPLEMENTAR |
| M677 | Caixa do Master SaaS | Tratar reembolso de assinatura e estorno | FLUXO OPERACIONAL A IMPLEMENTAR |
| M678 | Caixa do Master SaaS | Mensalidade gera receita somente após liquidação | FLUXO OPERACIONAL A IMPLEMENTAR |
| M679 | Caixa do Master SaaS | RLS do Master não acessa extrato dos membros | FLUXO OPERACIONAL A IMPLEMENTAR |
| M680 | Caixa do Master SaaS | Demonstrativo SaaS completo e auditável | FLUXO OPERACIONAL A IMPLEMENTAR |
| M681 | Inadimplência | Separar atraso em dias de meses consecutivos | FLUXO OPERACIONAL A IMPLEMENTAR |
| M682 | Inadimplência | Três competências vencidas não quitadas | FLUXO OPERACIONAL A IMPLEMENTAR |
| M683 | Inadimplência | Pagamento parcial ainda não é quitação | FLUXO OPERACIONAL A IMPLEMENTAR |
| M684 | Inadimplência | Regularização tardia preserva histórico | FLUXO OPERACIONAL A IMPLEMENTAR |
| M685 | Inadimplência | Não apagar pagamentos confirmados | FLUXO OPERACIONAL A IMPLEMENTAR |
| M686 | Inadimplência | Não confiscar capital principal | FLUXO OPERACIONAL A IMPLEMENTAR |
| M687 | Inadimplência | Guardar versão da política por caixinha | FLUXO OPERACIONAL A IMPLEMENTAR |
| M688 | Inadimplência | Bloquear novas operações quando contratado | FLUXO OPERACIONAL A IMPLEMENTAR |
| M689 | Inadimplência | Registrar motivo e prova do bloqueio | FLUXO OPERACIONAL A IMPLEMENTAR |
| M690 | Inadimplência | Testar desbloqueio/contestações com auditoria | FLUXO OPERACIONAL A IMPLEMENTAR |
| M691 | Saída voluntária do membro | Pedido autenticado e identificável | FLUXO OPERACIONAL A IMPLEMENTAR |
| M692 | Saída voluntária do membro | Distinguir saída do membro de cancelamento SaaS | FLUXO OPERACIONAL A IMPLEMENTAR |
| M693 | Saída voluntária do membro | Preservar direitos adquiridos do adimplente | FLUXO OPERACIONAL A IMPLEMENTAR |
| M694 | Saída voluntária do membro | Conferir dívidas pendentes antes da saída | FLUXO OPERACIONAL A IMPLEMENTAR |
| M695 | Saída voluntária do membro | Conferir capital efetivamente confirmado | FLUXO OPERACIONAL A IMPLEMENTAR |
| M696 | Saída voluntária do membro | Conferir retorno devido e valor contestado | FLUXO OPERACIONAL A IMPLEMENTAR |
| M697 | Saída voluntária do membro | Registrar decisão independente e histórico | FLUXO OPERACIONAL A IMPLEMENTAR |
| M698 | Saída voluntária do membro | Restituição somente após prova bancária | FLUXO OPERACIONAL A IMPLEMENTAR |
| M699 | Saída voluntária do membro | Bloquear exclusão de dados históricos | FLUXO OPERACIONAL A IMPLEMENTAR |
| M700 | Saída voluntária do membro | Homologar no APK com perfis distintos | FLUXO OPERACIONAL A IMPLEMENTAR |
| M701 | Empréstimos e encargos | Vincular empréstimo ao tenant e ciclo | FLUXO OPERACIONAL A IMPLEMENTAR |
| M702 | Empréstimos e encargos | Parcelas Price vinculadas à política | FLUXO OPERACIONAL A IMPLEMENTAR |
| M703 | Empréstimos e encargos | Juros vencidos antes de mora e multa | FLUXO OPERACIONAL A IMPLEMENTAR |
| M704 | Empréstimos e encargos | Mora simples sem capitalização | FLUXO OPERACIONAL A IMPLEMENTAR |
| M705 | Empréstimos e encargos | Multa cobrada somente uma vez | FLUXO OPERACIONAL A IMPLEMENTAR |
| M706 | Empréstimos e encargos | Imputar primeiro à parcela vencida mais antiga | FLUXO OPERACIONAL A IMPLEMENTAR |
| M707 | Empréstimos e encargos | Amortizar apenas principal realmente pago | FLUXO OPERACIONAL A IMPLEMENTAR |
| M708 | Empréstimos e encargos | Não cobrar juros futuros em quitação antecipada | FLUXO OPERACIONAL A IMPLEMENTAR |
| M709 | Empréstimos e encargos | Bloquear empréstimo após inadimplência elegível | FLUXO OPERACIONAL A IMPLEMENTAR |
| M710 | Empréstimos e encargos | Integrar pagamento com contabilidade e Pix sandbox | FLUXO OPERACIONAL A IMPLEMENTAR |
| M711 | Fechamento anual | Resultado líquido exclui capital de cotas | FLUXO OPERACIONAL A IMPLEMENTAR |
| M712 | Fechamento anual | Receita deve ser realizada e evidenciada | FLUXO OPERACIONAL A IMPLEMENTAR |
| M713 | Fechamento anual | Despesas e perdas deduzidas corretamente | FLUXO OPERACIONAL A IMPLEMENTAR |
| M714 | Fechamento anual | Percentual 15/85 na caixinha do proprietário | FLUXO OPERACIONAL A IMPLEMENTAR |
| M715 | Fechamento anual | Outros tenants usam percentuais aceitos | FLUXO OPERACIONAL A IMPLEMENTAR |
| M716 | Fechamento anual | Capital-Dias V2 em America/Belem | FLUXO OPERACIONAL A IMPLEMENTAR |
| M717 | Fechamento anual | Excluir do peso só conforme regra aplicável | FLUXO OPERACIONAL A IMPLEMENTAR |
| M718 | Fechamento anual | Rateio de centavos por maiores restos | FLUXO OPERACIONAL A IMPLEMENTAR |
| M719 | Fechamento anual | Resíduo técnico segregado não vira receita | FLUXO OPERACIONAL A IMPLEMENTAR |
| M720 | Fechamento anual | Não fechar ciclo com obrigações pendentes | FLUXO OPERACIONAL A IMPLEMENTAR |
| M721 | Mercado Pago sandbox | Credencial Master guardada só no backend | FLUXO OPERACIONAL A IMPLEMENTAR |
| M722 | Mercado Pago sandbox | OAuth individual para cada vendedor tenant | FLUXO OPERACIONAL A IMPLEMENTAR |
| M723 | Mercado Pago sandbox | Não compartilhar token entre caixas | FLUXO OPERACIONAL A IMPLEMENTAR |
| M724 | Mercado Pago sandbox | Request Pix com idempotência estável | FLUXO OPERACIONAL A IMPLEMENTAR |
| M725 | Mercado Pago sandbox | Validar recebedor ID e valor | FLUXO OPERACIONAL A IMPLEMENTAR |
| M726 | Mercado Pago sandbox | Verificar referência da contribuição/contrato | FLUXO OPERACIONAL A IMPLEMENTAR |
| M727 | Mercado Pago sandbox | Webhook assinado não é liquidação sozinho | FLUXO OPERACIONAL A IMPLEMENTAR |
| M728 | Mercado Pago sandbox | Buscar GET autoritativo com token correto | FLUXO OPERACIONAL A IMPLEMENTAR |
| M729 | Mercado Pago sandbox | Testar reembolso, expiração e evento duplicado | FLUXO OPERACIONAL A IMPLEMENTAR |
| M730 | Mercado Pago sandbox | Não executar transferência ou Pix de produção | FLUXO OPERACIONAL A IMPLEMENTAR |
| M731 | Segurança e evidências | Validar SQL somente leitura dos dashboards | CI/AUDITORIA NO PACOTE |
| M732 | Segurança e evidências | Rejeitar documentos de outro tenant | CI/AUDITORIA NO PACOTE |
| M733 | Segurança e evidências | Rejeitar campos desconhecidos na UI | CI/AUDITORIA NO PACOTE |
| M734 | Segurança e evidências | Exigir resposta do servidor por esquema fechado | CI/AUDITORIA NO PACOTE |
| M735 | Segurança e evidências | Não persistir saldo financeiro em localStorage | CI/AUDITORIA NO PACOTE |
| M736 | Segurança e evidências | Bloquear números JavaScript imprecisos | CI/AUDITORIA NO PACOTE |
| M737 | Segurança e evidências | Bloquear consultas acima de limite sem truncar | CI/AUDITORIA NO PACOTE |
| M738 | Segurança e evidências | Não mostrar saldo disponível sem banco | CI/AUDITORIA NO PACOTE |
| M739 | Segurança e evidências | Registrar evidência de CI com SHA integral | CI/AUDITORIA NO PACOTE |
| M740 | Segurança e evidências | Não executar migration no PG5433 | CI/AUDITORIA NO PACOTE |
| M741 | Oracle OCI e operação | Prover staging com banco independente | FLUXO OPERACIONAL A IMPLEMENTAR |
| M742 | Oracle OCI e operação | Separar test/live por credencial | FLUXO OPERACIONAL A IMPLEMENTAR |
| M743 | Oracle OCI e operação | Gerenciar segredos no OCI Vault | FLUXO OPERACIONAL A IMPLEMENTAR |
| M744 | Oracle OCI e operação | Forçar TLS e HTTPS com domínio próprio | FLUXO OPERACIONAL A IMPLEMENTAR |
| M745 | Oracle OCI e operação | Executar backup criptografado | FLUXO OPERACIONAL A IMPLEMENTAR |
| M746 | Oracle OCI e operação | Testar restauração em ambiente descartável | FLUXO OPERACIONAL A IMPLEMENTAR |
| M747 | Oracle OCI e operação | Monitorar erros, filas e webhooks | FLUXO OPERACIONAL A IMPLEMENTAR |
| M748 | Oracle OCI e operação | Testar concorrência e idempotência | FLUXO OPERACIONAL A IMPLEMENTAR |
| M749 | Oracle OCI e operação | Executar testes de carga/segurança | FLUXO OPERACIONAL A IMPLEMENTAR |
| M750 | Oracle OCI e operação | Concluir homologação antes de fase jurídica | FLUXO OPERACIONAL A IMPLEMENTAR |
| M751 | Android e entrega | Adicionar API read-only de integridade | CI/AUDITORIA NO PACOTE |
| M752 | Android e entrega | Exibir painel somente ao administrador | CI/AUDITORIA NO PACOTE |
| M753 | Android e entrega | Mostrar pessoa distinta e vínculos | CI/AUDITORIA NO PACOTE |
| M754 | Android e entrega | Exibir contribuições em centavos exatos | CI/AUDITORIA NO PACOTE |
| M755 | Android e entrega | Exibir DR/CR e divergências | CI/AUDITORIA NO PACOTE |
| M756 | Android e entrega | Exibir alertas de ausência de prova bancária | CI/AUDITORIA NO PACOTE |
| M757 | Android e entrega | Não oferecer botão de fechamento real | CI/AUDITORIA NO PACOTE |
| M758 | Android e entrega | Validar troca de sessão no frontend | CI/AUDITORIA NO PACOTE |
| M759 | Android e entrega | Compilar Android só após os quatro gates | CI/AUDITORIA NO PACOTE |
| M760 | Android e entrega | Homologar interface no celular com dados sintéticos | FLUXO OPERACIONAL A IMPLEMENTAR |

## Gates próximos
- Conferir GitHub Actions no SHA exato, não apenas o status de uma execução antiga.
- Integrar históricos de saída voluntária, bloqueios e notificações em persistência versionada e testes PG descartável, sem impedir construção por ausência de análise jurídica.
- Desenvolver ambiente isolado para pagamentos Pix sandbox do Mercado Pago, segredos e OAuth de cada recebedor; homologar idempotência, conciliação, reversões e razão.
- Implementar lucro anual líquido e direitos no painel, com trilha de auditoria completa; validar assinatura SaaS Master em caixa empresarial independente.
- Implantar e testar staging na Oracle OCI, com backups, segurança, logs e testes de aparelho, depois abrir fase jurídica.
- PR #2 continua Draft. Não fazer merge para main até auditoria integral.

**As pendências técnicas NÃO são apagadas com testes sintéticos.**
