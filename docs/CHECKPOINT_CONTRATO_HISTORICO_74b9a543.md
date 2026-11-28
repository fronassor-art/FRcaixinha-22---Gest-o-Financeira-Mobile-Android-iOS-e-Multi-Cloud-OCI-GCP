# Checkpoint de auditoria — FRcaixinha 2.2

Data: 01/11/2026 (Belém). Base auditada: branch `atualizacao-ai-studio-9b46a63187`, commit `74b9a543895264c7ed7fadefc22af49f950edfd8`. Esta é uma fotografia anterior às correções posteriores.

Fontes: `public/assets/aistudio/FRcaixinha_2.2___Contrato_T_cnico_Mestre_ORIGINAL_LIMPO_7b28d5d5.pdf` (38 páginas; SHA-256 `7b28d5d5cf773fb5c35194bce64ebfdfec4d67422bafac4595a6662b4f45f468`) e `public/assets/aistudio/FRcaixinha_2.2___Caderno_Mestre_LIMPO___147_cl_usulas_94d2a15c.pdf` (57 páginas; SHA-256 `94d2a15c54d3f5982c09fe78762ae0f1c76e03fa644cb05a6404f5c7b2feb0f6`). A extração de texto encontrou 147 identificadores únicos nos dois documentos, na mesma ordem. A igualdade dos IDs não prova igualdade integral dos textos.

## Critério e limites

- **PARCIAL**: há código ou teste para parte da cláusula, sem demonstrar todos os requisitos.
- **BLOQUEADO**: fluxo indisponível ou dependente de implementação, infraestrutura ou homologação.
- **FALHA**: divergência concreta identificada no código na base auditada.
- **NÃO VERIFICADO**: identificado no inventário, mas sem revisão individual suficiente; não significa ausência nem conformidade.
- **DIVERGÊNCIA DOCUMENTADA**: decisão expressa do usuário substitui a solução técnica do documento.

O inventário cobre os 147 identificadores; a revisão técnica individual detalhada é parcial e as linhas não verificadas precisam de evidência própria. Não há declaração de conformidade global nem contagem de “147 testes aprovados”. Os cenários AT dos documentos não são automaticamente provas de execução. O ciclo de 2027 informado pelo usuário é 01/01/2027–31/12/2027, com liquidação em 10/01/2028.

## Evidência de execução

[GitHub Actions 41339114857](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/actions/runs/41339114857): frontend/lint/testes locais, API sem banco, migrações 001–007 e testes selecionados em PostgreSQL 16 descartável e APK debug passaram. O teste com dados sintéticos verifica login experimental e leitura isolada de cotas/contribuições; não valida todas as tabelas RLS, todas as telas, Pix externo, backup, operações financeiras nem APK no telefone. Não houve contato com o Mercado Pago nem migração em banco real.

## Achados prioritários

1. **P0 — 2.5/2.6/8.8:** autoempréstimo pode passar sem outros membros; consentimento anual/revogação e estados carecem de implementação. `backend/app/routers/loans.py`.
2. **P0 — 6.1:** convite informa sucesso sem criar ou enviar convite quando a URL do banco é configurada. `backend/app/routers/invitations.py`.
3. **P0 — 9.2–9.9:** provedor real, OAuth isolado por tenant, conciliação idempotente, webhooks persistentes e Pix de saída não foram demonstrados; bloquear baixas e recebimentos fictícios.
4. **P1 — 7/8/10:** ledger e fechamento não têm ponta a ponta; quitação, desembolso e fechamento retornam 503. RLS de tabelas financeiras adicionais e concessões exigem revisão.
5. **P1 — 2.3/13.1:** autenticação só em homologação; sessões e rate limit em memória; backend, TLS e recuperação seguros pendentes.
6. **P1 — 5.2/5.3:** o contrato descreve acesso excepcional condicionado; a justificativa no código sobre ausência contratual é incorreta. O recurso segue desabilitado até especificação e testes.
7. **P1 — 11/Android:** somente contribuições consulta API; outras telas usam seeds. O APK auditado anteriormente usa `com.fronassor.frcaixinha.aistudio`; novo usa `com.frcaixinha.app`; usuário aceitou instalação separada. Assinatura durável, backup da chave e verificação no aparelho pendentes.
8. **P1 — 13.4:** backup e restauração não foram testados neste projeto; `age` protege arquivos, mas não valida recuperação ou conciliação pós-restauração.

## Fases propostas

- **Fase 1: segurança e veracidade** — impedir falsos sucessos e autoaprovação indevida; corrigir testes; ampliar isolamento RLS por domínio.
- **Fase 2: núcleo financeiro** — identidade/vínculos, ciclos e políticas; leitura real das telas; empréstimos, ledger e fechamento com testes PostgreSQL e invariantes.
- **Fase 3: Mercado Pago** — conexão por conta e finalidade, OAuth, segredos, notificações assinadas, consulta autoritativa, idempotência e testes sandbox; saídas somente com capacidade comprovada.
- **Fase 4: operação Android** — PostgreSQL/backend acessíveis, backup cifrado e restauração ensaiada; assinatura durável e build; validação visual e funcional no celular.
- **Fase 5: PR** — revisar diffs, resolver conflitos e pendências, passar verificações; mesclar somente após os critérios de aceite.

## Inventário das 147 cláusulas

| Cláusula | Identificação | Estado | Evidência / pendência |
|---|---|---|---|
| 1.1 | Visão — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.2 | Público e modelo. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.3 | Princípios não negociáveis — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.4 | Diferença essencial entre software e operação. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.5 | Primeira entrega — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.6 | Escopo por prontidão, sem circularidade — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.7 | Dinheiro real e fronteira de responsabilidade — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.8 | Ambiente técnico oficialmente escolhido — DEFINIDO. | DIVERGÊNCIA DOCUMENTADA | Contrato cita Flutter; usuário confirmou React/Capacitor em 01/11/2026. Backend FastAPI/PostgreSQL ainda em homologação. |
| 1.9 | Desenvolvimento independente e orçamento inicial — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.10 | Titularidade e estratégia comercial. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.11 | Documentos empresariais por estágio. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 1.12 | Plano econômico enxuto. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 2.1 | Perfis funcionais — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 2.2 | Direitos do administrador contratante — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 2.3 | Papéis simultâneos e troca de contexto. | BLOQUEADO | Login experimental recusa múltiplos vínculos; troca de contexto retorna 503. auth.py e dependencies.py. |
| 2.4 | Administrador também é membro — DEFINIDO. | BLOQUEADO | Convivência de administrador e membro com alternância verificada não implementada de ponta a ponta. |
| 2.5 | Autorização coletiva anual para crédito próprio — DEFINIDO COMO MODELO CONTRATUAL. | FALHA | loans.py aprova autoempréstimo sem outros membros e conta votos por operação; falta autorização anual e revalidação. |
| 2.6 | Ausência de outros membros ou falta de unanimidade. | FALHA | approve_loan usa other_members_count > 0; zero outros membros não impede aprovação. |
| 2.7 | Transparência aos membros. | PARCIAL | Contribuições têm leitura filtrada e teste API/RLS; demais dados e telas exigem verificação. |
| 2.8 | Acesso de Master. | PARCIAL | Teste de Master negado em cotas e contribuições; demais recursos e acesso excepcional não validados. |
| 2.9 | Matriz básica de permissões. | PARCIAL | dependencies.py e testes cobrem perfis e alguns recursos; RLS das demais tabelas ainda exige testes com dados reais. |
| 3.1 | Início da contratação e tenant preliminar — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.1-A | Cadastro e identificação do Administrador Contratante — DEFINIDO E APROVADO em 16/10/2026. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.1-A.1 | Verificação e segurança. | BLOQUEADO | Login somente de homologação; recuperação por e-mail e identidade confirmada não implementadas. |
| 3.1-A.2 | Aceite, identidade e privacidade. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.2 | Tabela comercial — DEFINIDA E APROVADA. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.2-A | Preço comercial dinâmico e anual automático — DEFINIDO. | PARCIAL | Cálculo anual testado localmente; preços autoritativos e persistência/versão não comprovados. |
| 3.2-B | Cobrança por resultado das caixinhas — EM ESTUDO, não aprovada. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.3 | Enquadramento sem lacunas. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.4 | Contagem de capacidade — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.5 | Aceite de licença. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.6 | Pagamento de licença. | BLOQUEADO | Cobrança e conciliação da licença não implementadas. |
| 3.7 | Vigência mensal/anual — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.8 | Tolerância = ZERO DIAS — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.9 | Reativação e cobranças revertidas. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.10 | Alteração, cancelamento e reembolso — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 3.11 | Separação de receitas. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 4.1 | Política financeira por tenant — DEFINIDO. | FALHA | loans.py usa limites e 20% fixos em partes; parametrização integral por tenant não comprovada. |
| 4.2 | Configuração inaugural da caixinha do proprietário — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 4.3 | Percentual administrativo — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 4.4 | Vigência das políticas e dos percentuais — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 4.5 | CALENDÁRIO FINANCEIRO CENTRAL — DEFINIDO E NÃO EDITÁVEL PELO TENANT. | PARCIAL | Ciclo indicado pelo usuário: 01/01/2027–31/12/2027, liquidação 10/01/2028; persistência e execução de calendário não validadas ponta a ponta. |
| 4.6 | Fases do fechamento sem mudar datas. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 4.7 | Entrada após 01/01 e lançamento futuro. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 4.8 | Separação do ciclo e da licença. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 5.1 | Atendimento normal. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 5.2 | Acesso excepcional consentido. | BLOQUEADO | Acesso excepcional consentido não implementado. |
| 5.3 | Prazo e gatilhos de suporte — APROVADO COMO REQUISITO DOCUMENTAL. | BLOQUEADO | Contrato prevê suporte consentido e contingência restrita; código bloqueia recurso e sua justificativa afirma incorretamente ausência de previsão. |
| 5.4 | Vedações invariáveis. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 5.5 | Operação da manutenção. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 6.1 | Adesão. | FALHA | invitations.py responde sucesso quando DATABASE_URL existe sem gravar convite nem enviar mensagem. |
| 6.1-A | Cadastro e identificação do Membro — DEFINIDO E APROVADO em 16/10/2026. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 6.1-A.1 | Aceite e liberação de acesso. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 6.1-A.2 | Identidade única, cotas, privacidade e isolamento. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 6.2 | Capital e cotas. | PARCIAL | Teste de leitura RLS de cotas; ciclo de aquisição/aceite e dados de cota ainda sem ponta a ponta. |
| 6.3 | Contribuições. | PARCIAL | GET contribuições testado por usuário/tenant e tela consulta API; criação de cobrança Pix bloqueada. |
| 6.4 | Estados. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 6.5 | Regra específica da caixinha do proprietário — DEFINIDO, sujeita à validação jurídica antes da execução real. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 6.6 | Proibição de confisco e exclusão indevida. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 7.1 | Segregação. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 7.2 | Ledger autoritativo. | BLOQUEADO | Endpoints de leitura existem; invariantes, fonte autoritativa e partidas dobradas não testados ponta a ponta. |
| 7.3 | Diferenciar saldos e evitar dupla dedução. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 7.4 | Concorrência. | BLOQUEADO | Reserva atômica, concorrência e reconciliação de desembolso não demonstradas. |
| 7.5 | Controle de integridade. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 7.6 | Fronteira regulatória entre livro e custódia — CONSOLIDADO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 8.1 | Exclusividade interna. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 8.2 | Parametrização financeira na primeira entrega — APROVADO COMO REQUISITO DOCUMENTAL. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 8.3 | Elegibilidade e limites verificáveis. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 8.4 | Simulação obrigatória e datas. | PARCIAL | Simulação existe; integração com desembolso efetivo e calendário anual sem teste completo. |
| 8.5 | Price com primeiro período irregular — DEFINIDO. | PARCIAL | Exemplos Price testados em TypeScript; paridade com backend em PostgreSQL real não comprovada. |
| 8.6 | Atrasos, imputação parcial e quitação — DEFINIDO. | BLOQUEADO | Cálculos isolados existem; rotas de recebimento e quitação retornam 503 até conciliação. |
| 8.7 | Aprovação. | FALHA | Pedido/aprovação não estão validados e retorno declara LoanResponse enquanto chama listagem. |
| 8.8 | Empréstimo do administrador-membro. | FALHA | Consentimentos anuais/revogação e revalidação não implementados de forma completa; ver 2.5/2.6. |
| 8.9 | Proibição de fechamento indevido. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 9.1 | Contas e finalidade. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 9.2 | Integração escolhida. | BLOQUEADO | Adaptador só constrói requisições; sem execução externa, OAuth, segregação de tokens ou provedor ativo. |
| 9.3 | Recebimento. | BLOQUEADO | Endpoint Pix retorna 503; não há consulta/baixa conciliada do provedor. |
| 9.4 | Saída, autorização e idempotência. | BLOQUEADO | Desembolso retorna 503; idempotência econômica, reserva e timeout não implementados ponta a ponta. |
| 9.5 | Reversão ou falha. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 9.6 | Fechamento. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 9.7 | Bolões. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 9.8 | Verificações mínimas. | BLOQUEADO | Testes de webhook repetido, restauração e concorrência com efeitos reais no banco não comprovados. |
| 9.8-A | Interfaces estáveis de integração para futura migração — CONSOLIDADO. | PARCIAL | Validador HMAC e construtores HTTP testados isoladamente; portas completas e simulador transacional ausentes. |
| 9.9 | Ambientes e liberação por finalidade — APROVADO COMO REQUISITO DOCUMENTAL. | BLOQUEADO | Separação operacional DEMO/HOMOLOGAÇÃO/PRODUÇÃO não comprovada. |
| 10.1 | Formação da base e corte de realização. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 10.2 | Percentuais por caixinha — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 10.3 | Rateio Capital-Dias V2 — motor comum, com corte diário aprovado. | BLOQUEADO | Função isolada usa corte 31/12, mas fechamento está em 503 e faltam eventos parciais/reversões. |
| 10.4 | Rateio, precisão e destino definitivo dos centavos — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 10.5 | Distinguir administrador como beneficiário duplo. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 10.6 | Fechamento anual e obrigações remanescentes. | BLOQUEADO | Fechamento retorna 503 para impedir liquidação sem prova; fluxo por estados pendente. |
| 10.7 | Documentos e conferência. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 10.8 | Imutabilidade e versões de resultado — DEFINIDO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 11.0-A | Telas de demonstrador regulatório e evolução — CONSOLIDADO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 11.1 | Design simples. | PARCIAL | Contribuições usa cartões responsivos; não há validação visual em aparelho para todas as telas. |
| 11.2 | Estados visuais. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 11.3 | Textos de transparência. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 11.4 | Manual oficial para administradores — ENTREGÁVEL DO MVP. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 11.5 | Apoio comercial e demonstração — ENTREGÁVEL NÃO TRANSACIONAL. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 12.1 | Padrões de todas as tabelas. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 12.2 | Entidades fundamentais (tabelas e colunas mínimas). | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 12.2-B | Vínculos semânticos obrigatórios identificados na auditoria. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 12.2-A | Campos de preparação para novos provedores, sem código bancário — CONSOLIDADO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 12.3 | Regras de chaves e índices. | PARCIAL | Migrações 001–007 aplicadas em PostgreSQL descartável; integridade multitenant geral e migração evolutiva não comprovadas. |
| 12.4 | Relações de negócio. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 12.5 | Entidades futuras de bolões — não migrar na primeira entrega. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.1 | Defesa em camadas. | BLOQUEADO | Sessões e limite de tentativas em memória, login de homologação; autorização e RLS incompletos. |
| 13.2 | LGPD e minimização. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.3 | Controle fiscal e conformidade da plataforma. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.4 | Política mínima de backup e recuperação — APROVADO COMO REQUISITO DOCUMENTAL. | BLOQUEADO | Sem pipeline de backup e restauração do banco deste app com teste de recuperação e reconciliação. |
| 13.5 | Monitoramento enxuto. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.6 | Homologação. | PARCIAL | CI usa PostgreSQL descartável e APK debug; sem teste funcional no celular nem homologação do provedor. |
| 13.7 | Projeto preparado para evolução institucional — CONSOLIDADO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.8 | Possível instituição financeira ou de pagamento no futuro — CONDICIONADO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.9 | Linha de licenciamento/homologação — CONSOLIDADO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.10 | Formalização empresarial digital — ROTEIRO PARA O PROPRIETÁRIO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.11 | Propriedade intelectual e documentos de titularidade. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.12 | Assistência gratuita e autonomia nos requerimentos. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.13 | Matriz documental de conformidade por função — PARA CONSTRUÇÃO E AUDITORIA. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 13.14 | Regra de licenciamento sem impasse circular. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 14.1 | Modelo escolhido — CONDICIONADO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 14.2 | Preço final e margem — DEFINIDO COMO MODELO ECONÔMICO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 14.3 | Destinação e risco. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 14.4 | Fluxo de demonstrador completo e futura operação condicionada. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 14.5 | Barreiras de operação, NÃO de desenvolvimento demonstrável. | NÃO VERIFICADO | Investigar se módulos demonstrativos evitam cobrança real e identificam simulação em todas as telas. |
| 14.6 | Demonstração e prova regulatória. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.1 | Ordem de trabalho. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.2 | Estimativa inicial, sem promessa de entrega. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.2-A | Condição de prontidão do escopo. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.2-B | Pacotes independentes, sem circularidade. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.2-C | Prazo e conclusão honesta. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.3 | Gestão do cronograma por etapa. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.3-A | Evidências técnicas obrigatórias para apresentar a terceiros. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.4 | Gates independentes. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.5 | Execução técnica. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.6 | Plano de negócios e chegada ao mercado — FORA DOS 60 DIAS DE CODIFICAÇÃO. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 15.7 | Autonomia de produção de documentos. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.1 | Itens definidos que NÃO devem voltar como perguntas. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.2 | Quatro convenções financeiras complementares — DEFINIDAS E APROVADAS PELO PROPRIETÁRIO em 16/10/2026. | PARCIAL | Há testes de matemática local e corte; ausência de testes integrados de todo fluxo e histórico real. |
| 16.2-A | Limites externos e recursos não liberados pelo aceite documental. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.3 | Condições de ativação real, não bloqueios de codificação ou demonstração. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.3-A | Limite de decisões não documentadas pelo tenant. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.4 | Cenários de auditoria documental e posterior teste — AT-01 a AT-23, complementados até AT-50. | BLOQUEADO | Suíte AT-01–50 não foi demonstrada ponta a ponta; testes de lógica não validam todos os cenários. |
| 16.4-A | Testes adicionais da auditoria de evolução e licenciamento (AT-24 a AT-31). | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.4-C | Testes de aceite acrescidos nesta versão (AT-32 a AT-44), após futura programação. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.4-E | Testes de cadastro e vínculos incorporados após aprovação dos itens 3.1-A e 6.1-A (AT-45 a AT-50). | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.4-D | Auditoria do código efetivamente existente. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
| 16.5 | Estado deste documento — APROVADO PARA DESENVOLVIMENTO, NÃO PARA EXECUÇÃO AUTOMÁTICA. | NÃO VERIFICADO | Inventariada; leitura de código e teste específicos ainda pendentes. |
