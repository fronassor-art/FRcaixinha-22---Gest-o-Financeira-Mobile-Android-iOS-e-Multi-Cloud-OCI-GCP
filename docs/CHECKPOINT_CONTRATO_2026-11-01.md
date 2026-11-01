# Checkpoint atualizado — FRcaixinha 2.2

Data: 01/11/2026 UTC. Branch atualizacao-ai-studio-9b46a63187. Base da rodada: 9200d4a831739c4a5131049f3fc7fd88a73d49d7. Fotografia anterior preservada em CHECKPOINT_CONTRATO_HISTORICO_74b9a543.md.

## Fontes e critério

Contrato Técnico Mestre original: 38 páginas, SHA-256 7b28d5d5cf773fb5c35194bce64ebfdfec4d67422bafac4595a6662b4f45f468. Caderno Mestre: 57 páginas, SHA-256 94d2a15c54d3f5982c09fe78762ae0f1c76e03fa644cb05a6404f5c7b2feb0f6. Ambos em public/assets/aistudio; 147 IDs na mesma ordem. Cópias em dist byte-idênticas. Nenhuma versão documental mais recente identificada. Diferenças textuais entre os dois PDFs requerem decisão cláusula a cláusula.

A instrução atual do proprietário preserva bolão e rifa como demonstradores, mesmo diante da restrição documental à rifa privada; não autoriza operação real. React + Capacitor prevalece sobre a prescrição técnica Flutter da cláusula 1.8. Ciclo 01/01/2027–31/12/2027; liquidação prevista 10/01/2028, sem alongar Capital-Dias.

CONCLUÍDO E TESTADO exige prova integral; PARCIAL cobre apenas parte; BLOQUEADO retém fluxo por implementação, decisão ou infraestrutura; AUSENTE requer ausência apurada; DIVERGENTE indica conflito; NÃO VERIFICADO não afirma conformidade nem ausência. Testes isolados não comprovam API, PostgreSQL, provedor ou aparelho.

## Matriz das 147 cláusulas

| Cláusula | Requisito identificado | Estado atual | Arquivo/função relevante | Teste executado ou inexistente | Pendência |
|---|---|---|---|---|---|
| 1.1 | Visão — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.2 | Público e modelo. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.3 | Princípios não negociáveis — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.4 | Diferença essencial entre software e operação. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.5 | Primeira entrega — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.6 | Escopo por prontidão, sem circularidade — APROVADO COMO REQUISITO DOCUMENTAL. | DIVERGENTE | src/components/RaffleView.tsx | sem teste integral | Contrato restringe rifa privada; proprietário determinou preservar o demonstrador sem operação real. |
| 1.7 | Dinheiro real e fronteira de responsabilidade — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.8 | Ambiente técnico oficialmente escolhido — DEFINIDO. | DIVERGENTE | package.json; capacitor.config.ts; android/ | CI build web/APK | Contrato cita Flutter; proprietário determinou React + Capacitor. |
| 1.9 | Desenvolvimento independente e orçamento inicial — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.10 | Titularidade e estratégia comercial. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.11 | Documentos empresariais por estágio. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 1.12 | Plano econômico enxuto. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 2.1 | Perfis funcionais — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/dependencies.py; backend/app/routers/auth.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 2.2 | Direitos do administrador contratante — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/dependencies.py; backend/app/routers/auth.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 2.3 | Papéis simultâneos e troca de contexto. | PARCIAL | backend/app/routers/auth.py: list_contexts, switch_context; dependencies.py: get_current_session | test_rls_isolation_ci.py: sessão/contextos | Homologação apenas; testar interface e demais domínios. |
| 2.4 | Administrador também é membro — DEFINIDO. | PARCIAL | backend/app/routers/auth.py: switch_context; dependencies.py: require_tenant_access | test_rls_isolation_ci.py: Master como membro | Cobertura incompleta de papéis simultâneos. |
| 2.5 | Autorização coletiva anual para crédito próprio — DEFINIDO COMO MODELO CONTRATUAL. | BLOQUEADO | backend/app/annual_consent.py: assess_annual_consent; routers/consents.py | test_annual_consent.py: unanimidade, ingresso, revogação, expiração; lógica isolada | Persistir assinaturas anuais e revalidar na aprovação, reserva e envio. |
| 2.6 | Ausência de outros membros ou falta de unanimidade. | BLOQUEADO | backend/app/annual_consent.py; routers/loans.py: approve_loan | test_annual_consent.py: zero outros membros; test_security_guards.py | Ligar motor ao banco; proibição financeira permanece. |
| 2.7 | Transparência aos membros. | PARCIAL | backend/app/routers/contributions.py; migrations/009_tenant_context_and_references.sql | test_rls_isolation_ci.py: dois tenants | Validar demais recursos e telas. |
| 2.8 | Acesso de Master. | PARCIAL | backend/app/dependencies.py; migrations/009_tenant_context_and_references.sql | test_rls_isolation_ci.py: Master/membro | Auditar todas as operações. |
| 2.9 | Matriz básica de permissões. | PARCIAL | backend/app/dependencies.py; migrations/009_tenant_context_and_references.sql | test_rls_isolation_ci.py: RLS selecionada | Matriz completa CRUD e API pendente. |
| 3.1 | Início da contratação e tenant preliminar — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.1-A | Cadastro e identificação do Administrador Contratante — DEFINIDO E APROVADO em 16/10/2026. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.1-A.1 | Verificação e segurança. | BLOQUEADO | backend/app/routers/; backend/migrations/ | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Login somente de homologação; recuperação por e-mail e identidade confirmada não implementadas. |
| 3.1-A.2 | Aceite, identidade e privacidade. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.2 | Tabela comercial — DEFINIDA E APROVADA. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.2-A | Preço comercial dinâmico e anual automático — DEFINIDO. | PARCIAL | backend/app/routers/; backend/migrations/ | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Cálculo anual testado localmente; preços autoritativos e persistência/versão não comprovados. |
| 3.2-B | Cobrança por resultado das caixinhas — EM ESTUDO, não aprovada. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.3 | Enquadramento sem lacunas. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.4 | Contagem de capacidade — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.5 | Aceite de licença. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.6 | Pagamento de licença. | BLOQUEADO | backend/app/routers/; backend/migrations/ | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Cobrança e conciliação da licença não implementadas. |
| 3.7 | Vigência mensal/anual — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.8 | Tolerância = ZERO DIAS — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.9 | Reativação e cobranças revertidas. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.10 | Alteração, cancelamento e reembolso — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 3.11 | Separação de receitas. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/; backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 4.1 | Política financeira por tenant — DEFINIDO. | DIVERGENTE | backend/app/routers/loans.py | test_price_contract.py: fórmula, não política | Parâmetros fixos ainda divergentes da política por tenant. |
| 4.2 | Configuração inaugural da caixinha do proprietário — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 4.3 | Percentual administrativo — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 4.4 | Vigência das políticas e dos percentuais — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 4.5 | CALENDÁRIO FINANCEIRO CENTRAL — DEFINIDO E NÃO EDITÁVEL PELO TENANT. | PARCIAL | backend/app/routers/loans.py: calculate_price_installments | test_price_contract.py: calendário de parcelas | Calendário central e fechamento ainda pendentes. |
| 4.6 | Fases do fechamento sem mudar datas. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 4.7 | Entrada após 01/01 e lançamento futuro. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 4.8 | Separação do ciclo e da licença. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 5.1 | Atendimento normal. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/support.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 5.2 | Acesso excepcional consentido. | BLOQUEADO | backend/app/routers/support.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Acesso excepcional consentido não implementado. |
| 5.3 | Prazo e gatilhos de suporte — APROVADO COMO REQUISITO DOCUMENTAL. | DIVERGENTE | backend/app/routers/support.py | sem teste de acesso excepcional | Texto/código de suporte não reflete a exceção contratual condicionada. |
| 5.4 | Vedações invariáveis. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/support.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 5.5 | Operação da manutenção. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/support.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 6.1 | Adesão. | BLOQUEADO | backend/app/routers/invitations.py | test_security_guards.py: sem falso sucesso | Persistir e entregar convite; nenhum sucesso falso atual. |
| 6.1-A | Cadastro e identificação do Membro — DEFINIDO E APROVADO em 16/10/2026. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/contributions.py; quotas.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 6.1-A.1 | Aceite e liberação de acesso. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/contributions.py; quotas.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 6.1-A.2 | Identidade única, cotas, privacidade e isolamento. | PARCIAL | backend/app/routers/auth.py: switch_context; migrations/009_tenant_context_and_references.sql | test_rls_isolation_ci.py: vínculos/RLS | Cadastro/aceite/privacidade completos pendentes. |
| 6.2 | Capital e cotas. | PARCIAL | backend/app/routers/contributions.py; quotas.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Teste de leitura RLS de cotas; ciclo de aquisição/aceite e dados de cota ainda sem ponta a ponta. |
| 6.3 | Contribuições. | PARCIAL | backend/app/routers/contributions.py; quotas.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: GET contribuições testado por usuário/tenant e tela consulta API; criação de cobrança Pix bloqueada. |
| 6.4 | Estados. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/contributions.py; quotas.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 6.5 | Regra específica da caixinha do proprietário — DEFINIDO, sujeita à validação jurídica antes da execução real. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/contributions.py; quotas.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 6.6 | Proibição de confisco e exclusão indevida. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/contributions.py; quotas.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 7.1 | Segregação. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/migrations/010_ledger_integrity.sql | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 7.2 | Ledger autoritativo. | PARCIAL | backend/migrations/010_ledger_integrity.sql | test_rls_isolation_ci.py: equilíbrio, duplicata, rollback | API autoritativa e concorrência pendentes. |
| 7.3 | Diferenciar saldos e evitar dupla dedução. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/migrations/010_ledger_integrity.sql | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 7.4 | Concorrência. | BLOQUEADO | backend/migrations/010_ledger_integrity.sql | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Reserva atômica, concorrência e reconciliação de desembolso não demonstradas. |
| 7.5 | Controle de integridade. | PARCIAL | backend/migrations/010_ledger_integrity.sql | test_rls_isolation_ci.py: invariantes selecionados | Imutabilidade e reconciliação fim a fim pendentes. |
| 7.6 | Fronteira regulatória entre livro e custódia — CONSOLIDADO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/migrations/010_ledger_integrity.sql | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 8.1 | Exclusividade interna. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 8.2 | Parametrização financeira na primeira entrega — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 8.3 | Elegibilidade e limites verificáveis. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 8.4 | Simulação obrigatória e datas. | PARCIAL | backend/app/routers/loans.py: calculate_price_installments | test_price_contract.py: datas/prazo | Simulação sem desembolso integrado. |
| 8.5 | Price com primeiro período irregular — DEFINIDO. | PARCIAL | backend/app/routers/loans.py: calculate_price_installments | test_price_contract.py: desconto Price e primeiro período | Paridade completa e todos casos documentais pendentes. |
| 8.6 | Atrasos, imputação parcial e quitação — DEFINIDO. | BLOQUEADO | backend/app/routers/loans.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Cálculos isolados existem; rotas de recebimento e quitação retornam 503 até conciliação. |
| 8.7 | Aprovação. | BLOQUEADO | backend/app/routers/loans.py: approve_loan | test_security_guards.py: autoaprovação bloqueada | Aprovação e desembolso fim a fim não disponíveis. |
| 8.8 | Empréstimo do administrador-membro. | BLOQUEADO | backend/app/annual_consent.py; routers/consents.py; routers/loans.py | test_annual_consent.py: motor; test_security_guards.py: bloqueio | Assinaturas persistentes e revalidação em cada etapa pendentes. |
| 8.9 | Proibição de fechamento indevido. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/routers/loans.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 9.1 | Contas e finalidade. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/mercado_pago.py; routers/pix.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 9.2 | Integração escolhida. | BLOQUEADO | backend/app/mercado_pago.py; routers/pix.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Adaptador só constrói requisições; sem execução externa, OAuth, segregação de tokens ou provedor ativo. |
| 9.3 | Recebimento. | BLOQUEADO | backend/app/mercado_pago.py; routers/pix.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Endpoint Pix retorna 503; não há consulta/baixa conciliada do provedor. |
| 9.4 | Saída, autorização e idempotência. | BLOQUEADO | backend/app/mercado_pago.py; routers/pix.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Desembolso retorna 503; idempotência econômica, reserva e timeout não implementados ponta a ponta. |
| 9.5 | Reversão ou falha. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/mercado_pago.py; routers/pix.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 9.6 | Fechamento. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/mercado_pago.py; routers/pix.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 9.7 | Bolões. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/mercado_pago.py; routers/pix.py | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 9.8 | Verificações mínimas. | BLOQUEADO | backend/app/mercado_pago.py; routers/pix.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Testes de webhook repetido, restauração e concorrência com efeitos reais no banco não comprovados. |
| 9.8-A | Interfaces estáveis de integração para futura migração — CONSOLIDADO. | PARCIAL | backend/app/mercado_pago.py; routers/pix.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Validador HMAC e construtores HTTP testados isoladamente; portas completas e simulador transacional ausentes. |
| 9.9 | Ambientes e liberação por finalidade — APROVADO COMO REQUISITO DOCUMENTAL. | BLOQUEADO | backend/app/mercado_pago.py; routers/pix.py | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Separação operacional DEMO/HOMOLOGAÇÃO/PRODUÇÃO não comprovada. |
| 10.1 | Formação da base e corte de realização. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/finance/; backend/app/routers/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 10.2 | Percentuais por caixinha — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/finance/; backend/app/routers/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 10.3 | Rateio Capital-Dias V2 — motor comum, com corte diário aprovado. | BLOQUEADO | src/finance/; backend/app/routers/ | testes TypeScript isolados | Capital-Dias corta em 31/12/2027; liquidação em 10/01/2028 não estende período. Fechamento persistente ausente. |
| 10.4 | Rateio, precisão e destino definitivo dos centavos — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/finance/; backend/app/routers/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 10.5 | Distinguir administrador como beneficiário duplo. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/finance/; backend/app/routers/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 10.6 | Fechamento anual e obrigações remanescentes. | BLOQUEADO | src/finance/; backend/app/routers/ | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Fechamento retorna 503 para impedir liquidação sem prova; fluxo por estados pendente. |
| 10.7 | Documentos e conferência. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/finance/; backend/app/routers/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 10.8 | Imutabilidade e versões de resultado — DEFINIDO. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/finance/; backend/app/routers/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 11.0-A | Telas de demonstrador regulatório e evolução — CONSOLIDADO. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/App.tsx; src/components/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 11.1 | Design simples. | PARCIAL | src/App.tsx; src/components/ | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Contribuições usa cartões responsivos; não há validação visual em aparelho para todas as telas. |
| 11.2 | Estados visuais. | PARCIAL | src/App.tsx; src/services/authService.ts; financialApiService.ts | CI build web; sem teste visual | Estados de todas as telas e celular pendentes. |
| 11.3 | Textos de transparência. | PARCIAL | src/App.tsx; src/components/RaffleView.tsx; BolaoView.tsx | CI build; sem teste visual | Identificar todos os dados seed como demonstração. |
| 11.4 | Manual oficial para administradores — ENTREGÁVEL DO MVP. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/App.tsx; src/components/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 11.5 | Apoio comercial e demonstração — ENTREGÁVEL NÃO TRANSACIONAL. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/App.tsx; src/components/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 12.1 | Padrões de todas as tabelas. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 12.2 | Entidades fundamentais (tabelas e colunas mínimas). | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 12.2-B | Vínculos semânticos obrigatórios identificados na auditoria. | PARCIAL | backend/migrations/009_tenant_context_and_references.sql; 010_ledger_integrity.sql | test_rls_isolation_ci.py: FK entre tenants | Revisar demais vínculos. |
| 12.2-A | Campos de preparação para novos provedores, sem código bancário — CONSOLIDADO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 12.3 | Regras de chaves e índices. | PARCIAL | backend/migrations/001_initial_schema.sql a 010_ledger_integrity.sql | CI PostgreSQL 16: migrações/FKs | Sem migração em banco real nesta rodada. |
| 12.4 | Relações de negócio. | PARCIAL | backend/migrations/009_tenant_context_and_references.sql; 010_ledger_integrity.sql | test_rls_isolation_ci.py: relações selecionadas | Validar entidades restantes. |
| 12.5 | Entidades futuras de bolões — não migrar na primeira entrega. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/migrations/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.1 | Defesa em camadas. | PARCIAL | backend/app/dependencies.py: get_current_session; migrations/008_persistent_auth_sessions.sql | test_rls_isolation_ci.py: expiração/revogação/RLS | Autenticação ainda só em homologação; TLS/rate limit/produção pendentes. |
| 13.2 | LGPD e minimização. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.3 | Controle fiscal e conformidade da plataforma. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.4 | Política mínima de backup e recuperação — APROVADO COMO REQUISITO DOCUMENTAL. | PARCIAL | backend/scripts/backup_age.sh; restore_disposable_ci.sh | CI: age, restauração em PostgreSQL descartável | Termux e reconciliação pós-restauração pendentes. |
| 13.5 | Monitoramento enxuto. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.6 | Homologação. | PARCIAL | .github/workflows/validacao-atualizacao.yml; backend/tests/; src/tests/ | CI web/API/PostgreSQL/APK | Sem teste no aparelho ou provedor. |
| 13.7 | Projeto preparado para evolução institucional — CONSOLIDADO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.8 | Possível instituição financeira ou de pagamento no futuro — CONDICIONADO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.9 | Linha de licenciamento/homologação — CONSOLIDADO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.10 | Formalização empresarial digital — ROTEIRO PARA O PROPRIETÁRIO. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.11 | Propriedade intelectual e documentos de titularidade. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.12 | Assistência gratuita e autonomia nos requerimentos. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.13 | Matriz documental de conformidade por função — PARA CONSTRUÇÃO E AUDITORIA. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 13.14 | Regra de licenciamento sem impasse circular. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/app/; .github/workflows/validacao-atualizacao.yml | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 14.1 | Modelo escolhido — CONDICIONADO. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/components/BolaoView.tsx; RaffleView.tsx | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 14.2 | Preço final e margem — DEFINIDO COMO MODELO ECONÔMICO. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/components/BolaoView.tsx; RaffleView.tsx | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 14.3 | Destinação e risco. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/components/BolaoView.tsx; RaffleView.tsx | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 14.4 | Fluxo de demonstrador completo e futura operação condicionada. | NÃO VERIFICADO | Não identificado individualmente; área provável: src/components/BolaoView.tsx; RaffleView.tsx | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 14.5 | Barreiras de operação, NÃO de desenvolvimento demonstrável. | PARCIAL | src/components/BolaoView.tsx; RaffleView.tsx | CI build; sem teste regulatório | Preservar demonstradores; nenhuma operação real. |
| 14.6 | Demonstração e prova regulatória. | PARCIAL | src/components/BolaoView.tsx; RaffleView.tsx | CI build; sem teste regulatório | Evidenciar dados fictícios em todos os percursos. |
| 15.1 | Ordem de trabalho. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.2 | Estimativa inicial, sem promessa de entrega. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.2-A | Condição de prontidão do escopo. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.2-B | Pacotes independentes, sem circularidade. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.2-C | Prazo e conclusão honesta. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.3 | Gestão do cronograma por etapa. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.3-A | Evidências técnicas obrigatórias para apresentar a terceiros. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.4 | Gates independentes. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.5 | Execução técnica. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.6 | Plano de negócios e chegada ao mercado — FORA DOS 60 DIAS DE CODIFICAÇÃO. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 15.7 | Autonomia de produção de documentos. | NÃO VERIFICADO | Não identificado individualmente; área provável: README.md; documentação | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.1 | Itens definidos que NÃO devem voltar como perguntas. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.2 | Quatro convenções financeiras complementares — DEFINIDAS E APROVADAS PELO PROPRIETÁRIO em 16/10/2026. | PARCIAL | backend/tests/; src/tests/ | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Há testes de matemática local e corte; ausência de testes integrados de todo fluxo e histórico real. |
| 16.2-A | Limites externos e recursos não liberados pelo aceite documental. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.3 | Condições de ativação real, não bloqueios de codificação ou demonstração. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.3-A | Limite de decisões não documentadas pelo tenant. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.4 | Cenários de auditoria documental e posterior teste — AT-01 a AT-23, complementados até AT-50. | BLOQUEADO | backend/tests/; src/tests/ | Cobertura histórica parcial; sem teste integral da cláusula | Revalidar: Suíte AT-01–50 não foi demonstrada ponta a ponta; testes de lógica não validam todos os cenários. |
| 16.4-A | Testes adicionais da auditoria de evolução e licenciamento (AT-24 a AT-31). | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.4-C | Testes de aceite acrescidos nesta versão (AT-32 a AT-44), após futura programação. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.4-E | Testes de cadastro e vínculos incorporados após aprovação dos itens 3.1-A e 6.1-A (AT-45 a AT-50). | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |
| 16.4-D | Auditoria do código efetivamente existente. | PARCIAL | docs/CHECKPOINT_CONTRATO_2026-11-01.md; backend/tests/; src/tests/ | CI: testes selecionados | AT-01 a AT-50 não executados integralmente. |
| 16.5 | Estado deste documento — APROVADO PARA DESENVOLVIMENTO, NÃO PARA EXECUÇÃO AUTOMÁTICA. | NÃO VERIFICADO | Não identificado individualmente; área provável: backend/tests/; src/tests/ | Nenhum teste específico identificado ou executado | Revisão individual e evidência ainda necessárias. |

## Contagem e histórico

| Estado | Quantidade |
|---|---:|
| CONCLUÍDO E TESTADO | 0 |
| PARCIAL | 28 |
| BLOQUEADO | 18 |
| AUSENTE | 0 |
| DIVERGENTE | 4 |
| NÃO VERIFICADO | 97 |

Mudanças de estado frente à fotografia anterior: 23. Mudanças de FALHA e DIVERGÊNCIA DOCUMENTADA também normalizam os rótulos.

| Cláusula | Antes | Agora |
|---|---|---|
| 1.6 | NÃO VERIFICADO | DIVERGENTE |
| 1.8 | DIVERGÊNCIA DOCUMENTADA | DIVERGENTE |
| 2.3 | BLOQUEADO | PARCIAL |
| 2.4 | BLOQUEADO | PARCIAL |
| 2.5 | FALHA | BLOQUEADO |
| 2.6 | FALHA | BLOQUEADO |
| 4.1 | FALHA | DIVERGENTE |
| 5.3 | BLOQUEADO | DIVERGENTE |
| 6.1 | FALHA | BLOQUEADO |
| 6.1-A.2 | NÃO VERIFICADO | PARCIAL |
| 7.2 | BLOQUEADO | PARCIAL |
| 7.5 | NÃO VERIFICADO | PARCIAL |
| 8.7 | FALHA | BLOQUEADO |
| 8.8 | FALHA | BLOQUEADO |
| 11.2 | NÃO VERIFICADO | PARCIAL |
| 11.3 | NÃO VERIFICADO | PARCIAL |
| 12.2-B | NÃO VERIFICADO | PARCIAL |
| 12.4 | NÃO VERIFICADO | PARCIAL |
| 13.1 | BLOQUEADO | PARCIAL |
| 13.4 | BLOQUEADO | PARCIAL |
| 14.5 | NÃO VERIFICADO | PARCIAL |
| 14.6 | NÃO VERIFICADO | PARCIAL |
| 16.4-D | NÃO VERIFICADO | PARCIAL |

## Cenários AT e limites

AT-01 a AT-50 não tiveram execução integral. Testes de matemática, FastAPI, RLS com dados sintéticos, backup/restauração descartável e APK debug são provas parciais apenas dos pontos indicados. Não houve Pix real, banco do Termux alterado, homologação do Mercado Pago ou teste visual no aparelho.

Convite não declara sucesso sem persistência; voto anual e aprovação de autoempréstimo permanecem bloqueados. Motor puro de unanimidade foi testado mas não ligado a assinaturas persistentes. Por isso nenhuma cláusula financeira ampla foi marcada CONCLUÍDO E TESTADO.
